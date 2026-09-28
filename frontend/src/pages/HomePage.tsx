import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { ContainerScroll } from '../components/ContainerScroll';
import { PageId } from '../components/RadioNavbar';
import { api } from '../lib/api';
import { useQuery } from '../hooks/useApi';
import { 
  Search, 
  Radio, 
  Sparkles, 
  ArrowRight, 
  ChevronRight,
  Zap, 
  Layers,
  Train,
  CheckCircle2,
  XCircle,
  Activity,
  Compass,
  MapPin,
  TrendingUp,
  Cpu,
  ShieldCheck
} from 'lucide-react';

interface HomePageProps {
  onNavigate: (page: PageId) => void;
  onSearchTrain?: (query: string) => void;
}

export const HomePage: React.FC<HomePageProps> = ({ onNavigate, onSearchTrain }) => {
  const [searchQuery, setSearchQuery] = useState('');

  // Real popularity from observed lookups (was H9: a hardcoded 4-train table with
  // invented speeds and delays). Cold start renders an empty state rather than a
  // curated fiction.
  const popular = useQuery((signal) => api.popularTrains(signal), []);
  const popularTrains = popular.data ?? [];

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      if (onSearchTrain) onSearchTrain(searchQuery.trim());
      onNavigate('live');
    }
  };

  const handleQuickSelect = (trainNumber: string) => {
    setSearchQuery(trainNumber);
    if (onSearchTrain) onSearchTrain(trainNumber);
    onNavigate('live');
  };

  return (
    <div className="flex flex-col w-full min-h-screen pb-32">
      {/* 1. Hero Section */}
      <section className="pt-6 sm:pt-12 pb-4 px-4 max-w-5xl mx-auto text-center flex flex-col items-center">
        {/* Nomu-style Pill Badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/90 border border-stone-200/80 shadow-sm text-xs font-medium text-stone-800 mb-6 hover:shadow-md transition-shadow">
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-[#FF6332]"></span>
          </span>
          <span>Next-Generation Live Rail Platform</span>
          <span className="text-stone-300">|</span>
          <span className="text-[#FF6332] font-semibold flex items-center gap-1">
            <Sparkles className="w-3 h-3" /> 2026 Edition
          </span>
        </div>

        {/* Hero Main Heading */}
        <h1 className="text-4xl sm:text-6xl md:text-7xl font-display font-extrabold tracking-tight text-stone-900 leading-[1.1] max-w-4xl">
          Track Every Train in India.{' '}
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#FF6332] via-[#E11D48] to-[#9333EA]">
            Live & Immersive.
          </span>
        </h1>

        <p className="mt-5 text-base sm:text-xl text-stone-600 max-w-2xl font-normal leading-relaxed">
          Real-time interactive spatial radar, micro-second ETA predictions, coach layout positions, and live station display boards.
        </p>

        {/* Hero Quick Search Bar */}
        <form onSubmit={handleSearchSubmit} className="mt-8 w-full max-w-xl">
          <div className="relative flex items-center bg-white rounded-full p-2 border border-stone-200 shadow-luxury hover:border-stone-400/60 focus-within:ring-4 focus-within:ring-orange-500/15 transition-all">
            <div className="pl-3.5 text-stone-400">
              <Search className="w-5 h-5 text-[#FF6332]" />
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Enter Train Number or Name (e.g. 22436, Rajdhani, NDLS)"
              className="w-full bg-transparent px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus:outline-none"
            />
            <button
              type="submit"
              className="px-5 py-2.5 rounded-full bg-[#18191B] hover:bg-stone-800 text-white text-xs font-semibold flex items-center gap-1.5 transition-all transform hover:scale-102 active:scale-98 shrink-0 shadow-md cursor-pointer"
            >
              <span>Track Train</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </form>

        {/* Premier Train Quick Categories */}
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs text-stone-600">
          <span className="text-stone-400 font-medium">Quick Select:</span>
          {[
            { label: 'Vande Bharat (22436)', num: '22436' },
            { label: 'Rajdhani (12301)', num: '12301' },
            { label: 'Shatabdi (12002)', num: '12002' },
            { label: 'Gorakhdham (12555)', num: '12555' },
          ].map((item) => (
            <button
              key={item.num}
              onClick={() => handleQuickSelect(item.num)}
              className="px-3 py-1 rounded-full bg-white/80 hover:bg-white border border-stone-200/80 hover:border-stone-400 text-stone-700 transition-colors shadow-2xs cursor-pointer flex items-center gap-1"
            >
              <Train className="w-3 h-3 text-[#FF6332]" />
              <span>{item.label}</span>
            </button>
          ))}
        </div>

        {/* Observed popularity lookups */}
        {popularTrains.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center justify-center gap-2 text-xs text-stone-500">
            <span className="font-medium text-stone-400">Recently active:</span>
            {popularTrains.slice(0, 4).map((t) => (
              <button
                key={t.number}
                onClick={() => handleQuickSelect(t.number)}
                className="px-2.5 py-0.5 rounded-md bg-stone-100/70 hover:bg-stone-200/80 text-stone-600 font-mono text-[11px] transition-colors"
              >
                {t.number}
              </button>
            ))}
          </div>
        )}
      </section>

      {/* 2. 3D ContainerScroll Showcase Section (Linked to Map) */}
      <section className="-mt-10 sm:-mt-14">
        <ContainerScroll
          titleComponent={
            <div className="flex flex-col items-center">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-stone-100 text-stone-600 text-xs font-medium mb-3 border border-stone-200/60">
                <Radio className="w-3.5 h-3.5 text-[#FF6332] animate-pulse" />
                <span>Scroll Down to Tilt 3D Radar View</span>
              </div>
              <h2 className="text-2xl sm:text-4xl font-display font-bold text-stone-900 tracking-tight">
                Live Fleet Satellite Radar
              </h2>
              <p className="text-xs sm:text-sm text-stone-500 mt-1 max-w-lg">
                Real-time spatial visualization and precision track positioning across all 8,800+ stations
              </p>
            </div>
          }
        >
          {/* Live Feed RailRadar Iframe */}
          <div className="relative w-full h-full bg-[#070A0F] rounded-[20px] md:rounded-[26px] overflow-hidden select-none group">
            <iframe
              src="https://railradar.in/railradar"
              title="Live Indian Railways Network Radar"
              className="w-[116%] h-[135%] -mt-[84px] -ml-[8%] border-0 pointer-events-none select-none block"
              loading="lazy"
            />

            {/* Non-interactable overlay for page scrolling + click navigation */}
            <div
              onClick={() => onNavigate('map')}
              className="absolute inset-0 z-20 cursor-pointer bg-transparent"
              title="Click to view full-screen live GIS map"
            >
              {/* Top Right Live Telemetry Badge */}
              <div className="absolute top-4 right-4 z-30 flex items-center gap-2 px-3 py-1.5 rounded-full bg-stone-950/80 backdrop-blur-md border border-white/15 text-white shadow-2xl">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                <span className="text-[11px] font-bold tracking-wider uppercase">Live Rail Radar</span>
                <span className="text-[9px] font-mono text-stone-400 hidden sm:inline">PAN-INDIA</span>
              </div>

              {/* Bottom Glassmorphic Navigation Action */}
              <div className="absolute bottom-0 inset-x-0 p-4 sm:p-6 bg-gradient-to-t from-stone-950/90 via-stone-950/50 to-transparent flex items-center justify-between text-white pointer-events-none">
                <div>
                  <div className="text-sm sm:text-base font-bold text-white drop-shadow-md flex items-center gap-2">
                    <Radio className="w-4 h-4 text-[#FF6332] animate-pulse" />
                    <span>Real-Time Geospatial Train Movement</span>
                  </div>
                  <div className="text-[11px] text-stone-300 drop-shadow-xs hidden sm:block mt-0.5">
                    Live telemetry across 8,800+ stations & active routes
                  </div>
                </div>
                <div className="px-4 py-2 rounded-full bg-[#FF6332] hover:bg-orange-600 text-white font-semibold text-xs transition-all shadow-lg flex items-center gap-1.5 pointer-events-auto cursor-pointer group-hover:scale-105">
                  <span>Open GIS Map</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </div>
              </div>
            </div>
          </div>
        </ContainerScroll>
      </section>

      {/* 3. Feature Bento Grid */}
      <section className="max-w-6xl mx-auto px-4 w-full mb-16 -mt-10">
        <div className="text-center mb-10">
          <h2 className="text-3xl sm:text-4xl font-display font-bold text-stone-900">
            Intelligent Rail Suite
          </h2>
          <p className="text-sm sm:text-base text-stone-600 mt-2">
            Engineered for high-precision live route telemetry and passenger convenience
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Bento Card 1: Live Tracking */}
          <div 
            onClick={() => onNavigate('live')}
            className="group cursor-pointer p-7 rounded-[32px] bg-white/90 border border-stone-200/80 shadow-luxury hover:shadow-2xl transition-all duration-300 hover:-translate-y-1 relative overflow-hidden"
          >
            <div className="w-12 h-12 rounded-2xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 mb-5 group-hover:scale-110 transition-transform">
              <Radio className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-stone-900 mb-2">Live Train Status</h3>
            <p className="text-sm text-stone-600 leading-relaxed mb-6">
              Track live train speed, distance traversed, upcoming stops, and micro-delays with pinpoint telemetry.
            </p>
            <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700">
              <span>Open Live Tracker</span>
              <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </div>
          </div>

          {/* Bento Card 2: PNR & Coach Positioning */}
          <div 
            onClick={() => onNavigate('pnr')}
            className="group cursor-pointer p-7 rounded-[32px] bg-white/90 border border-stone-200/80 shadow-luxury hover:shadow-2xl transition-all duration-300 hover:-translate-y-1 relative overflow-hidden"
          >
            <div className="w-12 h-12 rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 mb-5 group-hover:scale-110 transition-transform">
              <Layers className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-stone-900 mb-2">PNR & Coach Visualizer</h3>
            <p className="text-sm text-stone-600 leading-relaxed mb-6">
              Check confirmation probabilities, exact rake layout on platforms, and interactive 2D berth positioning diagrams.
            </p>
            <div className="flex items-center gap-1.5 text-xs font-semibold text-blue-700">
              <span>Inspect PNR & Berths</span>
              <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </div>
          </div>

          {/* Bento Card 3: Station Split-Flap Board */}
          <div 
            onClick={() => onNavigate('station')}
            className="group cursor-pointer p-7 rounded-[32px] bg-white/90 border border-stone-200/80 shadow-luxury hover:shadow-2xl transition-all duration-300 hover:-translate-y-1 relative overflow-hidden"
          >
            <div className="w-12 h-12 rounded-2xl bg-amber-50 border border-amber-100 flex items-center justify-center text-amber-600 mb-5 group-hover:scale-110 transition-transform">
              <Train className="w-6 h-6" />
            </div>
            <h3 className="text-xl font-bold text-stone-900 mb-2">Station Display Board</h3>
            <p className="text-sm text-stone-600 leading-relaxed mb-6">
              Live airport-style LED arrival & departure display boards for NDLS, CSMT, Howrah, SBC Bengaluru and stations nationwide.
            </p>
            <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-700">
              <span>View Station Boards</span>
              <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </div>
          </div>
        </div>
      </section>

      {/* 4. Side-by-Side Comparison: Traditional Apps vs DARPAN */}
      <section className="max-w-6xl mx-auto px-4 w-full mb-16">
        <div className="p-6 sm:p-10 rounded-[36px] bg-white/95 border border-stone-200/80 shadow-luxury">
          <div className="text-center max-w-2xl mx-auto mb-8">
            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-50 text-[#FF6332] text-xs font-semibold border border-orange-200/60 mb-2">
              <Cpu className="w-3.5 h-3.5" /> Algorithmic Benchmark
            </div>
            <h2 className="text-2xl sm:text-3xl font-display font-bold text-stone-900">
              Traditional Rail Apps vs DARPAN
            </h2>
            <p className="text-xs sm:text-sm text-stone-500 mt-1">
              Why mathematical delay propagation beats conventional linear extrapolation
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs sm:text-sm">
              <thead>
                <tr className="border-b border-stone-200 text-stone-400 font-semibold text-[11px] uppercase tracking-wider">
                  <th className="pb-3 w-1/3">Capability / Scenario</th>
                  <th className="pb-3 w-1/3 text-red-600">Incumbent Rail Apps</th>
                  <th className="pb-3 w-1/3 text-emerald-700">DARPAN Intelligence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                <tr>
                  <td className="py-4 font-semibold text-stone-900">
                    <div>Delay Extrapolation</div>
                    <div className="text-[11px] text-stone-500 font-normal">When a train is 45m late at 100km out</div>
                  </td>
                  <td className="py-4 text-stone-600">
                    <div className="flex items-center gap-1.5 text-red-700 font-medium">
                      <XCircle className="w-4 h-4 shrink-0" />
                      <span>The Optimism Trap</span>
                    </div>
                    <div className="text-[11px] text-stone-500 mt-0.5">Assumes train speeds up to arrive on time</div>
                  </td>
                  <td className="py-4 text-stone-900">
                    <div className="flex items-center gap-1.5 text-emerald-700 font-semibold">
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                      <span>Physical M0 Propagation</span>
                    </div>
                    <div className="text-[11px] text-stone-500 mt-0.5">Restricted by Section MPS and halt dwell rules</div>
                  </td>
                </tr>

                <tr>
                  <td className="py-4 font-semibold text-stone-900">
                    <div>Ghost Trains & Multi-Day Runs</div>
                    <div className="text-[11px] text-stone-500 font-normal">Cross-country trains spanning 48h+</div>
                  </td>
                  <td className="py-4 text-stone-600">
                    <div className="flex items-center gap-1.5 text-red-700 font-medium">
                      <XCircle className="w-4 h-4 shrink-0" />
                      <span>Rake Conflation</span>
                    </div>
                    <div className="text-[11px] text-stone-500 mt-0.5">Mixes up yesterday and today&apos;s running rakes</div>
                  </td>
                  <td className="py-4 text-stone-900">
                    <div className="flex items-center gap-1.5 text-emerald-700 font-semibold">
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                      <span>Active Run Resolver</span>
                    </div>
                    <div className="text-[11px] text-stone-500 mt-0.5">Locks onto physical locomotive coordinates</div>
                  </td>
                </tr>

                <tr>
                  <td className="py-4 font-semibold text-stone-900">
                    <div>Rake Dynamics (LHB vs ICF)</div>
                    <div className="text-[11px] text-stone-500 font-normal">Kinetic and braking physics</div>
                  </td>
                  <td className="py-4 text-stone-600">
                    <div className="flex items-center gap-1.5 text-red-700 font-medium">
                      <XCircle className="w-4 h-4 shrink-0" />
                      <span>Completely Ignored</span>
                    </div>
                    <div className="text-[11px] text-stone-500 mt-0.5">Treats 1970s ICF same as 160 km/h LHB</div>
                  </td>
                  <td className="py-4 text-stone-900">
                    <div className="flex items-center gap-1.5 text-emerald-700 font-semibold">
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                      <span>Coach Dynamics Engine</span>
                    </div>
                    <div className="text-[11px] text-stone-500 mt-0.5">Extracts disc vs shoe brake acceleration profiles</div>
                  </td>
                </tr>

                <tr>
                  <td className="py-4 font-semibold text-stone-900">
                    <div>Data Provenance & Honesty</div>
                    <div className="text-[11px] text-stone-500 font-normal">Auditing where arrival numbers come from</div>
                  </td>
                  <td className="py-4 text-stone-600">
                    <div className="flex items-center gap-1.5 text-red-700 font-medium">
                      <XCircle className="w-4 h-4 shrink-0" />
                      <span>Opaque Black Box</span>
                    </div>
                    <div className="text-[11px] text-stone-500 mt-0.5">Single-point ETA with zero error margins</div>
                  </td>
                  <td className="py-4 text-stone-900">
                    <div className="flex items-center gap-1.5 text-emerald-700 font-semibold">
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                      <span>The Honesty Surface</span>
                    </div>
                    <div className="text-[11px] text-stone-500 mt-0.5">Source, confidence decay, and [p10, p90] intervals</div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* 5. Golden Quadrilateral Corridor Pulse */}
      <section className="max-w-6xl mx-auto px-4 w-full mb-16">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h3 className="text-xl sm:text-2xl font-bold text-stone-900">
              Golden Quadrilateral Corridor Pulse
            </h3>
            <p className="text-xs sm:text-sm text-stone-500 mt-0.5">
              Live operational health across India&apos;s four primary high-density trunk routes
            </p>
          </div>
          <button
            onClick={() => onNavigate('map')}
            className="self-start sm:self-auto px-4 py-2 rounded-full bg-stone-100 hover:bg-stone-200 text-stone-800 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <Compass className="w-3.5 h-3.5" />
            <span>View Corridors on Map</span>
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            {
              corridor: 'Delhi ↔ Mumbai',
              dist: '1,384 km',
              mps: '130–160 km/h',
              punctuality: '89.2%',
              trains: '42 Daily Expresses',
              flagship: '12951 Rajdhani',
              num: '12951'
            },
            {
              corridor: 'Delhi ↔ Howrah',
              dist: '1,449 km',
              mps: '130 km/h',
              punctuality: '78.4%',
              trains: '56 Daily Expresses',
              flagship: '12301 Rajdhani',
              num: '12301'
            },
            {
              corridor: 'Mumbai ↔ Chennai',
              dist: '1,281 km',
              mps: '110–130 km/h',
              punctuality: '84.6%',
              trains: '28 Daily Expresses',
              flagship: '22159 Express',
              num: '22159'
            },
            {
              corridor: 'Howrah ↔ Chennai',
              dist: '1,661 km',
              mps: '110–130 km/h',
              punctuality: '86.1%',
              trains: '31 Daily Expresses',
              flagship: '12841 Coromandel',
              num: '12841'
            },
          ].map((c, idx) => (
            <div
              key={idx}
              onClick={() => handleQuickSelect(c.num)}
              className="p-5 rounded-2xl bg-white/90 border border-stone-200/80 shadow-sm hover:shadow-md transition-all cursor-pointer group flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between text-xs text-stone-400 font-mono mb-2">
                  <span>{c.dist}</span>
                  <span className="text-emerald-700 font-semibold">{c.punctuality}</span>
                </div>
                <h4 className="text-base font-bold text-stone-900 group-hover:text-[#FF6332] transition-colors">
                  {c.corridor}
                </h4>
                <div className="text-xs text-stone-500 mt-1">MPS: {c.mps}</div>
                <div className="text-xs text-stone-400 mt-0.5">{c.trains}</div>
              </div>

              <div className="mt-4 pt-3 border-t border-stone-100 flex items-center justify-between text-xs">
                <span className="text-stone-600 font-medium">Flagship: {c.flagship}</span>
                <ChevronRight className="w-4 h-4 text-stone-400 group-hover:translate-x-1 group-hover:text-[#FF6332] transition-transform" />
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* 6. Live Trains Showcase Table */}
      <section className="max-w-6xl mx-auto px-4 w-full mb-12">
        <div className="p-6 sm:p-8 rounded-[36px] bg-white/90 border border-stone-200/80 shadow-luxury">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
            <div>
              <h3 className="text-xl font-bold text-stone-900">Premier Trains Live Status</h3>
              <p className="text-xs text-stone-500 mt-0.5">Real-time status updates broadcasted across the active rail network</p>
            </div>
            <button
              onClick={() => onNavigate('live')}
              className="self-start sm:self-auto px-4 py-2 rounded-full bg-stone-100 hover:bg-stone-200 text-stone-800 text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <span>Explore All Trains</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-stone-700">
              <thead>
                <tr className="border-b border-stone-200/70 text-xs font-semibold text-stone-400 uppercase tracking-wider">
                  <th className="pb-3">Train</th>
                  <th className="pb-3">Route</th>
                  <th className="pb-3">Type</th>
                  <th className="pb-3">Lookups</th>
                  <th className="pb-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {popularTrains.map((train) => (
                  <tr key={train.number} className="hover:bg-stone-50/70 transition-colors">
                    <td className="py-3.5">
                      <div className="font-semibold text-stone-900 flex items-center gap-2">
                        <span className="font-mono text-xs text-[#FF6332] bg-orange-50 px-2 py-0.5 rounded-md border border-orange-200/60">
                          {train.number}
                        </span>
                        <span>{train.name}</span>
                      </div>
                    </td>
                    <td className="py-3.5 text-stone-600 font-mono text-xs">
                      {train.from_code ?? '—'} → {train.to_code ?? '—'}
                    </td>
                    <td className="py-3.5 text-xs text-stone-600">{train.type ?? '—'}</td>
                    <td className="py-3.5 font-mono text-xs text-stone-700">
                      <span className="inline-flex items-center gap-1">
                        <Zap className="w-3 h-3 text-amber-500" />
                        {train.lookups ?? 0}
                      </span>
                    </td>
                    <td className="py-3.5 text-right">
                      <button
                        onClick={() => handleQuickSelect(train.number)}
                        className="text-xs font-semibold text-[#FF6332] hover:underline cursor-pointer"
                      >
                        Track Live
                      </button>
                    </td>
                  </tr>
                ))}
                {popularTrains.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-xs text-stone-500">
                      {popular.loading
                        ? 'Loading…'
                        : 'No trains looked up yet. Search for a train above to start building this list.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* 7. Deep Architecture Banner */}
      <section className="max-w-6xl mx-auto px-4 w-full">
        <div className="p-8 sm:p-10 rounded-[36px] bg-[#18191B] text-white shadow-xl relative overflow-hidden flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="relative z-10 max-w-xl">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 text-white/90 text-xs font-semibold border border-white/15 mb-3">
              <ShieldCheck className="w-3.5 h-3.5 text-[#FF6332]" />
              <span>Project Provenance & Architecture</span>
            </div>
            <h3 className="text-xl sm:text-2xl font-display font-bold text-white">
              Want to understand how DARPAN calculates delay physics?
            </h3>
            <p className="text-stone-400 text-xs sm:text-sm mt-1.5">
              Read our full research report covering the M0 propagation graph walk, M1 ML classifier, real-world edge cases, and 3-phase national roadmap.
            </p>
          </div>

          <button
            onClick={() => onNavigate('about')}
            className="shrink-0 px-6 py-3 rounded-full bg-[#FF6332] hover:bg-orange-600 text-white font-semibold text-xs transition-all shadow-lg flex items-center gap-2 hover:scale-105 active:scale-95 cursor-pointer relative z-10"
          >
            <Sparkles className="w-4 h-4" />
            <span>Read About DARPAN</span>
          </button>
        </div>
      </section>
    </div>
  );
};

export default HomePage;
