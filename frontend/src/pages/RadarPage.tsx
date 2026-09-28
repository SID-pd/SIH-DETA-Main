/**
 * Control Room — Section Controller DRM Dispatch Cockpit & Spatial Radar
 *
 * Implements the SIH-DETA / RailPulse Layer 3 Operational Control & Resilience Cockpit:
 * 1. 3-Level Black Swan Degradation Monitor (LEVEL_1_NORMAL, LEVEL_2_DEAD_RECKONING, LEVEL_3_BLACK_SWAN)
 * 2. Real-Time Section Controller Incident Override Injector (CRO, ACP, TRACK_BLOCK, OHE_SNAP,
 *    SIGNAL_FAILURE, SHORT_TERMINATE, MELA_SPECIAL) persisted in controller_ops.db
 * 3. Yen's K-Shortest Path Electrified Bypass Rerouting Visualizer (25kV AC verified)
 * 4. Festival Surge (MAHA_KUMBH S=3.2, CHHATH_PUJA S=2.8, DIWALI_RUSH S=2.2) & G&SR Weather Simulator
 * 5. Adaptive Schedule-Aware Token-Bucket Pacing Telemetry + Optional Live Spatial Radar view
 */

import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  Radio,
  Zap,
  AlertTriangle,
  RefreshCw,
  Route,
  CloudFog,
  Flame,
  CheckCircle2,
  Trash2,
  TrainFront,
  Activity,
  Gauge,
  Radar,
  Sliders,
  ArrowRight,
  Lock,
  Sparkles,
} from 'lucide-react';
import { api, type ControlRoomState, type ReroutePlan } from '../lib/api';
import { PageId } from '../components/RadioNavbar';

interface RadarPageProps {
  onNavigate?: (page: PageId) => void;
  onInspectTrain?: (trainNo: string) => void;
}

const CORRIDOR_SECTIONS = [
  { from: 'CNB', to: 'PRYJ', label: 'Kanpur Central (CNB) ➔ Prayagraj Jn (PRYJ) [NCR High-Density]' },
  { from: 'ALJN', to: 'TDL', label: 'Aligarh Jn (ALJN) ➔ Tundla Jn (TDL) [NCR Trunk]' },
  { from: 'PRYJ', to: 'DDU', label: 'Prayagraj Jn (PRYJ) ➔ Pt. DD Upadhyaya (DDU) [Maha Kumbh Ring]' },
  { from: 'GAYA', to: 'DHN', label: 'Gaya Jn (GAYA) ➔ Dhanbad Jn (DHN) [Grand Chord]' },
  { from: 'VGLJ', to: 'RKMP', label: 'Virangana Lakshmibai (VGLJ) ➔ Rani Kamlapati (RKMP) [Central]' },
];

export const RadarPage: React.FC<RadarPageProps> = ({ onInspectTrain }) => {
  const [viewMode, setViewMode] = useState<'cockpit' | 'spatial'>('cockpit');
  const [state, setState] = useState<ControlRoomState | null>(null);
  const [reroutePreview, setReroutePreview] = useState<ReroutePlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Incident form state
  const [selectedSectionIdx, setSelectedSectionIdx] = useState(0);
  const [affectedTrain, setAffectedTrain] = useState('12301');
  const [customClearance, setCustomClearance] = useState<number | ''>('');

  // Weather & Surge simulator state
  const [visibilityM, setVisibilityM] = useState(4200);
  const [precipMm, setPrecipMm] = useState(0);
  const [tempC, setTempC] = useState(29);
  const [activeEventId, setActiveEventId] = useState('NOMINAL');

  const fetchState = async () => {
    try {
      setLoading(true);
      const sec = CORRIDOR_SECTIONS[selectedSectionIdx];
      const [ctrlRes, rerouteRes] = await Promise.all([
        api.detaControllerState(),
        api.detaReroute(sec.from, sec.to),
      ]);
      setState(ctrlRes.data);
      setReroutePreview(rerouteRes.data);
      setActiveEventId(ctrlRes.data.active_event_id);
      setVisibilityM(ctrlRes.data.weather_override.visibility_meters);
      setPrecipMm(ctrlRes.data.weather_override.precipitation_mm);
      setTempC(ctrlRes.data.weather_override.ambient_temp_c);
    } catch {
      // handled gracefully
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchState();
  }, [selectedSectionIdx]);

  const handleInjectIncident = async (incidentType: string) => {
    const sec = CORRIDOR_SECTIONS[selectedSectionIdx];
    try {
      setSubmitting(true);
      await api.detaReportIncident({
        incident_type: incidentType,
        section_from: sec.from,
        section_to: sec.to,
        affected_train_number: affectedTrain || '12301',
        estimated_clearance_mins: customClearance !== '' ? Number(customClearance) : undefined,
      });
      await fetchState();
    } finally {
      setSubmitting(false);
    }
  };

  const handleResolveIncident = async (incidentId = 'ALL') => {
    try {
      setSubmitting(true);
      await api.detaResolveIncident(incidentId);
      await fetchState();
    } finally {
      setSubmitting(false);
    }
  };

  const handleApplyEnvironment = async (nextEventId?: string, nextVis?: number, nextPrecip?: number, nextTemp?: number) => {
    try {
      setSubmitting(true);
      const res = await api.detaSetEnvironment({
        event_id: nextEventId ?? activeEventId,
        visibility_meters: nextVis ?? visibilityM,
        precipitation_mm: nextPrecip ?? precipMm,
        ambient_temp_c: nextTemp ?? tempC,
      });
      setState(res.data);
    } finally {
      setSubmitting(false);
    }
  };

  const degLevel = state?.degradation_level ?? 'LEVEL_1_NORMAL';
  const degBadgeStyle =
    degLevel === 'LEVEL_3_BLACK_SWAN'
      ? 'bg-rose-950 text-rose-200 border-rose-500/60'
      : degLevel === 'LEVEL_2_DEAD_RECKONING'
        ? 'bg-amber-950 text-amber-200 border-amber-500/60'
        : 'bg-emerald-950 text-emerald-200 border-emerald-500/60';

  // Compute live G&SR effective MPS preview
  const effectiveMps =
    precipMm >= 50
      ? 10
      : visibilityM < 100
        ? 30
        : tempC >= 46
          ? 45
          : visibilityM < 600 || precipMm >= 15
            ? 75
            : 130;

  return (
    <div className="max-w-6xl mx-auto px-4 pt-4 sm:pt-8 pb-28">
      {/* Header & View Switcher */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-orange-50 text-[#FF6332] text-xs font-semibold mb-2 border border-orange-200/70">
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>SIH-DETA Layer 3 · Divisional Operations Control (DRM / FOIS / COA)</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-display font-bold text-stone-900 tracking-tight">
            Section Controller Dispatch Cockpit
          </h1>
          <p className="text-xs sm:text-sm text-stone-500 mt-1">
            Real-time incident overrides, Yen&apos;s K-Shortest Path electrified bypass rerouting, festival surge multipliers, and G&amp;SR weather speed caps.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <div className="flex bg-stone-100 p-1 rounded-full border border-stone-200">
            <button
              onClick={() => setViewMode('cockpit')}
              className={`px-4 py-2 rounded-full text-xs font-semibold transition-all flex items-center gap-1.5 ${
                viewMode === 'cockpit' ? 'bg-[#18191B] text-white shadow-sm' : 'text-stone-600 hover:text-stone-900'
              }`}
            >
              <Sliders className="w-3.5 h-3.5 text-[#FF6332]" />
              DRM Cockpit
            </button>
            <button
              onClick={() => setViewMode('spatial')}
              className={`px-4 py-2 rounded-full text-xs font-semibold transition-all flex items-center gap-1.5 ${
                viewMode === 'spatial' ? 'bg-[#18191B] text-white shadow-sm' : 'text-stone-600 hover:text-stone-900'
              }`}
            >
              <Radar className="w-3.5 h-3.5 text-emerald-500" />
              Spatial Radar
            </button>
          </div>
          <button
            onClick={fetchState}
            className="p-2.5 rounded-full bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 shadow-xs"
            title="Refresh Control Room State"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-[#FF6332]' : ''}`} />
          </button>
        </div>
      </div>

      {viewMode === 'spatial' ? (
        <div className="rounded-[32px] overflow-hidden border border-stone-200 shadow-luxury bg-[#070A0F] h-[76vh] relative">
          <iframe
            src="https://railradar.in/railradar"
            title="RailRadar Live Network Radar"
            className="w-full h-full border-0 block"
            sandbox="allow-scripts allow-same-origin allow-forms"
            referrerPolicy="no-referrer"
          />
        </div>
      ) : (
        <div className="space-y-6">
          {/* 1. 3-Level Black Swan Circuit Breaker Banner */}
          <div className={`p-5 sm:p-6 rounded-[28px] border shadow-luxury ${degBadgeStyle}`}>
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-start gap-3.5">
                <div className="p-3 rounded-2xl bg-white/10 border border-white/15 shrink-0">
                  {degLevel === 'LEVEL_3_BLACK_SWAN' ? (
                    <AlertTriangle className="w-6 h-6 text-rose-400 animate-bounce" />
                  ) : degLevel === 'LEVEL_2_DEAD_RECKONING' ? (
                    <CloudFog className="w-6 h-6 text-amber-400" />
                  ) : (
                    <CheckCircle2 className="w-6 h-6 text-emerald-400" />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2.5 flex-wrap">
                    <span className="font-mono text-xs font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-white/10 border border-white/15">
                      {degLevel}
                    </span>
                    <span className="text-xs opacity-80">
                      Unidirectional Space-Time DAG · Max Iterations K_max = 3 (Zero Cyclic Feedback)
                    </span>
                  </div>
                  <h2 className="text-lg sm:text-xl font-display font-bold text-white mt-1">
                    {state?.degradation_description ??
                      'Full Hybrid Quantile LightGBM (P10/P50/P90) + IntervalTree Platform Allocation Active'}
                  </h2>
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <button
                  onClick={() => onInspectTrain?.(affectedTrain || '12301')}
                  className="px-4 py-2.5 rounded-full bg-[#FF6332] hover:bg-orange-600 text-white text-xs font-semibold flex items-center gap-1.5 shadow-md transition-all"
                >
                  <TrainFront className="w-3.5 h-3.5" />
                  Inspect Train {affectedTrain || '12301'} ETA
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
                {(state?.active_incidents?.length ?? 0) > 0 && (
                  <button
                    onClick={() => handleResolveIncident('ALL')}
                    disabled={submitting}
                    className="px-4 py-2.5 rounded-full bg-white/10 hover:bg-white/20 text-white border border-white/20 text-xs font-semibold flex items-center gap-1.5 transition-all"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Clear All ({state?.active_incidents.length})
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* 2. Target Corridor & Incident Injector Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left 7 cols: Section Controller Incident Override Deck */}
            <div className="lg:col-span-7 bg-white/95 rounded-[28px] border border-stone-200 p-5 sm:p-6 shadow-luxury">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[#FF6332]">
                    Section Controller Authority Override
                  </span>
                  <h3 className="text-xl font-display font-bold text-stone-900">
                    Inject Real-World Operational Incident
                  </h3>
                </div>
                <span className="font-mono text-[11px] px-2.5 py-1 rounded-full bg-stone-100 border border-stone-200 text-stone-600">
                  controller_ops.db
                </span>
              </div>

              {/* Target Section & Train Selector */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5 p-3.5 rounded-2xl bg-stone-50 border border-stone-200/80">
                <div className="sm:col-span-2">
                  <label className="block text-[11px] font-semibold text-stone-500 uppercase mb-1">
                    Block Section (From ➔ To)
                  </label>
                  <select
                    value={selectedSectionIdx}
                    onChange={(e) => setSelectedSectionIdx(Number(e.target.value))}
                    className="w-full px-3 py-2 rounded-xl bg-white border border-stone-200 text-xs font-semibold text-stone-900 focus:outline-none focus:border-[#FF6332]"
                  >
                    {CORRIDOR_SECTIONS.map((s, idx) => (
                      <option key={`${s.from}-${s.to}`} value={idx}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-[11px] font-semibold text-stone-500 uppercase mb-1">
                    Focal Train No.
                  </label>
                  <div className="flex gap-1.5">
                    <input
                      type="text"
                      value={affectedTrain}
                      onChange={(e) => setAffectedTrain(e.target.value)}
                      placeholder="12301"
                      className="w-full px-3 py-2 rounded-xl bg-white border border-stone-200 font-mono text-xs font-bold text-stone-900 focus:outline-none focus:border-[#FF6332]"
                    />
                    <input
                      type="number"
                      value={customClearance}
                      onChange={(e) => setCustomClearance(e.target.value === '' ? '' : Number(e.target.value))}
                      placeholder="Min"
                      title="Optional custom clearance minutes"
                      className="w-16 px-2 py-2 rounded-xl bg-white border border-stone-200 font-mono text-xs text-stone-700 focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              {/* 7 One-Click Incident Override Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {(state?.incident_catalog ?? []).map((inc) => {
                  const isBlackSwan = inc.type === 'TRACK_BLOCK' || inc.type === 'OHE_SNAP';
                  return (
                    <button
                      key={inc.type}
                      disabled={submitting}
                      onClick={() => handleInjectIncident(inc.type)}
                      className={`text-left p-3.5 rounded-2xl border transition-all hover:shadow-md active:scale-[0.99] cursor-pointer ${
                        isBlackSwan
                          ? 'bg-rose-50/60 hover:bg-rose-50 border-rose-200/80'
                          : 'bg-stone-50/70 hover:bg-white border-stone-200/80'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2 mb-1">
                        <span className="font-mono text-xs font-extrabold px-2 py-0.5 rounded bg-stone-900 text-white">
                          {inc.type}
                        </span>
                        <span
                          className={`font-mono text-[11px] font-bold px-2 py-0.5 rounded-full ${
                            isBlackSwan
                              ? 'bg-rose-100 text-rose-800 border border-rose-200'
                              : 'bg-amber-100 text-amber-800 border border-amber-200'
                          }`}
                        >
                          +{inc.default_detention_mins}m · {inc.default_severity}
                        </span>
                      </div>
                      <div className="text-xs font-bold text-stone-900 mt-1">{inc.title}</div>
                      <p className="text-[11px] text-stone-500 mt-1 line-clamp-2">{inc.physics_mechanism}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Right 5 cols: Festival Surge & G&SR Weather Physics Simulator */}
            <div className="lg:col-span-5 bg-white/95 rounded-[28px] border border-stone-200 p-5 sm:p-6 shadow-luxury flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <span className="text-[11px] font-bold uppercase tracking-wider text-purple-600">
                      Layer 1 &amp; G&amp;SR Rulebook Simulator
                    </span>
                    <h3 className="text-xl font-display font-bold text-stone-900">
                      Festival Surge &amp; Weather Caps
                    </h3>
                  </div>
                  <Sparkles className="w-5 h-5 text-purple-600" />
                </div>

                {/* Festival Surge Selector */}
                <div className="mb-5">
                  <label className="block text-xs font-bold text-stone-700 mb-2">
                    Active Event / Festival Crowd Surge (S_event)
                  </label>
                  <div className="grid grid-cols-1 gap-2">
                    {(state?.available_event_presets ?? []).map((ev) => {
                      const active = activeEventId === ev.event_id;
                      return (
                        <button
                          key={ev.event_id}
                          onClick={() => {
                            setActiveEventId(ev.event_id);
                            handleApplyEnvironment(ev.event_id, visibilityM, precipMm, tempC);
                          }}
                          className={`p-3 rounded-2xl border text-left transition-all flex items-center justify-between ${
                            active
                              ? 'bg-[#18191B] text-white border-stone-900 shadow-sm'
                              : 'bg-stone-50 hover:bg-stone-100 border-stone-200 text-stone-800'
                          }`}
                        >
                          <div className="min-w-0 pr-2">
                            <div className="text-xs font-bold truncate">{ev.event_name}</div>
                            <div className={`text-[10px] truncate ${active ? 'text-stone-300' : 'text-stone-500'}`}>
                              {ev.description}
                            </div>
                          </div>
                          <span
                            className={`font-mono text-xs font-extrabold px-2.5 py-1 rounded-full shrink-0 ${
                              active ? 'bg-[#FF6332] text-white' : 'bg-white border border-stone-200 text-stone-700'
                            }`}
                          >
                            S={ev.surge_multiplier.toFixed(1)}x
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* G&SR Weather Sliders */}
                <div className="space-y-3.5 p-4 rounded-2xl bg-stone-50 border border-stone-200/80">
                  <div>
                    <div className="flex justify-between text-xs font-semibold mb-1">
                      <span className="text-stone-700 flex items-center gap-1">
                        <CloudFog className="w-3.5 h-3.5 text-sky-600" /> Fog Visibility (G&amp;SR 3.61)
                      </span>
                      <span className="font-mono font-bold text-stone-900">{visibilityM} m</span>
                    </div>
                    <input
                      type="range"
                      min={50}
                      max={4500}
                      step={50}
                      value={visibilityM}
                      onChange={(e) => setVisibilityM(Number(e.target.value))}
                      onMouseUp={() => handleApplyEnvironment(activeEventId, visibilityM, precipMm, tempC)}
                      onTouchEnd={() => handleApplyEnvironment(activeEventId, visibilityM, precipMm, tempC)}
                      className="w-full accent-[#FF6332]"
                    />
                    <div className="flex justify-between text-[10px] text-stone-400 font-mono">
                      <span>50m (30 km/h)</span>
                      <span>350m (FSD 75 km/h)</span>
                      <span>4500m (Clear)</span>
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-xs font-semibold mb-1">
                      <span className="text-stone-700">Monsoon Rainfall (G&amp;SR 2.11)</span>
                      <span className="font-mono font-bold text-stone-900">{precipMm} mm/h</span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={65}
                      step={5}
                      value={precipMm}
                      onChange={(e) => setPrecipMm(Number(e.target.value))}
                      onMouseUp={() => handleApplyEnvironment(activeEventId, visibilityM, precipMm, tempC)}
                      onTouchEnd={() => handleApplyEnvironment(activeEventId, visibilityM, precipMm, tempC)}
                      className="w-full accent-[#FF6332]"
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-xs font-semibold mb-1">
                      <span className="text-stone-700 flex items-center gap-1">
                        <Flame className="w-3.5 h-3.5 text-orange-600" /> Ambient Temp (CWR Buckling)
                      </span>
                      <span className="font-mono font-bold text-stone-900">{tempC} °C</span>
                    </div>
                    <input
                      type="range"
                      min={15}
                      max={50}
                      step={1}
                      value={tempC}
                      onChange={(e) => setTempC(Number(e.target.value))}
                      onMouseUp={() => handleApplyEnvironment(activeEventId, visibilityM, precipMm, tempC)}
                      onTouchEnd={() => handleApplyEnvironment(activeEventId, visibilityM, precipMm, tempC)}
                      className="w-full accent-[#FF6332]"
                    />
                  </div>
                </div>
              </div>

              {/* Effective G&SR Speed Cap Readout */}
              <div className="mt-4 p-3.5 rounded-2xl bg-stone-900 text-white flex items-center justify-between">
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-stone-400">
                    Enforced G&amp;SR Maximum Speed
                  </div>
                  <div className="text-xs font-semibold text-stone-200 mt-0.5">
                    {effectiveMps < 130 ? 'Temporary Speed Restriction (TSR) Active' : 'Nominal Sectional MPS'}
                  </div>
                </div>
                <div className="font-mono text-xl font-black text-[#FF6332]">
                  {effectiveMps} km/h
                </div>
              </div>
            </div>
          </div>

          {/* 3. Active Incident Queue & Yen's K-Shortest Path Electrified Bypass */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Active Incidents & Trailing Train FIFO Headway Cascade */}
            <div className="lg:col-span-6 bg-white/95 rounded-[28px] border border-stone-200 p-5 sm:p-6 shadow-luxury">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <span className="text-[11px] font-bold uppercase tracking-wider text-rose-600">
                    FIFO Block Headway Queue
                  </span>
                  <h3 className="text-lg font-display font-bold text-stone-900">
                    Active Section Incidents ({state?.active_incidents?.length ?? 0})
                  </h3>
                </div>
                <Activity className="w-5 h-5 text-rose-500" />
              </div>

              {(state?.active_incidents?.length ?? 0) === 0 ? (
                <div className="p-8 rounded-2xl bg-stone-50 border border-stone-200/60 text-center">
                  <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                  <div className="text-sm font-bold text-stone-900">All Block Sections Clear</div>
                  <p className="text-xs text-stone-500 mt-1">
                    Click any incident card above (e.g. CRO, ACP, TRACK_BLOCK) to simulate live propagation and trailing train headway cascades.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {state!.active_incidents.map((inc) => (
                    <div
                      key={inc.incident_id}
                      className="p-4 rounded-2xl bg-rose-50/50 border border-rose-200/80 flex flex-col gap-2"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-rose-700 text-white">
                            {inc.incident_type}
                          </span>
                          <span className="font-mono text-xs font-bold text-stone-900">
                            {inc.section_from} ➔ {inc.section_to}
                          </span>
                          <span className="font-mono text-xs text-rose-700 font-bold">
                            +{inc.estimated_clearance_mins}m
                          </span>
                        </div>
                        <button
                          onClick={() => handleResolveIncident(inc.incident_id)}
                          className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-white hover:bg-emerald-50 text-emerald-700 border border-emerald-200 transition-colors"
                        >
                          Resolve
                        </button>
                      </div>
                      <div className="text-xs font-bold text-stone-900">{inc.title}</div>
                      <div className="text-[11px] text-stone-600">{inc.physics_mechanism}</div>
                      {inc.trailing_trains_delayed && inc.trailing_trains_delayed.length > 0 && (
                        <div className="pt-2 border-t border-rose-200/60 flex items-center gap-1.5 flex-wrap">
                          <span className="text-[10px] font-bold uppercase text-rose-800">
                            FIFO Trailing Cascade:
                          </span>
                          {inc.trailing_trains_delayed.map((tNo) => (
                            <button
                              key={tNo}
                              onClick={() => onInspectTrain?.(tNo)}
                              className="font-mono text-[11px] font-bold px-2 py-0.5 rounded bg-white border border-rose-200 text-rose-800 hover:bg-rose-100"
                            >
                              #{tNo}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Yen's K-Shortest Path Electrified Bypass Visualizer */}
            <div className="lg:col-span-6 bg-white/95 rounded-[28px] border border-stone-200 p-5 sm:p-6 shadow-luxury">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-700">
                    Topological Graph Search (8,990 Nodes)
                  </span>
                  <h3 className="text-lg font-display font-bold text-stone-900">
                    Yen&apos;s K-Shortest Electrified Bypass
                  </h3>
                </div>
                <Route className="w-5 h-5 text-emerald-600" />
              </div>

              {reroutePreview && (
                <div className="space-y-4">
                  <div className="p-4 rounded-2xl bg-stone-900 text-white">
                    <div className="flex items-center justify-between text-xs text-stone-400 mb-2">
                      <span>Severed Mainline Edge: {reroutePreview.severed_section}</span>
                      <span className="font-mono text-rose-400 font-bold">{reroutePreview.edge_weight}</span>
                    </div>
                    <div className="text-xs font-semibold text-emerald-400 mb-2">
                      ✓ {reroutePreview.traction_verified}
                    </div>
                    <div className="flex items-center gap-1.5 flex-wrap mt-2">
                      {reroutePreview.detour_via_stations.map((stn, idx) => (
                        <React.Fragment key={stn}>
                          <span className="font-mono text-xs font-bold px-2.5 py-1 rounded-lg bg-white/10 border border-white/15 text-white">
                            {stn}
                          </span>
                          {idx < reroutePreview.detour_via_stations.length - 1 && (
                            <ArrowRight className="w-3.5 h-3.5 text-[#FF6332]" />
                          )}
                        </React.Fragment>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    <div className="p-3 rounded-2xl bg-stone-50 border border-stone-200/80 text-center">
                      <div className="text-[10px] uppercase text-stone-500 font-semibold">Direct Dist</div>
                      <div className="font-mono text-base font-extrabold text-stone-900 mt-0.5">
                        {reroutePreview.original_distance_km} km
                      </div>
                    </div>
                    <div className="p-3 rounded-2xl bg-stone-50 border border-stone-200/80 text-center">
                      <div className="text-[10px] uppercase text-stone-500 font-semibold">Chord Bypass</div>
                      <div className="font-mono text-base font-extrabold text-emerald-700 mt-0.5">
                        {reroutePreview.detour_distance_km} km (+{reroutePreview.added_distance_km})
                      </div>
                    </div>
                    <div className="p-3 rounded-2xl bg-orange-50 border border-orange-200/80 text-center">
                      <div className="text-[10px] uppercase text-orange-800 font-semibold">Detour Penalty</div>
                      <div className="font-mono text-base font-extrabold text-[#FF6332] mt-0.5">
                        +{reroutePreview.estimated_detour_penalty_mins} min
                      </div>
                    </div>
                  </div>

                  <div className="text-[11px] text-stone-500 bg-stone-50 p-3 rounded-xl border border-stone-200/60">
                    <strong>Corridors Traversed:</strong> {reroutePreview.detour_corridors.join(' ➔ ')}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 4. Adaptive Schedule-Aware Token-Bucket Pacing Strip */}
          {state?.adaptive_pacing_engine && (
            <div className="p-5 rounded-[28px] bg-white/95 border border-stone-200 shadow-luxury">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                <div className="flex items-center gap-2">
                  <Gauge className="w-4 h-4 text-[#FF6332]" />
                  <span className="text-xs font-bold uppercase tracking-wider text-stone-900">
                    Adaptive Schedule-Aware Token-Bucket Pacing Engine
                  </span>
                </div>
                <span className="font-mono text-xs text-emerald-700 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200 font-semibold">
                  Zero-Ban Rate Limiter: {state.adaptive_pacing_engine.token_bucket_rate_rps} RPS (Burst {state.adaptive_pacing_engine.token_bucket_burst_capacity})
                </span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-center">
                <div className="p-3 rounded-2xl bg-stone-50 border border-stone-200/70">
                  <div className="font-mono text-lg font-extrabold text-stone-900">
                    {state.adaptive_pacing_engine.active_window_trains_polled.toLocaleString()} / {state.adaptive_pacing_engine.cataloged_trains_total.toLocaleString()}
                  </div>
                  <div className="text-[10px] text-stone-500 uppercase font-semibold mt-0.5">
                    Active Running Window Polled (-79.9% Load)
                  </div>
                </div>
                <div className="p-3 rounded-2xl bg-stone-50 border border-stone-200/70">
                  <div className="font-mono text-lg font-extrabold text-emerald-700">
                    {state.adaptive_pacing_engine.spatial_weather_hex_cells} Hex Cells
                  </div>
                  <div className="text-[10px] text-stone-500 uppercase font-semibold mt-0.5">
                    Covers {state.adaptive_pacing_engine.stations_covered_by_hex_grid.toLocaleString()} Stations (-98% API Calls)
                  </div>
                </div>
                <div className="p-3 rounded-2xl bg-stone-50 border border-stone-200/70">
                  <div className="font-mono text-lg font-extrabold text-[#FF6332]">
                    {state.adaptive_pacing_engine.outer_deceleration_poll_interval_sec}s
                  </div>
                  <div className="text-[10px] text-stone-500 uppercase font-semibold mt-0.5">
                    704 Approach Cabins (Decel &lt;25 km/h)
                  </div>
                </div>
                <div className="p-3 rounded-2xl bg-stone-50 border border-stone-200/70">
                  <div className="font-mono text-lg font-extrabold text-stone-900">
                    {state.adaptive_pacing_engine.tier1_rajdhani_vb_poll_interval_sec}s
                  </div>
                  <div className="text-[10px] text-stone-500 uppercase font-semibold mt-0.5">
                    Tier-1 Rajdhani / Vande Bharat
                  </div>
                </div>
                <div className="p-3 rounded-2xl bg-stone-50 border border-stone-200/70">
                  <div className="font-mono text-lg font-extrabold text-stone-900">
                    {state.adaptive_pacing_engine.tier2_express_poll_interval_sec}s
                  </div>
                  <div className="text-[10px] text-stone-500 uppercase font-semibold mt-0.5">
                    Open-Line Express / Superfast
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default RadarPage;
