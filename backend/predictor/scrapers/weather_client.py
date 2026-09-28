"""
Weather Client using Open-Meteo API.
Retrieves historical weather (up to 10 years) and real-time forecast weather for station coordinates.
Calculates temperature, precipitation, fog risk index, and weather severity score.
"""

import logging
from typing import Any, Dict, Optional

from predictor.config import OPENMETEO_ARCHIVE_URL, OPENMETEO_FORECAST_URL
from predictor.scrapers.base_scraper import BaseScraper

logger = logging.getLogger("predictor.scrapers.weather")


class WeatherClient(BaseScraper):
    """Fetches real-time and multi-year historical weather for railway station coordinates."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cache: Dict[str, Dict[str, float]] = {}

    def get_weather(
        self,
        latitude: float,
        longitude: float,
        date_str: Optional[str] = None,
        hour: int = 12,
        fetch_live: bool = False,
    ) -> Dict[str, float]:
        """
        Retrieves weather parameters for coordinates (lat, lon).
        If fetch_live=False, uses fast seasonal meteorological distribution (ideal for bulk training).
        If fetch_live=True, queries Open-Meteo API.
        """
        cache_key = f"{round(latitude, 2)}_{round(longitude, 2)}_{date_str}_{hour}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # If not live fetch, use fast seasonal meteorological calculation
        if not fetch_live:
            month = 9
            if date_str and len(date_str) >= 7:
                try:
                    month = int(date_str.split("-")[1])
                except Exception:
                    pass

            # Gangetic plains fog dynamics (lat > 24.0, winter morning/night)
            is_gangetic = latitude >= 23.5 and 75.0 <= longitude <= 89.0
            is_winter = month in (12, 1, 2)
            is_fog_hour = hour in (22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9)

            if is_winter and is_gangetic and is_fog_hour:
                fog_risk = 0.85
                vis = 250.0
                temp = 9.0
            elif is_winter and is_gangetic:
                fog_risk = 0.40
                vis = 1500.0
                temp = 14.0
            else:
                fog_risk = 0.05
                vis = 9000.0
                temp = 28.0

            # Monsoon precipitation dynamics (June to Sept)
            is_monsoon = month in (6, 7, 8, 9)
            precip = 18.0 if is_monsoon and (latitude < 22.0 or longitude > 85.0) else 0.0

            severity = min(1.0, (precip / 30.0) * 0.5 + fog_risk * 0.5)
            res = {
                "temperature_c": temp,
                "precipitation_mm": precip,
                "visibility_m": vis,
                "fog_risk_score": round(fog_risk, 3),
                "weather_severity_score": round(severity, 3),
            }
            self._cache[cache_key] = res
            return res

        # Live fetch from Open-Meteo API
        default_weather = {
            "temperature_c": 28.0,
            "precipitation_mm": 0.0,
            "visibility_m": 10000.0,
            "fog_risk_score": 0.0,
            "weather_severity_score": 0.1,
        }

        endpoint = OPENMETEO_ARCHIVE_URL if date_str else OPENMETEO_FORECAST_URL
        params = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "hourly": "temperature_2m,relative_humidity_2m,precipitation,weather_code,visibility",
            "timezone": "Asia/Kolkata",
        }
        if date_str:
            params["start_date"] = date_str
            params["end_date"] = date_str

        data = self.fetch_json(endpoint, params=params)
        if not data or "hourly" not in data:
            self._cache[cache_key] = default_weather
            return default_weather

        try:
            hourly = data["hourly"]
            idx = min(max(0, hour), len(hourly.get("time", [])) - 1)

            temp = float(hourly["temperature_2m"][idx]) if "temperature_2m" in hourly else 28.0
            precip = float(hourly["precipitation"][idx]) if "precipitation" in hourly else 0.0
            vis = float(hourly["visibility"][idx]) if "visibility" in hourly else 10000.0
            humidity = float(hourly["relative_humidity_2m"][idx]) if "relative_humidity_2m" in hourly else 60.0
            w_code = int(hourly["weather_code"][idx]) if "weather_code" in hourly else 0

            # Compute fog risk score (0 to 1) based on low visibility (< 1000m) or high humidity with low temp
            fog_risk = 0.0
            if vis < 1000:
                fog_risk = 1.0 - (vis / 1000.0)
            elif humidity > 85 and temp < 15:
                fog_risk = 0.6
            elif w_code in (45, 48):  # WMO Fog codes
                fog_risk = 0.9

            # Overall weather severity (0: perfect clear, 1: severe monsoon/dense fog)
            severity = min(1.0, (precip / 30.0) * 0.5 + fog_risk * 0.5)

            result = {
                "temperature_c": temp,
                "precipitation_mm": precip,
                "visibility_m": vis,
                "fog_risk_score": round(fog_risk, 3),
                "weather_severity_score": round(severity, 3),
            }
            self._cache[cache_key] = result
            return result

        except Exception as exc:
            logger.warning(f"Error extracting weather values: {exc}")
            self._cache[cache_key] = default_weather
            return default_weather
