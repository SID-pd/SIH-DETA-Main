/**
 * Radar View — Live Spatial Radar embedded from RailRadar
 *
 * Engineered with:
 * 1. Exact top-left searchbox cover overlay with custom DARPAN branding and About Page quick launcher.
 * 2. Strict sandbox & Permissions Policy blocking Google One Tap / sign-in popups while permitting geolocation.
 * 3. Responsive breakpoint alignment (Desktop: 480px, Tablet: 400px, Mobile: 90vw).
 */

import React, { useState, useEffect } from 'react';
import { RefreshCw, Radar, AlertTriangle, Home } from 'lucide-react';
import { PageId } from '../components/RadioNavbar';

interface RadarPageProps {
  onNavigate?: (page: PageId) => void;
}

const RADAR_URL = 'https://railradar.in/railradar';
const LOAD_TIMEOUT_MS = 15000;

export const RadarPage: React.FC<RadarPageProps> = ({ onNavigate }) => {
  const [frameKey, setFrameKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setLoading(true);
    setFailed(false);
    const id = setTimeout(() => {
      setLoading((stillLoading) => {
        if (stillLoading) setFailed(true);
        return stillLoading;
      });
    }, LOAD_TIMEOUT_MS);
    return () => clearTimeout(id);
  }, [frameKey]);

  const reload = () => {
    setLoading(true);
    setFailed(false);
    setFrameKey((k) => k + 1);
  };

  return (
    <div className="radar-iframe-container fixed inset-0 z-0 bg-[#070A0F] w-screen h-screen overflow-hidden select-none box-border">
      {/* 
        Base Element: Iframe loaded at full 100% viewport.
        Strict Security & Policy to block Google Sign-In popups & FedCM One-Tap:
        - sandbox lacks 'allow-popups' and 'allow-modals': completely prevents OAuth popup windows.
        - identity-credentials-get 'none': disables FedCM auto-sign-in prompts.
        - geolocation 'src': preserves user location permissions.
      */}
      <iframe
        key={frameKey}
        src={RADAR_URL}
        title="RailRadar Live Network Radar"
        onLoad={() => {
          setLoading(false);
          setFailed(false);
        }}
        onError={() => {
          setLoading(false);
          setFailed(true);
        }}
        className="w-full h-full border-0 block relative z-0"
        sandbox="allow-scripts allow-same-origin allow-forms"
        referrerPolicy="no-referrer"
        loading="lazy"
        allow="geolocation 'src'; identity-credentials-get 'none'; publickey-credentials-get 'none'; otp-credentials 'none'; payment 'none'; camera 'none'; microphone 'none'"
      />

      {/* Loading Overlay */}
      {loading && !failed && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#0A0D14] text-stone-300 gap-3 pointer-events-none">
          <Radar className="w-10 h-10 animate-pulse text-emerald-400" />
          <div className="text-center">
            <p className="text-sm font-semibold text-[#f8f9fa]">
              Connecting to Indian Railways Spatial Network…
            </p>
            <p className="text-xs text-stone-500 mt-0.5">
              Streaming real-time positioning beacons
            </p>
          </div>
        </div>
      )}

      {/* Failed State Overlay */}
      {failed && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-[#0A0D14] text-center px-6 gap-3 pointer-events-auto">
          <AlertTriangle className="w-10 h-10 text-amber-400" />
          <h3 className="text-lg font-display font-bold text-stone-100">
            RailRadar Map Could Not Be Loaded
          </h3>
          <p className="text-xs sm:text-sm text-stone-400 max-w-md">
            The external stream may be temporarily blocked by your browser network or security settings.
          </p>
          <div className="flex items-center gap-3 mt-2">
            <button
              onClick={reload}
              className="px-5 py-2.5 rounded-full bg-white/10 hover:bg-white/20 border border-white/15 text-stone-100 text-xs font-semibold inline-flex items-center gap-2 transition-colors cursor-pointer"
            >
              <RefreshCw className="w-3.5 h-3.5" /> Retry Connection
            </button>
            <button
              onClick={() => onNavigate && onNavigate('home')}
              className="px-5 py-2.5 rounded-full bg-[#FF6332] hover:bg-orange-600 text-white text-xs font-semibold inline-flex items-center gap-2 transition-colors shadow-lg cursor-pointer"
            >
              <Home className="w-3.5 h-3.5" /> Back to Home
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default RadarPage;
