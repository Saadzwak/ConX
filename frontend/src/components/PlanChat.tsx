/**
 * J16 — Chat itératif Agent Plan (Claude Opus 4.7 via SSE).
 *
 * - Premier message : auto-injecté par le backend (POST /agents/plan/start
 *   prend la fiche bâtiment et la préférence biosource).
 * - Stream SSE consommé via EventSource sur /api/agents/plan/:sid/stream.
 *   Le composant agrège les events `agent.message` partials → texte complet.
 * - Versioning : chaque user message → version N+1. Affiché en chips v1/v2/v3.
 * - Fallback B-001 : si l'API renvoie `was_replayed: true`, on bascule
 *   silencieusement vers la nouvelle session_id (le frontend ne casse pas).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Sparkles, Send, Loader2, AlertCircle, History, Database } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  getCachedPlan,
  planStreamUrl,
  sendPlanMessage,
  startPlanSession,
  type BuildingDetail,
} from "@/lib/api";

/**
 * Composants markdown stylés via Tailwind utilitaires (pas de plugin
 * @tailwindcss/typography pour limiter les deps). Tableaux GFM activés
 * via remark-gfm pour le bilan carbone + budget.
 */
const MD_COMPONENTS = {
  h1: (p: { children?: React.ReactNode }) => (
    <h1 className="text-base font-bold mt-3 mb-1.5">{p.children}</h1>
  ),
  h2: (p: { children?: React.ReactNode }) => (
    <h2 className="text-sm font-bold mt-3 mb-1.5 text-foreground">{p.children}</h2>
  ),
  h3: (p: { children?: React.ReactNode }) => (
    <h3 className="text-sm font-semibold mt-2.5 mb-1 text-foreground">{p.children}</h3>
  ),
  h4: (p: { children?: React.ReactNode }) => (
    <h4 className="text-xs font-semibold mt-2 mb-1 text-foreground uppercase tracking-wide">
      {p.children}
    </h4>
  ),
  p: (p: { children?: React.ReactNode }) => (
    <p className="my-1.5 leading-relaxed">{p.children}</p>
  ),
  ul: (p: { children?: React.ReactNode }) => (
    <ul className="list-disc pl-5 my-1.5 space-y-0.5">{p.children}</ul>
  ),
  ol: (p: { children?: React.ReactNode }) => (
    <ol className="list-decimal pl-5 my-1.5 space-y-0.5">{p.children}</ol>
  ),
  li: (p: { children?: React.ReactNode }) => <li className="leading-snug">{p.children}</li>,
  strong: (p: { children?: React.ReactNode }) => (
    <strong className="font-semibold text-foreground">{p.children}</strong>
  ),
  em: (p: { children?: React.ReactNode }) => <em className="italic">{p.children}</em>,
  code: (p: { children?: React.ReactNode }) => (
    <code className="bg-muted px-1 py-0.5 rounded text-[11px] font-mono">{p.children}</code>
  ),
  blockquote: (p: { children?: React.ReactNode }) => (
    <blockquote className="border-l-2 border-primary/40 pl-3 my-2 italic text-foreground/80">
      {p.children}
    </blockquote>
  ),
  hr: () => <hr className="my-3 border-border" />,
  table: (p: { children?: React.ReactNode }) => (
    <div className="my-2 overflow-x-auto">
      <table className="text-[11.5px] border-collapse w-full">{p.children}</table>
    </div>
  ),
  thead: (p: { children?: React.ReactNode }) => (
    <thead className="bg-muted/60">{p.children}</thead>
  ),
  th: (p: { children?: React.ReactNode }) => (
    <th className="border border-border px-2 py-1 text-left font-semibold">{p.children}</th>
  ),
  td: (p: { children?: React.ReactNode }) => (
    <td className="border border-border px-2 py-1 align-top">{p.children}</td>
  ),
  a: (p: { children?: React.ReactNode; href?: string }) => (
    <a
      href={p.href}
      target="_blank"
      rel="noreferrer noopener"
      className="text-primary underline underline-offset-2 hover:text-primary/80"
    >
      {p.children}
    </a>
  ),
};

const SLOW_PLAN_THRESHOLD_MS = 90_000; // 90 s — bouton "Use cache" apparaît

interface PlanVersion {
  version: number;
  user_message: string | null;
  agent_text: string;
  status: "streaming" | "idle" | "error" | "terminated";
  started_at: number; // epoch ms
  ended_at?: number;
}

interface Props {
  building: BuildingDetail;
}

export function PlanChat({ building }: Props) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [versions, setVersions] = useState<PlanVersion[]>([]);
  const [activeVersion, setActiveVersion] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [replayed, setReplayed] = useState<{ from: string; to: string } | null>(null);
  const evtSrcRef = useRef<EventSource | null>(null);
  const [slowMode, setSlowMode] = useState(false);
  const slowTimerRef = useRef<number | null>(null);

  // Cleanup EventSource on unmount
  useEffect(() => {
    return () => {
      evtSrcRef.current?.close();
      if (slowTimerRef.current) window.clearTimeout(slowTimerRef.current);
    };
  }, []);

  /** Affiche le plan en cache (fallback). */
  const loadFromCache = useCallback(
    async (version: number) => {
      const cached = await getCachedPlan(building.building_id, version);
      if (!cached) {
        setError(`Pas de plan v${version} en cache pour ce bâtiment.`);
        return false;
      }
      const cacheVersion: PlanVersion = {
        version,
        user_message:
          version === 1
            ? null
            : "Et plutôt avec du chanvre comme matériau dominant ?",
        agent_text: cached.plan_text,
        status: "idle",
        started_at: Date.now(),
        ended_at: Date.now(),
      };
      setVersions((vs) => {
        const without = vs.filter((v) => v.version !== version);
        return [...without, cacheVersion].sort((a, b) => a.version - b.version);
      });
      setActiveVersion(version);
      setSessionId(`cache:${cached.session_id}`);
      setBusy(false);
      setSlowMode(false);
      evtSrcRef.current?.close();
      return true;
    },
    [building],
  );

  /** Attache un EventSource sur la session courante, version cible donnée. */
  const attachStream = useCallback((sid: string, versionTarget: number) => {
    evtSrcRef.current?.close();
    if (slowTimerRef.current) window.clearTimeout(slowTimerRef.current);
    setSlowMode(false);
    slowTimerRef.current = window.setTimeout(() => {
      setSlowMode(true);
    }, SLOW_PLAN_THRESHOLD_MS);

    const url = planStreamUrl(sid);
    const es = new EventSource(url, { withCredentials: false });
    evtSrcRef.current = es;
    let buffer = "";

    es.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        // Events agent.message arrivent en chunks (text deltas)
        if (data.type === "agent.message" || data.type === "agent_message") {
          const content = data.content;
          if (Array.isArray(content)) {
            for (const block of content) {
              const t = (block as { text?: string }).text;
              if (t) buffer += t;
            }
          }
          setVersions((vs) =>
            vs.map((v) =>
              v.version === versionTarget ? { ...v, agent_text: buffer } : v,
            ),
          );
        } else if (data.type === "session.idle" || data.type === "session.status_idle") {
          setVersions((vs) =>
            vs.map((v) =>
              v.version === versionTarget
                ? { ...v, status: "idle", ended_at: Date.now() }
                : v,
            ),
          );
          es.close();
          setBusy(false);
          if (slowTimerRef.current) window.clearTimeout(slowTimerRef.current);
          setSlowMode(false);
        } else if (data.type === "session.terminated" || data.type === "session.error") {
          setVersions((vs) =>
            vs.map((v) =>
              v.version === versionTarget
                ? { ...v, status: "terminated", ended_at: Date.now() }
                : v,
            ),
          );
          es.close();
          setBusy(false);
        }
      } catch {
        // Keepalive / commentaire SSE — ignorer
      }
    };
    es.onerror = () => {
      // Le SSE peut hoqueter sur les proxies — on tolère un re-essai
      setError((prev) => prev ?? "Connexion SSE interrompue.");
      es.close();
      setBusy(false);
    };
  }, []);

  /** Démarre une nouvelle session sur le bâtiment courant. */
  const start = useCallback(async () => {
    setError(null);
    setBusy(true);
    setReplayed(null);
    try {
      const resp = await startPlanSession({
        building_id: building.building_id,
        target_class: "C",
        preferences: { biosource: true },
      });
      setSessionId(resp.session_id);
      const v1: PlanVersion = {
        version: 1,
        user_message: null, // construit côté backend
        agent_text: "",
        status: "streaming",
        started_at: Date.now(),
      };
      setVersions([v1]);
      setActiveVersion(1);
      attachStream(resp.session_id, 1);
    } catch (e) {
      // Si l'API plante (Anthropic down, rate limit), on tente le cache.
      const fellBack = await loadFromCache(1);
      if (!fellBack) {
        setError((e as Error).message);
        setBusy(false);
      }
    }
  }, [building, attachStream, loadFromCache]);

  /** Envoie un nouveau message utilisateur (v2, v3, ...). */
  const sendNext = useCallback(async () => {
    if (!sessionId || !draft.trim() || busy) return;
    const content = draft.trim();
    setDraft("");
    setError(null);
    setBusy(true);

    // Mode cache (sessionId préfixé "cache:") : pas de vraie session Anthropic
    // côté serveur, donc on ne peut pas POST /agents/plan/<sid>/message. On
    // tente de charger la version suivante depuis le cache local (pour la
    // démo : Wazemmes v2 chanvre est pré-caché). Si absent → message clair.
    if (sessionId.startsWith("cache:")) {
      const nextVersion = (activeVersion ?? 1) + 1;
      const ok = await loadFromCache(nextVersion);
      if (!ok) {
        setError(
          `Plan v${nextVersion} non disponible en cache. Pour itérer en live, ` +
            `recliquez "Générer un plan rénovation IA".`,
        );
      }
      setBusy(false);
      return;
    }

    try {
      const resp = await sendPlanMessage(sessionId, content);
      // Si le backend a engagé le fallback replay, on update sessionId
      if (resp.was_replayed && resp.previous_session_id) {
        setReplayed({ from: resp.previous_session_id, to: resp.session_id });
        setSessionId(resp.session_id);
      }
      const nv: PlanVersion = {
        version: resp.version,
        user_message: content,
        agent_text: "",
        status: "streaming",
        started_at: Date.now(),
      };
      // Dedup : si le backend a engagé le replay fallback (TTL session
      // expirée), il renvoie version=1 quelle que soit la position dans
      // l'historique (cf. routers/agents.py:482). Sans filtre on aurait
      // deux entrées v1 dans `versions` → React duplicate key warning.
      setVersions((vs) => {
        const without = vs.filter((v) => v.version !== resp.version);
        return [...without, nv].sort((a, b) => a.version - b.version);
      });
      setActiveVersion(resp.version);
      attachStream(resp.session_id, resp.version);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }, [sessionId, draft, busy, attachStream, activeVersion, loadFromCache]);

  // === Render ===
  const active = versions.find((v) => v.version === activeVersion);

  if (!sessionId) {
    return (
      <div className="border-t bg-muted/30 p-3 space-y-2">
        <Button className="w-full" onClick={start} disabled={busy}>
          {busy ? (
            <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
          ) : (
            <Sparkles className="h-4 w-4 mr-1.5" />
          )}
          {busy ? "Génération…" : "Générer un plan rénovation IA"}
        </Button>
        <Button
          className="w-full"
          variant="ghost"
          size="sm"
          onClick={() => {
            // Pas de setSessionId optimiste — sinon, si le cache 404 (bâtiment
            // non pré-cachée), sessionId reste collé à "cache:<building_id>"
            // (pas une vraie session Anthropic) et tout Send subséquent POST
            // sur /agents/plan/cache:bdnb-bg-.../message → 404. loadFromCache
            // pose lui-même sessionId = "cache:<vrai sesn_id>" en cas de
            // succès (cf. ligne ~86).
            setActiveVersion(1);
            void loadFromCache(1);
          }}
        >
          <Database className="h-3.5 w-3.5 mr-1.5" />
          Utiliser le plan pré-calculé
        </Button>
        <p className="text-[11px] text-muted-foreground leading-snug">
          L'agent Plan (Claude Opus 4.7) génère un plan complet hors-site biosourcé
          en ~60-90 s. Coût ~0.30 €. Cache disponible pour les bâtiments vedettes.
        </p>
        {error && (
          <div className="text-xs text-destructive flex items-start gap-1.5">
            <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      className="border-t bg-card flex flex-col shrink min-h-0"
      style={{ flex: "0 1 540px", minHeight: 220 }}
    >
      {/* Versions chips */}
      <div className="px-3 py-2 border-b flex items-center gap-1.5 overflow-x-auto">
        <History className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        {versions.map((v) => (
          <button
            key={v.version}
            onClick={() => setActiveVersion(v.version)}
            className={cn(
              "px-2 py-0.5 text-xs rounded-full border shrink-0 transition",
              activeVersion === v.version
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-background text-foreground hover:bg-accent",
            )}
          >
            v{v.version}
            {v.status === "streaming" && (
              <Loader2 className="inline h-3 w-3 ml-1 animate-spin" />
            )}
          </button>
        ))}
        {replayed && (
          <Badge variant="secondary" className="ml-2 shrink-0" title="Session reprise après TTL">
            session renouvelée
          </Badge>
        )}
        {sessionId?.startsWith("cache:") && (
          <Badge variant="outline" className="ml-2 shrink-0">
            <Database className="h-3 w-3 mr-1" />
            cache
          </Badge>
        )}
      </div>

      {/* Bandeau "slow mode" : 90 s passé, propose cache */}
      {slowMode && busy && (
        <div className="px-3 py-2 bg-amber-50 border-b border-amber-200 text-xs flex items-center justify-between gap-2">
          <span className="text-amber-900">
            Génération &gt; 90 s — utiliser le plan pré-calculé ?
          </span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void loadFromCache(activeVersion ?? 1)}
          >
            <Database className="h-3.5 w-3.5 mr-1" />
            Charger cache
          </Button>
        </div>
      )}

      {/* Active version content — rendu markdown (GFM tables, listes, etc.) */}
      <div className="flex-1 overflow-y-auto p-3 text-[12.5px] leading-relaxed">
        {active?.user_message && (
          <div className="mb-3 pb-3 border-b text-foreground/80 text-xs">
            <strong className="text-foreground">Vous :</strong> {active.user_message}
          </div>
        )}
        {active?.agent_text ? (
          <div className="space-y-1">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
              {active.agent_text}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="text-muted-foreground italic">
            {active?.status === "streaming"
              ? "L'agent réfléchit et stream sa réponse…"
              : "Aucune sortie reçue."}
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t p-2 flex gap-2">
        <input
          type="text"
          placeholder='Itère : "plutôt en chanvre", "réduis le coût", "viser A"…'
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendNext();
            }
          }}
          disabled={busy}
          className="flex-1 h-9 px-3 text-sm rounded-md border border-input bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <Button size="icon" onClick={sendNext} disabled={busy || !draft.trim()}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </div>

      {error && (
        <div className="px-3 pb-2 text-xs text-destructive flex items-start gap-1.5">
          <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
