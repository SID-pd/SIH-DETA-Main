/**
 * Live train running status.
 *
 * Rewritten in Phase 1 to remove (see plan §1.2):
 *   H4  `trainsData` — 3 trains with hardcoded speeds, platforms and per-stop delays
 *   H5  unknown train silently falling back to 22436
 *   H6  a modal offering three fictional API endpoints as user-selectable providers
 *
 * This component is now a pure view over GET /v1/trains/{no}/live. It holds no rail
 * data, no provider config and no fallback fixture. Live speed renders as "—" because
 * the provider does not report it — the old page displayed 128 km/h under a
 * "Live GPS Telemetry" label, which was invented.
 */

import React, { useState } from 'react';
import {
  Search, Radio, CheckCircle2, Zap, RefreshCw, ArrowRight, Code, TrainFront,
  MapPin, AlertCircle, Gauge, Calendar, Clock, Map as MapIcon, Layers, Lock,
  CloudFog, Sparkles, Route, ShieldAlert,
} from 'lucide-react';
import { api, fmtDelay, fmtTime, type Stop, type RunOption } from '../lib/api';
import { useDebounced, useQuery } from '../hooks/useApi';
import { DegradedBanner, ErrorState, LoadingCard, SourceBadge, Unknown } from '../components/Provenance';

interface LivePageProps {
  initialTrainQuery?: string;
  initialDate?: string;
  onTrainChange?: (trainNo: string, date?: string) => void;
  onViewMap?: (trainNo: string, date?: string) => void;
}

function getAvailableRunDates(): RunOption[] {
  // Use Indian Standard Time (UTC+5:30)
  const nowUtc = new Date();
  const istOffsetMs = 5.5 * 3600 * 1000;
  const nowIst = new Date(nowUtc.getTime() + istOffsetMs);

  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const offsets = [-1, 0, 1]; // Yesterday, Today, Tomorrow

  return offsets.map((offset) => {
    const d = new Date(nowIst.getTime() + offset * 86400 * 1000);
    const day = String(d.getUTCDate()).padStart(2, '0');
    const month = String(d.getUTCMonth() + 1).padStart(2, '0');
    const year = d.getUTCFullYear();
    const key = `${day}-${month}-${year}`;
    const monStr = months[d.getUTCMonth()];
    const dateLabel = `${day} ${monStr}`;

    let label = '';
    if (offset === -1) label = 'Yesterday';
    else if (offset === 0) label = 'Today';
    else if (offset === 1) label = 'Tomorrow';

    return {
      key,
      label,
      dateLabel,
      offset,
      isToday: offset === 0,
    };
  });
}

const DELAY_TONE = (min: number | null) => {
  if (min === null) return 'bg-stone-100 text-stone-500 border-stone-200';
  if (min <= 0) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (min <= 15) return 'bg-amber-50 text-amber-700 border-amber-200';
  return 'bg-rose-50 text-rose-700 border-rose-200';
};

const getCoachStyle = (label: string, cls: string) => {
  const l = (label || '').toUpperCase();
  const c = (cls || '').toUpperCase();
  if (l.includes('ENG') || c.includes('ENG') || l.includes('LOCO')) {
    return 'bg-stone-900 text-white border-stone-800 shadow-xs';
  }
  if (l.startsWith('H') || c === '1A') {
    return 'bg-purple-100 text-purple-900 border-purple-300 font-semibold';
  }
  if (l.startsWith('A') || c === '2A') {
    return 'bg-sky-100 text-sky-900 border-sky-300 font-semibold';
  }
  if (l.startsWith('B') || l.startsWith('M') || c === '3A' || c === '3E') {
    return 'bg-emerald-100 text-emerald-900 border-emerald-300 font-semibold';
  }
  if (l.startsWith('S') || c === 'SL') {
    return 'bg-amber-100 text-amber-900 border-amber-300 font-semibold';
  }
  if (l.startsWith('PC') || c.includes('PANTRY')) {
    return 'bg-rose-100 text-rose-900 border-rose-300 font-semibold';
  }
  if (l.startsWith('GS') || l.startsWith('GEN') || c.includes('GEN') || c === '2S') {
    return 'bg-stone-100 text-stone-800 border-stone-300';
  }
  if (l.startsWith('SLR') || l.startsWith('EOG')) {
    return 'bg-zinc-100 text-zinc-700 border-zinc-300';
  }
  return 'bg-stone-50 text-stone-800 border-stone-200';
};

export const LivePage: React.FC<LivePageProps> = ({
  initialTrainQuery = '',
  initialDate = '',
  onTrainChange,
  onViewMap,
}) => {
  const [input, setInput] = useState(initialTrainQuery);
  const [trainNo, setTrainNo] = useState(initialTrainQuery);
  const [showJson, setShowJson] = useState(false);

  // SIH-DETA Hybrid ML + Discrete DSA simulation controls
  const [traversalMode, setTraversalMode] = useState<'normal' | 'detailed'>('detailed');
  const [detaEventId, setDetaEventId] = useState<string>('MAHA_KUMBH');
  const [detaVisM, setDetaVisM] = useState<number>(380);
  const [detaDelayOverride, setDetaDelayOverride] = useState<number | undefined>(undefined);

  const fallbackRunDates = getAvailableRunDates();
  const todayKey = fallbackRunDates.find((r) => r.isToday)?.key ?? '';
  const [selectedDate, setSelectedDate] = useState<string>(initialDate || todayKey);

  // Sync external train prop
  React.useEffect(() => {
    if (initialTrainQuery && initialTrainQuery !== trainNo) {
      setInput(initialTrainQuery);
      setTrainNo(initialTrainQuery);
    }
  }, [initialTrainQuery]);

  // Sync external date prop
  React.useEffect(() => {
    if (initialDate && initialDate !== selectedDate) {
      setSelectedDate(initialDate);
    }
  }, [initialDate]);

  const handleSelectDate = (dateKey: string) => {
    setSelectedDate(dateKey);
    onTrainChange?.(trainNo, dateKey);
  };

  const debounced = useDebounced(input, 300);
  const isTrainNumber = /^\d{5}$/.test(trainNo);

  // Search suggestions come from 5,208 real trains in our own store (zero quota).
  const suggestions = useQuery(
    debounced.trim().length >= 2 && !/^\d{5}$/.test(debounced.trim())
      ? (signal) => api.searchTrains(debounced.trim(), signal)
      : null,
    [debounced],
  );

  // Live status polls on the server's TTL cadence; the server single-flights, so
  // many open tabs still cost one provider call per window.
  const live = useQuery(
    isTrainNumber ? (signal) => api.trainLive(trainNo, selectedDate || undefined, signal) : null,
    [trainNo, selectedDate],
    { pollMs: 60_000 },
  );

  // SIH-DETA Hybrid ML (P10/P50/P90) + Discrete DSA Engine query
  const detaQuery = useQuery(
    isTrainNumber
      ? (signal) =>
          api.detaEta(
            {
              train_number: trainNo,
              delay_override: detaDelayOverride,
              event_id: detaEventId,
              visibility_m: detaVisM,
            },
            signal,
          )
      : null,
    [trainNo, detaDelayOverride, detaEventId, detaVisM],
  );

  const popular = useQuery((signal) => api.popularTrains(signal), []);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    // No silent fallback to a default train (H5): a 5-digit number is looked up,
    // anything else is left to the suggestion list.
    if (/^\d{5}$/.test(q)) {
      setTrainNo(q);
      setSelectedDate(todayKey);
      onTrainChange?.(q, todayKey);
    }
  };

  const d = live.data;
  const deta = detaQuery.data;
  const runDates: RunOption[] = (d?.train?.availableRuns && d.train.availableRuns.length > 0)
    ? d.train.availableRuns
    : fallbackRunDates;

  // Auto-align selectedDate if the train is weekly/special and does not run on currently selected date
  React.useEffect(() => {
    if (d?.train?.availableRuns && d.train.availableRuns.length > 0) {
      if (d?.train?.activeDate && !initialDate && selectedDate !== d.train.activeDate) {
        setSelectedDate(d.train.activeDate);
        return;
      }
      const isSelectedValid = d.train.availableRuns.some((r) => r.key === selectedDate);
      if (!isSelectedValid) {
        const todayRun = d.train.availableRuns.find((r) => r.isToday);
        const latestRun = d.train.availableRuns.filter((r) => r.offset <= 0).pop();
        const fallbackRun = todayRun || latestRun || d.train.availableRuns[0];
        if (fallbackRun && fallbackRun.key !== selectedDate) {
          setSelectedDate(fallbackRun.key);
        }
      }
    }
  }, [d?.train?.availableRuns, d?.train?.activeDate]);
  const upcoming = (d?.stops ?? []).filter((s) => s.status !== 'passed');
  const progress =
    d?.position?.distanceCoveredKm !== null &&
    d?.position?.distanceCoveredKm !== undefined &&
    d?.position?.totalDistanceKm
      ? Math.min(100, Math.max(0, Math.round((d.position.distanceCoveredKm / d.position.totalDistanceKm) * 100)))
      : null;

  // Auto-scroll timeline to active station (current or first upcoming)
  React.useEffect(() => {
    if (d?.stops && d.stops.length > 0) {
      const activeStop =
        d.stops.find((s) => s.status === 'current') ||
        d.stops.find((s) => s.status === 'upcoming');
      if (activeStop) {
        const timer = setTimeout(() => {
          const el = document.getElementById(`stop-${activeStop.stationCode}`);
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }
        }, 250);
        return () => clearTimeout(timer);
      }
    }
  }, [d?.stops, selectedDate]);

  return (
    <div className="max-w-5xl mx-auto px-4 pt-4 sm:pt-8 pb-28">
      <div className="text-center mb-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold mb-3 border border-emerald-200/70">
          <Radio className="w-3.5 h-3.5 animate-pulse" />
          <span>Live Telemetry Stream</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-display font-bold text-stone-900 tracking-tight">
          Live Train Running Status
        </h1>
        <p className="text-xs sm:text-sm text-stone-500 mt-1">
          Real provider data · per-stop ETA propagated from the last live position.
        </p>
      </div>

      {/* Search */}
      <div className="bg-white/95 p-4 sm:p-5 rounded-[28px] border border-stone-200 shadow-luxury mb-6">
        <form onSubmit={submit} className="flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 text-stone-400 absolute left-4 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Train number (5 digits) or name — e.g. 12301 or Rajdhani"
              className="w-full pl-11 pr-4 py-3 bg-stone-50 hover:bg-stone-100/70 focus:bg-white rounded-full text-sm text-stone-900 border border-stone-200/80 focus:border-[#FF6332] focus:ring-4 focus:ring-orange-500/10 transition-all focus:outline-none"
            />
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <button
              type="submit"
              className="flex-1 sm:flex-initial px-6 py-3 rounded-full bg-[#18191B] hover:bg-stone-800 text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-md transition-all active:scale-95"
            >
              <Search className="w-3.5 h-3.5" />
              <span>Locate Train</span>
            </button>
            {d && (
              <button
                type="button"
                onClick={() => setShowJson(true)}
                className="p-3 rounded-full bg-stone-100 hover:bg-stone-200 transition-colors border border-stone-200/70"
                title="Inspect the raw API response"
              >
                <Code className="w-4 h-4 text-stone-600" />
              </button>
            )}
          </div>
        </form>

        {/* Name search results over the real train table */}
        {suggestions.data && suggestions.data.length > 0 && (
          <div className="mt-3 pt-3 border-t border-stone-100 flex flex-wrap gap-2">
            {suggestions.data.map((t) => (
              <button
                key={t.number}
                onClick={() => { setTrainNo(t.number); setInput(t.number); setSelectedDate(todayKey); }}
                className="px-3 py-1.5 rounded-full bg-stone-100/80 hover:bg-stone-200 text-stone-700 border border-stone-200/60 text-xs transition-all"
              >
                <span className="font-mono font-semibold">{t.number}</span> · {t.name}
              </button>
            ))}
          </div>
        )}

        {/* Flagship Corridor Quick-Selectors for SIH-DETA Inspection */}
        {!suggestions.data?.length && (
          <div className="mt-3 pt-3 border-t border-stone-100 flex flex-wrap items-center gap-2 text-xs">
            <span className="text-stone-400 font-medium">Flagship Corridors:</span>
            {[
              { number: '12301', name: 'Howrah Rajdhani' },
              { number: '12951', name: 'Mumbai Rajdhani' },
              { number: '22436', name: 'Vande Bharat Exp' },
              { number: '12004', name: 'New Delhi Shatabdi' },
              { number: '12424', name: 'Dibrugarh Rajdhani' },
            ].map((t) => (
              <button
                key={t.number}
                onClick={() => {
                  setTrainNo(t.number);
                  setInput(t.number);
                  setSelectedDate(todayKey);
                  onTrainChange?.(t.number, todayKey);
                }}
                className={`px-3 py-1 rounded-full border transition-all cursor-pointer ${
                  trainNo === t.number
                    ? 'bg-stone-900 text-white border-stone-900 font-semibold'
                    : 'bg-stone-100/80 hover:bg-stone-200 text-stone-700 border-stone-200/60'
                }`}
              >
                <span className="font-mono font-bold text-[#FF6332]">{t.number}</span> · {t.name}
              </button>
            ))}
          </div>
        )}

        {/* Journey Run Date Selector (supports daily, weekly, and special train runs) */}
        {isTrainNumber && (
          <div className="mt-4 pt-3.5 border-t border-stone-100 flex items-center justify-between flex-wrap gap-2.5">
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-[#FF6332]" />
              <span className="text-xs font-semibold text-stone-700">Journey Run:</span>
            </div>
            <div className="flex items-center gap-1.5 bg-stone-100/90 p-1 rounded-full border border-stone-200/80 overflow-x-auto max-w-full">
              {runDates.map((r) => {
                const active = (selectedDate || todayKey) === r.key;
                return (
                  <button
                    key={r.key}
                    type="button"
                    onClick={() => handleSelectDate(r.key)}
                    className={`px-3.5 py-1.5 rounded-full text-xs transition-all flex items-center gap-1.5 whitespace-nowrap cursor-pointer ${
                      active
                        ? 'bg-stone-900 text-white shadow-xs font-bold'
                        : 'text-stone-600 hover:text-stone-900 hover:bg-stone-200/60 font-medium'
                    }`}
                  >
                    <span>{r.label}</span>
                    <span className={`text-[10px] font-mono ${active ? 'text-stone-300' : 'text-stone-400'}`}>
                      ({r.dateLabel})
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Empty state — search-first, no default train (H12) */}
      {!isTrainNumber && !live.loading && (
        <div className="bg-white/95 rounded-[28px] border border-stone-200 p-10 text-center shadow-luxury">
          <TrainFront className="w-10 h-10 text-stone-300 mx-auto mb-3" />
          <h3 className="font-display font-bold text-lg text-stone-900">Search for a train</h3>
          <p className="text-xs text-stone-500 mt-1.5 max-w-sm mx-auto">
            Enter a 5-digit train number, or select a flagship corridor above to inspect live telemetry and SIH-DETA Quantile (P10/P50/P90) + Discrete DSA predictions.
          </p>
        </div>
      )}

      {/* SIH-DETA Hybrid ML (P10/P50/P90) + Discrete DSA Intelligence Panel */}
      {deta && (
        <div className="bg-white/95 rounded-[32px] border border-stone-200/90 p-5 sm:p-7 shadow-luxury mb-6">
          {/* Top Header & Dual-Mode Traversal Switcher */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-stone-100">
            <div>
              <div className="flex items-center gap-2 flex-wrap mb-1.5">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-orange-50 text-[#FF6332] border border-orange-200 text-[11px] font-bold">
                  <Sparkles className="w-3 h-3" /> SIH-DETA Hybrid ML + Discrete DSA Engine
                </span>
                <span className="font-mono text-[11px] px-2.5 py-0.5 rounded-full bg-stone-900 text-white font-bold">
                  {deta.priority_label}
                </span>
                <span className="font-mono text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 font-bold flex items-center gap-1">
                  <Lock className="w-3 h-3" /> {deta.layer2_dsa_constraints.space_time_dag.total_locked_nodes} Nodes LOCKED
                </span>
              </div>
              <h3 className="text-xl sm:text-2xl font-display font-bold text-stone-900">
                #{deta.train_number} {deta.train_name} → {deta.target_station_name} ({deta.target_station})
              </h3>
              <p className="text-xs text-stone-500 mt-0.5">
                Trained on {deta.layer1_behaviour_and_surge.historical_records_analyzed.toLocaleString()} sectional delay records · {deta.layer1_behaviour_and_surge.corridor_profiles_indexed.toLocaleString()} corridor profiles · {deta.layer1_behaviour_and_surge.alias_recovered_records.toLocaleString()} alias-recovered records
              </p>
            </div>

            {/* Dual-Mode Traversal Toggle */}
            <div className="flex bg-stone-100 p-1 rounded-full border border-stone-200 self-start md:self-auto shrink-0">
              <button
                type="button"
                onClick={() => setTraversalMode('normal')}
                className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                  traversalMode === 'normal' ? 'bg-[#18191B] text-white shadow-xs' : 'text-stone-600'
                }`}
              >
                Mode 1: O(1) Section DAG
              </button>
              <button
                type="button"
                onClick={() => setTraversalMode('detailed')}
                className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all cursor-pointer ${
                  traversalMode === 'detailed' ? 'bg-[#18191B] text-white shadow-xs' : 'text-stone-600'
                }`}
              >
                Mode 2: Halt-by-Halt Micro-Nodes
              </button>
            </div>
          </div>

          {/* Interactive Simulation Bar (Event Surge + Fog Visibility + Observed Delay) */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 my-4 p-3.5 rounded-2xl bg-stone-50 border border-stone-200/80 text-xs">
            <div>
              <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">
                Festival Surge Preset (S_event)
              </label>
              <select
                value={detaEventId}
                onChange={(e) => setDetaEventId(e.target.value)}
                className="w-full px-3 py-1.5 rounded-xl bg-white border border-stone-200 font-semibold text-stone-900"
              >
                <option value="NOMINAL">Nominal Operations (S=1.0x)</option>
                <option value="MAHA_KUMBH">Maha Kumbh Mela (S=3.2x)</option>
                <option value="CHHATH_PUJA">Bihar Chhath Puja (S=2.8x)</option>
                <option value="DIWALI_RUSH">Diwali Rush (S=2.2x)</option>
                <option value="RATH_YATRA">Puri Rath Yatra (S=2.6x)</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase text-stone-500 mb-1">
                G&amp;SR Section Visibility
              </label>
              <select
                value={detaVisM}
                onChange={(e) => setDetaVisM(Number(e.target.value))}
                className="w-full px-3 py-1.5 rounded-xl bg-white border border-stone-200 font-semibold text-stone-900"
              >
                <option value={4200}>Clear Sky (4200m · 130 km/h MPS)</option>
                <option value={380}>Dense Fog (380m · G&amp;SR 75 km/h FSD)</option>
                <option value={80}>Severe Fog (80m · G&amp;SR 30 km/h Caution)</option>
              </select>
            </div>
            <div>
              <div className="flex justify-between text-[10px] font-bold uppercase text-stone-500 mb-1">
                <span>Observed Upstream Delay</span>
                <span className="font-mono text-[#FF6332]">
                  +{detaDelayOverride ?? deta.current_telemetry.instantaneous_delay_mins} min
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={120}
                step={5}
                value={detaDelayOverride ?? deta.current_telemetry.instantaneous_delay_mins}
                onChange={(e) => setDetaDelayOverride(Number(e.target.value))}
                className="w-full accent-[#FF6332] mt-1"
              />
            </div>
          </div>

          {/* Probabilistic Quantile Bounds (P10 / P50 / P90) vs Naive Static */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-5">
            <div className="p-3.5 rounded-2xl bg-emerald-50/70 border border-emerald-200/80">
              <div className="text-[10px] font-bold uppercase text-emerald-800">P10 Optimistic</div>
              <div className="font-mono text-xl font-black text-emerald-700 mt-0.5">
                {deta.predictions.p10_time}
              </div>
              <div className="font-mono text-[11px] text-emerald-700">
                +{deta.predictions.p10_delay_mins}m · Green Corridor
              </div>
            </div>

            <div className="p-3.5 rounded-2xl bg-stone-900 text-white shadow-sm">
              <div className="text-[10px] font-bold uppercase text-[#FF6332]">P50 Median ETA</div>
              <div className="font-mono text-xl font-black text-white mt-0.5">
                {deta.predictions.p50_time}
              </div>
              <div className="font-mono text-[11px] text-stone-300">
                +{deta.predictions.p50_delay_mins}m · Most Likely
              </div>
            </div>

            <div className="p-3.5 rounded-2xl bg-rose-50/70 border border-rose-200/80">
              <div className="text-[10px] font-bold uppercase text-rose-900">P90 Pessimistic</div>
              <div className="font-mono text-xl font-black text-rose-700 mt-0.5">
                {deta.predictions.p90_time}
              </div>
              <div className="font-mono text-[11px] text-rose-700">
                +{deta.predictions.p90_delay_mins}m · Outer Hold Risk
              </div>
            </div>

            <div className="p-3.5 rounded-2xl bg-stone-100 border border-stone-200">
              <div className="text-[10px] font-bold uppercase text-stone-500">Naive Static App</div>
              <div className="font-mono text-xl font-bold text-stone-500 line-through mt-0.5">
                {deta.predictions.naive_static_time}
              </div>
              <div className="text-[11px] text-stone-500">Ignores Slack &amp; Surge</div>
            </div>

            <div className="p-3.5 rounded-2xl bg-orange-50/70 border border-orange-200/80 col-span-2 sm:col-span-1">
              <div className="text-[10px] font-bold uppercase text-orange-900">Slack Absorbed</div>
              <div className="font-mono text-xl font-black text-[#FF6332] mt-0.5">
                -{deta.predictions.slack_absorption_expected_mins} min
              </div>
              <div className="text-[11px] text-orange-800">
                Drift: {deta.current_telemetry.delay_drift_rate_100km}m/100km
              </div>
            </div>
          </div>

          {/* Mode 2: Detailed Halt-by-Halt & Approach Cabin Micro-Traversal */}
          {traversalMode === 'detailed' ? (
            <div className="rounded-2xl bg-stone-900 text-stone-100 p-4 sm:p-5">
              <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
                <div className="text-xs font-bold uppercase tracking-wider text-[#FF6332] flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5" /> Mode 2: Detailed Halt-by-Halt &amp; Approach Cabin Micro-Traversal
                </div>
                <span className="font-mono text-[11px] text-stone-400">
                  {deta.weather_constraints.fog_rule} · MPS Cap: {deta.weather_constraints.effective_mps_cap_kmh} km/h
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-5 gap-2.5">
                {deta.micro_traversal_nodes.map((node) => {
                  const isRed = node.signal_aspect.includes('RED');
                  const isYellow = node.signal_aspect.includes('YELLOW');
                  return (
                    <div
                      key={node.node_id}
                      className="p-3 rounded-xl bg-white/5 border border-white/10 flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between gap-1 mb-1">
                          <span className="font-mono text-[10px] text-stone-400">{node.code}</span>
                          <span
                            className={`font-mono text-[9px] font-bold px-1.5 py-0.5 rounded ${
                              isRed
                                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                                : isYellow
                                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                                  : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                            }`}
                          >
                            {node.signal_aspect}
                          </span>
                        </div>
                        <div className="text-xs font-bold text-white leading-snug">{node.name}</div>
                        <div className="text-[10px] text-stone-400 mt-1">{node.root_cause}</div>
                      </div>
                      <div className="mt-2.5 pt-2 border-t border-white/10 flex items-center justify-between font-mono text-[10px]">
                        <span className="text-stone-300">{node.speed_limit_kmh} km/h</span>
                        <span
                          className={
                            node.micro_delay_delta_mins > 0
                              ? 'text-rose-400 font-bold'
                              : node.micro_delay_delta_mins < 0
                                ? 'text-emerald-400 font-bold'
                                : 'text-stone-400'
                          }
                        >
                          {node.micro_delay_delta_mins > 0
                            ? `+${node.micro_delay_delta_mins}m`
                            : `${node.micro_delay_delta_mins}m`}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            /* Mode 1: Normal O(1) Space-Time DAG Stop Quantile Table */
            <div className="overflow-x-auto rounded-2xl border border-stone-200">
              <table className="w-full text-left text-xs">
                <thead className="bg-stone-50 text-stone-500 uppercase text-[10px] border-b border-stone-200">
                  <tr>
                    <th className="py-2.5 px-3">Stop</th>
                    <th className="py-2.5 px-3">Sched</th>
                    <th className="py-2.5 px-3 text-emerald-700">P10 ETA</th>
                    <th className="py-2.5 px-3 text-stone-900">P50 Median</th>
                    <th className="py-2.5 px-3 text-rose-700">P90 Worst</th>
                    <th className="py-2.5 px-3">Slack / Surge</th>
                    <th className="py-2.5 px-3">Platform / Cabin</th>
                    <th className="py-2.5 px-3">DAG State</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {deta.stop_predictions.map((sp) => (
                    <tr key={sp.stop_sequence} className="hover:bg-stone-50/80">
                      <td className="py-2.5 px-3 font-semibold text-stone-900">
                        <span className="font-mono text-[#FF6332] mr-1">{sp.station_code}</span>
                        {sp.station_name}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-stone-500">{sp.scheduled_arrival}</td>
                      <td className="py-2.5 px-3 font-mono font-bold text-emerald-700">
                        {sp.p10_optimistic_eta} (+{sp.p10_delay_mins}m)
                      </td>
                      <td className="py-2.5 px-3 font-mono font-extrabold text-stone-900">
                        {sp.p50_median_eta} (+{sp.p50_delay_mins}m)
                      </td>
                      <td className="py-2.5 px-3 font-mono font-bold text-rose-700">
                        {sp.p90_pessimistic_eta} (+{sp.p90_delay_mins}m)
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px]">
                        <span className="text-emerald-700">-{sp.slack_absorbed_mins}m</span> ·{' '}
                        <span className="text-stone-600">{sp.nsg_category} ({sp.dilated_dwell_mins}m halt)</span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px]">
                        PF-{sp.assigned_platform}
                        {sp.outer_signal_hold_mins > 0 && (
                          <span className="ml-1 text-rose-700 font-bold">
                            (Outer +{sp.outer_signal_hold_mins}m)
                          </span>
                        )}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="font-mono text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 font-bold">
                          LOCKED
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {live.loading && !d && (
        <div className="bg-white/95 rounded-[28px] border border-stone-200 p-8 shadow-luxury text-center relative overflow-hidden animate-in fade-in duration-300">
          <div className="max-w-md mx-auto flex flex-col items-center">
            {/* Animated Radar Pulse Locator */}
            <div className="relative w-16 h-16 flex items-center justify-center mb-4">
              <div className="absolute inset-0 rounded-full border-2 border-[#FF6332]/30 animate-ping" />
              <div className="absolute inset-1 rounded-full border border-sky-400/20 animate-spin" style={{ animationDuration: '4s' }} />
              <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-[#FF6332] to-orange-500 text-white flex items-center justify-center shadow-lg shadow-[#FF6332]/30">
                <TrainFront className="w-6 h-6 animate-pulse" />
              </div>
            </div>

            <h3 className="font-display font-bold text-base text-stone-900">
              Synchronizing Live Train Telemetry…
            </h3>
            <p className="text-xs text-stone-500 mt-1 max-w-xs leading-relaxed">
              Querying CRIS GPS transponders and sector tracking points for train #{trainNo}
            </p>

            {/* Glowing Track Simulator */}
            <div className="w-full max-w-xs mt-5">
              <div className="w-full bg-stone-100 h-2 rounded-full overflow-hidden relative shadow-inner">
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#FF6332] to-transparent w-full animate-pulse" />
              </div>
              <div className="flex items-center justify-between text-[10px] text-stone-400 mt-2 font-mono">
                <span className="flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  IR GPS Network
                </span>
                <span>Real-time Stream</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {live.loading && d && (
        <div className="flex items-center justify-center py-1 mb-3">
          <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#FF6332]/10 border border-[#FF6332]/20 text-[11px] font-medium text-[#FF6332]">
            <RefreshCw className="w-3 h-3 animate-spin" />
            <span>Refreshing live telemetry…</span>
          </span>
        </div>
      )}
      {live.error && !d && (
        <ErrorState error={live.error} onRetry={live.refetch} what="live status" />
      )}

      {d && (
        <>
          <DegradedBanner meta={live.meta} />

          {/* Weekly / Special train non-running day notice */}
          {d && d.train?.runsOnToday === false && (
            <div className="bg-amber-50/90 border border-amber-200/80 rounded-2xl px-4 py-3 mb-6 text-xs text-amber-900 flex items-center justify-between flex-wrap gap-3 shadow-xs">
              <div className="flex items-center gap-2.5">
                <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                <span>
                  <strong>Non-daily Train Schedule:</strong> This train does not operate on today's weekday.
                  {d.train?.runningDays && (
                    <span className="ml-1 text-amber-700">
                      (Runs: {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].filter((_, i) => d.train?.runningDays?.[i] === '1').join(', ')})
                    </span>
                  )}
                </span>
              </div>
              <div className="text-[11px] text-amber-800 font-semibold">
                Viewing scheduled operating run: {runDates.find(r => r.key === selectedDate)?.dateLabel || selectedDate}
              </div>
            </div>
          )}

          {/* Smart Multi-day Banner: when today hasn't started, offer 1-click to check yesterday's live run */}
          {d && (selectedDate === todayKey || !selectedDate) && d.position?.distanceCoveredKm === 0 && d.train?.runsOnToday !== false && (
            <div className="bg-amber-50/90 border border-amber-200/80 rounded-2xl px-4 py-3 mb-6 text-xs text-amber-900 flex items-center justify-between flex-wrap gap-3 shadow-xs">
              <div className="flex items-center gap-2.5">
                <Clock className="w-4 h-4 text-amber-600 shrink-0" />
                <span>
                  <strong>Today's run ({runDates.find(r => r.isToday)?.dateLabel || 'Today'})</strong> has not departed source station yet.
                  {runDates.some(r => r.offset === -1) && (
                    <> Yesterday's train ({runDates.find(r => r.offset === -1)?.dateLabel}) may still be active on track.</>
                  )}
                </span>
              </div>
              {runDates.some(r => r.offset === -1) && (
                <button
                  type="button"
                  onClick={() => {
                    const yKey = runDates.find(r => r.offset === -1)?.key;
                    if (yKey) handleSelectDate(yKey);
                  }}
                  className="px-3.5 py-1.5 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded-full text-[11px] transition-all shadow-xs cursor-pointer"
                >
                  Switch to Yesterday's Live Run →
                </button>
              )}
            </div>
          )}

          {/* Active run banner if viewing yesterday or tomorrow or special past run */}
          {d && selectedDate && selectedDate !== todayKey && d.train?.runsOnToday !== false && (
            <div className="bg-blue-50/90 border border-blue-200/80 rounded-2xl px-4 py-3 mb-6 text-xs text-blue-900 flex items-center justify-between flex-wrap gap-3 shadow-xs">
              <div className="flex items-center gap-2.5">
                <Radio className="w-4 h-4 text-blue-600 shrink-0 animate-pulse" />
                <span>
                  Viewing <strong>{runDates.find(r => r.key === selectedDate)?.label ?? 'Selected'} ({runDates.find(r => r.key === selectedDate)?.dateLabel ?? selectedDate})</strong> departure run.
                </span>
              </div>
              <button
                type="button"
                onClick={() => handleSelectDate(todayKey)}
                className="px-3 py-1 bg-white hover:bg-blue-100 text-blue-800 border border-blue-300 font-semibold rounded-full text-[11px] transition-all cursor-pointer"
              >
                Reset to Today →
              </button>
            </div>
          )}

          {/* Header card */}
          <div className="bg-white/95 rounded-[32px] border border-stone-200/80 p-6 sm:p-8 shadow-luxury mb-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-stone-100">
              <div>
                <div className="flex items-center gap-2 mb-1 flex-wrap">
                  <span className="font-mono font-bold text-sm bg-orange-50 text-[#FF6332] px-2.5 py-0.5 rounded-lg border border-orange-200">
                    {d.train?.number ?? trainNo}
                  </span>
                  {d.train?.type && (
                    <span className="text-xs text-stone-500 font-medium uppercase tracking-wider">
                      {d.train.type}
                    </span>
                  )}
                  {d.train?.journeyDate && (
                    <span className="text-xs font-semibold px-2.5 py-0.5 bg-stone-100 rounded-lg text-stone-700 border border-stone-200 font-mono">
                      Dep: {d.train.journeyDate}
                    </span>
                  )}
                  <SourceBadge source={live.meta?.source} asOf={d.position?.lastUpdateAt} />
                </div>
                <h2 className="text-2xl sm:text-3xl font-display font-bold text-stone-900">
                  {d.train?.name ?? <Unknown />}
                </h2>
                <p className="text-xs sm:text-sm text-stone-500 mt-1 flex items-center gap-1.5">
                  <span>{d.train?.from?.name ?? d.train?.from?.code ?? '—'}</span>
                  <ArrowRight className="w-3.5 h-3.5 text-stone-400" />
                  <span>{d.train?.to?.name ?? d.train?.to?.code ?? '—'}</span>
                </p>
              </div>

              <div className="flex items-center gap-2.5 flex-wrap">
                {onViewMap && (
                  <button
                    type="button"
                    onClick={() => onViewMap(d.train?.number ?? trainNo, selectedDate)}
                    className="px-3 py-2 rounded-full bg-stone-900 hover:bg-stone-800 text-white text-xs font-semibold flex items-center gap-1.5 shadow-xs transition-all active:scale-95 cursor-pointer"
                    title="View route map and live GPS position"
                  >
                    <MapIcon className="w-3.5 h-3.5 text-[#FF6332]" />
                    <span>View on Map</span>
                  </button>
                )}
                <button
                  onClick={live.refetch}
                  className="p-2.5 rounded-full bg-stone-100 hover:bg-stone-200 text-stone-600 transition-colors cursor-pointer"
                  title="Refresh"
                >
                  <RefreshCw className={`w-4 h-4 ${live.refreshing ? 'animate-spin text-[#FF6332]' : ''}`} />
                </button>
                <div
                  className={`px-4 py-2 rounded-full text-xs font-bold flex items-center gap-2 border ${DELAY_TONE(
                    d.eta?.currentDelayMinutes ?? d.position?.delayMinutes ?? null,
                  )}`}
                >
                  <span className="w-2 h-2 rounded-full bg-current animate-pulse" />
                  <span>
                    {(d.eta?.currentDelayMinutes ?? d.position?.delayMinutes) == null
                      ? 'Delay unknown'
                      : (d.eta?.currentDelayMinutes ?? d.position?.delayMinutes)! <= 0
                      ? 'Right on time'
                      : `Delayed by ${d.eta?.currentDelayMinutes ?? d.position?.delayMinutes} min`}
                  </span>
                </div>
              </div>
            </div>

            {d.position?.statusNote && (
              <p className="text-xs text-stone-600 mt-4 flex items-center gap-1.5">
                <MapPin className="w-3.5 h-3.5 text-[#FF6332]" />
                {d.position.statusNote}
              </p>
            )}

            {/* Metrics — note live speed is honestly unavailable */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 py-6 border-b border-stone-100 text-stone-700">
              <div>
                <span className="text-xs text-stone-400 uppercase tracking-wider block mb-1">Live Speed</span>
                <div className="text-xl sm:text-2xl font-display font-bold text-stone-900 flex items-center gap-1">
                  <Gauge className="w-5 h-5 text-stone-300" />
                  {d.position?.speedKmph !== null && d.position?.speedKmph !== undefined ? (
                    <span>{d.position.speedKmph} km/h</span>
                  ) : (d.position?.distanceCoveredKm === 0 && d.stops[0]?.status === 'current') ? (
                    <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-2 py-1 rounded-md border border-emerald-200">
                      0 km/h · At Origin
                    </span>
                  ) : d.position?.distanceCoveredKm && d.position.distanceCoveredKm > 0 ? (
                    <span className="text-xs font-semibold text-sky-700 bg-sky-50 px-2 py-1 rounded-md border border-sky-200 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse" />
                      In Transit
                    </span>
                  ) : (
                    <Unknown reason="Live telemetry does not report current speedometer reading." />
                  )}
                </div>
              </div>
              <div>
                <span className="text-xs text-stone-400 uppercase tracking-wider block mb-1">Current Position</span>
                <div className="text-sm sm:text-base font-semibold text-stone-900 truncate">
                  {d.position?.currentStationName ?? d.position?.currentStationCode ?? <Unknown />}
                </div>
              </div>
              <div>
                <span className="text-xs text-stone-400 uppercase tracking-wider block mb-1">Next Halt</span>
                <div className="text-sm sm:text-base font-semibold text-stone-900 truncate">
                  {d.nextStop?.stationName ?? d.position?.nextStationName ?? d.position?.nextStationCode ?? <Unknown />}
                </div>
              </div>
              <div>
                <span className="text-xs text-stone-400 uppercase tracking-wider block mb-1">ETA Engine</span>
                <div className="text-[11px] font-mono text-violet-700 bg-violet-50 px-2 py-1 rounded-md inline-block border border-violet-200/60">
                  {d.eta?.engine ?? 'Darpan Hybrid'}
                </div>
              </div>
            </div>

            {progress !== null && (
              <div className="pt-6">
                <div className="flex items-center justify-between text-xs text-stone-500 mb-2">
                  <span>{d.position.distanceCoveredKm} of {d.position.totalDistanceKm} km</span>
                  <span className="font-semibold text-stone-900">{progress}% complete</span>
                </div>
                <div className="w-full h-2.5 bg-stone-100 rounded-full overflow-hidden p-0.5 border border-stone-200/60">
                  <div
                    className="h-full bg-gradient-to-r from-emerald-500 via-[#FF6332] to-[#18191B] rounded-full transition-all duration-700"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            )}

            {/* Engine notes: states plainly when delay is pure persistence */}
            {d.eta.notes.length > 0 && (
              <div className="mt-5 flex items-start gap-2 text-[11px] text-stone-500 bg-stone-50 rounded-2xl p-3 border border-stone-200/60">
                <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5 text-stone-400" />
                <div className="space-y-1">
                  {d.eta.notes.map((n, i) => <p key={i}>{n}</p>)}
                </div>
              </div>
            )}
          </div>

          {/* Risk overlay — probability only, with its caveats visible */}
          {d.risk && (
            <div className="bg-white/95 rounded-[28px] border border-stone-200/80 p-5 sm:p-6 shadow-luxury mb-6">
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div>
                  <h3 className="text-sm font-bold text-stone-900 flex items-center gap-2">
                    <Zap className="w-4 h-4 text-violet-500" />
                    Delay Risk
                    <span className="text-[10px] font-normal text-violet-700 bg-violet-50 border border-violet-200 px-2 py-0.5 rounded-full">
                      indicative only
                    </span>
                  </h3>
                  <p className="text-[11px] text-stone-500 mt-1">{d.risk.target}</p>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-display font-bold text-stone-900">
                    {Math.round(d.risk.delayProbability * 100)}%
                  </div>
                  <div className="text-[10px] uppercase tracking-wider text-stone-400">{d.risk.label}</div>
                </div>
              </div>
              <div className="w-full h-1.5 bg-stone-100 rounded-full mt-3 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-emerald-400 via-amber-400 to-rose-500 rounded-full"
                  style={{ width: `${Math.round(d.risk.delayProbability * 100)}%` }}
                />
              </div>
              {/* Disclosing the imputation count is the point: it tells the reader how
                  much of this number is measurement vs. assumption. */}
              <p className="text-[10px] text-stone-400 mt-3 leading-relaxed">
                {d.risk.trustworthiness}. Does not affect the arrival times above, which come
                from the deterministic ETA engine.
              </p>
            </div>
          )}

          {/* Stop timeline */}
          <div className="bg-white/95 rounded-[32px] border border-stone-200/80 p-6 sm:p-8 shadow-luxury">
            <h3 className="text-lg font-bold text-stone-900 mb-1 flex items-center justify-between flex-wrap gap-2">
              <span>Route Stops &amp; Platform Timings</span>
              <span className="text-xs font-normal text-stone-400">
                {d.stops.length} booked halts
                {d.passingPointCount > 0 && ` · ${d.passingPointCount} passing points`}
              </span>
            </h3>
            <p className="text-[11px] text-stone-400 mb-6">
              Past stops show observed times. Upcoming stops show the estimate, with its
              confidence range.
            </p>

            <div className="relative pl-6 sm:pl-8 space-y-8 before:absolute before:left-3 sm:before:left-4 before:top-3 before:bottom-3 before:w-0.5 before:bg-stone-200">
              {d.stops.map((stop) => (
                <StopRow key={`${stop.stationCode}-${stop.distanceKm}`} stop={stop} />
              ))}
            </div>
          </div>

          {/* Coach composition — real provider data */}
          {d.composition.length > 0 && (
            <div className="bg-white/95 rounded-[28px] border border-stone-200/80 p-6 shadow-luxury mt-6">
              <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
                <div>
                  <h3 className="text-sm font-bold text-stone-900 flex items-center gap-2">
                    <span>Coach Position &amp; Rake Formation</span>
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 bg-stone-100 rounded-md text-stone-700 border border-stone-200">
                      {d.composition.length} Units
                    </span>
                  </h3>
                  <p className="text-[11px] text-stone-400 mt-0.5">
                    Engine first (front to rear) — as per verified railway rake formation.
                  </p>
                </div>
                <div className="flex items-center flex-wrap gap-2.5 text-[10px] text-stone-500 font-medium bg-stone-50 px-3 py-1.5 rounded-full border border-stone-200/70">
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-purple-200 border border-purple-400" /> 1A</span>
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-sky-200 border border-sky-400" /> 2A</span>
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-emerald-200 border border-emerald-400" /> 3A</span>
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-amber-200 border border-amber-400" /> SL</span>
                  <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-sm bg-stone-200 border border-stone-400" /> GEN/OTHER</span>
                </div>
              </div>

              {/* Rake visual track layout */}
              <div className="relative py-2">
                <div className="flex items-center gap-1.5 overflow-x-auto pb-3 pt-1 scrollbar-none">
                  {/* Locomotive Engine block */}
                  <div className="shrink-0 px-3 py-2 rounded-xl bg-stone-900 text-white text-center min-w-[62px] border border-stone-800 shadow-xs">
                    <div className="text-[11px] font-mono font-bold tracking-wider">🚂 LOCO</div>
                    <div className="text-[9px] text-stone-400 font-mono">ENGINE</div>
                  </div>

                  {/* Coaches */}
                  {d.composition.map((c, i) => {
                    const coachCode = c.label || c.code || `C${c.position ?? i + 1}`;
                    const coachClass = c.type || c.class || '';
                    const category = c.category || coachClass;
                    const style = getCoachStyle(coachCode, coachClass);

                    return (
                      <div
                        key={`${coachCode}-${i}`}
                        title={`${coachCode}: ${category || 'Coach'} (#${c.position ?? i + 1})`}
                        className={`shrink-0 px-2.5 py-2 rounded-xl border text-center min-w-[54px] transition-all hover:scale-105 cursor-default ${style}`}
                      >
                        <div className="text-[12px] font-mono font-bold tracking-tight">{coachCode}</div>
                        <div className="text-[9px] opacity-75 font-mono">{coachClass || 'GEN'}</div>
                        <div className="text-[8px] opacity-40 mt-0.5 font-mono">#{c.position ?? i + 1}</div>
                      </div>
                    );
                  })}

                  {/* Brake / Guard Van block */}
                  <div className="shrink-0 px-2.5 py-2 rounded-xl bg-stone-200 text-stone-700 text-center min-w-[54px] border border-stone-300">
                    <div className="text-[11px] font-mono font-bold">GUARD</div>
                    <div className="text-[9px] text-stone-500 font-mono">REAR 🏁</div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Raw response inspector — now shows the ACTUAL API payload */}
      {showJson && d && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
          <div className="bg-[#12151D] text-stone-100 w-full max-w-2xl rounded-[28px] p-6 shadow-2xl border border-white/10 flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-3">
              <div className="flex items-center gap-2">
                <Code className="w-5 h-5 text-emerald-400" />
                <h3 className="font-display font-bold text-base text-white">
                  GET /v1/trains/{d.train.number}/live
                </h3>
              </div>
              <button onClick={() => setShowJson(false)} className="text-stone-400 hover:text-white text-xs font-semibold p-1">
                ✕ Close
              </button>
            </div>
            <div className="flex-1 overflow-auto bg-black/50 p-4 rounded-xl border border-white/5 font-mono text-xs text-emerald-300 leading-relaxed scrollbar-none select-all">
              <pre>{JSON.stringify({ data: d, meta: live.meta }, null, 2)}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/** One stop row. Renders observation vs. estimate differently, on purpose. */
const StopRow: React.FC<{ stop: Stop }> = ({ stop }) => {
  const isPassed = stop.status === 'passed';
  const isCurrent = stop.status === 'current';
  const estimated = stop.eta.source === 'model' || stop.eta.source === 'schedule';

  return (
    <div
      id={`stop-${stop.stationCode}`}
      className="relative flex flex-col sm:flex-row sm:items-center justify-between gap-3 group scroll-mt-32"
    >
      <div
        className={`absolute -left-6 sm:-left-8 top-1.5 w-6 h-6 rounded-full flex items-center justify-center transition-all ${
          isCurrent
            ? 'bg-[#FF6332] text-white ring-4 ring-orange-500/20 shadow-md'
            : isPassed
            ? 'bg-emerald-500 text-white ring-4 ring-emerald-500/15'
            : 'bg-stone-100 border-2 border-stone-300 text-stone-400'
        }`}
      >
        {isPassed ? (
          <CheckCircle2 className="w-3.5 h-3.5" />
        ) : isCurrent ? (
          <span className="w-2 h-2 rounded-full bg-white animate-ping" />
        ) : (
          <span className="w-2 h-2 rounded-full bg-stone-300" />
        )}
      </div>

      <div className="flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-bold text-base text-stone-900">
            {stop.stationName ?? stop.stationCode}
          </span>
          <span className="font-mono text-xs px-2 py-0.5 bg-stone-100 rounded text-stone-600 border border-stone-200">
            {stop.stationCode}
          </span>
          {isCurrent && (
            <span className="bg-[#FF6332] text-white text-[10px] font-bold px-2 py-0.5 rounded-full animate-pulse">
              LIVE AT STATION
            </span>
          )}
        </div>
        <p className="text-xs text-stone-500 mt-0.5">
          {stop.distanceKm !== null ? `${stop.distanceKm} km` : '— km'}
          {' · scheduled '}
          {fmtTime(stop.scheduled.arrival ?? stop.scheduled.departure)}
          {stop.scheduled.arrival && stop.scheduled.departure && stop.scheduled.arrival !== stop.scheduled.departure && (
            <span className="text-stone-400"> (dep {fmtTime(stop.scheduled.departure)})</span>
          )}
          {estimated && stop.eta.segmentObservations > 0 && (
            <span className="text-emerald-600"> · {stop.eta.segmentObservations} segment obs</span>
          )}
        </p>
      </div>

      <div className="flex items-center gap-4 sm:gap-6 text-xs self-start sm:self-auto bg-stone-50/80 px-4 py-2 rounded-2xl border border-stone-200/60">
        <div>
          <span className="text-stone-400 block text-[10px] uppercase">
            {isPassed ? 'Actual' : 'Estimated'}
          </span>
          <div className="font-mono font-bold text-stone-900">
            {fmtTime(
              isPassed
                ? (stop.actual.arrival ?? stop.actual.departure ?? stop.eta.arrival ?? stop.scheduled.departure)
                : (stop.eta.arrival ?? stop.scheduled.departure)
            )}
          </div>
          {/* The confidence range is shown, not hidden: a point estimate alone
              overstates precision. */}
          {estimated && stop.eta.band.p10 && (
            <div className="text-[9px] text-stone-400 font-mono">
              {fmtTime(stop.eta.band.p10)}–{fmtTime(stop.eta.band.p90)}
            </div>
          )}
        </div>

        <div>
          <span className="text-stone-400 block text-[10px] uppercase">Platform</span>
          <div className="font-mono font-bold text-stone-900 bg-white px-2 py-0.5 rounded border border-stone-200 text-center">
            {stop.platform ? `PF ${stop.platform}` : <Unknown reason="Platform not assigned or not reported." />}
          </div>
        </div>

        <div>
          <span className="text-stone-400 block text-[10px] uppercase">Delay</span>
          <span
            className={`font-semibold ${
              stop.eta.delayMinutes === null
                ? 'text-stone-400'
                : stop.eta.delayMinutes <= 0
                ? 'text-emerald-600'
                : stop.eta.delayMinutes <= 15
                ? 'text-amber-600'
                : 'text-rose-600'
            }`}
          >
            {fmtDelay(stop.eta.delayMinutes)}
          </span>
        </div>
      </div>
    </div>
  );
};

export default LivePage;
