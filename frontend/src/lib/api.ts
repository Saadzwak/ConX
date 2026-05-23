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
  // --- Identité étendue ---
  code_commune_insee?: string | null;
  code_iris?: string | null;
  commune_nom?: string | null;
  code_epci_insee?: string | null;
  bdnb_millesime?: string | null;

  // --- Adresse BAN ---
  adresse_postale?: string | null;
  cle_interop_ban?: string | null;

  // --- Bâti ---
  nb_niveaux_ffo?: number | null;
  periode_construction?: string | null;
  periode_thermique_reglementaire?: string | null;
  materiau_mur?: string | null;
  materiau_toiture?: string | null;
  spr?: boolean | null;

  // --- DPE base ---
  classe_emission_ges?: string | null;
  dpe_kg_co2_m2_an?: number | null;
  dpe_coefficient_ep_electricite?: number | null;
  identifiant_dpe_ademe?: string | null;
  date_etablissement_dpe?: string | null;
  date_reception_dpe?: string | null;
  dpe_expire_le?: string | null;
  shab_immeuble_m2?: number | null;

  // --- Géom ---
  geom_geojson?: GeoJsonMultiPolygon | null;

  // --- Score (à plat, fix PHASE 1.1) ---
  thresholds_version?: string | null;
  computed_at?: string | null;
  incomplete_data?: boolean | null;
  s_faisa_partial?: boolean | null;
  missing_fields?: string[] | null;
  cout_eur_par_t_co2?: number | null;
  // Compat objet niché
  score?: Record<string, unknown> | null;

  // --- Voisinage ---
  neighbors?: { building_id: string; dpe_classe: string | null; distance_m: number }[];

  // --- QPV ---
  dans_qpv?: boolean;
  qpv_nom?: string | null;

  // --- Réseau de chaleur ---
  reseau_chaleur_id?: string | null;
  reseau_chaleur_prioritaire?: boolean;
  reseau_chaleur_distance?: string | null;

  // --- Diagnostic technique ---
  diagnostic_technique?: DiagnosticTechnique | null;

  // --- RPLS ---
  rpls?: RplsData | null;

  // --- Conso réelle 7 ans ---
  conso_reelle_annuelle?: ConsoAnnuelle[];

  // --- Risques ---
  risques?: { radon: string | null; argile: string | null; sismique: string | null };

  // --- Urbanisme ---
  urbanisme?: {
    zone_ac1: boolean;
    zone_plu_bati_patrimonial: boolean;
    distance_monument_historique: number | null;
    denomination_monument_historique: string | null;
  };

  // --- Fiabilité ---
  fiabilite?: {
    emprise_sol: string | null;
    hauteur: string | null;
    adresse: boolean | null;
  };

  // --- Accès chantier ---
  acces_chantier?: {
    score: number;
    nearest_largeur_m: number | null;
    nearest_distance_m: number | null;
  } | null;

  // --- Dérivés économiques ---
  cout_energie_annuel_eur?: number | null;
  cout_energie_30_ans_eur?: number | null;
  emissions_totales_30_ans_t?: number | null;

  // --- Aides ---
  aides_eligibles?: AideEligible[];
}

export interface DiagnosticTechnique {
  classe_emission_ges?: string | null;
  type_installation_chauffage?: string | null;
  type_energie_chauffage?: string | null;
  type_generateur_chauffage?: string | null;
  type_generateur_chauffage_anciennete?: string | null;
  type_installation_ecs?: string | null;
  type_energie_ecs?: string | null;
  type_generateur_ecs?: string | null;
  type_generateur_ecs_anciennete?: string | null;
  type_ventilation?: string | null;
  type_vitrage?: string | null;
  type_materiaux_menuiserie?: string | null;
  vitrage_vir?: boolean | null;
  uw?: number | null;
  type_isolation_mur_exterieur?: string | null;
  materiaux_structure_mur_exterieur?: string | null;
  epaisseur_structure_mur_exterieur?: string | null;
  u_mur_exterieur?: number | null;
  type_isolation_plancher_bas?: string | null;
  u_plancher_bas_final_deperditif?: number | null;
  type_isolation_plancher_haut?: string | null;
  u_plancher_haut_deperditif?: number | null;
  type_adjacence_principal_plancher_haut?: string | null;
  u_porte?: number | null;
  surface_porte?: number | null;
  deperdition_mur?: number | null;
  deperdition_plancher_haut?: number | null;
  deperdition_plancher_bas?: number | null;
  deperdition_baie_vitree?: number | null;
  deperdition_porte?: number | null;
}

export interface RplsData {
  rpls_open: boolean;
  classe_ener_principale: string | null;
  classe_ges_principale: string | null;
  accessible_pmr: boolean | null;
  dans_qpv: boolean;
  shab_total_m2: number | null;
  distribution_dpe: { A: number; B: number; C: number; D: number; E: number; F: number; G: number };
}

export interface ConsoAnnuelle {
  annee: string;
  pdl_elec_residentiel: number | null;
  kwh_elec_residentiel: number | null;
  pdl_gaz_residentiel: number | null;
  kwh_gaz_residentiel: number | null;
}

export interface AideEligible {
  code: string;
  nom: string;
  condition: string;
  montant_estimatif_eur: number | null;
  source: string;
}

export interface BuildingRank {
  building_id: string;
  score_total: number;
  rank_iris: number | null;
  total_iris: number | null;
  percentile_iris: number | null;
  rank_commune: number | null;
  total_commune: number | null;
  rank_dept: number | null;
  total_dept: number | null;
}

export async function getBuildingRank(
  buildingId: string,
  signal?: AbortSignal,
): Promise<BuildingRank> {
  return fetchJson<BuildingRank>(
    `${API_BASE}/buildings/${encodeURIComponent(buildingId)}/rank`,
    { signal },
  );
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

export interface CachedPlanResponse {
  target_key?: string;
  building_id: string;
  version: number;
  session_id: string;
  plan_text: string;
  generated_at: string;
  label?: string;
}

/** Tente de récupérer un plan pré-calculé. Retourne null si absent. */
export async function getCachedPlan(
  buildingId: string,
  version: number,
): Promise<CachedPlanResponse | null> {
  try {
    const headers = await authHeaders();
    const resp = await fetch(
      `${API_BASE}/agents/plan/cached/${encodeURIComponent(buildingId)}/${version}`,
      { headers },
    );
    if (resp.status === 404) return null;
    if (!resp.ok) return null;
    return (await resp.json()) as CachedPlanResponse;
  } catch {
    return null;
  }
}

/** URL SSE pour `EventSource`. L'auth est portée par cookies/JWT du domaine. */
export function planStreamUrl(sessionId: string, after?: string): string {
  const params = new URLSearchParams();
  if (after) params.set("after", after);
  const qs = params.toString() ? `?${params.toString()}` : "";
  return `${API_BASE}/agents/plan/${encodeURIComponent(sessionId)}/stream${qs}`;
}

/**
 * Demande au backend de générer un PDF du plan v{version} et le télécharge.
 *
 * Le `plan_text` est envoyé par le frontend (il l'a déjà après le SSE ou
 * via le cache local) pour éviter au backend un re-fetch Anthropic qui
 * coûterait des tokens. Le bâtiment est utilisé pour enrichir la couverture
 * du PDF (adresse, identifiant DPE ADEME).
 *
 * Trigger un download navigateur via un blob temporaire.
 */
export async function exportPlanPdf(args: {
  sessionId: string;
  version: number;
  planText: string;
  buildingId: string;
}): Promise<void> {
  const jwt = await getCurrentJwt();
  const r = await fetch(
    `${API_BASE}/agents/plan/${encodeURIComponent(args.sessionId)}/export-pdf?version=${args.version}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(jwt ? { Authorization: `Bearer ${jwt}` } : {}),
      },
      body: JSON.stringify({
        plan_text: args.planText,
        building_id: args.buildingId,
      }),
    },
  );
  if (!r.ok) {
    const detail = await r.text().catch(() => r.statusText);
    throw new Error(`Export PDF échoué (${r.status}) : ${detail}`);
  }
  const blob = await r.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `ConX_pre-cadrage_${args.buildingId}_v${args.version}.pdf`;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  }, 100);
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
