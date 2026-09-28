"""
SIH-DETA Network Anomalies & Stochastic Incidents Configuration
Defines operational incident categories, detention distributions, and bottleneck junction topology.
"""

from pathlib import Path

# Paths
MODULE_DIR = Path(__file__).resolve().parent
DATA_DIR = MODULE_DIR / "data"
EXPORTS_DIR = DATA_DIR / "exports"

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DB_PATH = DATA_DIR / "anomalies.db"
HISTORICAL_DB_PATH = MODULE_DIR.parent / "Historical-Delay-Records" / "data" / "historical.db"
BACKUP_HISTORICAL_DB_PATH = Path("/scratch/home/sid01/sih_deta_data_backup/Historical-Delay-Records-data/historical.db")
STATIONS_DB_PATH = MODULE_DIR.parent / "Station-Halt Scraper" / "data" / "stations.db"

# ==============================================================================
# Indian Railways Stochastic Incident Categories & Parameters
# ==============================================================================

INCIDENT_CATEGORIES = {
    "SIGNAL_FAILURE_AUTO": {
        "name": "Automatic Block Signal Failure (Stop & Proceed)",
        "mean_detention_min": 25.0,
        "std_dev_min": 8.0,
        "min_detention_min": 10.0,
        "max_detention_min": 60.0,
        "speed_restriction_kmh": 15,
        "description": "Signal at danger; loco pilot stops 1 min (day) / 2 min (night), then proceeds at 15 km/h",
    },
    "SIGNAL_FAILURE_ABSOLUTE": {
        "name": "Absolute Block Signal Failure (PLCT Operation)",
        "mean_detention_min": 65.0,
        "std_dev_min": 20.0,
        "min_detention_min": 35.0,
        "max_detention_min": 150.0,
        "speed_restriction_kmh": 25,
        "description": "Block instrument failure; stations revert to manual Paper Line Clear Ticket dispatching",
    },
    "ALARM_CHAIN_PULLING": {
        "name": "Alarm Chain Pulling (ACP) & Brake Binding",
        "mean_detention_min": 18.0,
        "std_dev_min": 6.0,
        "min_detention_min": 8.0,
        "max_detention_min": 45.0,
        "speed_restriction_kmh": 0,
        "description": "Crew resets coach clack valve and waits for brake pipe pressure to rebuild to 5.0 kg/cm2",
    },
    "CATTLE_RUN_OVER": {
        "name": "Cattle Run-Over (CRO) & Track Obstruction",
        "mean_detention_min": 30.0,
        "std_dev_min": 12.0,
        "min_detention_min": 15.0,
        "max_detention_min": 75.0,
        "speed_restriction_kmh": 0,
        "description": "Emergency braking inspection, air hose continuity check, and cattle carcass clearance",
    },
    "OHE_BREAKDOWN": {
        "name": "Overhead Equipment (OHE) & Traction Failure",
        "mean_detention_min": 85.0,
        "std_dev_min": 35.0,
        "min_detention_min": 40.0,
        "max_detention_min": 240.0,
        "speed_restriction_kmh": 0,
        "description": "Pantograph entanglement or substation tripping; tower wagon deployed or diesel rescue",
    },
    "OUTER_SIGNAL_WAIT": {
        "name": "Junction Outer Home Signal Queuing (Platform Starvation)",
        "mean_detention_min": 28.0,
        "std_dev_min": 10.0,
        "min_detention_min": 10.0,
        "max_detention_min": 65.0,
        "speed_restriction_kmh": 0,
        "description": "Platform starvation / interlocking queuing outside high-density junction throats",
    },
}

# High-Congestion Junctions Prone to Outer Signal Queuing
BOTTLENECK_JUNCTIONS = {
    "CNB": {"name": "Kanpur Central", "platforms": 10, "peak_congestion_factor": 1.45},
    "PRYJ": {"name": "Prayagraj Junction", "platforms": 10, "peak_congestion_factor": 1.35},
    "DDU": {"name": "Pt Deen Dayal Upadhyaya", "platforms": 8, "peak_congestion_factor": 1.40},
    "GZB": {"name": "Ghaziabad Junction", "platforms": 6, "peak_congestion_factor": 1.50},
    "ET": {"name": "Itarsi Junction", "platforms": 8, "peak_congestion_factor": 1.30},
    "BZA": {"name": "Vijayawada Junction", "platforms": 10, "peak_congestion_factor": 1.25},
    "NGP": {"name": "Nagpur Junction", "platforms": 8, "peak_congestion_factor": 1.20},
    "BSL": {"name": "Bhusawal Junction", "platforms": 8, "peak_congestion_factor": 1.25},
    "PNBE": {"name": "Patna Junction", "platforms": 10, "peak_congestion_factor": 1.30},
    "ADI": {"name": "Ahmedabad Junction", "platforms": 12, "peak_congestion_factor": 1.20},
}

# Historical 3-Sigma Anomaly Detection Parameters
ANOMALY_SIGMA_THRESHOLD = 3.0  # Delays exceeding mean + 3*std are classified as stochastic anomalies
MIN_SECTIONAL_SAMPLES = 10     # Minimum historical runs to compute robust z-scores
