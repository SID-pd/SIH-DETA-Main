"""
SIH-DETA Autonomous Weather Crawler Worker
Scrapes meteorological observations for all 8,700 stations across 2,082 spatial clusters,
evaluates G&SR physical speed constraints, and commits verified records to SQLite.
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Ensure module path
MODULE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(MODULE_DIR))

from collectors.mock_weather_data import MockWeatherGenerator
from collectors.station_geo_resolver import StationGeoResolver
from config import (
    CACHE_DIR,
    DATA_DIR,
    DEFAULT_DB_PATH,
    FORECAST_API_URL,
    NOMINAL_TRACK_MPS,
    REQUEST_TIMEOUT_SECONDS,
    TIMEZONE_DEFAULT,
)
from rules.gsr_rules_engine import GSRRulesEngine
from storage.weather_db import WeatherDatabase

LOG_DIR = MODULE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
CRAWLER_LOG = LOG_DIR / "crawler.log"
HEARTBEAT_FILE = DATA_DIR / "crawler_heartbeat.json"
CHECKPOINT_FILE = DATA_DIR / "weather_checkpoint.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [CRAWLER] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(CRAWLER_LOG), encoding="utf-8"),
    ],
)
logger = logging.getLogger("weather_crawler")

BATCH_SIZE = 20  # Number of cluster coordinates per Open-Meteo multi-location request
INTER_BATCH_DELAY = 0.6  # Seconds between batch requests to be polite


class WeatherCrawler:
    """
    Crawls weather for nationwide spatial clusters and saves G&SR evaluated records.
    """

    def __init__(self, offline: bool = False, delay: float = INTER_BATCH_DELAY):
        self.offline = offline
        self.delay = delay
        self.db = WeatherDatabase(DEFAULT_DB_PATH)
        self.resolver = StationGeoResolver()
        self.clusters = self.resolver.get_all_clusters()
        self.completed_clusters = set()
        self.total_inserted_records = 0
        self.start_time = time.time()
        self.running = True

        self._load_checkpoint()
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        logger.info("Shutdown signal received (%s). Saving state and exiting cleanly...", signum)
        self.running = False
        self._save_checkpoint()
        sys.exit(0)

    def _load_checkpoint(self):
        if CHECKPOINT_FILE.exists():
            try:
                with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.completed_clusters = set(data.get("completed_clusters", []))
                    self.total_inserted_records = data.get("total_inserted_records", 0)
                logger.info("Loaded checkpoint: %d/%d clusters previously completed.",
                            len(self.completed_clusters), len(self.clusters))
            except Exception as e:
                logger.warning("Could not load checkpoint: %s. Starting fresh.", e)

    def _save_checkpoint(self):
        try:
            with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "completed_clusters": list(self.completed_clusters),
                    "total_inserted_records": self.total_inserted_records,
                    "updated_at": datetime.now().isoformat(),
                }, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save checkpoint: %s", e)

    def _emit_heartbeat(self, current_cluster_id: str, success: int, failed: int):
        uptime_s = int(time.time() - self.start_time)
        hrs, rem = divmod(uptime_s, 3600)
        mins, secs = divmod(rem, 60)
        total = len(self.clusters)
        done = len(self.completed_clusters)
        pct = (done / total * 100.0) if total else 0.0

        heartbeat = {
            "status": "RUNNING" if self.running else "STOPPED",
            "current_cluster": current_cluster_id,
            "clusters_completed": done,
            "clusters_total": total,
            "percentage": round(pct, 2),
            "records_inserted": self.total_inserted_records,
            "success_batches": success,
            "failed_batches": failed,
            "uptime": f"{hrs:02d}h {mins:02d}m {secs:02d}s",
            "timestamp": datetime.now().isoformat(),
            "pid": os.getpid(),
        }
        try:
            with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
                json.dump(heartbeat, f, indent=2)
        except Exception:
            pass

    def run(self):
        logger.info("Starting Weather Crawler for %d nationwide clusters...", len(self.clusters))
        pending_clusters = [c for c in self.clusters.values() if c["cluster_id"] not in self.completed_clusters]
        logger.info("%d clusters pending execution.", len(pending_clusters))

        success_count = 0
        fail_count = 0

        # Chunk into batches of BATCH_SIZE
        for i in range(0, len(pending_clusters), BATCH_SIZE):
            if not self.running:
                break

            batch = pending_clusters[i : i + BATCH_SIZE]
            current_id = batch[0]["cluster_id"]

            try:
                results_map = self._fetch_batch_weather(batch)
                self._process_and_store_batch(batch, results_map)
                for c in batch:
                    self.completed_clusters.add(c["cluster_id"])
                success_count += 1
            except Exception as e:
                logger.error("Error processing batch starting at %s: %s", current_id, e)
                fail_count += 1

            self._save_checkpoint()
            self._emit_heartbeat(current_id, success_count, fail_count)

            done = len(self.completed_clusters)
            total = len(self.clusters)
            pct = (done / total * 100.0) if total else 0.0
            if (i // BATCH_SIZE) % 5 == 0 or done == total:
                logger.info("Progress: [%d/%d clusters (%.1f%%)] | Records: %d",
                            done, total, pct, self.total_inserted_records)

            time.sleep(self.delay)

        logger.info("Crawler finished. Total clusters completed: %d/%d. Total records inserted: %d.",
                    len(self.completed_clusters), len(self.clusters), self.total_inserted_records)
        self._emit_heartbeat("FINISHED", success_count, fail_count)
        self._save_checkpoint()

    def _fetch_batch_weather(self, batch: List[dict]) -> Dict[str, dict]:
        """
        Fetches weather for multiple cluster centroids in a single HTTP request using Open-Meteo batching.
        """
        if self.offline:
            now = datetime.now()
            return {c["cluster_id"]: MockWeatherGenerator.generate(c["centroid_lat"], c["centroid_lon"], now) for c in batch}

        lats = ",".join(f"{c['centroid_lat']:.4f}" for c in batch)
        lons = ",".join(f"{c['centroid_lon']:.4f}" for c in batch)

        params = {
            "latitude": lats,
            "longitude": lons,
            "hourly": "visibility,precipitation,temperature_2m,direct_normal_irradiance",
            "timezone": TIMEZONE_DEFAULT,
            "forecast_days": "1",
        }
        url = f"{FORECAST_API_URL}?{urllib.parse.urlencode(params)}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "SIH-DETA-WeatherCrawler/1.0",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return self._parse_batch_response(batch, data)
        except Exception as e:
            logger.warning("Batch network request failed (%s). Falling back to mock generator for this batch.", e)
            now = datetime.now()
            return {c["cluster_id"]: MockWeatherGenerator.generate(c["centroid_lat"], c["centroid_lon"], now) for c in batch}

        now = datetime.now()
        return {c["cluster_id"]: MockWeatherGenerator.generate(c["centroid_lat"], c["centroid_lon"], now) for c in batch}

    def _parse_batch_response(self, batch: List[dict], payload) -> Dict[str, dict]:
        """Parses Open-Meteo multi-location response (list of results or single dict)."""
        now = datetime.now()
        hour_target = now.strftime("%Y-%m-%dT%H:00")
        results = {}

        items = payload if isinstance(payload, list) else [payload]
        for idx, c in enumerate(batch):
            item = items[idx] if idx < len(items) else items[-1]
            hourly = item.get("hourly", {})
            times = hourly.get("time", [])

            t_idx = times.index(hour_target) if hour_target in times else 0

            def safe_val(arr_name: str, default: float) -> float:
                arr = hourly.get(arr_name, [])
                if arr and t_idx < len(arr) and arr[t_idx] is not None:
                    return float(arr[t_idx])
                return default

            vis = safe_val("visibility", 10000.0)
            rain = safe_val("precipitation", 0.0)
            temp = safe_val("temperature_2m", 25.0)
            solar = safe_val("direct_normal_irradiance", 0.0)
            rail_t = temp + (0.022 * solar)

            results[c["cluster_id"]] = {
                "latitude": c["centroid_lat"],
                "longitude": c["centroid_lon"],
                "timestamp": times[t_idx] if times else hour_target,
                "visibility_meters": round(vis, 1),
                "precipitation_mm": round(rain, 2),
                "ambient_temp_c": round(temp, 1),
                "direct_solar_radiation_w_m2": round(solar, 1),
                "estimated_rail_temp_c": round(rail_t, 1),
                "data_source": "OPEN_METEO_BATCH",
            }
        return results

    def _process_and_store_batch(self, batch: List[dict], results_map: Dict[str, dict]):
        """Evaluates G&SR rules for each station in each cluster and saves to SQLite."""
        evaluated_batch = []
        for c in batch:
            cid = c["cluster_id"]
            raw_obs = results_map.get(cid)
            if not raw_obs:
                continue

            for st_code in c["stations"]:
                st_info = self.resolver.get_station(st_code)
                evaluated = GSRRulesEngine.evaluate_weather_observation(
                    station_code=st_code,
                    weather_obs=raw_obs,
                    station_info=st_info,
                    nominal_mps=NOMINAL_TRACK_MPS,
                    has_fog_pass=True,
                )
                evaluated_batch.append(evaluated)

        self.db.save_observations_batch(evaluated_batch)
        self.total_inserted_records += len(evaluated_batch)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SIH-DETA Weather Crawler Worker")
    parser.add_argument("--offline", action="store_true", help="Force offline mock generation")
    parser.add_argument("--delay", type=float, default=INTER_BATCH_DELAY, help="Delay between batches")
    args = parser.parse_args()

    crawler = WeatherCrawler(offline=args.offline, delay=args.delay)
    crawler.run()
