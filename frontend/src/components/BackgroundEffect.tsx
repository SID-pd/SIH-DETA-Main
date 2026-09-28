import React from 'react';

export const BackgroundEffect: React.FC = () => {
  return (
    <div className="fixed inset-0 pointer-events-none -z-10 overflow-hidden bg-[#FAF7F2]">
      {/* SVG Grid Pattern */}
      <svg
        aria-hidden="true"
        className="absolute inset-0 h-full w-full stroke-stone-900/[0.04] [mask-image:radial-gradient(ellipse_at_center,white_40%,transparent_85%)]"
      >
        <defs>
          <pattern
            id="nomu-bg-pattern"
            width="48"
            height="48"
            patternUnits="userSpaceOnUse"
          >
            <path d="M.5 48V.5H48" fill="none" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" strokeWidth="0" fill="url(#nomu-bg-pattern)" />
      </svg>

      {/* Warm Ambient Blobs inspired by nomu.store */}
      <div 
        className="absolute -top-[20%] left-1/2 -translate-x-1/2 w-[900px] h-[500px] rounded-full blur-[140px] opacity-40 pointer-events-none"
        style={{
          background: 'radial-gradient(circle, rgba(255,116,72,0.3) 0%, rgba(251,191,36,0.18) 50%, transparent 80%)'
        }}
      />
      
      <div 
        className="absolute top-[40%] -left-[10%] w-[600px] h-[600px] rounded-full blur-[150px] opacity-25 pointer-events-none"
        style={{
          background: 'radial-gradient(circle, rgba(37,99,235,0.15) 0%, rgba(147,197,253,0.05) 70%, transparent 80%)'
        }}
      />

      <div 
        className="absolute top-[65%] -right-[10%] w-[700px] h-[550px] rounded-full blur-[160px] opacity-30 pointer-events-none"
        style={{
          background: 'radial-gradient(circle, rgba(255,138,76,0.2) 0%, rgba(245,158,11,0.12) 60%, transparent 80%)'
        }}
      />

      {/* Subtle organic vignetting */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[#FAF7F2]/60" />
    </div>
  );
};
