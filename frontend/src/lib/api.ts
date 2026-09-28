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
