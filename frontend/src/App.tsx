import React, { useState, useEffect } from 'react';
import { BackgroundEffect } from './components/BackgroundEffect';
import { Header } from './components/Header';
import { PageId } from './components/RadioNavbar';
import { HomePage } from './pages/HomePage';
import { LivePage } from './pages/LivePage';
import { PnrPage } from './pages/PnrPage';
import { StationPage } from './pages/StationPage';
import { MapPage } from './pages/MapPage';
import { RadarPage } from './pages/RadarPage';
import { AboutPage } from './pages/AboutPage';
import { IntroSplash } from './components/IntroSplash';
import { AnimatePresence, motion } from 'framer-motion';

export const App: React.FC = () => {
  const [activePage, setActivePage] = useState<PageId>('home');
  // First-time load intro animation flag (session-based)
  const [showSplash, setShowSplash] = useState<boolean>(() => {
    try {
      return !sessionStorage.getItem('darpan_intro_seen');
    } catch {
      return false;
    }
  });

  const handleSplashComplete = () => {
    try {
      sessionStorage.setItem('darpan_intro_seen', '1');
    } catch {}
    setShowSplash(false);
  };

  // H12: was hardcoded to '22436'. The Live page now opens in a search-first empty
  // state, so no train is implied before the user asks for one.
  const [trackedTrain, setTrackedTrain] = useState<string>('');
  const [trackedDate, setTrackedDate] = useState<string>('');

  // Smooth scroll to top when page changes
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [activePage]);

  const handleSearchTrainFromHome = (query: string) => {
    setTrackedTrain(query);
    setTrackedDate('');
    setActivePage('live');
  };

  const isFullScreen = activePage === 'map' || activePage === 'radar';

  return (
    <div className={`relative min-h-screen selection:bg-[#FF6332] selection:text-white ${isFullScreen ? 'overflow-hidden bg-[#070A0F]' : ''}`}>
      {/* First-time load cinematic intro animation */}
      <AnimatePresence>
        {showSplash && (
          <IntroSplash onComplete={handleSplashComplete} />
        )}
      </AnimatePresence>

      {/* Warm Ambient Background (nomu.store inspired) — hidden on full-screen map/radar */}
      {!isFullScreen && <BackgroundEffect />}

      {/* Floating Radio Sliding Top Navbar */}
      <Header
        activePage={activePage}
        onSelectPage={setActivePage}
      />

      {/* Main Content Pages with smooth fade/slide transition */}
      <main className={isFullScreen ? 'fixed inset-0 w-screen h-screen overflow-hidden' : 'w-full pt-16 sm:pt-20'}>
        <AnimatePresence mode="wait">
          {activePage === 'home' && (
            <motion.div
              key="home"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.2 }}
            >
              <HomePage
                onNavigate={setActivePage}
                onSearchTrain={handleSearchTrainFromHome}
              />
            </motion.div>
          )}

          {activePage === 'live' && (
            <motion.div
              key="live"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.2 }}
            >
              <LivePage
                initialTrainQuery={trackedTrain}
                initialDate={trackedDate}
                onTrainChange={(num, date) => {
                  if (num) setTrackedTrain(num);
                  if (date !== undefined) setTrackedDate(date);
                }}
                onViewMap={(num, date) => {
                  if (num) setTrackedTrain(num);
                  if (date !== undefined) setTrackedDate(date);
                  setActivePage('map');
                }}
              />
            </motion.div>
          )}

          {activePage === 'pnr' && (
            <motion.div
              key="pnr"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.2 }}
            >
              <PnrPage />
            </motion.div>
          )}

          {activePage === 'station' && (
            <motion.div
              key="station"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.2 }}
            >
              <StationPage />
            </motion.div>
          )}

          {activePage === 'radar' && (
            <motion.div
              key="radar"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="fixed inset-0 w-screen h-screen overflow-hidden"
            >
              <RadarPage onNavigate={setActivePage} />
            </motion.div>
          )}

          {activePage === 'about' && (
            <motion.div
              key="about"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -12 }}
              transition={{ duration: 0.2 }}
            >
              <AboutPage onNavigate={setActivePage} />
            </motion.div>
          )}

          {activePage === 'map' && (
            <motion.div
              key="map"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="fixed inset-0 w-screen h-screen overflow-hidden"
            >
              <MapPage
                initialTrainQuery={trackedTrain}
                initialDate={trackedDate}
                onTrainChange={(num, date) => {
                  setTrackedTrain(num);
                  if (date !== undefined) setTrackedDate(date);
                }}
                onViewLive={(num, date) => {
                  if (num) setTrackedTrain(num);
                  if (date !== undefined) setTrackedDate(date);
                  setActivePage('live');
                }}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
};

export default App;
