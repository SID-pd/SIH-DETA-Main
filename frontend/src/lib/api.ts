/**
 * DARPAN API client.
 *
 * The frontend's ONLY data source. Consequences of that, by design:
 *   - no third-party hostname appears in this bundle (was: api.apimitra.in)
 *   - no API key exists client-side (was: localStorage 'darpan_api_config')
 *   - no fallback fixture exists anywhere (was: getSimulatedPnr)
 *
 * Types mirror the server envelope. When the OpenAPI generator is wired up
 * (packages/contracts), this file becomes generated output; until then it is the
 * hand-maintained boundary and the shapes below are the contract.
 */

import { sessionCache } from './sessionCache';
export { sessionCache } from './sessionCache';

const BASE = (import.meta as any).env?.VITE_API_BASE ?? '/v1';

// --- envelope ---------------------------------------------------------------

/** Where a value came from. Rendered in the UI — never silently dropped. */
export type Source = 'live' | 'fresh' | 'cache' | 'stale' | 'schedule' | 'model' | 'error';

export interface Meta {
  source: Source;
  asOf: string;
  provider: string;
  confidence: number | null;
  degraded: boolean;
  unavailableFields: string[];
  [k: string]: unknown;
}

export interface ApiError {
  code: string;
  message: string;
  retryable: boolean;
}

export interface Envelope<T> {
  data: T | null;
  meta: Meta;
  error: ApiError | null;
}

/** Thrown for any non-2xx. Carries the server's typed code so UIs can branch. */
export class ApiFailure extends Error {
  constructor(
    public code: string,
    message: string,
    public retryable: boolean,
    public status: number,
  ) {
    super(message);
    this.name = 'ApiFailure';
  }

  /** Distinguishes "no such train" from "provider is down" for the empty state. */
  get isNotFound() {
    return this.code === 'NOT_FOUND' || this.code === 'PNR_NOT_FOUND';
  }

  get isProviderDown() {
    return ['PROVIDER_UNAVAILABLE', 'PROVIDER_TIMEOUT', 'QUOTA_EXHAUSTED', 'PROVIDER_ERROR'].includes(this.code);
  }
}

export interface Result<T> {
  data: T;
  meta: Meta;
}

export interface RequestOptions {
  forceFresh?: boolean;
  ttlMs?: number;
}

async function request<T>(path: string, signal?: AbortSignal, options?: RequestOptions): Promise<Result<T>> {
  if (!options?.forceFresh) {
    const cached = sessionCache.get<T>(path);
    if (cached) {
      return cached;
    }
  }

  let resp: Response;
  try {
    resp = await fetch(`${BASE}${path}`, {
      headers: { Accept: 'application/json' },
      signal,
    });
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err;
    const fallback = sessionCache.get<T>(path);
    if (fallback) {
      return { ...fallback, meta: { ...fallback.meta, source: 'cache', degraded: true } };
    }
    throw new ApiFailure('NETWORK', 'Cannot reach the DARPAN API.', true, 0);
  }

  let body: Envelope<T>;
  try {
    body = await resp.json();
  } catch {
    throw new ApiFailure('BAD_RESPONSE', 'API returned a malformed response.', true, resp.status);
  }

  if (!resp.ok || body.error || body.data === null) {
    const e = body.error;
    throw new ApiFailure(
      e?.code ?? 'UNKNOWN',
      e?.message ?? `Request failed (${resp.status})`,
      e?.retryable ?? false,
      resp.status,
    );
  }

  const result: Result<T> = { data: body.data, meta: body.meta };
  sessionCache.set<T>(path, result, options?.ttlMs);
  return result;
}

// --- domain types -----------------------------------------------------------

export interface StationSummary {
  code: string;
  name: string;
  state: string | null;
  zone: string | null;
  lat: number | null;
  lon: number | null;
}

export interface TrainSummary {
  number: string;
  name: string;
  type: string | null;
  from_code: string | null;
  from_name: string | null;
  to_code: string | null;
  to_name: string | null;
  departure: string | null;
  arrival: string | null;
  duration_min: number | null;
  distance_km: number | null;
  lookups?: number;
}

/** A value the provider may not supply. `null` means unknown — render "—". */
export interface StopEta {
  arrival: string | null;
  delayMinutes: number | null;
  band: { p10: string | null; p90: string | null };
  source: 'observed' | 'model' | 'schedule' | 'unknown';
  confidence: number | null;
  providerArrival: string | null;
  providerDivergenceMinutes: number | null;
  segmentObservations: number;
}

export interface Stop {
  stationCode: string;
  stationName: string | null;
  distanceKm: number | null;
  platform: string | null;
  status: 'passed' | 'current' | 'upcoming' | null;
  scheduled: { arrival: string | null; departure?: string | null };
  actual: { arrival: string | null; departure?: string | null };
  eta: StopEta;
  coordinates: { lat: number; lon: number } | null;
}

export interface Coach {
  type?: string | null;
  label?: string | null;
  code?: string | null;
  category?: string | null;
  class?: string | null;
  position: number | null;
}

export interface Risk {
  delayProbability: number;
  label: 'low' | 'moderate' | 'elevated';
  modelVersion: string;
  target: string;
  imputedFeatures: string[];
  imputedFeatureCount: number;
  trustworthiness: string;
  appliesToClockTimes: boolean;
}

export interface RunOption {
  key: string;
  label: string;
  dateLabel: string;
  dayName?: string;
  fullDayName?: string;
  offset: number;
  isToday: boolean;
  isActive?: boolean;
  preview?: {
    distanceCoveredKm?: number | null;
    delayMinutes?: number | null;
    status?: string;
  };
}

export interface LiveStatus {
  train: {
    number: string | null;
    name: string | null;
    type: string | null;
    journeyDate: string | null;
    from: { code: string | null; name: string | null };
    to: { code: string | null; name: string | null };
    availableRuns?: RunOption[];
    runsOnToday?: boolean;
    runningDays?: string | null;
    activeDate?: string | null;
    selectedDate?: string | null;
  };
  position: {
    currentStationCode: string | null;
    currentStationName?: string | null;
    lastStationCode: string | null;
    lastStationName?: string | null;
    nextStationCode: string | null;
    nextStationName?: string | null;
    delayMinutes: number | null;
    /** Always null with the current provider — it reports no live speed. */
    speedKmph: number | null;
    distanceCoveredKm: number | null;
    totalDistanceKm: number | null;
    statusNote: string | null;
    lastUpdateAt: string | null;
    coordinates: { lat: number; lon: number } | null;
  };
  nextStop: Stop | null;
  stops: Stop[];
  passingPointCount: number;
  composition: Coach[];
  eta: {
    currentDelayMinutes: number | null;
    delaySource: string;
    engine: string;
    notes: string[];
  };
  risk: Risk | null;
}

export interface BoardTrain {
  trainNumber: string;
  trainName: string | null;
  trainType: string | null;
  from: { code: string | null; name: string | null };
  to: { code: string | null; name: string | null };
  classes: string | null;
  platform: string | null;
  cancelled: boolean;
  arrival: { scheduled: string | null; actual: string | null; delayMinutes: number | null };
  departure: { scheduled: string | null; actual: string | null; delayMinutes: number | null };
}

export interface StationBoard {
  station: StationSummary | { code: string };
  window: number;
  mode: string;
  totalTrains: number | null;
  trains: BoardTrain[];
}

export interface Passenger {
  serial: number;
  bookingStatus: string | null;
  currentStatus: string | null;
  coach: string | null;
  berth: number | null;
  berthType: string | null;
}

export interface PnrStatus {
  pnr: string;
  train: { number: string | null; name: string | null };
  journeyDate: string | null;
  from: { code: string | null; name: string | null };
  to: { code: string | null; name: string | null };
  reservationClass: string | null;
  quota: string | null;
  chartPrepared: boolean | null;
  passengers: Passenger[];
  trainStatic: TrainSummary | null;
}

export interface ProviderHealth {
  gateway: { reachable: boolean; quota?: { used: number; remaining: number; limit: number } };
  client: {
    breaker: { state: string; failures: number; trips: number };
    endpoints: Record<string, { calls: number; errors: number; avgLatencyMs: number }>;
    lastError: string | null;
  };
}

export interface DetaDatabaseModule {
  module: string;
  db_key: string;
  file_name: string;
  present_on_disk: boolean;
  size_mb: number;
  tables: Record<string, number>;
  status: string;
}

export interface DetaOverview {
  system_name: string;
  version: string;
  architecture_layers: {
    layer_1_ml: string;
    layer_2_dsa: string;
    layer_3_ops: string;
  };
  data_lake: {
    modules: DetaDatabaseModule[];
    audit_remediation: {
      issue_1_station_alias_engine: {
        status: string;
        recovered_records: number;
        recovered_block_sections: number;
        sample_aliases: Record<string, string>;
      };
      issue_2_route_stops_bridge: { status: string; active_source: string };
      issue_3_pk_column_normalization: { status: string; view: string };
      issue_4_live_kinematic_pacing: { status: string; engine: string };
      issue_5_exception_hardening: { status: string; locations_hardened: number };
    };
  };
  control_room: ControlRoomState;
}

export interface ReroutePlan {
  severed_section: string;
  edge_weight: string;
  original_via_stations: string[];
  original_distance_km: number;
  detour_via_stations: string[];
  detour_corridors: string[];
  detour_distance_km: number;
  added_distance_km: number;
  estimated_detour_penalty_mins: number;
  traction_verified: string;
  algorithm: string;
}

export interface ControllerIncident {
  incident_id: string;
  incident_type: string;
  title: string;
  section_from: string;
  section_to: string;
  severity: string;
  estimated_clearance_mins: number;
  affected_train_number: string;
  controller_id: string;
  physics_mechanism: string;
  action_recommended: string;
  created_at: string;
  is_resolved: boolean;
  trailing_trains_delayed?: string[];
  reroute_plan?: ReroutePlan | null;
}

export interface EventSurgePreset {
  event_id: string;
  event_name: string;
  surge_multiplier: number;
  waitlist_load_factor: number;
  special_trains_injected: number;
  affected_stations: string[];
  description: string;
}

export interface ControlRoomState {
  as_of: string;
  degradation_level: 'LEVEL_1_NORMAL' | 'LEVEL_2_DEAD_RECKONING' | 'LEVEL_3_BLACK_SWAN';
  degradation_description: string;
  active_event_id: string;
  active_event_preset: EventSurgePreset;
  available_event_presets: EventSurgePreset[];
  weather_override: {
    visibility_meters: number;
    precipitation_mm: number;
    ambient_temp_c: number;
  };
  active_incidents: ControllerIncident[];
  incident_catalog: Array<{
    type: string;
    title: string;
    default_detention_mins: number;
    default_severity: string;
    physics_mechanism: string;
    trailing_trains_affected: string[];
    action_recommended: string;
  }>;
  adaptive_pacing_engine: {
    cataloged_trains_total: number;
    active_window_trains_polled: number;
    inactive_sleeping_trains: number;
    network_load_reduction_pct?: number;
    network_Load_reduction_pct?: number;
    spatial_weather_hex_cells: number;
    stations_covered_by_hex_grid: number;
    weather_api_reduction_pct: number;
    token_bucket_rate_rps: number;
    token_bucket_burst_capacity: number;
    outer_deceleration_poll_interval_sec: number;
    tier1_rajdhani_vb_poll_interval_sec: number;
    tier2_express_poll_interval_sec: number;
  };
}

export interface HybridStopPrediction {
  stop_sequence: number;
  station_code: string;
  station_name: string;
  distance_km: number;
  status: 'PASSED' | 'CURRENT' | 'UPCOMING';
  scheduled_arrival: string;
  p10_optimistic_eta: string;
  p50_median_eta: string;
  p90_pessimistic_eta: string;
  p10_delay_mins: number;
  p50_delay_mins: number;
  p90_delay_mins: number;
  naive_static_eta: string;
  naive_static_delay_mins: number;
  slack_absorbed_mins: number;
  scheduled_dwell_mins: number;
  dilated_dwell_mins: number;
  nsg_category: string;
  surge_multiplier: number;
  assigned_platform: number;
  outer_signal_hold_mins: number;
  outer_signal_hold_risk: number;
  approach_cabin: { cabin_code: string; cabin_name: string; distance_to_parent_km?: number; signal_aspect?: string } | null;
  dag_lock_status: string;
}

export interface MicroTraversalNode {
  node_id: string;
  node_type: string;
  code: string;
  name: string;
  signal_aspect: string;
  visibility_m: number;
  speed_limit_kmh: number;
  micro_delay_delta_mins: number;
  root_cause: string;
}

export interface HybridEtaPayload {
  train_number: string;
  train_name: string;
  train_type: string;
  priority_tier: number;
  priority_label: string;
  degradation_level: string;
  traversal_mode: string;
  target_station: string;
  target_station_name: string;
  scheduled_arrival: string;
  current_telemetry: {
    last_reported_station: string;
    last_reported_station_name: string;
    distance_covered_km: number;
    distance_remaining_km: number;
    instantaneous_delay_mins: number;
    delay_drift_rate_100km: number;
    delay_trend: string;
  };
  predictions: {
    p10_optimistic_arrival: string;
    p50_median_arrival: string;
    p90_pessimistic_arrival: string;
    p10_time: string;
    p50_time: string;
    p90_time: string;
    naive_static_time: string;
    p10_delay_mins: number;
    p50_delay_mins: number;
    p90_delay_mins: number;
    slack_absorption_expected_mins: number;
    confidence_interval_width_mins: number;
    monotonic_bounds_verified: boolean;
  };
  layer1_behaviour_and_surge: {
    corridor_profiles_indexed: number;
    historical_records_analyzed: number;
    alias_recovered_records: number;
    target_station_surge: StationSurgeProfile;
  };
  layer2_dsa_constraints: {
    assigned_platform: number;
    outer_signal_hold_risk: number;
    outer_signal_detention_mins: number;
    approach_cabin: { cabin_code: string; cabin_name: string } | null;
    headway_guard_margin_mins: number;
    space_time_dag: {
      architecture: string;
      max_iterations_k_max: number;
      cyclic_feedback_possible: boolean;
      total_locked_nodes: number;
    };
    active_tsr_on_corridor: Array<{
      section: string;
      speed_cap_kmh: number;
      nominal_mps_kmh: number;
      reason: string;
      rule: string;
    }>;
    reroute_plan: ReroutePlan | null;
  };
  weather_constraints: {
    station_code: string;
    visibility_meters: number;
    is_foggy: boolean;
    fog_speed_cap_kmh: number | null;
    fog_rule: string;
    precipitation_mm: number;
    monsoon_active: boolean;
    monsoon_speed_cap_kmh: number | null;
    monsoon_rule: string;
    ambient_temp_c: number;
    estimated_rail_temp_c: number;
    heat_buckling_warning: boolean;
    nominal_mps_kmh: number;
    effective_mps_cap_kmh: number;
    throttle_reason: string;
    speed_penalty_mins_per_100km: number;
  };
  micro_traversal_nodes: MicroTraversalNode[];
  stop_predictions: HybridStopPrediction[];
  active_corridor_incidents: ControllerIncident[];
}

export interface StationSurgeProfile {
  station_code: string;
  station_name: string;
  zone: string;
  platforms: number;
  nsg_category: string;
  nsg_details: {
    tier: string;
    revenue_criterion: string;
    passengers_criterion: string;
    footfall_index: number;
    base_dwell_pad_mins: number;
    acp_risk_mins: number;
  };
  active_event: string;
  event_id: string;
  surge_multiplier_s_event: number;
  scheduled_dwell_mins: number;
  dilated_dwell_mins: number;
  dwell_inflation_added_mins: number;
  acp_risk_added_mins: number;
  platform_saturation_rho: number;
  outer_signal_starvation_prob: number;
  formula_trace: string;
}

export interface PlatformIntervalEntry {
  interval_id: string;
  platform_number: number;
  train_number: string;
  train_name: string;
  priority_tier: number;
  priority_label: string;
  unconstrained_arrival?: string;
  arrival_time: string;
  departure_time: string;
  start_mins: number;
  end_mins: number;
  dwell_mins: number;
  status: 'PLATFORM_ASSIGNED' | 'OUTER_SIGNAL_HOLD';
  outer_detention_mins: number;
  held_at_cabin: string | null;
  cabin_code?: string;
}

export interface StationPlatformIntervals {
  station_code: string;
  station_name: string;
  zone: string;
  platform_count: number;
  headway_buffer_mins: number;
  surge_profile: StationSurgeProfile;
  approach_cabins: Array<{
    cabin_code?: string;
    cabin_name?: string;
    point_code?: string;
    point_name?: string;
    distance_to_parent_km?: number;
    signal_aspect?: string;
  }>;
  intervals: PlatformIntervalEntry[];
  outer_held_trains: PlatformIntervalEntry[];
  saturation_summary: {
    total_trains_in_window: number;
    direct_ingress_count: number;
    outer_signal_held_count: number;
    mutual_exclusion_verified: boolean;
  };
}

async function requestPost<T>(path: string, payload: Record<string, unknown>): Promise<Result<T>> {
  let resp: Response;
  try {
    resp = await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiFailure('NETWORK', 'Cannot reach the DARPAN API.', true, 0);
  }

  let body: Envelope<T>;
  try {
    body = await resp.json();
  } catch {
    throw new ApiFailure('BAD_RESPONSE', 'API returned a malformed response.', true, resp.status);
  }

  if (!resp.ok || body.error || body.data === null) {
    const e = body.error;
    throw new ApiFailure(
      e?.code ?? 'UNKNOWN',
      e?.message ?? `Request failed (${resp.status})`,
      e?.retryable ?? false,
      resp.status,
    );
  }

  sessionCache.clear();
  return { data: body.data, meta: body.meta };
}

// --- endpoints --------------------------------------------------------------

export const api = {
  searchStations: (q: string, signal?: AbortSignal, opts?: RequestOptions) =>
    request<StationSummary[]>(`/stations?q=${encodeURIComponent(q)}&limit=8`, signal, opts),

  stationBoard: (code: string, window = 2, mode = 'dep', signal?: AbortSignal, opts?: RequestOptions) =>
    request<StationBoard>(`/stations/${encodeURIComponent(code)}/board?window=${window}&mode=${mode}`, signal, opts),

  searchTrains: (q: string, signal?: AbortSignal, opts?: RequestOptions) =>
    request<TrainSummary[]>(`/trains?q=${encodeURIComponent(q)}&limit=8`, signal, opts),

  popularTrains: (signal?: AbortSignal, opts?: RequestOptions) =>
    request<TrainSummary[]>('/trains/popular?limit=6', signal, opts),

  trainLive: (number: string, date?: string, signal?: AbortSignal, opts?: RequestOptions) => {
    const q = date ? `?date=${encodeURIComponent(date)}` : '';
    return request<LiveStatus>(`/trains/${encodeURIComponent(number)}/live${q}`, signal, opts);
  },

  routeGeoJson: (number: string, signal?: AbortSignal, opts?: RequestOptions) =>
    request<any>(`/trains/${encodeURIComponent(number)}/route.geojson`, signal, opts),

  pnr: (pnr: string, signal?: AbortSignal, opts?: RequestOptions) =>
    request<PnrStatus>(`/pnr/${encodeURIComponent(pnr)}`, signal, opts),

  providerHealth: (signal?: AbortSignal, opts?: RequestOptions) =>
    request<ProviderHealth>('/health/providers', signal, opts),

  modelMeta: (signal?: AbortSignal, opts?: RequestOptions) => request<any>('/meta/model', signal, opts),

  // SIH-DETA Hybrid ML + Discrete DSA Endpoints
  detaOverview: (signal?: AbortSignal, opts?: RequestOptions) =>
    request<DetaOverview>('/deta/overview', signal, { forceFresh: true, ...opts }),

  detaEta: (
    params: {
      train_number: string;
      target_station?: string;
      delay_override?: number;
      event_id?: string;
      visibility_m?: number;
    },
    signal?: AbortSignal,
    opts?: RequestOptions,
  ) => {
    const qs = new URLSearchParams({ train_number: params.train_number });
    if (params.target_station) qs.set('target_station', params.target_station);
    if (params.delay_override !== undefined) qs.set('delay_override', String(params.delay_override));
    if (params.event_id) qs.set('event_id', params.event_id);
    if (params.visibility_m !== undefined) qs.set('visibility_m', String(params.visibility_m));
    return request<HybridEtaPayload>(`/deta/eta?${qs.toString()}`, signal, { forceFresh: true, ...opts });
  },

  detaControllerState: (signal?: AbortSignal, opts?: RequestOptions) =>
    request<ControlRoomState>('/deta/controller/state', signal, { forceFresh: true, ...opts }),

  detaReportIncident: (payload: {
    incident_type: string;
    section_from?: string;
    section_to?: string;
    severity?: string;
    estimated_clearance_mins?: number;
    affected_train_number?: string;
    controller_id?: string;
  }) => requestPost<any>('/deta/controller/incident', payload),

  detaResolveIncident: (incident_id = 'ALL') =>
    requestPost<any>('/deta/controller/resolve', { incident_id }),

  detaSetEnvironment: (payload: {
    event_id?: string;
    visibility_meters?: number;
    precipitation_mm?: number;
    ambient_temp_c?: number;
  }) => requestPost<ControlRoomState>('/deta/controller/environment', payload),

  detaStationPlatforms: (
    code: string,
    event_id?: string,
    center_mins = 840,
    signal?: AbortSignal,
    opts?: RequestOptions,
  ) => {
    const qs = new URLSearchParams({ center_mins: String(center_mins) });
    if (event_id) qs.set('event_id', event_id);
    return request<StationPlatformIntervals>(
      `/deta/stations/${encodeURIComponent(code)}/platforms?${qs.toString()}`,
      signal,
      { forceFresh: true, ...opts },
    );
  },

  detaReroute: (from_station: string, to_station: string, signal?: AbortSignal, opts?: RequestOptions) =>
    request<ReroutePlan>(
      `/deta/reroute?from_station=${encodeURIComponent(from_station)}&to_station=${encodeURIComponent(to_station)}`,
      signal,
      { forceFresh: true, ...opts },
    ),
};

// --- display helpers --------------------------------------------------------

/** Renders an ISO instant as IST clock time, or "—" when unknown. */
export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString('en-IN', {
    hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata',
  });
}

export function fmtDelay(min: number | null | undefined): string {
  if (min === null || min === undefined) return '—';
  if (min === 0) return 'RT';
  if (min < 0) return `${Math.abs(min)}m early`;
  return `+${min}m`;
}

export function fmtRelative(iso: string | null | undefined): string {
  if (!iso) return 'unknown';
  const secs = (Date.now() - new Date(iso).getTime()) / 1000;
  if (Number.isNaN(secs)) return 'unknown';
  if (secs < 60) return 'just now';
  if (secs < 3600) return `${Math.floor(secs / 60)} min ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)} h ago`;
  return `${Math.floor(secs / 86400)} d ago`;
}
