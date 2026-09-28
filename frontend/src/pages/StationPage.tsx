/**
 * Live Station Display Board & SIH-DETA Platform IntervalTree / Surge Dilation Inspector.
 *
 * Combines:
 * 1. Real-time Station PIDS Arrival/Departure Board across all 8,990 stations (GET /v1/stations/{code}/board)
 * 2. SIH-DETA Layer 2 Platform Slot Mutual-Exclusion IntervalTree Allocator & Outer Home Signal Hold
 *    Calculator (GET /v1/deta/stations/{code}/platforms)
 * 3. Station NSG (1–6) Categorization & Festival Surge Dwell Inflation Equation (Maha Kumbh, Chhath Puja, Diwali)
 */

import React, { useState } from 'react';
import {
  Building2,
  Search,
  RefreshCw,
  ArrowUpRight,
  ArrowDownLeft,
  XCircle,
  Layers,
  AlertTriangle,
  CheckCircle2,
  Sparkles,
  Lock,
  Radio,
} from 'lucide-react';
import { api, fmtDelay, fmtTime, type BoardTrain } from '../lib/api';
import { useDebounced, useQuery } from '../hooks/useApi';
import { DegradedBanner, ErrorState, LoadingCard, SourceBadge, Unknown } from '../components/Provenance';

const WINDOWS = [2, 4, 8] as const;

const FEATURED_HUBS = [
  { code: 'CNB', name: 'Kanpur Central Jn', tag: 'NSG-1 Bottleneck' },
  { code: 'PRYJ', name: 'Prayagraj Jn (ALD)', tag: 'Maha Kumbh Hub' },
  { code: 'DDU', name: 'Pt. DD Upadhyaya Jn (MGS)', tag: 'Grand Chord Throat' },
  { code: 'NDLS', name: 'New Delhi', tag: '16-Platform Terminal' },
  { code: 'HWH', name: 'Howrah Jn', tag: '23-Platform Mega Hub' },
  { code: 'VGLJ', name: 'Virangana Lakshmibai (JHS)', tag: 'Central Trunk' },
];

const SURGE_EVENTS = [
  { id: 'NOMINAL', label: 'Normal Operations (S=1.0x)' },
  { id: 'MAHA_KUMBH', label: 'Maha Kumbh Mela Surge (S=3.2x)' },
  { id: 'CHHATH_PUJA', label: 'Bihar Chhath Puja Rush (S=2.8x)' },
  { id: 'DIWALI_RUSH', label: 'Pan-India Diwali Exodus (S=2.2x)' },
  { id: 'RATH_YATRA', label: 'Puri Rath Yatra Surge (S=2.6x)' },
];

export const StationPage: React.FC = () => {
  const [selected, setSelected] = useState<{ code: string; name: string } | null>({
    code: 'CNB',
    name: 'Kanpur Central Jn',
  });
  const [search, setSearch] = useState('');
  const [window, setWindow] = useState<2 | 4 | 8>(2);
  const [mode, setMode] = useState<'dep' | 'arr'>('dep');
  const [activeTab, setActiveTab] = useState<'intervals' | 'live_board'>('intervals');
  const [eventId, setEventId] = useState<string>('MAHA_KUMBH');

  const debounced = useDebounced(search, 250);

  const stations = useQuery(
    debounced.trim().length >= 2 ? (signal) => api.searchStations(debounced.trim(), signal) : null,
    [debounced],
  );

  const board = useQuery(
    selected && activeTab === 'live_board'
      ? (signal) => api.stationBoard(selected.code, window, mode, signal)
      : null,
    [selected?.code, window, mode, activeTab],
    { pollMs: 90_000 },
  );

  const platformData = useQuery(
    selected ? (signal) => api.detaStationPlatforms(selected.code, eventId, 840, signal) : null,
    [selected?.code, eventId],
  );

  const trains = board.data?.trains ?? [];
  const pf = platformData.data;

  return (
    <div className="max-w-5xl mx-auto px-4 pt-6 sm:pt-10 pb-36">
      <div className="text-center mb-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 text-amber-800 text-xs font-semibold mb-3 border border-amber-200/70">
          <Building2 className="w-3.5 h-3.5" />
          <span>SIH-DETA Station PIDS &amp; Platform IntervalTree Allocator</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-display font-bold text-stone-900 tracking-tight">
          Station Master PIDS &amp; Platform Scheduling
        </h1>
        <p className="text-xs sm:text-sm text-stone-500 mt-1">
          Mutual-exclusion platform occupancy intervals, approach cabin outer-signal holds, and NSG festival surge dwell dilation across 8,990 stations.
        </p>
      </div>

      {/* Station autocomplete + Featured Junction Pills */}
      <div className="bg-white/95 p-4 sm:p-5 rounded-[28px] border border-stone-200 shadow-luxury mb-6">
        <div className="relative">
          <Search className="w-4 h-4 text-stone-400 absolute left-4 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search any of 8,990 stations — name or code (e.g. Prayagraj, PRYJ, ALD, DDU, NDLS)"
            className="w-full pl-11 pr-4 py-3 bg-stone-50 hover:bg-stone-100/70 focus:bg-white rounded-full text-sm text-stone-900 border border-stone-200/80 focus:border-[#FF6332] focus:ring-4 focus:ring-orange-500/10 transition-all focus:outline-none"
          />
        </div>

        {/* Quick-Pick Junction Hubs */}
        <div className="mt-3 flex items-center gap-2 flex-wrap">
          <span className="text-[11px] font-semibold text-stone-400 uppercase tracking-wider mr-1">
            Major Junctions:
          </span>
          {FEATURED_HUBS.map((h) => {
            const isSel = selected?.code === h.code;
            return (
              <button
                key={h.code}
                onClick={() => {
                  setSelected({ code: h.code, name: h.name });
                  setSearch('');
                }}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all flex items-center gap-1.5 ${
                  isSel
                    ? 'bg-[#18191B] text-white border-stone-900 shadow-xs'
                    : 'bg-stone-50 hover:bg-stone-100 text-stone-700 border-stone-200/80'
                }`}
              >
                <span className="font-mono font-bold text-[#FF6332]">{h.code}</span>
                <span>{h.name.split(' ')[0]}</span>
              </button>
            );
          })}
        </div>

        {stations.data && stations.data.length > 0 && (
          <div className="mt-3 pt-3 border-t border-stone-100 grid sm:grid-cols-2 gap-2">
            {stations.data.map((s) => (
              <button
                key={s.code}
                onClick={() => {
                  setSelected({ code: s.code, name: s.name });
                  setSearch('');
                }}
                className="flex items-center justify-between px-3.5 py-2.5 rounded-2xl bg-stone-50 hover:bg-stone-100 border border-stone-200/60 text-left transition-all"
              >
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-stone-900 truncate">{s.name}</div>
                  <div className="text-[11px] text-stone-500">
                    {s.state ?? '—'}
                    {s.zone ? ` · ${s.zone}` : ''}
                  </div>
                </div>
                <span className="font-mono text-xs px-2 py-0.5 bg-white rounded border border-stone-200 text-stone-600 shrink-0 ml-2">
                  {s.code}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {selected && (
        <>
          {/* Mode Switcher Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
            <div>
              <h2 className="text-xl font-display font-bold text-stone-900 flex items-center gap-2 flex-wrap">
                {pf?.station_name ?? selected.name}
                <span className="font-mono text-xs px-2.5 py-0.5 bg-stone-900 text-white rounded-full">
                  {pf?.station_code ?? selected.code}
                </span>
                {pf?.surge_profile && (
                  <span className="font-mono text-xs px-2.5 py-0.5 bg-orange-50 text-[#FF6332] border border-orange-200 rounded-full font-bold">
                    {pf.surge_profile.nsg_category} · {pf.platform_count} Platforms
                  </span>
                )}
              </h2>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex bg-stone-100 p-1 rounded-full border border-stone-200">
                <button
                  onClick={() => setActiveTab('intervals')}
                  className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all flex items-center gap-1.5 ${
                    activeTab === 'intervals' ? 'bg-[#18191B] text-white shadow-xs' : 'text-stone-600'
                  }`}
                >
                  <Layers className="w-3.5 h-3.5 text-[#FF6332]" />
                  Platform IntervalTree &amp; Surge
                </button>
                <button
                  onClick={() => setActiveTab('live_board')}
                  className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all flex items-center gap-1.5 ${
                    activeTab === 'live_board' ? 'bg-[#18191B] text-white shadow-xs' : 'text-stone-600'
                  }`}
                >
                  <Radio className="w-3.5 h-3.5 text-emerald-500" />
                  Live Provider Board
                </button>
              </div>
            </div>
          </div>

          {activeTab === 'intervals' && pf && (
            <div className="space-y-6">
              {/* 1. Station NSG & Festival Surge Dwell Dilation Card */}
              <div className="bg-white/95 rounded-[28px] border border-stone-200 p-5 sm:p-6 shadow-luxury">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 pb-4 border-b border-stone-100">
                  <div>
                    <div className="text-[11px] font-bold uppercase tracking-wider text-[#FF6332] flex items-center gap-1">
                      <Sparkles className="w-3.5 h-3.5" /> Station NSG Classification &amp; Crowd Surge Dwell Dilation
                    </div>
                    <h3 className="text-lg font-display font-bold text-stone-900 mt-0.5">
                      {pf.surge_profile.nsg_category} ({pf.surge_profile.nsg_details.passengers_criterion} · {pf.surge_profile.nsg_details.revenue_criterion})
                    </h3>
                  </div>

                  <div className="flex items-center gap-2">
                    <select
                      value={eventId}
                      onChange={(e) => setEventId(e.target.value)}
                      className="px-3.5 py-2 rounded-full bg-stone-900 text-white text-xs font-semibold border border-stone-800 focus:outline-none cursor-pointer"
                    >
                      {SURGE_EVENTS.map((ev) => (
                        <option key={ev.id} value={ev.id}>
                          {ev.label}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={platformData.refetch}
                      className="p-2 rounded-full bg-stone-100 hover:bg-stone-200 text-stone-700"
                    >
                      <RefreshCw className={`w-4 h-4 ${platformData.refreshing ? 'animate-spin text-[#FF6332]' : ''}`} />
                    </button>
                  </div>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                  <div className="p-3.5 rounded-2xl bg-stone-50 border border-stone-200/80">
                    <div className="text-[10px] uppercase font-semibold text-stone-500">Scheduled Halt</div>
                    <div className="font-mono text-xl font-extrabold text-stone-900 mt-0.5">
                      {pf.surge_profile.scheduled_dwell_mins} min
                    </div>
                    <div className="text-[11px] text-stone-500">Published WTT Dwell</div>
                  </div>
                  <div className="p-3.5 rounded-2xl bg-orange-50/70 border border-orange-200/80">
                    <div className="text-[10px] uppercase font-semibold text-orange-900">Dilated Surge Halt</div>
                    <div className="font-mono text-xl font-extrabold text-[#FF6332] mt-0.5">
                      {pf.surge_profile.dilated_dwell_mins} min (+{pf.surge_profile.dwell_inflation_added_mins}m)
                    </div>
                    <div className="text-[11px] text-orange-800">
                      S_event = {pf.surge_profile.surge_multiplier_s_event}x
                    </div>
                  </div>
                  <div className="p-3.5 rounded-2xl bg-stone-50 border border-stone-200/80">
                    <div className="text-[10px] uppercase font-semibold text-stone-500">M/M/c Platform Load (ρ)</div>
                    <div className="font-mono text-xl font-extrabold text-stone-900 mt-0.5">
                      {Math.round(pf.surge_profile.platform_saturation_rho * 100)}%
                    </div>
                    <div className="text-[11px] text-stone-500">
                      {pf.platform_count} Physical Platforms
                    </div>
                  </div>
                  <div className="p-3.5 rounded-2xl bg-rose-50/70 border border-rose-200/80">
                    <div className="text-[10px] uppercase font-semibold text-rose-900">Outer Signal Hold Prob</div>
                    <div className="font-mono text-xl font-extrabold text-rose-700 mt-0.5">
                      {Math.round(pf.surge_profile.outer_signal_starvation_prob * 100)}%
                    </div>
                    <div className="text-[11px] text-rose-800">
                      ACP Risk +{pf.surge_profile.acp_risk_added_mins}m
                    </div>
                  </div>
                </div>

                {/* Formula Trace */}
                <div className="p-3.5 rounded-2xl bg-stone-900 text-stone-200 font-mono text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <span>
                    <strong className="text-[#FF6332]">Dwell Inflation Equation:</strong> {pf.surge_profile.formula_trace}
                  </span>
                  <span className="text-[11px] text-emerald-400 shrink-0">
                    ✓ Headway Guard Buffer h_buf = {pf.headway_buffer_mins} min
                  </span>
                </div>
              </div>

              {/* 2. Platform Slot IntervalTree Allocation Board */}
              <div className="bg-white/95 rounded-[28px] border border-stone-200 overflow-hidden shadow-luxury">
                <div className="px-6 py-4 border-b border-stone-100 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <div className="text-[11px] font-bold uppercase tracking-wider text-emerald-700 flex items-center gap-1">
                      <Lock className="w-3 h-3" /> IntervalTree Mutual-Exclusion Schedule
                    </div>
                    <h3 className="text-base font-bold text-stone-900">
                      Platform Slot Occupancy &amp; Outer Home Signal Detention Queue
                    </h3>
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 font-semibold">
                      Direct Ingress: {pf.saturation_summary.direct_ingress_count}
                    </span>
                    <span className="px-2.5 py-1 rounded-full bg-rose-50 text-rose-800 border border-rose-200 font-semibold">
                      Outer Signal Held: {pf.saturation_summary.outer_signal_held_count}
                    </span>
                  </div>
                </div>

                <div className="divide-y divide-stone-100">
                  {pf.intervals.map((iv) => {
                    const isHeld = iv.status === 'OUTER_SIGNAL_HOLD';
                    return (
                      <div
                        key={iv.interval_id}
                        className={`px-5 sm:px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                          isHeld ? 'bg-rose-50/40' : ''
                        }`}
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-12 h-12 rounded-2xl bg-stone-900 text-white flex flex-col items-center justify-center shrink-0">
                            <span className="text-[9px] uppercase text-stone-400">PF</span>
                            <span className="font-mono text-base font-black text-[#FF6332]">
                              {iv.platform_number}
                            </span>
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-orange-50 text-[#FF6332] border border-orange-200">
                                #{iv.train_number}
                              </span>
                              <span className="text-sm font-bold text-stone-900 truncate">
                                {iv.train_name}
                              </span>
                              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-stone-100 text-stone-600 border border-stone-200">
                                {iv.priority_label}
                              </span>
                            </div>
                            <div className="text-xs text-stone-500 mt-1 flex items-center gap-2 flex-wrap">
                              <span>Dwell: {iv.dwell_mins} min</span>
                              {isHeld && iv.held_at_cabin && (
                                <span className="text-rose-700 font-semibold flex items-center gap-1">
                                  <AlertTriangle className="w-3.5 h-3.5" />
                                  Held at {iv.held_at_cabin} (+{iv.outer_detention_mins}m until PF-{iv.platform_number} clears)
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-4 shrink-0 self-end sm:self-center">
                          <div className="text-right">
                            <div className="font-mono text-sm font-bold text-stone-900">
                              {iv.arrival_time} ➔ {iv.departure_time}
                            </div>
                            {isHeld && iv.unconstrained_arrival && (
                              <div className="text-[10px] font-mono text-stone-400">
                                Unconstrained Arr: {iv.unconstrained_arrival}
                              </div>
                            )}
                          </div>
                          <span
                            className={`font-mono text-[11px] font-bold px-2.5 py-1 rounded-full border ${
                              isHeld
                                ? 'bg-rose-100 text-rose-800 border-rose-200'
                                : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            }`}
                          >
                            {isHeld ? `OUTER HOLD +${iv.outer_detention_mins}m` : 'PF LOCKED'}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Cataloged Approach Cabins Footer */}
                {pf.approach_cabins && pf.approach_cabins.length > 0 && (
                  <div className="px-6 py-3.5 bg-stone-50 border-t border-stone-200/80 flex items-center justify-between flex-wrap gap-2">
                    <span className="text-xs font-bold text-stone-700">
                      Monitored Approach Cabins &amp; Block Huts (telemetry.db):
                    </span>
                    <div className="flex items-center gap-2 flex-wrap">
                      {pf.approach_cabins.map((c, i) => (
                        <span
                          key={i}
                          className="font-mono text-[11px] px-2.5 py-1 rounded-full bg-white border border-stone-200 text-stone-800"
                        >
                          {c.cabin_name ?? c.point_name ?? c.cabin_code} ({c.signal_aspect ?? 'MONITORED'})
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'live_board' && (
            <>
              <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
                <div className="flex items-center gap-2">
                  <SourceBadge source={board.meta?.source} asOf={board.meta?.asOf} />
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex bg-stone-100 rounded-full p-0.5 border border-stone-200">
                    {(['dep', 'arr'] as const).map((m) => (
                      <button
                        key={m}
                        onClick={() => setMode(m)}
                        className={`px-3 py-1.5 rounded-full text-[11px] font-semibold transition-all flex items-center gap-1 ${
                          mode === m ? 'bg-white text-stone-900 shadow-xs' : 'text-stone-500'
                        }`}
                      >
                        {m === 'dep' ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownLeft className="w-3 h-3" />}
                        {m === 'dep' ? 'Departures' : 'Arrivals'}
                      </button>
                    ))}
                  </div>
                  <div className="flex bg-stone-100 rounded-full p-0.5 border border-stone-200">
                    {WINDOWS.map((w) => (
                      <button
                        key={w}
                        onClick={() => setWindow(w)}
                        className={`px-3 py-1.5 rounded-full text-[11px] font-semibold transition-all ${
                          window === w ? 'bg-white text-stone-900 shadow-xs' : 'text-stone-500'
                        }`}
                      >
                        {w}h
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={board.refetch}
                    className="p-2.5 rounded-full bg-stone-100 hover:bg-stone-200 text-stone-600 transition-colors"
                    title="Refresh board"
                  >
                    <RefreshCw className={`w-4 h-4 ${board.refreshing ? 'animate-spin text-[#FF6332]' : ''}`} />
                  </button>
                </div>
              </div>

              <DegradedBanner meta={board.meta} />
              {board.loading && <LoadingCard label="Fetching live board…" rows={5} />}
              {board.error && !board.data && (
                <ErrorState error={board.error} onRetry={board.refetch} what="station board" />
              )}

              {board.data && (
                <div className="bg-white/95 rounded-[32px] border border-stone-200/80 overflow-hidden shadow-luxury">
                  <div className="px-6 py-4 border-b border-stone-100 flex items-center justify-between">
                    <span className="text-sm font-bold text-stone-900">
                      {trains.length} train{trains.length === 1 ? '' : 's'} in the next {window}h
                    </span>
                  </div>

                  {trains.length === 0 ? (
                    <div className="px-6 py-10 text-center text-xs text-stone-500">
                      No trains reported at this station in the next {window} hours.
                    </div>
                  ) : (
                    <div className="divide-y divide-stone-100">
                      {trains.map((t) => (
                        <BoardRow
                          key={`${t.trainNumber}-${t.arrival.scheduled ?? t.departure.scheduled}`}
                          t={t}
                          mode={mode}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
};

const BoardRow: React.FC<{ t: BoardTrain; mode: 'dep' | 'arr' }> = ({ t, mode }) => {
  const leg = mode === 'dep' ? t.departure : t.arrival;
  const delay = leg.delayMinutes;

  return (
    <div className={`px-5 sm:px-6 py-3.5 flex items-center gap-4 ${t.cancelled ? 'opacity-60' : ''}`}>
      <div className="font-mono text-xs font-bold text-[#FF6332] bg-orange-50 px-2 py-1 rounded border border-orange-200 shrink-0">
        {t.trainNumber}
      </div>

      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-stone-900 truncate flex items-center gap-2">
          {t.trainName ?? <Unknown />}
          {t.cancelled && (
            <span className="text-[10px] font-bold text-rose-700 bg-rose-50 border border-rose-200 px-1.5 py-0.5 rounded-full inline-flex items-center gap-1">
              <XCircle className="w-2.5 h-2.5" /> CANCELLED
            </span>
          )}
        </div>
        <div className="text-[11px] text-stone-500 truncate">
          {t.from.name ?? t.from.code ?? '—'} → {t.to.name ?? t.to.code ?? '—'}
          {t.trainType ? ` · ${t.trainType}` : ''}
        </div>
      </div>

      <div className="text-right shrink-0">
        <div className="font-mono text-sm font-bold text-stone-900">{fmtTime(leg.actual ?? leg.scheduled)}</div>
        {leg.actual && leg.scheduled && leg.actual !== leg.scheduled && (
          <div className="text-[10px] text-stone-400 font-mono line-through">{fmtTime(leg.scheduled)}</div>
        )}
      </div>

      <div className="w-14 text-center shrink-0">
        <div className="text-[9px] uppercase text-stone-400">PF</div>
        <div className="font-mono text-sm font-bold text-stone-900">
          {t.platform ?? <Unknown reason="Platform not yet assigned." />}
        </div>
      </div>

      <div className="w-16 text-right shrink-0">
        <span
          className={`text-xs font-semibold ${
            delay === null ? 'text-stone-400' : delay <= 0 ? 'text-emerald-600' : delay <= 15 ? 'text-amber-600' : 'text-rose-600'
          }`}
        >
          {fmtDelay(delay)}
        </span>
      </div>
    </div>
  );
};

export default StationPage;
