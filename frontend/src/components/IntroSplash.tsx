import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Train, ShieldCheck, Zap, Radio, ChevronRight } from 'lucide-react';

interface IntroSplashProps {
  onComplete: () => void;
}

export const IntroSplash: React.FC<IntroSplashProps> = ({ onComplete }) => {
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState('BOOTING TELEMETRY KERNEL...');

  useEffect(() => {
    // Progress counter animation
    const startTime = Date.now();
    const duration = 2200; // 2.2s total

    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const pct = Math.min(100, Math.round((elapsed / duration) * 100));
      setProgress(pct);

      if (pct < 30) {
        setStatusText('INITIALIZING IRCTC SPATIAL NODES...');
      } else if (pct < 65) {
        setStatusText('CALIBRATING 8,818 STATIONS & M0 GRAPH...');
      } else if (pct < 90) {
        setStatusText('SECURING ENCRYPTED SATELLITE BEACONS...');
      } else {
        setStatusText('SYSTEM ONLINE — WELCOME TO DARPAN');
      }

      if (elapsed >= duration) {
        clearInterval(interval);
        setTimeout(onComplete, 350); // slight pause at 100% before exit
      }
    }, 25);

    // Keyboard 'Escape' to skip immediately
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onComplete();
    };
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      clearInterval(interval);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [onComplete]);

  return (
    <motion.div
      initial={{ opacity: 1 }}
      exit={{ opacity: 0, scale: 1.04, filter: 'blur(10px)' }}
      transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-[#07090E] text-white overflow-hidden select-none cursor-pointer"
      onClick={onComplete}
    >
      {/* Background Radial Ambient Glow */}
      <div 
        className="absolute inset-0 pointer-events-none opacity-40"
        style={{
          background: 'radial-gradient(circle at 50% 45%, rgba(255, 99, 50, 0.18) 0%, rgba(56, 189, 248, 0.08) 35%, transparent 70%)',
        }}
      />

      {/* Futuristic Grid Pattern */}
      <div 
        className="absolute inset-0 pointer-events-none opacity-[0.035]"
        style={{
          backgroundImage: `linear-gradient(to right, #ffffff 1px, transparent 1px), linear-gradient(to bottom, #ffffff 1px, transparent 1px)`,
          backgroundSize: '48px 48px',
        }}
      />

      {/* Skip Button (Top Right) */}
      <motion.button
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        onClick={(e) => {
          e.stopPropagation();
          onComplete();
        }}
        className="absolute top-6 right-6 z-20 px-3.5 py-1.5 rounded-full bg-white/5 hover:bg-white/15 border border-white/10 text-stone-400 hover:text-white text-xs font-mono tracking-wider transition-all flex items-center gap-1.5 cursor-pointer"
      >
        <span>SKIP INTRO</span>
        <ChevronRight className="w-3 h-3 text-[#FF6332]" />
      </motion.button>

      {/* Center Cinematic Container */}
      <div className="relative z-10 flex flex-col items-center text-center px-4 max-w-lg w-full">
        {/* Animated Sonar Radar Beacon & Icon */}
        <div className="relative mb-6 flex items-center justify-center">
          {/* Radar Ring 1 */}
          <motion.div
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: [1, 1.4, 1], opacity: [0.2, 0.6, 0.2] }}
            transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
            className="absolute w-28 h-28 rounded-full border border-[#FF6332]/30 pointer-events-none"
          />
          {/* Radar Ring 2 */}
          <motion.div
            initial={{ scale: 0.6, opacity: 0 }}
            animate={{ scale: [1, 1.8, 1], opacity: [0.1, 0.4, 0.1] }}
            transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut', delay: 0.4 }}
            className="absolute w-36 h-36 rounded-full border border-sky-500/20 pointer-events-none"
          />

          {/* Rotating Reticle */}
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 10, repeat: Infinity, ease: 'linear' }}
            className="absolute w-24 h-24 rounded-full border border-dashed border-white/15 pointer-events-none"
          />

          {/* Core Train Icon Badge */}
          <motion.div
            initial={{ scale: 0, rotate: -20 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ type: 'spring', damping: 14, stiffness: 120 }}
            className="relative w-16 h-16 rounded-2xl bg-gradient-to-br from-stone-900 to-black border border-white/15 shadow-2xl flex items-center justify-center shadow-orange-500/20"
          >
            <Train className="w-8 h-8 text-[#FF6332]" />
            {/* Live Beacon Dot */}
            <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-emerald-500 border-2 border-[#07090E] animate-pulse" />
          </motion.div>
        </div>

        {/* High-Speed Track Laser Streak SVG */}
        <div className="w-full max-w-xs h-3 relative my-2 overflow-hidden">
          <svg className="w-full h-full" viewBox="0 0 320 12" fill="none">
            {/* Rail Lines */}
            <line x1="0" y1="3" x2="320" y2="3" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
            <line x1="0" y1="9" x2="320" y2="9" stroke="rgba(255,255,255,0.08)" strokeWidth="1" />
            {/* Sleepers */}
            {[...Array(16)].map((_, i) => (
              <line 
                key={i} 
                x1={i * 20 + 10} 
                y1="1" 
                x2={i * 20 + 10} 
                y2="11" 
                stroke="rgba(255,255,255,0.06)" 
                strokeWidth="1.5" 
              />
            ))}
            {/* High-speed Laser Pulse */}
            <motion.line
              x1="0"
              y1="6"
              x2="80"
              y2="6"
              stroke="url(#pulse-grad)"
              strokeWidth="2.5"
              strokeLinecap="round"
              initial={{ x: -100 }}
              animate={{ x: 360 }}
              transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
            />
            <defs>
              <linearGradient id="pulse-grad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#FF6332" stopOpacity="0" />
                <stop offset="50%" stopColor="#FF6332" stopOpacity="1" />
                <stop offset="100%" stopColor="#38BDF8" stopOpacity="1" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* Title & Brand Reveal */}
        <motion.div
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
        >
          <div className="flex items-center justify-center gap-3">
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-[0.25em] uppercase font-display bg-gradient-to-r from-white via-stone-100 to-stone-400 bg-clip-text text-transparent">
              DARPAN
            </h1>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-[#FF6332]/20 border border-[#FF6332]/40 text-[#FF6332]">
              v2.4
            </span>
          </div>
          <p className="text-[11px] sm:text-xs font-medium tracking-wider text-stone-400 mt-1.5 uppercase">
            Dynamic Arrival & Real-Time Predictive Analytics Network
          </p>
        </motion.div>

        {/* Telemetry Progress Indicator */}
        <div className="w-full max-w-xs mt-6">
          {/* Progress Bar Track */}
          <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden p-[1px]">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-[#FF6332] via-amber-400 to-sky-400"
              style={{ width: `${progress}%` }}
              transition={{ ease: 'easeOut' }}
            />
          </div>

          {/* Telemetry Status Log */}
          <div className="flex items-center justify-between text-[10px] font-mono text-stone-500 mt-2">
            <span className="flex items-center gap-1 text-stone-300">
              <Radio className="w-2.5 h-2.5 text-emerald-400 animate-pulse" />
              <span>{statusText}</span>
            </span>
            <span className="text-[#FF6332] font-semibold">{progress}%</span>
          </div>
        </div>

        {/* Bottom Feature Badges */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="flex items-center justify-center gap-4 mt-8 text-[11px] font-mono text-stone-500"
        >
          <span className="flex items-center gap-1">
            <Zap className="w-3 h-3 text-amber-400" />
            <span>M0 Propagation</span>
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 text-emerald-400" />
            <span>Honesty Surface</span>
          </span>
        </motion.div>
      </div>
    </motion.div>
  );
};

export default IntroSplash;
