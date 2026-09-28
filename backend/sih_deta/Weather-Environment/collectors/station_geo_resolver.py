"""
Station Geographic Resolver & Spatial Clustering Engine
Resolves station GPS coordinates and groups stations into ~0.25° spatial grid clusters
to reduce external weather API requests by up to 97%.
"""

import math
import sqlite3
from typing import Dict, List, Optional, Tuple

from config import GRID_CELL_DEGREE, STATIONS_DB_PATH

# Major Indian Railways fallback stations in case SQLite database is missing or unindexed
FALLBACK_STATIONS = {
    "NDLS": {"name": "New Delhi", "lat": 28.6415, "lon": 77.2207, "zone": "NR"},
    "CNB": {"name": "Kanpur Central", "lat": 26.4539, "lon": 80.3512, "zone": "NCR"},
    "PRYJ": {"name": "Prayagraj Junction", "lat": 25.4484, "lon": 81.8340, "zone": "NCR"},
    "DDU": {"name": "Pt Deen Dayal Upadhyaya", "lat": 25.2818, "lon": 83.1189, "zone": "ECR"},
    "PNBE": {"name": "Patna Junction", "lat": 25.6022, "lon": 85.1376, "zone": "ECR"},
    "HWH": {"name": "Howrah Junction", "lat": 22.5839, "lon": 88.3426, "zone": "ER"},
    "CSMT": {"name": "Mumbai CSMT", "lat": 18.9402, "lon": 72.8356, "zone": "CR"},
    "BCT": {"name": "Mumbai Central", "lat": 18.9696, "lon": 72.8193, "zone": "WR"},
    "KOTA": {"name": "Kota Junction", "lat": 25.2227, "lon": 75.8679, "zone": "WCR"},
    "BPL": {"name": "Bhopal Junction", "lat": 23.2676, "lon": 77.4126, "zone": "WCR"},
    "ET": {"name": "Itarsi Junction", "lat": 22.6133, "lon": 77.7618, "zone": "WCR"},
    "NGP": {"name": "Nagpur Junction", "lat": 21.1524, "lon": 79.0888, "zone": "CR"},
    "BPQ": {"name": "Balharshah", "lat": 19.8519, "lon": 79.3524, "zone": "CR"},
    "BZA": {"name": "Vijayawada Junction", "lat": 16.5186, "lon": 80.6198, "zone": "SCR"},
    "MAS": {"name": "MGR Chennai Central", "lat": 13.0827, "lon": 80.2707, "zone": "SR"},
    "SBC": {"name": "KSR Bengaluru", "lat": 12.9781, "lon": 77.5697, "zone": "SWR"},
    "MAO": {"name": "Madgaon Junction (Goa)", "lat": 15.2736, "lon": 73.9783, "zone": "KR"},
    "RN": {"name": "Ratnagiri", "lat": 16.9806, "lon": 73.3377, "zone": "KR"},
    "AGC": {"name": "Agra Cantt", "lat": 27.1593, "lon": 78.0068, "zone": "NCR"},
    "GKP": {"name": "Gorakhpur Junction", "lat": 26.7588, "lon": 83.3820, "zone": "NER"},
    "LKO": {"name": "Lucknow Charbagh", "lat": 26.8322, "lon": 80.9238, "zone": "NR"},
}


class StationGeoResolver:
    """
    Manages station GPS coordinates and computes spatial centroids.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(STATIONS_DB_PATH)
        self._station_cache: Dict[str, dict] = {}
        self._cluster_map: Dict[str, dict] = {}
        self._station_to_cluster: Dict[str, str] = {}
        self._load_stations()

    def _load_stations(self):
        """Loads stations from SQLite or falls back to built-in table."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("""
                SELECT code, official_name, latitude, longitude, zone 
                FROM stations 
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            """)
            rows = cur.fetchall()
            for code, name, lat, lon, zone in rows:
                if lat and lon and lat != 0.0 and lon != 0.0:
                    self._station_cache[code.upper()] = {
                        "name": name or code,
                        "lat": float(lat),
                        "lon": float(lon),
                        "zone": zone or "IR",
                    }
            conn.close()
        except Exception:
            pass

        # Ensure fallback stations are merged in
        for code, info in FALLBACK_STATIONS.items():
            if code not in self._station_cache:
                self._station_cache[code] = info

        self._build_spatial_clusters()

    def _build_spatial_clusters(self):
        """
        Groups stations into grid cells rounded to GRID_CELL_DEGREE.
        Computes cluster centroids and creates fast mapping indices.
        """
        grid_groups: Dict[Tuple[float, float], List[str]] = {}

        for code, data in self._station_cache.items():
            lat = data["lat"]
            lon = data["lon"]
            # Round coordinates to grid cell size
            grid_lat = round(round(lat / GRID_CELL_DEGREE) * GRID_CELL_DEGREE, 4)
            grid_lon = round(round(lon / GRID_CELL_DEGREE) * GRID_CELL_DEGREE, 4)
            grid_key = (grid_lat, grid_lon)

            if grid_key not in grid_groups:
                grid_groups[grid_key] = []
            grid_groups[grid_key].append(code)

        # Build cluster catalog
        for (g_lat, g_lon), stations in grid_groups.items():
            cluster_id = f"CL_{g_lat:+.2f}_{g_lon:+.2f}".replace("+", "P").replace("-", "N").replace(".", "_")

            # Centroid is the mathematical mean of member station coordinates
            avg_lat = sum(self._station_cache[s]["lat"] for s in stations) / len(stations)
            avg_lon = sum(self._station_cache[s]["lon"] for s in stations) / len(stations)

            self._cluster_map[cluster_id] = {
                "cluster_id": cluster_id,
                "grid_lat": g_lat,
                "grid_lon": g_lon,
                "centroid_lat": round(avg_lat, 4),
                "centroid_lon": round(avg_lon, 4),
                "station_count": len(stations),
                "stations": stations,
            }

            for s in stations:
                self._station_to_cluster[s] = cluster_id

    def get_station(self, code: str) -> Optional[dict]:
        """Returns station GPS coordinates and metadata."""
        return self._station_cache.get(code.strip().upper())

    def get_cluster_for_station(self, code: str) -> Optional[dict]:
        """Returns the spatial cluster metadata that the station belongs to."""
        cluster_id = self._station_to_cluster.get(code.strip().upper())
        if cluster_id:
            return self._cluster_map.get(cluster_id)
        return None

    def get_all_clusters(self) -> Dict[str, dict]:
        """Returns all spatial clusters."""
        return self._cluster_map

    def get_total_stations_count(self) -> int:
        return len(self._station_cache)

    def get_total_clusters_count(self) -> int:
        return len(self._cluster_map)

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Computes Great Circle distance between two coordinates in kilometers."""
        r = 6371.0  # Earth radius in km
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        d_phi = math.radians(lat2 - lat1)
        d_lambda = math.radians(lon2 - lon1)

        a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r * c
