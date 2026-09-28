import React from 'react';
import { Train, Sparkles } from 'lucide-react';
import { PageId, RadioNavbar } from './RadioNavbar';

interface HeaderProps {
  activePage: PageId;
  onSelectPage: (page: PageId) => void;
}

export const Header: React.FC<HeaderProps> = ({ activePage, onSelectPage }) => {
  const isFullScreen = activePage === 'radar' || activePage === 'map';
  const showSideWidgets = !isFullScreen;

  return (
    <header className="fixed top-3 sm:top-3.5 left-0 right-0 z-50 w-full px-3 sm:px-6 pointer-events-none">
      <div className="w-full max-w-7xl mx-auto grid grid-cols-[1fr_auto_1fr] items-center">
        {/* Left Column: Brand Logo Widget (Home, Live, PNR, Station, About) */}
        <div className="justify-self-start pointer-events-auto">
          {showSideWidgets ? (
            <div 
              onClick={() => onSelectPage('home')}
              className="flex items-center gap-2 sm:gap-2.5 cursor-pointer group select-none px-2.5 sm:px-3 py-1.5 rounded-full bg-white/85 border border-stone-200/80 shadow-sm backdrop-blur-md hover:bg-white transition-all shrink-0"
              title="DARPAN Home"
            >
              <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-xl bg-[#18191B] text-white flex items-center justify-center shadow-xs group-hover:scale-105 transition-transform">
                <Train className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-[#FF6332]" />
              </div>
              <span className="font-display font-extrabold text-base sm:text-lg tracking-wider text-stone-900 pr-1 hidden sm:inline">
                DARPAN
              </span>
            </div>
          ) : (
            <div className="w-8 h-8 sm:w-10 sm:h-10 opacity-0 pointer-events-none" />
          )}
        </div>

        {/* Center Column: RadioNavbar — Mathematically locked at 50% dead center on EVERY page */}
        <div className="justify-self-center pointer-events-auto">
          <RadioNavbar activePage={activePage} onSelectPage={onSelectPage} />
        </div>

        {/* Right Column: About Button (Home, Live, PNR, Station, About) */}
        <div className="justify-self-end pointer-events-auto">
          {showSideWidgets ? (
            <button
              onClick={() => onSelectPage('about')}
              className={`hidden sm:flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-semibold shadow-sm transition-all transform hover:scale-105 active:scale-95 cursor-pointer ${
                activePage === 'about'
                  ? 'bg-[#FF6332] text-white shadow-orange-500/20'
                  : 'bg-[#18191B] hover:bg-stone-800 text-white'
              }`}
            >
              <Sparkles className={`w-3.5 h-3.5 ${activePage === 'about' ? 'text-white' : 'text-[#FF6332]'}`} />
              <span>About DARPAN</span>
            </button>
          ) : (
            <div className="w-8 h-8 sm:w-10 sm:h-10 opacity-0 pointer-events-none hidden sm:block" />
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;
