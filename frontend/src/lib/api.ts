/**
 * ConX — Client API typé.
 *
 * Routes consommées : voir `backend/app/routers/buildings.py`.
 */

import { getCurrentJwt } from "@/lib/supabase";

const API_BASE = (import.meta.env.VITE_API_BASE as string) ?? "/api";

export interface BuildingListItem {
  building_id: string;
  rnb_id: string | null;
  dept: string | null;
  // L'API renvoie centroid_lon/centroid_lat plats. On expose un objet
  // dérivé `centroid` côté frontend pour faciliter l'usage deck.gl.
  centroid_lon: number;
  centroid_lat: number;
  centroid: { lon: number; lat: number };
  surface_m2: number | null;
  hauteur_m?: number | null;
  nb_logements: number | null;
  annee_constr: number | null;
  type_principal: string | null;
  type_proprietaire: string | null;
  dpe_classe: string | null;
  dpe_kwh_ep_m2_an?: number | null;
  dpe_source: string | null;
  monument_historique?: boolean | null;
  score_total: number | null;
  s_co2: number | null;
  s_faisa: number | null;
  s_cout: number | null;
  s_social: number | null;
  s_passoire: number | null;
  co2_evite_t: number | null;
  cout_estime_eur: number | null;
  confidence: number | null;
}

export interface BuildingsListResponse {
  items: BuildingListItem[];
  count: number;
  next_cursor: string | null;
  weights_used: Record<string, number>;
  bbox: [number, number, number, number] | null;
}

export interface GeoJsonMultiPolygon {
  type: "MultiPolygon";
  coordinates: number[][][][];
}

export interface BuildingDetail extends BuildingListItem {
  materiau_mur?: string | null;
  periode_construction?: string | null;
  spr?: boolean | null;
  acces_chantier_m?: number | null;
  dpe_kg_co2_m2_an?: number | null;
  dpe_coefficient_ep_electricite?: number | null;
  code_commune_insee?: string | null;
  code_iris?: string | null;
  bdnb_millesime?: string | null;
  thresholds_version?: string | null;
  geom_geojson?: GeoJsonMultiPolygon | null;
}

export interface BuildingsListParams {
  bbox?: [number, number, number, number]; // [west,south,east,north] WGS84
  dept?: string[];
  dpe_classes?: string[];
  typo_proprietaire?: string[];
  annee_max?: number;
  annee_min?: number;
  surface_min_m2?: number;
  w_co2?: number;
  w_faisa?: number;
  w_cout?: number;
  w_social?: number;
  w_passoire?: number;
  limit?: number;
  cursor?: string;
}

async function authHeaders(): Promise<Record<string, string>> {
  const jwt = await getCurrentJwt();
  return jwt ? { Authorization: `Bearer ${jwt}` } : {};
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(await authHeaders()),
    ...((init?.headers as Record<string, string>) ?? {}),
  };
  const resp = await fetch(url, { ...init, headers });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`HTTP ${resp.status} ${resp.statusText} — ${text.slice(0, 200)}`);
  }
  return (await resp.json()) as T;
}

function normalizeBuilding<T extends { centroid_lon: number; centroid_lat: number }>(
  raw: T,
): T & { centroid: { lon: number; lat: number } } {
  return { ...raw, centroid: { lon: raw.centroid_lon, lat: raw.centroid_lat } };
}

export async function listBuildings(
  params: BuildingsListParams = {},
  signal?: AbortSignal,
): Promise<BuildingsListResponse> {
  const search = new URLSearchParams();
  if (params.bbox) search.set("bbox", params.bbox.map((v) => v.toFixed(6)).join(","));
  for (const dept of params.dept ?? []) search.append("dept", dept);
  for (const c of params.dpe_classes ?? []) search.append("dpe_classes", c);
  for (const t of params.typo_proprietaire ?? []) search.append("typo_proprietaire", t);
  if (params.annee_max !== undefined) search.set("annee_max", String(params.annee_max));
  if (params.annee_min !== undefined) search.set("annee_min", String(params.annee_min));
  if (params.surface_min_m2 !== undefined)
    search.set("surface_min_m2", String(params.surface_min_m2));
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  if (params.cursor) search.set("cursor", params.cursor);
  for (const k of ["w_co2", "w_faisa", "w_cout", "w_social", "w_passoire"] as const) {
    if (params[k] !== undefined) search.set(k, String(params[k]));
  }
  const raw = await fetchJson<BuildingsListResponse>(
    `${API_BASE}/buildings?${search.toString()}`,
    { signal },
  );
  return {
    ...raw,
    items: raw.items.map((b) => normalizeBuilding(b)),
  };
}

export async function getBuilding(id: string, signal?: AbortSignal): Promise<BuildingDetail> {
  const raw = await fetchJson<BuildingDetail>(
    `${API_BASE}/buildings/${encodeURIComponent(id)}`,
    { signal },
  );
  return normalizeBuilding(raw);
}

/** URL d'export téléchargeable (le browser handle l'auth via session/cookies si configuré). */
export function exportUrl(format: "csv" | "geojson", params: BuildingsListParams): string {
  const search = new URLSearchParams();
  if (params.bbox) search.set("bbox", params.bbox.map((v) => v.toFixed(6)).join(","));
  for (const dept of params.dept ?? []) search.append("dept", dept);
  for (const c of params.dpe_classes ?? []) search.append("dpe_classes", c);
  for (const t of params.typo_proprietaire ?? []) search.append("typo_proprietaire", t);
  if (params.annee_max !== undefined) search.set("annee_max", String(params.annee_max));
  if (params.limit !== undefined) search.set("limit", String(params.limit));
  return `${API_BASE}/exports/strategie.${format}?${search.toString()}`;
}

// ---------------------------------------------------------------------------
// Mode Projet — Agent Plan (chat itératif)
// ---------------------------------------------------------------------------

export interface PlanStartRequest {
  building_id: string;
  target_class?: string;
  preferences?: Record<string, unknown>;
  initial_message?: string;
}

export interface PlanStartResponse {
  session_id: string;
  agent_name: string;
  building_id: string;
  status: string;
  cost_estimate_eur: [number, number];
}

export interface PlanMessageResponse {
  session_id: string;
  version: number;
  cost_estimate_eur: [number, number];
  was_replayed: boolean;
  previous_session_id: string | null;
}

export async function startPlanSession(req: PlanStartRequest): Promise<PlanStartResponse> {
  return fetchJson<PlanStartResponse>(`${API_BASE}/agents/plan/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

export async function sendPlanMessage(
  sessionId: string,
  content: string,
): Promise<PlanMessageResponse> {
  return fetchJson<PlanMessageResponse>(
    `${API_BASE}/agents/plan/${encodeURIComponent(sessionId)}/message`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    },
  );
}

/** URL SSE pour `EventSource`. L'auth est portée par cookies/JWT du domaine. */
export function planStreamUrl(sessionId: string, after?: string): string {
  const params = new URLSearchParams();
  if (after) params.set("after", after);
  const qs = params.toString() ? `?${params.toString()}` : "";
  return `${API_BASE}/agents/plan/${encodeURIComponent(sessionId)}/stream${qs}`;
}

// ---------------------------------------------------------------------------
// Conformité IFC (J17)
// ---------------------------------------------------------------------------

export interface IfcCheck {
  name: string;
  pass: boolean | null;
  value?: unknown;
  threshold?: unknown;
  message?: string;
}

export interface IfcReport {
  schema?: string;
  entities_count?: Record<string, number>;
  summary?: {
    walls?: number;
    doors?: number;
    windows?: number;
    spaces?: number;
  };
  re2020_checks?: Record<string, IfcCheck>;
  pmr_checks?: Record<string, IfcCheck>;
  warnings?: string[];
}

export interface IfcUploadResponse {
  validation_id: string;
  ifc_filename: string;
  rapport_json: IfcReport;
  pdf_url: string;
  re2020_pass: boolean | null;
  pmr_pass: boolean | null;
}

export async function uploadIfc(file: File): Promise<IfcUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const headers = await authHeaders();
  // Note: ne PAS forcer Content-Type, le navigateur set le multipart boundary.
  const resp = await fetch(`${API_BASE}/ifc/upload`, {
    method: "POST",
    headers,
    body: form,
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`HTTP ${resp.status} ${resp.statusText} — ${text.slice(0, 300)}`);
  }
  return (await resp.json()) as IfcUploadResponse;
}

/** Géocodage adresse via la BAN (data.gouv) — appel direct frontend (pas de proxy). */
export interface BanFeature {
  properties: {
    label: string;
    score: number;
    citycode: string;
    city: string;
    context: string;
    postcode?: string;
  };
  geometry: { type: "Point"; coordinates: [number, number] };
}

export interface BanResponse {
  features: BanFeature[];
}

export async function geocodeAddress(q: string, limit = 5): Promise<BanFeature[]> {
  if (!q.trim()) return [];
  const url = `https://api-adresse.data.gouv.fr/search/?q=${encodeURIComponent(q)}&limit=${limit}`;
  const resp = await fetch(url);
  if (!resp.ok) return [];
  const json = (await resp.json()) as BanResponse;
  return json.features ?? [];
}
