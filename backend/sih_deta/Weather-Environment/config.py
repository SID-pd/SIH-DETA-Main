"""
SIH-DETA Weather & Environmental Constraints Configuration
Defines API endpoints, Indian Railways G&SR statutory thresholds, and caching parameters.
"""

from pathlib import Path

# Paths
MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
EXPORTS_DIR = DATA_DIR / "exports"
CACHE_DIR = DATA_DIR / "cache"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DB_PATH = DATA_DIR / "weather.db"
STATIONS_DB_PATH = MODULE_DIR.parent / "Station-Halt Scraper" / "data" / "stations.db"
TRAINS_DB_PATH = MODULE_DIR.parent / "Train-Scraper" / "data" / "trains.db"

# Open-Meteo REST API Endpoints
FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_API_URL = "https://archive-api.open-meteo.com/v1/archive"

# Geographic & Spatial Clustering Configuration
GRID_CELL_DEGREE = 0.25  # ~25 km x 28 km mesoscale grid
TIMEZONE_DEFAULT = "Asia/Kolkata"
REQUEST_TIMEOUT_SECONDS = 12.0
MAX_RETRIES = 3
BACKOFF_FACTOR = 1.5
CACHE_TTL_SECONDS = 3600  # 1 hour in-memory cache TTL for live observations

# ==============================================================================
# Indian Railways G&SR Operational Constants
# ==============================================================================

# 1. Fog Visibility Rules (G&SR 3.61 & Railway Board Directives)
FOG_VISIBILITY_THRESHOLD_METERS = 600.0  # Dense fog begins below 600m
FOG_SEVERE_THRESHOLD_METERS = 100.0      # Zero-visibility emergency below 100m
SPEED_CAP_STANDARD_FOG = 60              # km/h standard locomotive rule
SPEED_CAP_FOG_PASS_GPS = 75              # km/h if fitted with ISRO/GPS FOG-PASS unit
SPEED_CAP_SEVERE_FOG = 30                # km/h blind signal approach caution
NOMINAL_TRACK_MPS = 130                  # km/h standard superfast / Rajdhani MPS

# 2. Monsoon & Waterlogging Rules (G&SR 2.11)
# Konkan Railway Monsoon Timetable runs from June 10 to October 31
KONKAN_MONSOON_START = (6, 10)  # (Month, Day)
KONKAN_MONSOON_END = (10, 31)   # (Month, Day)
SPEED_CAP_KONKAN_MONSOON = 75   # km/h (reduced from nominal 110-120 km/h)

# Water Above Rail Flange Rule
FLANGE_WATER_RAIN_THRESHOLD_MM = 50.0  # mm/hr extreme downpour triggering waterlogging risk
SPEED_CAP_FLANGE_WATER = 10            # km/h strict caution / stop-and-proceed

# Konkan Railway Known Station Codes / Prefixes
KONKAN_STATIONS = {
    "ROHA", "MNI", "KHED", "CHI", "SVX", "SGR", "RN", "ADVI", "VID", "RAJP",
    "VBW", "KKW", "SNDD", "KUDL", "SWV", "MADR", "PERN", "THVM", "KRMI", "MAO",
    "BWS", "CNO", "AT", "KAWR", "ANKL", "GOK", "KT", "MRDW", "BTJL", "BYNR",
    "KUDA", "BKJ", "UD", "MULK", "SL", "TOK", "MAJN"
}

# 3. Summer Rail Temperature & Buckling Rules (Track Manual Para 5.2)
# Rail surface temperature heats up beyond ambient: T_rail = T_air + 0.022 * solar_radiation_W/m2
# Or approximation: T_rail = T_air + 18°C during peak sunlight
RAIL_TEMP_SOLAR_COEFF = 0.022
RAIL_TEMP_DEFAULT_OFFSET = 18.0
RAIL_BUCKLING_THRESHOLD_C = 60.0  # Td + 20°C where neutral temp Td ~ 40°C in India
SPEED_CAP_HEAT_BUCKLING = 40      # km/h midday speed restriction for hot weather patrolling
