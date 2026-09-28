"""
Open-Meteo REST API Client
Fetches high-resolution weather data (hourly visibility, precipitation, temperature, solar radiation)
with in-memory TTL caching, exponential backoff, and seamless offline fallback.
"""

import logging
import time
from datetime import datetime
from typing import Dict, Optional
import urllib.parse
import urllib.request
import json

from config import (
    ARCHIVE_API_URL,
    BACKOFF_FACTOR,
    CACHE_TTL_SECONDS,
    FORECAST_API_URL,
    MAX_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
    TIMEZONE_DEFAULT,
)
from collectors.mock_weather_data import MockWeatherGenerator

logger = logging.getLogger("weather_client")


class OpenMeteoClient:
    """
    High-throughput Open-Meteo API Client with TTL caching and offline resilience.
    """

    def __init__(self, use_offline_fallback: bool = True):
        self.use_offline_fallback = use_offline_fallback
        # In-memory cache: (lat_round, lon_round, hour_str) -> (timestamp, data)
        self._cache: Dict[str, Tuple[float, dict]] = {}

    def _get_cache_key(self, lat: float, lon: float, dt_str: str) -> str:
        return f"{round(lat, 2)}_{round(lon, 2)}_{dt_str}"

    def get_live_weather(self, lat: float, lon: float) -> dict:
        """
        Fetches current/hourly weather from Open-Meteo Forecast API.
        """
        now = datetime.now()
        hour_str = now.strftime("%Y-%m-%dT%H:00")
        cache_key = self._get_cache_key(lat, lon, hour_str)

        # 1. Check in-memory TTL cache
        if cache_key in self._cache:
            cached_time, cached_val = self._cache[cache_key]
            if time.time() - cached_time < CACHE_TTL_SECONDS:
                return cached_val

        # 2. Build REST request
        params = {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "hourly": "visibility,precipitation,temperature_2m,direct_normal_irradiance",
            "timezone": TIMEZONE_DEFAULT,
            "forecast_days": "1",
        }
        url = f"{FORECAST_API_URL}?{urllib.parse.urlencode(params)}"

        data = self._execute_http_request(url, lat, lon, now)
        if data:
            self._cache[cache_key] = (time.time(), data)
            return data

        # 3. Fallback to mock generator if offline / request failed
        if self.use_offline_fallback:
            mock = MockWeatherGenerator.generate(lat, lon, now)
            self._cache[cache_key] = (time.time(), mock)
            return mock

        raise RuntimeError(f"Failed to fetch live weather for coordinates ({lat}, {lon})")

    def get_historical_weather(self, lat: float, lon: float, dt: datetime) -> dict:
        """
        Fetches historical weather for a specific timestamp from Open-Meteo Archive API.
        """
        date_str = dt.strftime("%Y-%m-%d")
        hour_target = dt.strftime("%Y-%m-%dT%H:00")
        cache_key = self._get_cache_key(lat, lon, hour_target)

        if cache_key in self._cache:
            return self._cache[cache_key][1]

        params = {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "start_date": date_str,
            "end_date": date_str,
            "hourly": "visibility,precipitation,temperature_2m,direct_normal_irradiance",
            "timezone": TIMEZONE_DEFAULT,
        }
        url = f"{ARCHIVE_API_URL}?{urllib.parse.urlencode(params)}"

        data = self._execute_http_request(url, lat, lon, dt)
        if data:
            self._cache[cache_key] = (time.time(), data)
            return data

        if self.use_offline_fallback:
            return MockWeatherGenerator.generate(lat, lon, dt)

        raise RuntimeError(f"Failed to fetch historical weather for ({lat}, {lon}) on {date_str}")

    def _execute_http_request(self, url: str, lat: float, lon: float, target_dt: datetime) -> Optional[dict]:
        """
        Executes HTTP GET request with retries and exponential backoff.
        Extracts the hourly slice closest to target_dt.
        """
        target_iso_hour = target_dt.strftime("%Y-%m-%dT%H:00")
        delay = 1.0

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "SIH-DETA-WeatherEngine/1.0 (IndianRailwaysDynamicETA)",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                    if resp.status == 200:
                        payload = json.loads(resp.read().decode("utf-8"))
                        return self._parse_hourly_payload(payload, target_iso_hour, lat, lon)
            except Exception as e:
                logger.warning("Weather API attempt %d failed: %s (retrying in %.1fs)", attempt, e, delay)
                time.sleep(delay)
                delay *= BACKOFF_FACTOR

        return None

    def _parse_hourly_payload(self, payload: dict, target_iso_hour: str, lat: float, lon: float) -> dict:
        """Parses Open-Meteo hourly arrays and extracts matching index."""
        hourly = payload.get("hourly", {})
        times = hourly.get("time", [])

        # Find exact matching index or default to index 0
        idx = 0
        if target_iso_hour in times:
            idx = times.index(target_iso_hour)
        elif times:
            # Pick the closest available hour
            idx = len(times) - 1

        def safe_get(key: str, default: float) -> float:
            arr = hourly.get(key, [])
            if arr and idx < len(arr) and arr[idx] is not None:
                return float(arr[idx])
            return default

        visibility = safe_get("visibility", 10000.0)
        precipitation = safe_get("precipitation", 0.0)
        ambient_temp = safe_get("temperature_2m", 25.0)
        solar_radiation = safe_get("direct_normal_irradiance", 0.0)

        # Rail temperature approximation: T_rail = T_air + 0.022 * solar_radiation
        rail_temp = ambient_temp + (0.022 * solar_radiation)

        return {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "timestamp": times[idx] if idx < len(times) else target_iso_hour,
            "visibility_meters": round(visibility, 1),
            "precipitation_mm": round(precipitation, 2),
            "ambient_temp_c": round(ambient_temp, 1),
            "direct_solar_radiation_w_m2": round(solar_radiation, 1),
            "estimated_rail_temp_c": round(rail_temp, 1),
            "data_source": "OPEN_METEO_API",
        }
