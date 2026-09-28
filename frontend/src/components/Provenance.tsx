/**
 * Provenance UI — the visible half of ADR-004.
 *
 * The old app rendered simulated data tagged `provider: 'API Mitra'`, so a total
 * provider outage looked exactly like a healthy response. These components make the
 * difference impossible to miss: every screen states where its numbers came from and
 * how fresh they are, and an unknown value renders as "—" rather than a plausible
 * number.
 *
 * Colour carries meaning consistently:
 *   emerald = live from the provider    amber = cached/stale (still true, just older)
 *   stone   = timetable, not live       rose  = error / unavailable
 */

import React from 'react';
import { AlertTriangle, Clock, Database, Radio, RefreshCw, WifiOff } from 'lucide-react';
import type { Meta, Source } from '../lib/api';
import { ApiFailure, fmtRelative } from '../lib/api';

const SOURCE_LABEL: Record<Source, { text: string; cls: string; icon: React.ReactNode; help: string }> = {
  live: {
    text: 'Live', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: <Radio className="w-3 h-3 animate-pulse" />,
    help: 'Fetched from the railway provider just now.',
  },
  fresh: {
    text: 'Live', cls: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    icon: <Radio className="w-3 h-3 animate-pulse" />,
    help: 'Fetched from the railway provider just now.',
  },
  cache: {
    text: 'Cached', cls: 'bg-sky-50 text-sky-700 border-sky-200',
    icon: <Database className="w-3 h-3" />,
    help: 'Served from cache within its freshness window to save provider quota.',
  },
  stale: {
    text: 'Stale', cls: 'bg-amber-50 text-amber-800 border-amber-300',
    icon: <Clock className="w-3 h-3" />,
    help: 'The provider is unreachable. This is the last known data — it may be out of date.',
  },
  schedule: {
    text: 'Timetable', cls: 'bg-stone-100 text-stone-600 border-stone-300',
    icon: <Database className="w-3 h-3" />,
    help: 'From the published timetable, not live tracking.',
  },
  model: {
    text: 'Estimated', cls: 'bg-violet-50 text-violet-700 border-violet-200',
    icon: <Clock className="w-3 h-3" />,
    help: 'Estimated by the ETA engine from the last live position.',
  },
  error: {
    text: 'Unavailable', cls: 'bg-rose-50 text-rose-700 border-rose-200',
    icon: <WifiOff className="w-3 h-3" />,
    help: 'Could not be retrieved.',
  },
};

export const SourceBadge: React.FC<{
  source: Source | undefined;
  asOf?: string | null;
  confidence?: number | null;
  className?: string;
}> = ({ source, asOf, confidence, className = '' }) => {
  const s = SOURCE_LABEL[source ?? 'error'] ?? SOURCE_LABEL.error;
  return (
    <span
      title={`${s.help}${asOf ? ` Updated ${fmtRelative(asOf)}.` : ''}`}
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[10px] font-semibold ${s.cls} ${className}`}
    >
      {s.icon}
      <span>{s.text}</span>
      {asOf && <span className="font-normal opacity-70">· {fmtRelative(asOf)}</span>}
      {confidence !== null && confidence !== undefined && (
        <span className="font-normal opacity-70">· {Math.round(confidence * 100)}%</span>
      )}
    </span>
  );
};

/**
 * Banner shown when a response is degraded — stale data, or fields the provider
 * could not supply. Naming the missing fields is deliberate: "we don't have live
 * speed for this train" is useful; a fabricated 128 km/h is not.
 */
export const DegradedBanner: React.FC<{ meta: Meta | null }> = ({ meta }) => {
  if (!meta || !meta.degraded) return null;
  const stale = meta.source === 'stale';
  const fields = meta.unavailableFields ?? [];

  return (
    <div
      className={`flex items-start gap-2.5 px-4 py-2.5 rounded-2xl border text-xs mb-4 ${
        stale ? 'bg-amber-50 border-amber-300 text-amber-900' : 'bg-stone-50 border-stone-200 text-stone-600'
      }`}
    >
      <AlertTriangle className={`w-4 h-4 shrink-0 mt-0.5 ${stale ? 'text-amber-600' : 'text-stone-400'}`} />
      <div>
        {stale && (
          <p className="font-semibold">
            Showing last known data — the railway provider is currently unreachable.
          </p>
        )}
        {fields.length > 0 && (
          <p>
            Not reported by the provider for this train:{' '}
            <span className="font-mono">{fields.join(', ')}</span>. Shown as “—” rather than estimated.
          </p>
        )}
      </div>
    </div>
  );
};

/** Error state. Distinguishes "doesn't exist" from "we can't reach the provider". */
export const ErrorState: React.FC<{
  error: ApiFailure;
  onRetry?: () => void;
  what?: string;
}> = ({ error, onRetry, what = 'data' }) => {
  const notFound = error.isNotFound;
  return (
    <div className="bg-white/95 rounded-[28px] border border-stone-200 p-8 text-center shadow-luxury">
      <div
        className={`w-12 h-12 rounded-full mx-auto mb-4 flex items-center justify-center ${
          notFound ? 'bg-stone-100' : 'bg-rose-50'
        }`}
      >
        {notFound ? (
          <Database className="w-5 h-5 text-stone-400" />
        ) : (
          <WifiOff className="w-5 h-5 text-rose-500" />
        )}
      </div>
      <h3 className="font-display font-bold text-lg text-stone-900">
        {notFound ? `No ${what} found` : `Could not load ${what}`}
      </h3>
      <p className="text-xs text-stone-500 mt-1.5 max-w-md mx-auto">{error.message}</p>
      <p className="text-[10px] text-stone-400 mt-2 font-mono">{error.code}</p>

      {onRetry && error.retryable && (
        <button
          onClick={onRetry}
          className="mt-5 px-5 py-2 rounded-full bg-[#18191B] hover:bg-stone-800 text-white text-xs font-semibold inline-flex items-center gap-2 transition-all active:scale-95"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Try again
        </button>
      )}

      {/* No "show demo data" affordance exists, deliberately: there is no fixture to
          fall back to. An honest dead end beats a convincing fake. */}
    </div>
  );
};

export const LoadingCard: React.FC<{ label?: string; rows?: number }> = ({
  label = 'Loading…', rows = 3,
}) => (
  <div className="bg-white/95 rounded-[28px] border border-stone-200 p-6 shadow-luxury animate-pulse">
    <div className="flex items-center gap-2 mb-5">
      <RefreshCw className="w-4 h-4 text-stone-300 animate-spin" />
      <span className="text-xs text-stone-400">{label}</span>
    </div>
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-3.5 bg-stone-100 rounded-full" style={{ width: `${88 - i * 14}%` }} />
      ))}
    </div>
  </div>
);

/** Value that renders "—" when unknown, with the reason available on hover. */
export const Unknown: React.FC<{ reason?: string }> = ({
  reason = 'Not reported by the railway provider for this train.',
}) => (
  <span title={reason} className="text-stone-400 font-normal cursor-help">
    —
  </span>
);
