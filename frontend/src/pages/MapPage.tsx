/**
 * Full-Screen Route Map & Live Geospatial Radar with Leaflet.js
 *
 * Immersive GIS experience featuring:
 * - Real Basemap Tile Layers: CartoDB Voyager, Esri Satellite, CartoDB Dark
 * - Sequence-aware dual-tone track progression (emerald green passed vs dashed slate upcoming)
 * - Multi-tier station breakpoints by zoom level (Major hubs at low zoom, commercial halts at mid zoom, passing loops at high zoom)
 * - Aerodynamic professional locomotive marker with live sonar radar pulse & delay badge
 * - Floating glassmorphic Live Telemetry HUD with train search, multi-day run selector, and coach layout
 * - Floating top navigation division integration with zero layout bleed
 */

import React, { useMemo, useState, useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  Search, RefreshCw, ZoomIn, ZoomOut, Maximize2,
  Crosshair, Radio, CheckCircle2, Clock, MapPin, Gauge,
  ArrowRight, Layers, TrainFront, ChevronDown, ChevronUp, Eye, EyeOff,
  ExternalLink, Calendar, Filter, X, ChevronLeft, ChevronRight, Globe, Sparkles,
  Plus, Minus,
} from 'lucide-react';
import { api, fmtDelay, fmtTime, type Stop, type RunOption } from '../lib/api';
import { useDebounced, useQuery } from '../hooks/useApi';
import { LoadingCard } from '../components/Provenance';

interface MapPageProps {
  initialTrainQuery?: string;
  initialDate?: string;
  onTrainChange?: (trainNo: string, date?: string) => void;
  onViewLive?: (trainNo: string, date?: string) => void;
}

export interface StationItem {
  code: string;
  name: string;
  state?: string;
  zone?: string;
  lat: number;
  lng: number;
  train_count: number;
  category?: 'Terminal' | 'Junction' | 'Major' | 'Standard' | 'Halt';
}

type StationFilterMode = 'auto' | 'major' | 'halts' | 'all';
type BasemapType = 'voyager' | 'satellite' | 'dark';

const BASEMAP_TILES: Record<BasemapType, { url: string; attribution: string; maxZoom: number }> = {
  voyager: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri &mdash; Sources: Esri, DeLorme, NAVTEQ, USGS, Intermap, iPC, NRCAN, METI, TomTom',
    maxZoom: 19,
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri &mdash; Sources: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP',
    maxZoom: 19,
  },
  dark: {
    url: 'https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri &mdash; Sources: Esri, DeLorme, NAVTEQ',
    maxZoom: 16,
  },
};

const POPULAR_STATIONS = [
  { code: 'NDLS', name: 'New Delhi', zone: 'NR', state: 'Delhi', trains: '350+ Trains', lat: 28.6427, lng: 77.2201 },
  { code: 'HWH', name: 'Howrah Junction', zone: 'ER', state: 'West Bengal', trains: '290+ Trains', lat: 22.584, lng: 88.3426 },
  { code: 'CSMT', name: 'Mumbai CSMT', zone: 'CR', state: 'Maharashtra', trains: '260+ Trains', lat: 18.9402, lng: 72.8354 },
  { code: 'CNB', name: 'Kanpur Central', zone: 'NCR', state: 'Uttar Pradesh', trains: '310+ Trains', lat: 26.4542, lng: 80.3506 },
  { code: 'GKP', name: 'Gorakhpur Jn', zone: 'NER', state: 'Uttar Pradesh', trains: '190+ Trains', lat: 26.7588, lng: 83.3818 },
  { code: 'MAS', name: 'Chennai Central', zone: 'SR', state: 'Tamil Nadu', trains: '210+ Trains', lat: 13.0827, lng: 80.2755 },
];

const POPULAR_TRAINS = [
  { no: '12301', name: 'Howrah Rajdhani Express', route: 'HWH ➔ NDLS' },
  { no: '12951', name: 'Mumbai Tejas Rajdhani', route: 'MMCT ➔ NDLS' },
  { no: '22436', name: 'Vande Bharat Express', route: 'NDLS ➔ BSB' },
  { no: '12002', name: 'Bhopal Shatabdi Express', route: 'NDLS ➔ RKMP' },
  { no: '12555', name: 'Gorakhdham Express', route: 'GKP ➔ BTI' },
];

function getAvailableRunDates(): RunOption[] {
  const nowUtc = new Date();
  const istOffsetMs = 5.5 * 3600 * 1000;
  const nowIst = new Date(nowUtc.getTime() + istOffsetMs);

  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const offsets = [-1, 0, 1];

  return offsets.map((offset) => {
    const d = new Date(nowIst.getTime() + offset * 86400 * 1000);
    const day = String(d.getUTCDate()).padStart(2, '0');
    const month = String(d.getUTCMonth() + 1).padStart(2, '0');
    const year = d.getUTCFullYear();
    const key = `${day}-${month}-${year}`;
    const monStr = months[d.getUTCMonth()];
    const dateLabel = `${day} ${monStr}`;

    let label = '';
    if (offset === -1) label = 'Yesterday';
    else if (offset === 0) label = 'Today';
    else if (offset === 1) label = 'Tomorrow';

    return {
      key,
      label,
      dateLabel,
      offset,
      isToday: offset === 0,
    };
  });
}

const getCoachStyle = (label: string, cls: string) => {
  const l = (label || '').toUpperCase();
  const c = (cls || '').toUpperCase();
  if (l.includes('ENG') || c.includes('ENG') || l.includes('LOCO')) {
    return 'bg-stone-900 text-white border-stone-800 shadow-xs';
  }
  if (l.startsWith('H') || c === '1A') {
    return 'bg-purple-100 text-purple-900 border-purple-300 font-semibold';
  }
  if (l.startsWith('A') || c === '2A') {
    return 'bg-sky-100 text-sky-900 border-sky-300 font-semibold';
  }
  if (l.startsWith('B') || l.startsWith('M') || c === '3A' || c === '3E') {
    return 'bg-emerald-100 text-emerald-900 border-emerald-300 font-semibold';
  }
  if (l.startsWith('S') || c === 'SL') {
    return 'bg-amber-100 text-amber-900 border-amber-300 font-semibold';
  }
  if (l.startsWith('PC') || c.includes('PANTRY')) {
    return 'bg-rose-100 text-rose-900 border-rose-300 font-semibold';
  }
  if (l.startsWith('GS') || l.startsWith('GEN') || c.includes('GEN') || c === '2S') {
    return 'bg-stone-100 text-stone-800 border-stone-300';
  }
  if (l.startsWith('SLR') || l.startsWith('EOG')) {
    return 'bg-zinc-100 text-zinc-700 border-zinc-300';
  }
  return 'bg-stone-50 text-stone-800 border-stone-200';
};

export const MapPage: React.FC<MapPageProps> = ({
  initialTrainQuery = '',
  initialDate = '',
  onTrainChange,
  onViewLive,
}) => {
  const [trainInput, setTrainInput] = useState(initialTrainQuery || '');
  const [trainNo, setTrainNo] = useState(initialTrainQuery || '');

  const fallbackRunDates = getAvailableRunDates();
  const todayKey = fallbackRunDates.find((r) => r.isToday)?.key ?? '';
  const [selectedDate, setSelectedDate] = useState<string>(initialDate || todayKey);

  // Sync external date when passed from navigation
  useEffect(() => {
    if (initialDate && initialDate !== selectedDate) {
      setSelectedDate(initialDate);
    }
  }, [initialDate]);

  // Map & Visual States
  const [activeBasemap, setActiveBasemap] = useState<BasemapType>('voyager');
  const [showBasemapMenu, setShowBasemapMenu] = useState(false);
  const [currentZoom, setCurrentZoom] = useState(5);
  const [filterMode, setFilterMode] = useState<StationFilterMode>('auto');
  const [showCoaches, setShowCoaches] = useState(false);
  const [hudCollapsed, setHudCollapsed] = useState(false);
  const [selectedStation, setSelectedStation] = useState<any | null>(null);
  const [showLayerFilterModal, setShowLayerFilterModal] = useState(false);

  // Search mode: 'station' (default) vs 'train'
  const [searchMode, setSearchMode] = useState<'station' | 'train'>('station');
  const [stationInput, setStationInput] = useState('');
  const [gpsLoading, setGpsLoading] = useState(false);
  const userGpsGroupRef = useRef<L.LayerGroup | null>(null);

  // Indian-Map 8,800+ stations state
  const [allStations, setAllStations] = useState<StationItem[]>([]);

  // Leaflet references
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const routeGroupRef = useRef<L.LayerGroup | null>(null);
  const stationsGroupRef = useRef<L.LayerGroup | null>(null);
  const allStationsLayerRef = useRef<L.LayerGroup | null>(null);
  const canvasRendererRef = useRef<L.Canvas | null>(null);
  const locoMarkerRef = useRef<L.Marker | null>(null);

  const debounced = useDebounced(trainInput, 300);
  const isTrain = /^\d{5}$/.test(trainNo);

  // Load Indian-Map 8,800+ stations dataset on mount
  useEffect(() => {
    let isMounted = true;
    fetch('/data/stations.json')
      .then((res) => res.json())
      .then((data) => {
        if (isMounted && Array.isArray(data)) {
          setAllStations(data);
        }
      })
      .catch((err) => console.error('Failed to load stations dataset:', err));
    return () => {
      isMounted = false;
    };
  }, []);

  const suggestions = useQuery(
    debounced.trim().length >= 2 && !/^\d{5}$/.test(debounced.trim())
      ? (signal) => api.searchTrains(debounced.trim(), signal)
      : null,
    [debounced],
  );

  // In-memory instant search over 8,800+ stations
  const stationSuggestions = useMemo(() => {
    if (searchMode !== 'station' || !stationInput.trim() || stationInput.trim().length < 2) return [];
    const q = stationInput.trim().toLowerCase();
    return allStations
      .filter((s) => s.code.toLowerCase().startsWith(q) || s.name.toLowerCase().includes(q))
      .slice(0, 10);
  }, [searchMode, stationInput, allStations]);

  const flyToStation = (stn: { code: string; name: string; state?: string; zone?: string; category?: any; train_count?: number; lat: number; lng?: number; lon?: number }) => {
    const lat = stn.lat;
    const lon = stn.lng ?? stn.lon;
    if (!mapInstanceRef.current || lat == null || lon == null) return;
    mapInstanceRef.current.flyTo([lat, lon], 13, { duration: 1.2 });
    setSelectedStation({
      code: stn.code,
      name: stn.name,
      state: stn.state,
      zone: stn.zone,
      category: stn.category,
      train_count: stn.train_count,
      lat,
      lon,
      isPanIndia: true,
    });
  };

  const cycleBasemap = () => {
    setActiveBasemap((current) => {
      if (current === 'voyager') return 'satellite';
      if (current === 'satellite') return 'dark';
      return 'voyager';
    });
  };

  const locateUserGps = () => {
    if (!mapInstanceRef.current) return;
    if (!navigator.geolocation) {
      alert('Geolocation is not supported by your browser.');
      return;
    }

    setGpsLoading(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGpsLoading(false);
        const { latitude, longitude, accuracy } = pos.coords;
        const map = mapInstanceRef.current!;

        map.flyTo([latitude, longitude], 13, { duration: 1.5 });

        if (userGpsGroupRef.current) {
          map.removeLayer(userGpsGroupRef.current);
        }
        const group = L.layerGroup().addTo(map);
        userGpsGroupRef.current = group;

        // Accuracy circle
        L.circle([latitude, longitude], {
          radius: Math.max(accuracy || 150, 150),
          color: '#3b82f6',
          fillColor: '#3b82f6',
          fillOpacity: 0.12,
          weight: 1.5,
        }).addTo(group);

        // Pulsing GPS marker
        const gpsIcon = L.divIcon({
          className: 'user-gps-marker',
          html: `
            <div style="position:relative; width:24px; height:24px; display:flex; align-items:center; justify-content:center;">
              <div style="position:absolute; inset:0; border-radius:9999px; background:#3b82f6; opacity:0.5; animation:ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
              <div style="width:14px; height:14px; border-radius:9999px; background:#2563eb; border:2.5px solid #ffffff; box-shadow:0 2px 8px rgba(0,0,0,0.35);"></div>
            </div>
          `,
          iconSize: [24, 24],
          iconAnchor: [12, 12],
        });

        // Find nearest station from allStations
        let nearestStn: StationItem | null = null;
        let minKm = Infinity;
        for (const s of allStations) {
          if (s.lat == null || s.lng == null) continue;
          const dLat = (s.lat - latitude) * (Math.PI / 180);
          const dLng = (s.lng - longitude) * (Math.PI / 180);
          const a =
            Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(latitude * (Math.PI / 180)) *
              Math.cos(s.lat * (Math.PI / 180)) *
              Math.sin(dLng / 2) *
              Math.sin(dLng / 2);
          const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
          const dist = 6371 * c;
          if (dist < minKm) {
            minKm = dist;
            nearestStn = s;
          }
        }

        const marker = L.marker([latitude, longitude], { icon: gpsIcon }).addTo(group);
        const distStr = minKm < Infinity ? `${minKm.toFixed(1)} km` : '';
        marker
          .bindPopup(
            `<div style="font-family:sans-serif; min-width:180px; padding:2px;">
              <div style="font-weight:bold; color:#2563eb; font-size:12px; margin-bottom:4px;">📍 Your Live GPS Location</div>
              ${
                nearestStn
                  ? `<div style="font-size:11px; color:#1f2937;">Nearest Station: <b>${nearestStn.name} (${nearestStn.code})</b></div>
                     <div style="font-size:10px; color:#6b7280; margin-top:2px;">${distStr} away · ${nearestStn.category || 'Station'}</div>`
                  : ''
              }
            </div>`
          )
          .openPopup();
      },
      (err) => {
        setGpsLoading(false);
        console.warn('GPS location failed:', err);
        if (isTrain && d?.position?.coordinates?.lat) {
          focusOnTrain();
        } else {
          resetView();
        }
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const route = useQuery(isTrain ? (signal) => api.routeGeoJson(trainNo, signal) : null, [trainNo]);
  const live = useQuery(
    isTrain ? (signal) => api.trainLive(trainNo, selectedDate || undefined, signal) : null,
    [trainNo, selectedDate],
    { pollMs: 60_000 },
  );

  // Zero-flicker live state preservation & stale locomotive reset
  const lastLiveRef = useRef<any>(null);
  if (live.data) {
    lastLiveRef.current = live.data;
  }
  const d = live.data || lastLiveRef.current;

  // Immediately clear previous train's live cache when a new train is selected
  useEffect(() => {
    lastLiveRef.current = null;
    setSelectedStation(null);
  }, [trainNo, selectedDate]);

  // Cached available runs for smooth multi-day switcher
  const [stableRuns, setStableRuns] = useState<RunOption[]>([]);
  useEffect(() => {
    if (d?.train?.availableRuns && d.train.availableRuns.length > 0) {
      setStableRuns(d.train.availableRuns);
    }
    // Automatically sync to the active run date if user has not manually picked a date
    if (d?.train?.activeDate && !initialDate && selectedDate !== d.train.activeDate) {
      setSelectedDate(d.train.activeDate);
    }
  }, [d?.train?.availableRuns, d?.train?.activeDate]);

  const runDates: RunOption[] = stableRuns.length > 0 ? stableRuns : fallbackRunDates;

  // Sync external train prop
  useEffect(() => {
    if (initialTrainQuery !== undefined && initialTrainQuery !== trainNo) {
      setTrainInput(initialTrainQuery);
      setTrainNo(initialTrainQuery);
      if (initialDate) {
        setSelectedDate(initialDate);
      } else {
        setSelectedDate(todayKey);
      }
    }
  }, [initialTrainQuery, initialDate]);

  // Reset live ref and center map over Pan-India overview when train is cleared
  useEffect(() => {
    if (!trainNo) {
      lastLiveRef.current = null;
      if (mapInstanceRef.current) {
        mapInstanceRef.current.setView([22.5, 79.5], 5, { animate: true });
      }
    }
  }, [trainNo]);

  // 1. Initialize Leaflet Map Instance
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const map = L.map(mapContainerRef.current, {
      center: isTrain ? [26.8, 80.5] : [22.5, 79.5],
      zoom: isTrain ? 6 : 5,
      minZoom: 4,
      maxZoom: 18,
      zoomControl: false,
    });

    const baseConfig = BASEMAP_TILES[activeBasemap];
    const tileLayer = L.tileLayer(baseConfig.url, {
      attribution: baseConfig.attribution,
      maxZoom: baseConfig.maxZoom,
      subdomains: [],
    }).addTo(map);

    const canvasRenderer = L.canvas({ padding: 0.5 });
    const allStationsGroup = L.layerGroup().addTo(map);
    const routeGroup = L.layerGroup().addTo(map);
    const stationsGroup = L.layerGroup().addTo(map);

    canvasRendererRef.current = canvasRenderer;
    allStationsLayerRef.current = allStationsGroup;
    tileLayerRef.current = tileLayer;
    routeGroupRef.current = routeGroup;
    stationsGroupRef.current = stationsGroup;
    mapInstanceRef.current = map;

    map.on('zoomend', () => {
      setCurrentZoom(map.getZoom());
    });

    map.on('click', () => {
      setShowBasemapMenu(false);
      setShowLayerFilterModal(false);
    });

    return () => {
      map.remove();
      mapInstanceRef.current = null;
      allStationsLayerRef.current = null;
      canvasRendererRef.current = null;
    };
  }, []);

  // 2. Handle Basemap Switching
  useEffect(() => {
    if (!mapInstanceRef.current || !tileLayerRef.current) return;
    const map = mapInstanceRef.current;
    map.removeLayer(tileLayerRef.current);

    const baseConfig = BASEMAP_TILES[activeBasemap];
    const newTileLayer = L.tileLayer(baseConfig.url, {
      attribution: baseConfig.attribution,
      maxZoom: baseConfig.maxZoom,
      subdomains: [],
    }).addTo(map);

    // Ensure tiles stay beneath vector overlays
    newTileLayer.bringToBack();
    tileLayerRef.current = newTileLayer;
  }, [activeBasemap]);

  // 2b. Render All-India Stations with Adaptive LOD when !isTrain
  useEffect(() => {
    if (!mapInstanceRef.current || !allStationsLayerRef.current) return;
    const group = allStationsLayerRef.current;
    group.clearLayers();

    if (isTrain || !allStations.length) return;

    const zoom = currentZoom;
    const renderer = canvasRendererRef.current || undefined;

    allStations.forEach((stn) => {
      if (stn.lat == null || stn.lng == null) return;

      const cat = stn.category || 'Standard';

      // Adaptive Level of Detail (LOD)
      if (filterMode === 'major') {
        if (cat !== 'Terminal' && cat !== 'Junction' && cat !== 'Major') return;
      } else if (filterMode === 'halts') {
        if (stn.train_count < 10 && cat === 'Standard') return;
      } else if (filterMode === 'auto') {
        if (zoom <= 5) {
          if (cat !== 'Terminal' && cat !== 'Junction' && stn.train_count < 140) return;
        } else if (zoom <= 7) {
          if (cat === 'Standard' && stn.train_count < 25) return;
        } else if (zoom <= 9) {
          if (cat === 'Standard' && stn.train_count === 0 && !stn.name.includes('Jn')) return;
        }
      }

      let radius = 3;
      let color = '#ffffff';
      let fillColor = '#10b981';
      let fillOpacity = 0.8;
      let weight = 1;

      if (cat === 'Terminal') {
        radius = zoom >= 10 ? 8 : zoom >= 7 ? 6 : 4.5;
        fillColor = '#dc2626'; // Crimson
        fillOpacity = 0.95;
        weight = 1.5;
      } else if (cat === 'Junction') {
        radius = zoom >= 10 ? 6.5 : zoom >= 7 ? 5 : 3.8;
        fillColor = '#d97706'; // Amber
        fillOpacity = 0.9;
        weight = 1.2;
      } else if (cat === 'Major') {
        radius = zoom >= 10 ? 5.5 : zoom >= 7 ? 4.2 : 3.2;
        fillColor = '#2563eb'; // Blue
        fillOpacity = 0.85;
        weight = 1.2;
      } else {
        radius = zoom >= 12 ? 4.5 : zoom >= 9 ? 3 : 2;
        fillColor = '#10b981'; // Emerald
        fillOpacity = 0.7;
        weight = 0.8;
      }

      const marker = L.circleMarker([stn.lat, stn.lng], {
        renderer,
        radius,
        color,
        fillColor,
        fillOpacity,
        weight,
      });

      marker.bindTooltip(
        `<div class="text-[11px] font-bold font-mono text-stone-900">${stn.code}</div><div class="text-[10px] text-stone-600">${stn.name}</div><div class="text-[9px] text-[#FF6332] font-semibold">${stn.train_count ? `${stn.train_count} Scheduled Trains` : cat}</div>`,
        { direction: 'top', offset: [0, -4], opacity: 0.95 }
      );

      marker.on('click', () => {
        setSelectedStation({
          code: stn.code,
          name: stn.name,
          state: stn.state,
          zone: stn.zone,
          category: stn.category,
          train_count: stn.train_count,
          lat: stn.lat,
          lon: stn.lng,
          isPanIndia: true,
        });
      });

      group.addLayer(marker);
    });
  }, [allStations, isTrain, currentZoom, filterMode]);

  // 3. Process Stations & Route Data
  const routeFeatures = useMemo(() => {
    if (!route.data?.features) return null;
    const features: any[] = route.data.features;
    const line = features.find((f: any) => f.geometry?.type === 'LineString');
    const stations = features.filter((f: any) => f.geometry?.type === 'Point');
    const rawCoords: number[][] = line?.geometry?.coordinates ?? [];
    if (!rawCoords.length) return null;

    // Convert [lon, lat] -> [lat, lon] for Leaflet
    const latLngs: [number, number][] = rawCoords.map((c) => [c[1], c[0]]);

    const stopByCode = new Map<string, Stop>();
    (d?.stops ?? []).forEach((s: Stop) => stopByCode.set(s.stationCode, s));

    const distCovered = d?.position?.distanceCoveredKm ?? 0;
    const currentCode = d?.position?.currentStationCode || d?.position?.lastStationCode;

    const maxSeq = stations.length;
    const matchedCurrentStation = stations.find((f: any) => f.properties?.code === currentCode);
    const currentSeq = matchedCurrentStation?.properties?.seq ?? (distCovered === 0 ? 1 : maxSeq);

    const mappedStations = stations.map((f: any) => {
      const lon = f.geometry.coordinates[0];
      const lat = f.geometry.coordinates[1];
      const code: string = f.properties.code;
      const name: string = f.properties.name;
      const seq: number = f.properties.seq ?? 1;
      const liveStop = stopByCode.get(code);

      const isPassed = distCovered > 0 && seq < currentSeq;
      const isCurrent = (distCovered === 0 && seq === 1) || seq === currentSeq || code === currentCode;
      const isUpcoming = !isPassed && !isCurrent;

      const upperName = name.toUpperCase();
      const isMajorJunction =
        seq === 1 ||
        seq === maxSeq ||
        isCurrent ||
        upperName.includes(' JN') ||
        upperName.includes('JUNCTION') ||
        upperName.includes('CENTRAL') ||
        upperName.includes('CANTT') ||
        upperName.includes('TERMINUS') ||
        upperName.includes('TERMINAL');

      const isCommercialHalt = stopByCode.has(code);
      const tier: 1 | 2 | 3 = isMajorJunction ? 1 : isCommercialHalt ? 2 : 3;

      return {
        lat,
        lon,
        code,
        name,
        seq,
        tier,
        liveStop,
        isPassed,
        isCurrent,
        isUpcoming,
        isMajorJunction,
        isCommercialHalt,
      };
    });

    // Project locomotive GPS or current station onto closest point along track polyline
    let bestIdx = 0;
    let minD2 = Infinity;
    const tLat = d?.position?.coordinates?.lat ?? matchedCurrentStation?.geometry?.coordinates?.[1];
    const tLon = d?.position?.coordinates?.lon ?? matchedCurrentStation?.geometry?.coordinates?.[0];

    if (tLat != null && tLon != null) {
      for (let i = 0; i < latLngs.length; i++) {
        const dLat = latLngs[i][0] - tLat;
        const dLon = latLngs[i][1] - tLon;
        const distSq = dLat * dLat + dLon * dLon;
        if (distSq < minD2) {
          minD2 = distSq;
          bestIdx = i;
        }
      }
    } else {
      bestIdx = Math.min(latLngs.length - 1, Math.max(0, currentSeq - 1));
    }

    const passedLatLngs = distCovered > 0 ? latLngs.slice(0, bestIdx + 1) : [];
    const upcomingLatLngs = distCovered > 0 ? latLngs.slice(bestIdx) : latLngs;

    return {
      allLatLngs: latLngs,
      passedLatLngs,
      upcomingLatLngs,
      stations: mappedStations,
    };
  }, [route.data, d]);

  // 4. Render Route Polylines and Fit Bounds
  useEffect(() => {
    if (!mapInstanceRef.current || !routeGroupRef.current) return;
    const group = routeGroupRef.current;
    group.clearLayers();

    if (!isTrain || !routeFeatures) return;

    // Passed Completed Route (Solid Emerald Green with soft outer glow)
    if (routeFeatures.passedLatLngs.length > 1) {
      // Glow underlay
      L.polyline(routeFeatures.passedLatLngs, {
        color: '#10B981',
        weight: 9,
        opacity: 0.35,
        lineCap: 'round',
        lineJoin: 'round',
      }).addTo(group);

      // Main line
      L.polyline(routeFeatures.passedLatLngs, {
        color: '#10B981',
        weight: 4.5,
        opacity: 0.95,
        lineCap: 'round',
        lineJoin: 'round',
      }).addTo(group);
    }

    // Upcoming Route Ahead (Dashed Slate)
    if (routeFeatures.upcomingLatLngs.length > 1) {
      L.polyline(routeFeatures.upcomingLatLngs, {
        color: activeBasemap === 'satellite' ? '#E2E8F0' : '#475569',
        weight: 3.5,
        dashArray: '8, 6',
        opacity: 0.85,
        lineCap: 'round',
        lineJoin: 'round',
      }).addTo(group);
    }

    // Fit map bounds to show route cleanly beside left HUD
    if (routeFeatures.allLatLngs.length > 1) {
      const bounds = L.latLngBounds(routeFeatures.allLatLngs);
      const isDesktop = window.innerWidth >= 768;
      mapInstanceRef.current.fitBounds(bounds, {
        paddingTopLeft: isDesktop ? [hudCollapsed ? 120 : 440, 80] : [20, 80],
        paddingBottomRight: [50, 50],
        maxZoom: 10,
      });
    }
  }, [routeFeatures, activeBasemap, hudCollapsed, isTrain]);

  // 5. Render Stations with Adaptive Zoom Breakpoints
  useEffect(() => {
    if (!mapInstanceRef.current || !stationsGroupRef.current) return;
    const group = stationsGroupRef.current;
    group.clearLayers();

    if (!isTrain || !routeFeatures) return;

    routeFeatures.stations.forEach((s) => {
      // Breakpoint Visibility Rules
      let isVisible = false;
      if (filterMode === 'all') {
        isVisible = true;
      } else if (filterMode === 'major') {
        isVisible = s.tier === 1;
      } else if (filterMode === 'halts') {
        isVisible = s.tier <= 2;
      } else {
        // 'auto' mode
        if (s.tier === 1 || s.isCurrent) {
          isVisible = true; // Major junctions and active train station always visible
        } else if (s.tier === 2) {
          isVisible = currentZoom >= 7; // Commercial halts appear at zoom >= 7
        } else {
          isVisible = currentZoom >= 10; // Passing loops appear at zoom >= 10
        }
      }

      if (!isVisible) return;

      const circle = L.circleMarker([s.lat, s.lon], {
        radius: s.isCurrent ? 7.5 : s.tier === 1 ? 6 : s.tier === 2 ? 4.5 : 3,
        color: s.isCurrent
          ? '#FFA07A'
          : s.isPassed
          ? '#34D399'
          : s.tier === 1
          ? '#FFFFFF'
          : '#94A3B8',
        weight: s.isCurrent || s.isPassed ? 2.5 : 1.5,
        fillColor: s.isCurrent
          ? '#FF6332'
          : s.isPassed
          ? '#10B981'
          : s.tier === 1
          ? '#334155'
          : '#64748B',
        fillOpacity: s.isCurrent || s.isPassed ? 0.95 : 0.75,
      });

      // Hover Tooltip with IR Code and Name
      circle.bindTooltip(
        `<div class="text-[11px] font-bold font-mono text-stone-900">${s.code}</div><div class="text-[10px] text-stone-600">${s.name}</div>`,
        { direction: 'top', offset: [0, -6], opacity: 0.95 }
      );

      circle.on('click', () => {
        setSelectedStation(s);
      });

      circle.addTo(group);
    });
  }, [routeFeatures, currentZoom, filterMode, isTrain]);

  // 6. Render Real-Time Locomotive Marker
  useEffect(() => {
    if (!mapInstanceRef.current) return;
    const map = mapInstanceRef.current;
    const coords = d?.position?.coordinates;

    if (!isTrain || !coords || coords.lat == null || coords.lon == null) {
      if (locoMarkerRef.current) {
        map.removeLayer(locoMarkerRef.current);
        locoMarkerRef.current = null;
      }
      return;
    }

    const latLng: [number, number] = [coords.lat, coords.lon];
    const delay = d?.eta?.currentDelayMinutes ?? d?.position?.delayMinutes ?? null;
    const delayLabel = delay !== null ? (delay <= 0 ? 'RT' : `+${delay}m`) : 'LIVE';

    const locoIconHtml = `
      <div class="relative -translate-x-1/2 -translate-y-1/2 flex items-center justify-center cursor-pointer group">
        <!-- Dual Sonar Pulse Rings -->
        <div class="absolute -inset-4 rounded-full bg-[#FF6332] opacity-25 animate-ping"></div>
        <div class="absolute -inset-2 rounded-full bg-[#FF6332] opacity-40 animate-pulse"></div>

        <!-- Train Badge Marker -->
        <div class="relative w-9 h-9 rounded-full bg-[#070A0F] border-2 border-[#FF6332] shadow-2xl flex items-center justify-center text-white">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FF6332" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M5 8C5 6.34315 6.34315 5 8 5H24C25.6569 5 27 6.34315 27 8V20C27 22.2091 25.2091 24 23 24H9C6.79086 24 5 22.2091 5 20V8Z" fill="#1E293B"/>
            <rect x="8" y="8" width="16" height="5" rx="1.5" fill="#38BDF8"/>
            <circle cx="10" cy="18.5" r="2.2" fill="#FACC15"/>
            <circle cx="22" cy="18.5" r="2.2" fill="#FACC15"/>
            <circle cx="16" cy="18.5" r="1.2" fill="#FFFFFF"/>
          </svg>
        </div>

        <!-- Live Telemetry Tag -->
        <div class="absolute left-full ml-2 px-2 py-0.5 rounded-full bg-[#070A0F]/90 backdrop-blur-md border border-[#FF6332]/50 text-white text-[10px] font-mono font-bold whitespace-nowrap shadow-xl flex items-center gap-1">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>${trainNo} · ${delayLabel}</span>
        </div>
      </div>
    `;

    const customIcon = L.divIcon({
      html: locoIconHtml,
      className: 'bg-transparent border-0',
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });

    if (locoMarkerRef.current) {
      locoMarkerRef.current.setLatLng(latLng);
      locoMarkerRef.current.setIcon(customIcon);
    } else {
      const marker = L.marker(latLng, { icon: customIcon, zIndexOffset: 1000 }).addTo(map);
      locoMarkerRef.current = marker;
    }
  }, [d?.position?.coordinates, trainNo, isTrain, d?.eta?.currentDelayMinutes, d?.position?.delayMinutes]);

  // Controls Callbacks
  const zoomIn = () => mapInstanceRef.current?.zoomIn();
  const zoomOut = () => mapInstanceRef.current?.zoomOut();

  const resetView = () => {
    if (!mapInstanceRef.current) return;
    if (isTrain && routeFeatures?.allLatLngs?.length) {
      const bounds = L.latLngBounds(routeFeatures.allLatLngs);
      const isDesktop = window.innerWidth >= 768;
      mapInstanceRef.current.fitBounds(bounds, {
        paddingTopLeft: isDesktop ? [hudCollapsed ? 120 : 440, 80] : [20, 80],
        paddingBottomRight: [50, 50],
        maxZoom: 10,
      });
    } else {
      mapInstanceRef.current.setView([22.8, 79.5], 5, { animate: true });
    }
    setSelectedStation(null);
  };

  const focusOnTrain = () => {
    const coords = d?.position?.coordinates;
    if (!mapInstanceRef.current || !coords || coords.lat == null || coords.lon == null) return;
    mapInstanceRef.current.setView([coords.lat, coords.lon], 11, { animate: true });
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = trainInput.trim();
    if (/^\d{5}$/.test(q)) {
      setTrainNo(q);
      setSelectedDate(todayKey);
      setSelectedStation(null);
      onTrainChange?.(q, todayKey);
    } else if (suggestions.data && suggestions.data.length > 0) {
      const top = suggestions.data[0];
      setTrainInput(top.number);
      setTrainNo(top.number);
      setSelectedDate(todayKey);
      setSelectedStation(null);
      onTrainChange?.(top.number, todayKey);
    }
  };

  const progress =
    d?.position?.distanceCoveredKm !== null &&
    d?.position?.distanceCoveredKm !== undefined &&
    d?.position?.totalDistanceKm
      ? Math.min(100, Math.max(0, Math.round((d.position.distanceCoveredKm / d.position.totalDistanceKm) * 100)))
      : null;

  return (
    <div className="fixed inset-0 w-screen h-screen bg-[#070A0F] overflow-hidden z-0 select-none">
      {/* Full-Screen Leaflet Map Canvas */}
      <div ref={mapContainerRef} id="leafletMap" className="w-full h-full z-0" />


      {/* Floating Left HUD: Train Telemetry, Date Selector & Train Switcher */}
      <div
        className={`absolute top-20 left-4 z-20 transition-all duration-300 pointer-events-auto ${
          hudCollapsed ? 'w-auto' : 'w-[340px] sm:w-[380px] max-h-[calc(100vh-100px)]'
        }`}
      >
        {hudCollapsed ? (
          <button
            type="button"
            onClick={() => setHudCollapsed(false)}
            className="px-3.5 py-2.5 rounded-2xl bg-white/95 backdrop-blur-md border border-stone-200/90 text-stone-800 text-xs font-semibold flex items-center gap-2 shadow-xl hover:bg-white transition-all cursor-pointer"
          >
            {isTrain ? (
              <>
                <span className="w-2.5 h-2.5 rounded-full bg-[#FF6332] animate-pulse" />
                <span className="font-mono font-bold text-stone-900">{trainNo}</span>
                <span>Live Info</span>
              </>
            ) : (
              <>
                <MapPin className="w-3.5 h-3.5 text-[#FF6332]" />
                <span>Station Explorer</span>
              </>
            )}
            <ChevronRight className="w-3.5 h-3.5 text-stone-400" />
          </button>
        ) : !isTrain ? (
          <div className="bg-white/95 backdrop-blur-2xl rounded-3xl p-4.5 border border-stone-200/90 shadow-2xl text-stone-800 flex flex-col gap-3 overflow-y-auto max-h-[calc(100vh-110px)] scrollbar-none">
            {/* Explorer Header */}
            <div className="flex items-center justify-between gap-2 border-b border-stone-100 pb-2.5">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-[#FF6332]/10 border border-[#FF6332]/20 flex items-center justify-center text-[#FF6332]">
                  {searchMode === 'station' ? <MapPin className="w-4 h-4" /> : <TrainFront className="w-4 h-4" />}
                </div>
                <div>
                  <h3 className="text-xs font-bold text-stone-900 leading-tight">Pan-India Network</h3>
                  <p className="text-[10px] text-stone-500 leading-tight">8,800+ Stations & Halts</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setHudCollapsed(true)}
                className="p-1 rounded-full text-stone-400 hover:text-stone-700 hover:bg-stone-100 transition-colors cursor-pointer"
                title="Minimize HUD"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
            </div>

            {/* Segmented Mode Switcher: Stations (Default) vs Trains */}
            <div className="flex items-center p-1 bg-stone-100/90 rounded-2xl border border-stone-200/70 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setSearchMode('station')}
                className={`flex-1 py-1.5 px-3 rounded-xl transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                  searchMode === 'station'
                    ? 'bg-white text-[#FF6332] shadow-xs font-bold'
                    : 'text-stone-500 hover:text-stone-800'
                }`}
              >
                <MapPin className="w-3.5 h-3.5" />
                <span>Stations</span>
              </button>
              <button
                type="button"
                onClick={() => setSearchMode('train')}
                className={`flex-1 py-1.5 px-3 rounded-xl transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                  searchMode === 'train'
                    ? 'bg-white text-[#FF6332] shadow-xs font-bold'
                    : 'text-stone-500 hover:text-stone-800'
                }`}
              >
                <TrainFront className="w-3.5 h-3.5" />
                <span>Trains</span>
              </button>
            </div>

            {/* Search Input for Station (Default) or Train */}
            {/* Search Input for Station (Default) or Train */}
            {searchMode === 'station' ? (
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={stationInput}
                  onChange={(e) => setStationInput(e.target.value)}
                  placeholder="Search station (e.g. NDLS, Kanpur, Mumbai)..."
                  className="w-full pl-8 pr-8 py-2 bg-stone-100/90 hover:bg-stone-50 focus:bg-white text-xs text-stone-900 rounded-xl border border-stone-200 focus:border-[#FF6332] focus:outline-none transition-all placeholder:text-stone-400 font-medium"
                  autoFocus
                />
                {stationInput && (
                  <button
                    type="button"
                    onClick={() => setStationInput('')}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-700 p-1 cursor-pointer"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}

                {/* Instant Station Suggestions Dropdown - Opaque Solid White */}
                {stationSuggestions.length > 0 && (
                  <div className="absolute top-full mt-1.5 left-0 right-0 z-50 bg-white border border-stone-200/90 rounded-2xl shadow-2xl p-1.5 flex flex-col gap-1 max-h-56 overflow-y-auto">
                    {stationSuggestions.map((stn) => (
                      <button
                        key={stn.code}
                        type="button"
                        onClick={() => {
                          flyToStation(stn);
                          setStationInput(stn.name);
                        }}
                        className="text-left px-3 py-2 rounded-xl hover:bg-stone-100 text-xs text-stone-800 flex items-center justify-between transition-colors cursor-pointer group"
                      >
                        <div>
                          <span className="font-mono font-bold text-[#FF6332]">{stn.code}</span>
                          <span className="ml-2 font-semibold text-stone-800">{stn.name}</span>
                          <div className="text-[10px] text-stone-400 mt-0.5">
                            {stn.zone || 'IR'} · {stn.state || 'India'}
                          </div>
                        </div>
                        <div className="text-right">
                          <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium">
                            {stn.train_count ? `${stn.train_count} Trains` : stn.category || 'Station'}
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <form onSubmit={handleSearchSubmit} className="relative">
                <Search className="w-3.5 h-3.5 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={trainInput}
                  onChange={(e) => setTrainInput(e.target.value)}
                  placeholder="Enter 5-digit train no or name…"
                  className="w-full pl-8 pr-16 py-2 bg-stone-100/90 hover:bg-stone-50 focus:bg-white text-xs text-stone-900 rounded-xl border border-stone-200 focus:border-[#FF6332] focus:outline-none transition-all placeholder:text-stone-400 font-mono"
                  autoFocus
                />
                <button
                  type="submit"
                  className="absolute right-1 top-1/2 -translate-y-1/2 px-2.5 py-1 bg-[#FF6332] hover:bg-orange-600 text-white rounded-lg text-[10px] font-bold transition-all cursor-pointer"
                >
                  Track
                </button>

                {/* Train Suggestions Dropdown - Opaque Solid White */}
                {suggestions.data && suggestions.data.length > 0 && (
                  <div className="absolute top-full mt-1.5 left-0 right-0 z-50 bg-white border border-stone-200/90 rounded-2xl shadow-2xl p-1.5 flex flex-col gap-1 max-h-52 overflow-y-auto">
                    {suggestions.data.map((t) => (
                      <button
                        key={t.number}
                        type="button"
                        onClick={() => {
                          setTrainInput(t.number);
                          setTrainNo(t.number);
                          setSelectedDate(todayKey);
                          setSelectedStation(null);
                          onTrainChange?.(t.number, todayKey);
                        }}
                        className="text-left px-2.5 py-1.5 rounded-lg hover:bg-stone-100 text-xs text-stone-700 hover:text-stone-900 flex items-center justify-between transition-colors cursor-pointer"
                      >
                        <div>
                          <span className="font-mono font-bold text-[#FF6332]">{t.number}</span>
                          <span className="truncate ml-2 text-[11px] font-semibold">{t.name}</span>
                        </div>
                        <span className="text-[9px] text-stone-400 shrink-0 font-mono">
                          {t.from_code && t.to_code ? `${t.from_code} ➔ ${t.to_code}` : ''}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </form>
            )}

            {/* Featured Items: Stations or Routes (hidden while searching to avoid visual clutter) */}
            {((searchMode === 'station' && stationSuggestions.length === 0) ||
              (searchMode === 'train' && (!suggestions.data || suggestions.data.length === 0))) && (
              <div>
                <div className="flex items-center gap-1.5 text-[10px] text-stone-500 font-bold uppercase tracking-wider mb-2">
                  <Sparkles className="w-3 h-3 text-[#FF6332]" />
                  <span>{searchMode === 'station' ? 'Major Railway Hubs' : 'Featured Routes'}</span>
                </div>
                <div className="flex flex-col gap-1.5">
                {searchMode === 'station'
                  ? POPULAR_STATIONS.map((s) => (
                      <button
                        key={s.code}
                        type="button"
                        onClick={() => flyToStation(s)}
                        className="w-full text-left px-3 py-2 rounded-xl bg-stone-50 hover:bg-stone-100/90 border border-stone-200/70 hover:border-[#FF6332]/40 transition-all flex items-center justify-between group cursor-pointer"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono font-bold text-xs text-[#FF6332]">{s.code}</span>
                            <span className="text-xs text-stone-800 group-hover:text-stone-950 truncate font-semibold">
                              {s.name}
                            </span>
                          </div>
                          <div className="text-[10px] text-stone-400 font-mono">{s.zone} · {s.state}</div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-[10px] font-mono text-stone-500">{s.trains}</span>
                          <ArrowRight className="w-3.5 h-3.5 text-stone-400 group-hover:text-[#FF6332] transition-colors" />
                        </div>
                      </button>
                    ))
                  : POPULAR_TRAINS.map((t) => (
                      <button
                        key={t.no}
                        type="button"
                        onClick={() => {
                          setTrainInput(t.no);
                          setTrainNo(t.no);
                          setSelectedDate(todayKey);
                          setSelectedStation(null);
                          onTrainChange?.(t.no, todayKey);
                        }}
                        className="w-full text-left px-3 py-2 rounded-xl bg-stone-50 hover:bg-stone-100/90 border border-stone-200/70 hover:border-[#FF6332]/40 transition-all flex items-center justify-between group cursor-pointer"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono font-bold text-xs text-[#FF6332]">{t.no}</span>
                            <span className="text-xs text-stone-800 group-hover:text-stone-950 truncate font-semibold">
                              {t.name}
                            </span>
                          </div>
                          <div className="text-[10px] text-stone-400 font-mono">{t.route}</div>
                        </div>
                        <ArrowRight className="w-3.5 h-3.5 text-stone-400 group-hover:text-[#FF6332] transition-colors shrink-0" />
                      </button>
                    ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="bg-white/95 backdrop-blur-2xl rounded-3xl p-4.5 border border-stone-200/90 shadow-2xl text-stone-800 flex flex-col gap-3 overflow-y-auto max-h-[calc(100vh-110px)] scrollbar-none">
            {/* HUD Header Bar & Minimize & Clear */}
            <div className="flex items-center justify-between gap-2 border-b border-stone-100 pb-2.5">
              <div className="flex items-center gap-2 min-w-0">
                <span className="px-2.5 py-0.5 rounded-lg bg-[#FF6332] text-white text-xs font-mono font-bold shrink-0 shadow-xs">
                  {trainNo}
                </span>
                <h3 className="text-xs font-bold text-stone-900 truncate">
                  {d?.train?.name || (live.loading ? 'Scanning IR Satellites…' : 'Train Route')}
                </h3>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {onViewLive && (
                  <button
                    type="button"
                    onClick={() => onViewLive(trainNo, selectedDate)}
                    className="px-2 py-0.5 rounded-full bg-stone-100 hover:bg-stone-200 text-[10px] font-semibold text-stone-700 flex items-center gap-1 transition-all cursor-pointer"
                    title="Open full timeline in Live tab"
                  >
                    <span>Timeline</span>
                    <ExternalLink className="w-2.5 h-2.5 text-[#FF6332]" />
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setTrainNo('');
                    setTrainInput('');
                    setSelectedStation(null);
                    lastLiveRef.current = null;
                    onTrainChange?.('', '');
                  }}
                  className="p-1 rounded-full text-stone-400 hover:text-rose-500 hover:bg-stone-100 transition-colors cursor-pointer"
                  title="Clear train & return to Pan-India overview"
                >
                  <X className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setHudCollapsed(true)}
                  className="p-1 rounded-full text-stone-400 hover:text-stone-700 hover:bg-stone-100 transition-colors cursor-pointer"
                  title="Minimize HUD"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Quick Train Search Switcher */}
            <form onSubmit={handleSearchSubmit} className="relative">
              <Search className="w-3.5 h-3.5 text-stone-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={trainInput}
                onChange={(e) => setTrainInput(e.target.value)}
                placeholder="Search train (e.g. 12555 or Rajdhani)"
                className="w-full pl-8 pr-16 py-1.5 bg-stone-100/90 hover:bg-stone-50 focus:bg-white text-xs text-stone-900 rounded-xl border border-stone-200 focus:border-[#FF6332] focus:outline-none transition-all placeholder:text-stone-400 font-mono"
              />
              <button
                type="submit"
                className="absolute right-1 top-1/2 -translate-y-1/2 px-2.5 py-0.5 bg-[#FF6332] hover:bg-orange-600 text-white rounded-lg text-[10px] font-bold transition-all cursor-pointer"
              >
                Go
              </button>

              {/* Suggestions Dropdown */}
              {suggestions.data && suggestions.data.length > 0 && (
                <div className="absolute top-full mt-1.5 left-0 right-0 z-40 bg-white/98 backdrop-blur-xl border border-stone-200 rounded-2xl shadow-2xl p-1.5 flex flex-col gap-1 max-h-40 overflow-y-auto">
                  {suggestions.data.map((t) => (
                    <button
                      key={t.number}
                      type="button"
                      onClick={() => {
                        setTrainInput(t.number);
                        setTrainNo(t.number);
                        setSelectedDate(todayKey);
                        setSelectedStation(null);
                        onTrainChange?.(t.number, todayKey);
                      }}
                      className="text-left px-2 py-1 rounded-lg hover:bg-stone-100 text-xs text-stone-700 hover:text-stone-900 flex items-center justify-between transition-colors"
                    >
                      <span className="font-mono font-bold text-[#FF6332]">{t.number}</span>
                      <span className="truncate ml-2 text-[11px] font-semibold">{t.name}</span>
                    </button>
                  ))}
                </div>
              )}
            </form>

            {/* Radar Acquisition State or Real Train Data */}
            {!d ? (
              live.error ? (
                <div className="p-3 rounded-2xl bg-rose-50 border border-rose-200 text-xs text-rose-700 flex flex-col gap-2">
                  <div className="flex items-center gap-1.5 font-semibold">
                    <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
                    <span>Transponder Signal Interrupted</span>
                  </div>
                  <p className="text-[11px] text-rose-600">Could not synchronize telemetry for train #{trainNo}.</p>
                  <button
                    type="button"
                    onClick={() => live.refetch()}
                    className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-[10px] font-bold self-start cursor-pointer transition-all"
                  >
                    Retry Radar Ping
                  </button>
                </div>
              ) : (
                /* High-Speed Satellite Radar Acquisition Card */
                <div className="p-4 rounded-2xl bg-stone-50 border border-stone-200/80 flex flex-col items-center text-center gap-3 animate-in fade-in duration-300">
                  <div className="relative w-14 h-14 flex items-center justify-center">
                    <div className="absolute inset-0 rounded-full border-2 border-[#FF6332]/30 animate-ping" />
                    <div className="absolute inset-1.5 rounded-full border border-sky-400/30 animate-spin" style={{ animationDuration: '4s' }} />
                    <div className="w-10 h-10 rounded-full bg-white border border-stone-200 shadow-sm flex items-center justify-center">
                      <Radio className="w-5 h-5 text-[#FF6332] animate-pulse" />
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-bold text-stone-900 tracking-wide">Acquiring GPS Telemetry</div>
                    <div className="text-[10px] text-stone-500 mt-0.5 font-mono">Syncing CRIS & transponder #{trainNo}</div>
                  </div>
                  <div className="w-full bg-stone-200 h-1.5 rounded-full overflow-hidden relative">
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#FF6332] to-transparent w-full animate-pulse" />
                  </div>
                  <div className="flex items-center gap-2 text-[9px] font-mono text-stone-500">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    <span>IRNSS Satellite Radar Locked</span>
                  </div>
                </div>
              )
            ) : (
              <>
                {/* Journey Run Date Selector (Yesterday / Today / Tomorrow) */}
                <div>
                  <div className="flex items-center justify-between text-[10px] text-stone-500 mb-1.5 font-medium">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3 text-[#FF6332]" />
                      <span>Journey Run Date:</span>
                    </span>
                    {selectedDate && selectedDate !== todayKey && (
                      <span className="text-sky-600 font-semibold">Active Run</span>
                    )}
                  </div>
                  <div className="grid grid-cols-3 gap-1 bg-stone-100/90 p-1 rounded-xl border border-stone-200/70">
                    {runDates.map((r) => {
                      const active = (selectedDate || todayKey) === r.key;
                      return (
                        <button
                          key={r.key}
                          type="button"
                          onClick={() => {
                            setSelectedDate(r.key);
                            setSelectedStation(null);
                            onTrainChange?.(trainNo, r.key);
                          }}
                          className={`px-1.5 py-1 rounded-lg text-center transition-all cursor-pointer ${
                            active
                              ? 'bg-[#FF6332] text-white shadow-xs font-bold'
                              : 'text-stone-600 hover:text-stone-900 hover:bg-white'
                          }`}
                        >
                          <div className="text-[11px] font-medium leading-tight">{r.label}</div>
                          <div className="text-[9px] font-mono opacity-80 leading-tight">{r.dateLabel}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* From ➔ To */}
                <div className="text-[11px] text-stone-700 font-medium flex items-center justify-between gap-1.5 bg-stone-50 px-2.5 py-1.5 rounded-xl border border-stone-200/70">
                  <span className="truncate">{d?.train?.from?.name || d?.train?.from?.code || 'Origin'}</span>
                  <ArrowRight className="w-3 h-3 text-[#FF6332] shrink-0" />
                  <span className="truncate">{d?.train?.to?.name || d?.train?.to?.code || 'Destination'}</span>
                </div>

                {/* Metrics 2x2 Grid */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="bg-stone-50 p-2 rounded-xl border border-stone-200/70">
                    <span className="text-[10px] text-stone-500 uppercase tracking-wider block">Delay Status</span>
                    <span
                      className={`font-bold inline-flex items-center gap-1 text-[11px] mt-0.5 ${
                        (d?.eta?.currentDelayMinutes ?? d?.position?.delayMinutes) == null
                          ? 'text-stone-500'
                          : (d?.eta?.currentDelayMinutes ?? d?.position?.delayMinutes)! <= 0
                          ? 'text-emerald-600'
                          : 'text-rose-600'
                      }`}
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                      {(d?.eta?.currentDelayMinutes ?? d?.position?.delayMinutes) == null
                        ? 'Calculating'
                        : (d?.eta?.currentDelayMinutes ?? d?.position?.delayMinutes)! <= 0
                        ? 'On Time'
                        : `${d?.eta?.currentDelayMinutes ?? d?.position?.delayMinutes}m Late`}
                    </span>
                  </div>

                  <div className="bg-stone-50 p-2 rounded-xl border border-stone-200/70">
                    <span className="text-[10px] text-stone-500 uppercase tracking-wider block">Speed</span>
                    <span className="text-stone-800 font-semibold text-[11px] flex items-center gap-1 mt-0.5">
                      {d?.position?.speedKmph !== null && d?.position?.speedKmph !== undefined ? (
                        `${d.position.speedKmph} km/h`
                      ) : d?.position?.distanceCoveredKm && d.position.distanceCoveredKm > 0 ? (
                        <span className="text-sky-600 flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse" />
                          <span>In Transit</span>
                        </span>
                      ) : (
                        <span className="text-stone-500">Departing Origin</span>
                      )}
                    </span>
                  </div>

                  <div className="bg-stone-50 p-2 rounded-xl border border-stone-200/70 col-span-2">
                    <div className="flex items-center justify-between text-[10px] text-stone-500">
                      <span className="uppercase tracking-wider">Current Position</span>
                      {d?.position?.lastUpdateAt && (
                        <span className="text-[9px] font-mono">{fmtTime(d.position.lastUpdateAt)}</span>
                      )}
                    </div>
                    <div className="font-bold text-stone-900 text-xs mt-0.5 flex items-center gap-1.5">
                      <MapPin className="w-3.5 h-3.5 text-[#FF6332] shrink-0" />
                      <span className="truncate">
                        {d?.position?.currentStationName ||
                          d?.position?.currentStationCode ||
                          d?.position?.lastStationName ||
                          'At Origin Station'}
                      </span>
                    </div>
                  </div>

                  {d?.position?.nextStationName && (
                    <div className="bg-stone-50 p-2 rounded-xl border border-stone-200/70 col-span-2">
                      <span className="text-[10px] text-stone-500 uppercase tracking-wider block">Next Scheduled Halt</span>
                      <div className="font-semibold text-stone-800 text-xs mt-0.5 flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-sky-600 shrink-0" />
                        <span className="truncate">{d.position.nextStationName}</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Distance Progress Bar */}
                {progress !== null && (
                  <div className="bg-stone-50 p-2 rounded-xl border border-stone-200/70">
                    <div className="flex items-center justify-between text-[10px] text-stone-500 mb-1">
                      <span>Distance Progress</span>
                      <span className="font-mono font-bold text-stone-700">{progress}%</span>
                    </div>
                    <div className="w-full bg-stone-200 h-1.5 rounded-full overflow-hidden">
                      <div
                        className="bg-gradient-to-r from-emerald-500 to-[#FF6332] h-full rounded-full transition-all duration-500"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[9px] font-mono text-stone-500 mt-1">
                      <span>{d?.position?.distanceCoveredKm ?? 0} km</span>
                      <span>{d?.position?.totalDistanceKm ?? 0} km</span>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* Floating Bottom Left: Satellite / Dark / Voyager Basemap Switcher (Matches Image 1) */}
      <div className="absolute bottom-6 left-6 z-20 pointer-events-auto">
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowBasemapMenu((prev) => !prev)}
            className="w-[74px] h-[86px] bg-white/95 hover:bg-white rounded-2xl p-1.5 shadow-2xl border border-stone-200/90 hover:border-stone-300 transition-all duration-200 cursor-pointer flex flex-col items-center justify-between hover:scale-[1.03] active:scale-95"
            title="Change Basemap Tiles (Standard / Satellite / Dark Matter)"
          >
            {/* Thumbnail Preview Box */}
            <div className="w-[62px] h-[52px] rounded-xl overflow-hidden relative shadow-inner border border-stone-200 bg-stone-100 flex items-center justify-center">
              {activeBasemap === 'satellite' ? (
                /* Satellite view thumbnail */
                <div className="w-full h-full bg-[#0b192c] relative overflow-hidden flex items-center justify-center">
                  <div className="absolute inset-0 bg-gradient-to-br from-[#1e3a5f] via-[#102a43] to-[#061826]" />
                  <div className="absolute -top-2 -right-2 w-8 h-8 rounded-full bg-emerald-800/40 blur-xs" />
                  <div className="absolute bottom-0 left-1 w-8 h-8 rounded-full bg-amber-900/30 blur-xs" />
                  <svg className="w-full h-full opacity-60" viewBox="0 0 60 50">
                    <path d="M0 30 Q20 20 40 35 T60 20" stroke="#38bdf8" strokeWidth="1" fill="none" />
                    <path d="M10 0 Q30 25 50 50" stroke="#4ade80" strokeWidth="1" fill="none" strokeDasharray="2 2" />
                  </svg>
                  <span className="absolute text-[8px] font-bold text-white bg-black/60 px-1 rounded-sm shadow-xs backdrop-blur-xs">
                    Sat
                  </span>
                </div>
              ) : activeBasemap === 'dark' ? (
                /* Dark Matter view thumbnail */
                <div className="w-full h-full bg-[#12161f] relative overflow-hidden flex items-center justify-center">
                  <div className="absolute inset-0 opacity-30 bg-[radial-gradient(#64748b_1px,transparent_1px)] [background-size:6px_6px]" />
                  <svg className="w-full h-full text-stone-600 opacity-60" viewBox="0 0 60 50">
                    <path d="M0 25 Q30 15 60 35" stroke="#334155" strokeWidth="2" fill="none" />
                    <circle cx="30" cy="22" r="2.5" fill="#FF6332" />
                  </svg>
                  <span className="absolute text-[8px] font-bold text-white bg-black/70 px-1 rounded-sm shadow-xs">
                    Dark
                  </span>
                </div>
              ) : (
                /* Map view thumbnail */
                <div className="w-full h-full bg-[#f8f9fa] relative flex items-center justify-center">
                  <div className="absolute inset-0 opacity-40 bg-[radial-gradient(#94a3b8_1px,transparent_1px)] [background-size:8px_8px]" />
                  <svg className="w-full h-full text-stone-300" viewBox="0 0 60 50">
                    <path d="M0 25 Q30 10 60 30" stroke="#cbd5e1" strokeWidth="2.5" fill="none" />
                    <path d="M20 0 Q25 25 35 50" stroke="#fbbf24" strokeWidth="2" fill="none" />
                    <circle cx="30" cy="22" r="3" fill="#FF6332" />
                  </svg>
                  <span className="absolute text-[8px] font-bold text-stone-700 bg-white/85 px-1 rounded-sm shadow-xs">
                    Map
                  </span>
                </div>
              )}
            </div>
            {/* Label (Matches Image 1) */}
            <span className="text-[11px] font-bold text-stone-800 leading-none mb-0.5">
              {activeBasemap === 'satellite' ? 'Satellite' : activeBasemap === 'dark' ? 'Dark' : 'Map'}
            </span>
          </button>

          {/* Click-Activated Basemap Popover Menu */}
          {showBasemapMenu && (
            <div className="absolute bottom-full left-0 mb-2 flex flex-col bg-white rounded-2xl shadow-2xl border border-stone-200 p-1.5 gap-1 text-[11px] font-medium text-stone-700 min-w-[140px] animate-in fade-in slide-in-from-bottom-2 z-40">
              <div className="text-[10px] font-bold text-stone-400 uppercase tracking-wider px-2 py-1 border-b border-stone-100">
                Map Style
              </div>
              <button
                type="button"
                onClick={() => {
                  setActiveBasemap('voyager');
                  setShowBasemapMenu(false);
                }}
                className={`px-2.5 py-2 rounded-xl text-left hover:bg-stone-100 transition-colors flex items-center justify-between cursor-pointer ${
                  activeBasemap === 'voyager' ? 'bg-[#FF6332]/10 font-bold text-[#FF6332]' : ''
                }`}
              >
                <span>Standard (Map)</span>
                {activeBasemap === 'voyager' && <span className="w-2 h-2 rounded-full bg-[#FF6332]" />}
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveBasemap('satellite');
                  setShowBasemapMenu(false);
                }}
                className={`px-2.5 py-2 rounded-xl text-left hover:bg-stone-100 transition-colors flex items-center justify-between cursor-pointer ${
                  activeBasemap === 'satellite' ? 'bg-[#FF6332]/10 font-bold text-[#FF6332]' : ''
                }`}
              >
                <span>Satellite</span>
                {activeBasemap === 'satellite' && <span className="w-2 h-2 rounded-full bg-[#FF6332]" />}
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveBasemap('dark');
                  setShowBasemapMenu(false);
                }}
                className={`px-2.5 py-2 rounded-xl text-left hover:bg-stone-100 transition-colors flex items-center justify-between cursor-pointer ${
                  activeBasemap === 'dark' ? 'bg-[#FF6332]/10 font-bold text-[#FF6332]' : ''
                }`}
              >
                <span>Dark Matter</span>
                {activeBasemap === 'dark' && <span className="w-2 h-2 rounded-full bg-[#FF6332]" />}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Floating Bottom Right: Vertical White Navigation Dock (Matches Image 2) */}
      <div className="absolute bottom-6 right-6 z-20 pointer-events-auto flex flex-col items-center bg-white/95 backdrop-blur-md rounded-2xl shadow-xl border border-stone-200/90 p-1 text-stone-700">
        {/* 1. Layers Button */}
        <button
          type="button"
          onClick={() => setShowLayerFilterModal((prev) => !prev)}
          className={`p-2.5 rounded-xl transition-all cursor-pointer ${
            showLayerFilterModal ? 'bg-stone-100 text-[#FF6332]' : 'hover:bg-stone-100 text-stone-700 hover:text-stone-950'
          }`}
          title="Map Layers & Station Filters"
        >
          <Layers className="w-5 h-5" />
        </button>

        {/* 2. Crosshair / Live GPS Location Button */}
        <button
          type="button"
          onClick={locateUserGps}
          className={`p-2.5 rounded-xl hover:bg-stone-100 text-stone-700 hover:text-stone-950 transition-all cursor-pointer relative ${
            gpsLoading ? 'animate-spin text-[#FF6332]' : ''
          }`}
          title="Locate My Live GPS Position"
        >
          <Crosshair className={`w-5 h-5 ${gpsLoading ? 'text-[#FF6332]' : ''}`} />
          {gpsLoading && (
            <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-[#FF6332] animate-ping" />
          )}
        </button>

        {/* Divider (Horizontal line matching Image 2) */}
        <div className="w-6 h-[1px] bg-stone-200 my-1" />

        {/* 3. Zoom In (+) */}
        <button
          type="button"
          onClick={zoomIn}
          className="p-2.5 rounded-xl hover:bg-stone-100 text-stone-700 hover:text-stone-950 transition-all cursor-pointer"
          title="Zoom In"
        >
          <Plus className="w-5 h-5" />
        </button>

        {/* 4. Zoom Out (-) */}
        <button
          type="button"
          onClick={zoomOut}
          className="p-2.5 rounded-xl hover:bg-stone-100 text-stone-700 hover:text-stone-950 transition-all cursor-pointer"
          title="Zoom Out"
        >
          <Minus className="w-5 h-5" />
        </button>
      </div>

      {/* Station Layers & Filter Modal (Triggered by Layers in White Dock) */}
      {showLayerFilterModal && (
        <div className="absolute bottom-28 right-6 z-30 bg-white rounded-2xl shadow-2xl border border-stone-200 p-3.5 w-68 text-stone-800 animate-in fade-in slide-in-from-bottom-2 pointer-events-auto">
          <div className="flex items-center justify-between pb-2 border-b border-stone-100">
            <div className="flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-[#FF6332]" />
              <span className="text-xs font-bold text-stone-900">Map & Stations</span>
            </div>
            <button
              type="button"
              onClick={() => setShowLayerFilterModal(false)}
              className="text-stone-400 hover:text-stone-700 p-1 cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Basemap Switcher inside Layers Modal */}
          <div className="mt-2.5">
            <div className="text-[10px] uppercase font-bold tracking-wider text-stone-400 px-1 mb-1">
              Basemap Tile
            </div>
            <div className="grid grid-cols-3 gap-1 bg-stone-100/80 p-1 rounded-xl">
              {(['voyager', 'satellite', 'dark'] as BasemapType[]).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setActiveBasemap(mode)}
                  className={`py-1 px-1.5 rounded-lg text-center text-[10px] capitalize transition-all cursor-pointer ${
                    activeBasemap === mode
                      ? 'bg-white font-bold text-[#FF6332] shadow-xs'
                      : 'text-stone-600 hover:text-stone-900'
                  }`}
                >
                  {mode === 'voyager' ? 'Map' : mode === 'satellite' ? 'Satellite' : 'Dark'}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-3 space-y-1.5">
            <div className="text-[10px] uppercase font-bold tracking-wider text-stone-400 px-1">
              Station Density
            </div>
            {[
              { id: 'auto', label: 'Adaptive LOD (Smart)', desc: 'Hubs on zoom-out, halts on zoom-in' },
              { id: 'major', label: 'Major Junctions Only', desc: 'Terminals & large division hubs' },
              { id: 'halts', label: 'Passenger Halts', desc: 'Active commercial stops' },
              { id: 'all', label: 'All 8,800+ Stations', desc: 'Full national network with loops' },
            ].map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => {
                  setFilterMode(f.id as StationFilterMode);
                }}
                className={`w-full text-left px-2.5 py-1.5 rounded-xl transition-all cursor-pointer flex items-center justify-between ${
                  filterMode === f.id
                    ? 'bg-[#FF6332]/10 text-[#FF6332] font-semibold border border-[#FF6332]/30'
                    : 'hover:bg-stone-50 text-stone-700'
                }`}
              >
                <div>
                  <div className="text-xs leading-tight">{f.label}</div>
                  <div className="text-[9px] text-stone-400 leading-tight mt-0.5">{f.desc}</div>
                </div>
                {filterMode === f.id && <span className="w-2 h-2 rounded-full bg-[#FF6332]" />}
              </button>
            ))}
          </div>

          <div className="mt-3 pt-2 border-t border-stone-100 flex items-center justify-between text-[10px] text-stone-400 px-1 font-mono">
            <span>Map Zoom: z{currentZoom}</span>
            <span>{allStations.length.toLocaleString()} Stations</span>
          </div>
        </div>
      )}

      {/* Station Popover / Inspector Card (Floating when station clicked) */}
      {selectedStation && (
        <div className="absolute bottom-28 left-4 z-30 bg-white/98 backdrop-blur-2xl rounded-3xl p-4.5 border border-stone-200/90 text-stone-800 w-80 sm:w-88 shadow-2xl animate-in fade-in slide-in-from-bottom-2 pointer-events-auto">
          <div className="flex items-start justify-between gap-3 mb-2">
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-bold text-stone-900">{selectedStation.name}</h4>
                <span className="font-mono text-[11px] px-1.5 py-0.5 rounded-md bg-[#FF6332]/10 text-[#FF6332] font-bold border border-[#FF6332]/20">
                  {selectedStation.code}
                </span>
              </div>
              <p className="text-[11px] text-stone-500 mt-0.5">
                {selectedStation.isPanIndia
                  ? `${selectedStation.zone || 'IR'} Zone · ${selectedStation.state || 'India'}`
                  : selectedStation.liveStop?.distanceKm !== null && selectedStation.liveStop?.distanceKm !== undefined
                  ? `${selectedStation.liveStop.distanceKm} km from origin`
                  : 'Timetable Waypoint'}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setSelectedStation(null)}
              className="text-stone-400 hover:text-stone-700 text-xs font-bold p-1 cursor-pointer transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="space-y-1.5 text-xs pt-2 border-t border-stone-100">
            {selectedStation.isPanIndia ? (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-stone-500">Category:</span>
                  <span
                    className={`font-semibold px-2 py-0.5 rounded-full text-[10px] ${
                      selectedStation.category === 'Terminal'
                        ? 'bg-rose-50 text-rose-700 border border-rose-200'
                        : selectedStation.category === 'Junction'
                        ? 'bg-amber-50 text-amber-700 border border-amber-200'
                        : selectedStation.category === 'Major'
                        ? 'bg-sky-50 text-sky-700 border border-sky-200'
                        : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    }`}
                  >
                    {selectedStation.category || 'Standard Station'}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-stone-500">Scheduled Trains:</span>
                  <span className="font-mono font-bold text-stone-800">
                    {selectedStation.train_count ? `${selectedStation.train_count} Trains Passing` : 'Passing Loop / Halt'}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-stone-500">Coordinates:</span>
                  <span className="font-mono text-[10px] text-stone-600">
                    {selectedStation.lat?.toFixed(4)}°N, {selectedStation.lon?.toFixed(4)}°E
                  </span>
                </div>

                <div className="pt-2 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      if (mapInstanceRef.current && selectedStation.lat && selectedStation.lon) {
                        mapInstanceRef.current.setView([selectedStation.lat, selectedStation.lon], 12, { animate: true });
                      }
                    }}
                    className="flex-1 py-1.5 px-2.5 rounded-xl bg-stone-100 hover:bg-stone-200/80 text-stone-800 text-[11px] font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer border border-stone-200/80"
                  >
                    <Crosshair className="w-3.5 h-3.5 text-[#FF6332]" />
                    <span>Zoom In</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setTrainInput(selectedStation.code);
                      setHudCollapsed(false);
                    }}
                    className="flex-1 py-1.5 px-2.5 rounded-xl bg-[#FF6332] hover:bg-orange-600 text-white text-[11px] font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer shadow-xs"
                  >
                    <Search className="w-3.5 h-3.5" />
                    <span>Find Trains</span>
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-stone-500">Stop Classification:</span>
                  <span
                    className={`font-semibold px-2 py-0.5 rounded-full text-[10px] ${
                      selectedStation.isCurrent
                        ? 'bg-[#FF6332]/10 text-[#FF6332] border border-[#FF6332]/30'
                        : selectedStation.isPassed
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-stone-100 text-stone-700 border border-stone-200'
                    }`}
                  >
                    {selectedStation.isCurrent ? 'CURRENT LOCATION' : selectedStation.isPassed ? 'PASSED' : 'UPCOMING'}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-stone-500">Station Type:</span>
                  <span className="text-stone-800 text-[11px] font-medium">
                    {selectedStation.tier === 1 ? 'Major Junction / Hub' : selectedStation.tier === 2 ? 'Booked Passenger Halt' : 'Passing Station / Loop'}
                  </span>
                </div>

                {selectedStation.liveStop && (
                  <>
                    <div className="flex items-center justify-between">
                      <span className="text-stone-500">Scheduled:</span>
                      <span className="font-mono text-stone-800">
                        {fmtTime(selectedStation.liveStop.scheduled.arrival ?? selectedStation.liveStop.scheduled.departure)}
                        {selectedStation.liveStop.scheduled.departure && selectedStation.liveStop.scheduled.arrival !== selectedStation.liveStop.scheduled.departure && (
                          <span className="text-stone-400 text-[10px]"> (dep {fmtTime(selectedStation.liveStop.scheduled.departure)})</span>
                        )}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-stone-500">{selectedStation.isPassed ? 'Actual Time:' : 'Estimated ETA:'}</span>
                      <span className="font-mono font-bold text-stone-900">
                        {fmtTime(
                          selectedStation.isPassed
                            ? (selectedStation.liveStop.actual.arrival ?? selectedStation.liveStop.actual.departure ?? selectedStation.liveStop.eta.arrival)
                            : (selectedStation.liveStop.eta.arrival ?? selectedStation.liveStop.scheduled.departure)
                        )}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-stone-500">Platform:</span>
                      <span className="font-mono font-bold text-stone-800">
                        {selectedStation.liveStop.platform ? `PF ${selectedStation.liveStop.platform}` : 'Unassigned'}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-stone-500">Delay:</span>
                      <span
                        className={`font-semibold ${
                          selectedStation.liveStop.eta.delayMinutes === null
                            ? 'text-stone-400'
                            : selectedStation.liveStop.eta.delayMinutes <= 0
                            ? 'text-emerald-600'
                            : 'text-rose-600'
                        }`}
                      >
                        {fmtDelay(selectedStation.liveStop.eta.delayMinutes)}
                      </span>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Floating Bottom Center: Coach Formation Drawer Toggle */}
      {isTrain && d?.composition && d.composition.length > 0 && (
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-20 pointer-events-auto flex flex-col items-center">
          <button
            type="button"
            onClick={() => setShowCoaches(!showCoaches)}
            className="px-4 py-2 rounded-full bg-white/95 backdrop-blur-xl border border-stone-200/90 text-stone-800 text-xs font-bold flex items-center gap-2 shadow-2xl hover:bg-white hover:border-stone-300 transition-all cursor-pointer"
          >
            <TrainFront className="w-3.5 h-3.5 text-[#FF6332]" />
            <span>Coach Position ({d.composition.length} Units)</span>
            {showCoaches ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
          </button>

          {/* Collapsible Verified Coach Formation Layout */}
          {showCoaches && (
            <div className="mt-2 p-3.5 bg-white/98 backdrop-blur-2xl rounded-3xl border border-stone-200/90 text-stone-800 shadow-2xl animate-in fade-in slide-in-from-bottom-2 max-w-[95vw] sm:max-w-xl">
              <div className="flex items-center justify-between mb-2 text-[10px] text-stone-500 px-1 gap-2">
                <span className="font-bold text-stone-700">Engine Front ➔ Rear Guard</span>
                <div className="flex items-center gap-2">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-purple-300" /> 1A</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-sky-300" /> 2A</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-emerald-300" /> 3A</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-amber-300" /> SL</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-stone-300" /> GEN</span>
                </div>
              </div>

              <div className="flex items-center gap-1.5 overflow-x-auto pb-1.5 pt-0.5 scrollbar-none">
                <div className="shrink-0 px-2.5 py-1 rounded-lg bg-stone-900 text-white text-center min-w-[50px] border border-stone-800 shadow-xs">
                  <div className="text-[10px] font-mono font-bold">LOCO</div>
                  <div className="text-[7px] text-stone-400">ENGINE</div>
                </div>

                {d.composition.map((c: any, i: number) => {
                  const coachCode = c.label || c.code || `C${c.position ?? i + 1}`;
                  const coachClass = c.type || c.class || '';
                  const style = getCoachStyle(coachCode, coachClass);

                  return (
                    <div
                      key={`${coachCode}-${i}`}
                      title={`${coachCode}: ${c.category || coachClass || 'Coach'} (#${c.position ?? i + 1})`}
                      className={`shrink-0 px-2 py-1 rounded-lg border text-center min-w-[44px] ${style}`}
                    >
                      <div className="text-[10px] font-mono font-bold">{coachCode}</div>
                      <div className="text-[7px] opacity-75 font-mono">{coachClass || 'GEN'}</div>
                    </div>
                  );
                })}

                <div className="shrink-0 px-2.5 py-1 rounded-lg bg-stone-800 text-stone-200 text-center min-w-[46px] border border-stone-700 shadow-xs">
                  <div className="text-[10px] font-mono font-bold">GUARD</div>
                  <div className="text-[7px] text-stone-400">REAR</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default MapPage;
