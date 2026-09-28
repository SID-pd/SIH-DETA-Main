/**
 * Live station departure/arrival board.
 *
 * Phase 1 removals (plan §1.2):
 *   H7  `stationsList` — 6 hardcoded stations with invented platform counts
 *   H8  `stationBoards` — 13 hardcoded departures across 3 stations
 *
 * Station selection is now an autocomplete over all 8,990 real stations from our own
 * store (zero provider cost), and the board itself is GET /v1/stations/{code}/board.
 */

import React, { useState } from 'react';
import { Building2, Search, RefreshCw, ArrowUpRight, ArrowDownLeft, XCircle } from 'lucide-react';
import { api, fmtDelay, fmtTime, type BoardTrain } from '../lib/api';
import { useDebounced, useQuery } from '../hooks/useApi';
import { DegradedBanner, ErrorState, LoadingCard, SourceBadge, Unknown } from '../components/Provenance';

const WINDOWS = [2, 4, 8] as const;

export const StationPage: React.FC = () => {
  const [selected, setSelected] = useState<{ code: string; name: string } | null>(null);
  const [search, setSearch] = useState('');
  const [window, setWindow] = useState<2 | 4 | 8>(2);
  const [mode, setMode] = useState<'dep' | 'arr'>('dep');

  const debounced = useDebounced(search, 250);

  const stations = useQuery(
    debounced.trim().length >= 2 ? (signal) => api.searchStations(debounced.trim(), signal) : null,
    [debounced],
  );

  const board = useQuery(
    selected ? (signal) => api.stationBoard(selected.code, window, mode, signal) : null,
    [selected?.code, window, mode],
    { pollMs: 90_000 },
  );

  const trains = board.data?.trains ?? [];

  return (
    <div className="max-w-5xl mx-auto px-4 pt-6 sm:pt-10 pb-36">
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 text-amber-800 text-xs font-semibold mb-3 border border-amber-200/70">
          <Building2 className="w-3.5 h-3.5" />
          <span>Electronic Digital Station Board</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-display font-bold text-stone-900 tracking-tight">
          Live Station Display Board
        </h1>
        <p className="text-xs sm:text-sm text-stone-500 mt-1">
          Real platform assignments and live timings for any of 8,990 stations.
        </p>
      </div>

      {/* Station autocomplete over the full station table */}
      <div className="bg-white/95 p-4 sm:p-5 rounded-[28px] border border-stone-200 shadow-luxury mb-6">
        <div className="relative">
          <Search className="w-4 h-4 text-stone-400 absolute left-4 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search any station — name or code (e.g. New Delhi, NDLS, Howrah)"
            className="w-full pl-11 pr-4 py-3 bg-stone-50 hover:bg-stone-100/70 focus:bg-white rounded-full text-sm text-stone-900 border border-stone-200/80 focus:border-[#FF6332] focus:ring-4 focus:ring-orange-500/10 transition-all focus:outline-none"
          />
        </div>

        {stations.data && stations.data.length > 0 && (
          <div className="mt-3 pt-3 border-t border-stone-100 grid sm:grid-cols-2 gap-2">
            {stations.data.map((s) => (
              <button
                key={s.code}
                onClick={() => { setSelected({ code: s.code, name: s.name }); setSearch(''); }}
                className="flex items-center justify-between px-3.5 py-2.5 rounded-2xl bg-stone-50 hover:bg-stone-100 border border-stone-200/60 text-left transition-all"
              >
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-stone-900 truncate">{s.name}</div>
                  <div className="text-[11px] text-stone-500">
                    {s.state ?? '—'}{s.zone ? ` · ${s.zone}` : ''}
                  </div>
                </div>
                <span className="font-mono text-xs px-2 py-0.5 bg-white rounded border border-stone-200 text-stone-600 shrink-0 ml-2">
                  {s.code}
                </span>
              </button>
            ))}
          </div>
        )}

        {stations.data && stations.data.length === 0 && debounced.trim().length >= 2 && (
          <p className="mt-3 pt-3 border-t border-stone-100 text-xs text-stone-500">
            No station matches “{debounced}”.
          </p>
        )}
      </div>

      {/* Empty state instead of defaulting to NDLS */}
      {!selected && (
        <div className="bg-white/95 rounded-[28px] border border-stone-200 p-10 text-center shadow-luxury">
          <Building2 className="w-10 h-10 text-stone-300 mx-auto mb-3" />
          <h3 className="font-display font-bold text-lg text-stone-900">Pick a station</h3>
          <p className="text-xs text-stone-500 mt-1.5">
            Search above to see live arrivals and departures.
          </p>
        </div>
      )}

      {selected && (
        <>
          {/* Controls */}
          <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
            <div>
              <h2 className="text-xl font-display font-bold text-stone-900 flex items-center gap-2 flex-wrap">
                {selected.name}
                <span className="font-mono text-xs px-2 py-0.5 bg-stone-100 rounded border border-stone-200 text-stone-600">
                  {selected.code}
                </span>
                <SourceBadge source={board.meta?.source} asOf={board.meta?.asOf} />
              </h2>
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
                    <BoardRow key={`${t.trainNumber}-${t.arrival.scheduled ?? t.departure.scheduled}`} t={t} mode={mode} />
                  ))}
                </div>
              )}
            </div>
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
