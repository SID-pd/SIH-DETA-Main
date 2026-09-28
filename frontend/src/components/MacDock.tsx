import React, { useRef } from 'react';
import { motion, useMotionValue, useSpring, useTransform, MotionValue } from 'framer-motion';
import { Home, Radio, Ticket, Building2, MapPin, Compass, Sparkles } from 'lucide-react';

export type PageId = 'home' | 'live' | 'pnr' | 'station' | 'map';

interface DockItemProps {
  mouseX: MotionValue<number>;
  label: string;
  icon: React.ReactNode;
  isActive: boolean;
  onClick: () => void;
  badge?: string;
}

const DockIcon: React.FC<DockItemProps> = ({ mouseX, label, icon, isActive, onClick, badge }) => {
  const ref = useRef<HTMLButtonElement>(null);

  const distance = useTransform(mouseX, (val: number) => {
    const bounds = ref.current?.getBoundingClientRect() ?? { x: 0, width: 0 };
    return val - bounds.x - bounds.width / 2;
  });

  // Dynamic magnification mapping inspired by macOS dock
  const widthSync = useTransform(distance, [-120, 0, 120], [48, 72, 48]);
  const width = useSpring(widthSync, { mass: 0.1, stiffness: 220, damping: 14 });

  const [isHovered, setIsHovered] = React.useState(false);

  return (
    <div className="relative flex flex-col items-center group">
      {/* macOS Style Hover Tooltip */}
      {isHovered && (
        <motion.div
          initial={{ opacity: 0, y: 6, scale: 0.9 }}
          animate={{ opacity: 1, y: -10, scale: 1 }}
          exit={{ opacity: 0, y: 6, scale: 0.9 }}
          transition={{ duration: 0.15 }}
          className="absolute -top-10 px-3 py-1 rounded-full bg-[#18191B]/90 backdrop-blur-md text-white text-[11px] font-medium tracking-wide shadow-xl border border-white/10 whitespace-nowrap pointer-events-none z-50 flex items-center gap-1.5"
        >
          <span>{label}</span>
          {badge && (
            <span className="bg-[#FF6332] text-white text-[9px] px-1.5 py-0.2 rounded-full font-bold">
              {badge}
            </span>
          )}
        </motion.div>
      )}

      {/* Dock Item Icon Button */}
      <motion.button
        ref={ref}
        style={{ width, height: width }}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        onClick={onClick}
        whileTap={{ scale: 0.85, y: -4 }}
        className={`relative flex items-center justify-center rounded-2xl transition-all duration-200 ${
          isActive
            ? 'bg-gradient-to-b from-stone-900 to-stone-800 text-white shadow-lg shadow-black/20 border border-stone-700/80 ring-2 ring-stone-900/10'
            : 'bg-white/80 hover:bg-white text-stone-700 hover:text-stone-900 border border-stone-200/80 shadow-sm'
        }`}
        aria-label={label}
      >
        <div className="flex items-center justify-center w-full h-full p-2">
          {icon}
        </div>

        {/* Badge on Icon if any */}
        {badge && !isActive && (
          <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-[#FF6332] rounded-full border-2 border-white animate-pulse" />
        )}
      </motion.button>

      {/* macOS Active App Indicator Dot */}
      <div className="h-1.5 flex items-center justify-center mt-1">
        {isActive ? (
          <motion.div
            layoutId="active-dock-dot"
            className="w-1.5 h-1.5 rounded-full bg-stone-900 shadow-sm"
          />
        ) : (
          <div className="w-1.5 h-1.5" />
        )}
      </div>
    </div>
  );
};

interface MacDockProps {
  activePage: PageId;
  onSelectPage: (page: PageId) => void;
}

export const MacDock: React.FC<MacDockProps> = ({ activePage, onSelectPage }) => {
  const mouseX = useMotionValue(Infinity);

  const dockItems: Array<{
    id: PageId;
    label: string;
    icon: React.ReactNode;
    badge?: string;
  }> = [
    {
      id: 'home',
      label: 'Homepage',
      icon: <Home className="w-5 h-5 sm:w-6 sm:h-6" />,
    },
    {
      id: 'live',
      label: 'Live Tracking',
      icon: <Radio className="w-5 h-5 sm:w-6 sm:h-6 text-emerald-500" />,
      badge: 'LIVE',
    },
    {
      id: 'pnr',
      label: 'PNR Status & Coach',
      icon: <Ticket className="w-5 h-5 sm:w-6 sm:h-6 text-blue-500" />,
    },
    {
      id: 'station',
      label: 'Station Board',
      icon: <Building2 className="w-5 h-5 sm:w-6 sm:h-6 text-amber-500" />,
    },
    {
      id: 'map',
      label: 'Full Map Radar',
      icon: <Compass className="w-5 h-5 sm:w-6 sm:h-6 text-purple-500 animate-spin-slow" />,
    },
  ];

  return (
    <div className="fixed bottom-3 sm:bottom-6 left-1/2 -translate-x-1/2 z-50 select-none">
      <motion.div
        initial={{ y: 50, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ type: 'spring', stiffness: 260, damping: 20 }}
        onMouseMove={(e) => mouseX.set(e.pageX)}
        onMouseLeave={() => mouseX.set(Infinity)}
        className="flex items-end gap-2.5 sm:gap-3.5 px-4 sm:px-6 py-2 rounded-[28px] glass-dock shadow-2xl backdrop-blur-2xl"
      >
        {dockItems.map((item) => (
          <DockIcon
            key={item.id}
            mouseX={mouseX}
            label={item.label}
            icon={item.icon}
            badge={item.badge}
            isActive={activePage === item.id}
            onClick={() => onSelectPage(item.id)}
          />
        ))}

        {/* Separator */}
        <div className="h-8 w-[1px] bg-stone-300/70 self-center mx-1 sm:mx-1.5" />

        {/* Quick Help / Pulse Indicator */}
        <button
          onClick={() => onSelectPage('map')}
          title="Live Indian Railways Radar Grid"
          className="relative flex items-center justify-center w-10 h-10 sm:w-11 sm:h-11 rounded-2xl bg-orange-50 hover:bg-orange-100 border border-orange-200/80 text-[#FF6332] shadow-sm transition-all transform hover:scale-105"
        >
          <Sparkles className="w-4 h-4 sm:w-5 sm:h-5 animate-pulse" />
        </button>
      </motion.div>
    </div>
  );
};
