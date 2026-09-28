/**
 * PNR status.
 *
 * Phase 1 removals (plan §1.2):
 *   H1  `getSimulatedPnr()` — two complete fake PNR responses returned on ANY failure,
 *       labelled `provider: 'API Mitra'` so an outage was indistinguishable from success
 *   H2  `parseApiResponse()` defaults inventing "12301 / Howrah Rajdhani / HWH→NDLS"
 *       whenever a field was missing
 *   H3  the provider/API-key settings modal writing to localStorage
 *   H10 `coachRake` — a fabricated rake composition
 *
 * H10 turned out to be recoverable rather than deletable: the provider genuinely
 * reports coach position, so the panel now shows real data via the live endpoint —
 * but only when a train number is known and the provider supplies it.
 *
 * Privacy: passenger names are dropped server-side at the gateway boundary and never
 * reach this bundle. The PNR itself is never persisted.
 */

import React, { useState } from 'react';
import {
  Ticket, Search, CheckCircle2, Clock, TrainFront, ShieldCheck, Code, Lock, Users,
} from 'lucide-react';
import { api, type Coach, type Passenger } from '../lib/api';
import { useQuery } from '../hooks/useApi';
import { DegradedBanner, ErrorState, LoadingCard, SourceBadge, Unknown } from '../components/Provenance';

const STATUS_TONE = (status: string | null) => {
  const s = (status ?? '').toUpperCase();
  if (s.includes('CNF')) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (s.includes('RAC')) return 'bg-amber-50 text-amber-700 border-amber-200';
  if (s.includes('WL')) return 'bg-rose-50 text-rose-700 border-rose-200';
  if (s.includes('CAN')) return 'bg-stone-100 text-stone-500 border-stone-300';
  return 'bg-stone-100 text-stone-600 border-stone-200';
};

export const PnrPage: React.FC = () => {
  const [input, setInput] = useState('');
  const [pnr, setPnr] = useState('');
  const [showJson, setShowJson] = useState(false);

  const valid = /^\d{10}$/.test(pnr);
  const pnrQuery = useQuery(valid ? (signal) => api.pnr(pnr, signal) : null, [pnr]);
  const d = pnrQuery.data;

  // Coach composition comes from the live endpoint once we know the train number.
  const live = useQuery(
    d?.train?.number ? (signal) => api.trainLive(d.train.number as string, undefined, signal) : null,
    [d?.train?.number],
  );
  const coaches: Coach[] = live.data?.composition ?? [];

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.trim().replace(/\D/g, '');
    if (/^\d{10}$/.test(q)) setPnr(q);
  };

  const confirmedCount = (d?.passengers ?? []).filter(
    (p) => (p.currentStatus ?? '').toUpperCase().includes('CNF'),
  ).length;

  return (
    <div className="max-w-4xl mx-auto px-4 pt-6 sm:pt-10 pb-36">
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-sky-50 text-sky-700 text-xs font-semibold mb-3 border border-sky-200/70">
          <Ticket className="w-3.5 h-3.5" />
          <span>Reservation Status</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-display font-bold text-stone-900 tracking-tight">
          PNR Status Enquiry
        </h1>
        <p className="text-xs sm:text-sm text-stone-500 mt-1">
          Live chart verification, coach and berth allocation, real rake positioning.
        </p>
      </div>

      {/* Search */}
      <div className="bg-white/95 p-4 sm:p-5 rounded-[28px] border border-stone-200 shadow-luxury mb-6">
        <form onSubmit={submit} className="flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 text-stone-400 absolute left-4 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              inputMode="numeric"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              maxLength={13}
              placeholder="Enter your 10-digit PNR number"
              className="w-full pl-11 pr-4 py-3 bg-stone-50 hover:bg-stone-100/70 focus:bg-white rounded-full text-sm text-stone-900 border border-stone-200/80 focus:border-[#FF6332] focus:ring-4 focus:ring-orange-500/10 transition-all focus:outline-none font-mono tracking-wide"
            />
          </div>
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <button
              type="submit"
              disabled={!/^\d{10}$/.test(input.trim().replace(/\D/g, ''))}
              className="flex-1 sm:flex-initial px-6 py-3 rounded-full bg-[#18191B] hover:bg-stone-800 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold flex items-center justify-center gap-2 shadow-md transition-all active:scale-95"
            >
              <Search className="w-3.5 h-3.5" />
              <span>Check Status</span>
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

        {/* Privacy statement — a real property of the implementation, not a promise */}
        <p className="mt-3 pt-3 border-t border-stone-100 text-[11px] text-stone-500 flex items-start gap-1.5">
          <Lock className="w-3 h-3 mt-0.5 shrink-0 text-emerald-600" />
          Your PNR is not stored. It is cached for 60 seconds under a salted hash to
          avoid duplicate provider calls, and passenger names are discarded before the
          data reaches this page.
        </p>
      </div>

      {!valid && !pnrQuery.loading && (
        <div className="bg-white/95 rounded-[28px] border border-stone-200 p-10 text-center shadow-luxury">
          <Ticket className="w-10 h-10 text-stone-300 mx-auto mb-3" />
          <h3 className="font-display font-bold text-lg text-stone-900">Enter a PNR</h3>
          <p className="text-xs text-stone-500 mt-1.5 max-w-sm mx-auto">
            Ten digits, from your ticket or booking confirmation.
          </p>
        </div>
      )}

      {pnrQuery.loading && <LoadingCard label="Checking with the railway provider…" rows={4} />}

      {pnrQuery.error && !d && (
        <ErrorState error={pnrQuery.error} onRetry={pnrQuery.refetch} what="PNR" />
      )}

      {d && (
        <>
          <DegradedBanner meta={pnrQuery.meta} />

          {/* Journey header */}
          <div className="bg-white/95 rounded-[32px] border border-stone-200/80 p-6 sm:p-8 shadow-luxury mb-6">
            <div className="flex items-start justify-between gap-4 flex-wrap pb-5 border-b border-stone-100">
              <div>
                <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                  <span className="font-mono font-bold text-sm bg-orange-50 text-[#FF6332] px-2.5 py-0.5 rounded-lg border border-orange-200">
                    {d.train?.number ?? '—'}
                  </span>
                  <SourceBadge source={pnrQuery.meta?.source} asOf={pnrQuery.meta?.asOf} />
                </div>
                <h2 className="text-2xl font-display font-bold text-stone-900">
                  {d.train?.name ?? <Unknown reason="The provider did not return a train name for this PNR." />}
                </h2>
                <p className="text-xs text-stone-500 mt-1 font-mono">PNR {d.pnr}</p>
              </div>

              <div
                className={`px-4 py-2 rounded-full text-xs font-bold flex items-center gap-2 border ${
                  d.chartPrepared === null
                    ? 'bg-stone-100 text-stone-500 border-stone-200'
                    : d.chartPrepared
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-amber-50 text-amber-700 border-amber-200'
                }`}
              >
                {d.chartPrepared === null ? (
                  <Clock className="w-3.5 h-3.5" />
                ) : d.chartPrepared ? (
                  <ShieldCheck className="w-3.5 h-3.5" />
                ) : (
                  <Clock className="w-3.5 h-3.5" />
                )}
                {/* Tri-state, deliberately: "unknown" is not "not prepared" */}
                <span>
                  {d.chartPrepared === null
                    ? 'Chart status unknown'
                    : d.chartPrepared
                    ? 'Chart prepared'
                    : 'Chart not prepared'}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-5 text-stone-700">
              <Field label="From" value={d.from?.name ?? d.from?.code ?? (d as any).fromStation?.name ?? (d as any).fromStation?.code ?? '—'} />
              <Field label="To" value={d.to?.name ?? d.to?.code ?? (d as any).toStation?.name ?? (d as any).toStation?.code ?? '—'} />
              <Field label="Date of journey" value={d.journeyDate ?? (d.train as any)?.journeyDate ?? '—'} />
              <Field label="Class / quota"
                     value={[d.reservationClass ?? (d as any).travelClass, d.quota].filter(Boolean).join(' · ') || null} />
            </div>

            {d.trainStatic && (
              <p className="mt-5 text-[11px] text-stone-500 flex items-center gap-1.5">
                <TrainFront className="w-3.5 h-3.5 text-stone-400" />
                {d.trainStatic.type ?? 'Train'}
                {d.trainStatic.distance_km ? ` · ${d.trainStatic.distance_km} km route` : ''}
                {d.trainStatic.duration_min
                  ? ` · ${Math.floor(d.trainStatic.duration_min / 60)}h ${d.trainStatic.duration_min % 60}m scheduled`
                  : ''}
              </p>
            )}
          </div>

          {/* Passengers */}
          <div className="bg-white/95 rounded-[32px] border border-stone-200/80 p-6 sm:p-8 shadow-luxury mb-6">
            <h3 className="text-lg font-bold text-stone-900 mb-1 flex items-center justify-between flex-wrap gap-2">
              <span className="flex items-center gap-2">
                <Users className="w-4 h-4 text-stone-400" />
                Passengers
              </span>
              <span className="text-xs font-normal text-stone-400">
                {confirmedCount} of {d.passengers.length} confirmed
              </span>
            </h3>
            <p className="text-[11px] text-stone-400 mb-5">
              Names are intentionally not shown — they are discarded at the server boundary.
            </p>

            {d.passengers.length === 0 ? (
              <p className="text-xs text-stone-500 py-4">
                The provider returned no passenger rows for this PNR.
              </p>
            ) : (
              <div className="space-y-2.5">
                {d.passengers.map((p) => <PassengerRow key={p.serial} p={p} />)}
              </div>
            )}
          </div>

          {/* Real coach composition (H10) */}
          {coaches.length > 0 && (
            <div className="bg-white/95 rounded-[28px] border border-stone-200/80 p-6 shadow-luxury">
              <h3 className="text-sm font-bold text-stone-900 mb-1">Rake Composition</h3>
              <p className="text-[11px] text-stone-400 mb-4">
                {coaches.length} units for train {d.train?.number ?? '—'}, engine first — reported live
                by the provider. Your coach is highlighted.
              </p>
              <div className="flex gap-1.5 overflow-x-auto pb-2 scrollbar-none">
                {coaches.map((c, i) => {
                  const coachCode = c.label || c.code || `C${c.position ?? i + 1}`;
                  const coachClass = c.type || c.class || '';
                  const mine = d.passengers?.some(
                    (p) => p.coach && coachCode && p.coach.toUpperCase() === coachCode.toUpperCase(),
                  ) ?? false;
                  return (
                    <div
                      key={`${coachCode}-${i}`}
                      title={`${coachCode}: ${c.category || coachClass || 'Coach'} (#${c.position ?? i + 1})`}
                      className={`shrink-0 px-2.5 py-2 rounded-xl border text-center min-w-[54px] transition-all ${
                        mine
                          ? 'bg-[#FF6332] text-white border-[#FF6332] ring-4 ring-orange-500/20 scale-105 shadow-md'
                          : coachClass === 'ENG' || coachCode.includes('LOCO')
                          ? 'bg-stone-900 text-white border-stone-900'
                          : 'bg-stone-50 text-stone-700 border-stone-200'
                      }`}
                    >
                      <div className="text-[12px] font-mono font-bold">{coachCode}</div>
                      <div className="text-[9px] opacity-70 font-mono">{coachClass || 'GEN'}</div>
                      {mine && (
                        <div className="text-[8px] font-semibold text-white/90 uppercase tracking-tighter">Your Coach</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {live.error && d.train.number && (
            <p className="text-[11px] text-stone-500 mt-3">
              Coach position unavailable for this train right now ({live.error.code}).
            </p>
          )}
        </>
      )}

      {showJson && d && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
          <div className="bg-[#12151D] text-stone-100 w-full max-w-2xl rounded-[28px] p-6 shadow-2xl border border-white/10 flex flex-col max-h-[85vh]">
            <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-3">
              <div className="flex items-center gap-2">
                <Code className="w-5 h-5 text-emerald-400" />
                <h3 className="font-display font-bold text-base text-white">
                  GET /v1/pnr/•••••• (redacted)
                </h3>
              </div>
              <button onClick={() => setShowJson(false)} className="text-stone-400 hover:text-white text-xs font-semibold p-1">
                ✕ Close
              </button>
            </div>
            <div className="flex-1 overflow-auto bg-black/50 p-4 rounded-xl border border-white/5 font-mono text-xs text-emerald-300 leading-relaxed scrollbar-none select-all">
              <pre>{JSON.stringify({ data: d, meta: pnrQuery.meta }, null, 2)}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const Field: React.FC<{ label: string; value: string | null | undefined }> = ({ label, value }) => (
  <div>
    <span className="text-xs text-stone-400 uppercase tracking-wider block mb-1">{label}</span>
    <div className="text-sm font-semibold text-stone-900">{value ?? <Unknown />}</div>
  </div>
);

const PassengerRow: React.FC<{ p: Passenger }> = ({ p }) => (
  <div className="flex items-center gap-4 px-4 py-3 rounded-2xl bg-stone-50/80 border border-stone-200/60">
    <div className="w-8 h-8 rounded-full bg-white border border-stone-200 flex items-center justify-center text-xs font-bold text-stone-600 shrink-0">
      {p.serial}
    </div>

    <div className="flex-1 min-w-0">
      <div className="text-sm font-semibold text-stone-900">
        {p.coach && p.berth
          ? `Coach ${p.coach} · Berth ${p.berth}`
          : p.coach
          ? `Coach ${p.coach}`
          : 'Seat not yet allotted'}
      </div>
      <div className="text-[11px] text-stone-500">
        {p.berthType ?? '—'}
        {p.bookingStatus ? ` · booked as ${p.bookingStatus}` : ''}
      </div>
    </div>

    <span
      className={`px-3 py-1 rounded-full text-xs font-bold border shrink-0 inline-flex items-center gap-1.5 ${STATUS_TONE(
        p.currentStatus,
      )}`}
    >
      {(p.currentStatus ?? '').toUpperCase().includes('CNF') && <CheckCircle2 className="w-3 h-3" />}
      {p.currentStatus ?? 'Unknown'}
    </span>
  </div>
);

export default PnrPage;
