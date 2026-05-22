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
      setVersions((vs) => [...vs, nv]);
      setActiveVersion(resp.version);
      attachStream(resp.session_id, resp.version);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }, [sessionId, draft, busy, attachStream]);

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
            setSessionId(`cache:${building.building_id}`);
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
    <div className="border-t bg-card flex flex-col" style={{ minHeight: 320, maxHeight: 540 }}>
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

      {/* Active version content */}
      <div className="flex-1 overflow-y-auto p-3 text-sm font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap">
        {active?.user_message && (
          <div className="mb-3 pb-3 border-b text-foreground/80 font-sans text-xs">
            <strong className="text-foreground">Vous :</strong> {active.user_message}
          </div>
        )}
        {active?.agent_text ? (
          <div>{active.agent_text}</div>
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
