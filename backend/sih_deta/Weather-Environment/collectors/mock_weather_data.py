"""
Deterministic Mock Weather Data Generator
Provides resilient, zero-failure weather generation when external network access
is unavailable or rate-limited, modeling realistic seasonal patterns of Indian Railways.
"""

from datetime import datetime
from typing import Dict


class MockWeatherGenerator:
    """
    Generates realistic meteorological conditions based on latitude, longitude, and date/time.
    """

    @classmethod
    def generate(cls, lat: float, lon: float, dt: datetime = None) -> Dict:
        """
        Synthesizes realistic meteorological observations.
        """
        if dt is None:
            dt = datetime.now()

        month = dt.month
        hour = dt.hour

        # 1. Northern Plains Winter Fog (Dec 10 to Feb 15, early morning 03:00 to 09:00)
        # Lat > 24.5°N and Lon between 75°E and 88°E (Punjab, Haryana, UP, Bihar, Bengal)
        is_northern_plains = 24.0 <= lat <= 31.0 and 75.0 <= lon <= 88.0
        is_winter = month in (12, 1, 2)
        is_fog_hour = 3 <= hour <= 9

        if is_northern_plains and is_winter and is_fog_hour:
            # Dense fog
            visibility = 250.0 + ((lat * 13 + lon * 7) % 300.0)  # ~250m to 550m
            ambient_temp = 7.0 + ((hour - 3) * 1.5)
            precipitation = 0.0
            solar_radiation = 20.0 if hour >= 7 else 0.0
        elif 6 <= month <= 9 and (72.0 <= lon <= 75.5 and 12.0 <= lat <= 20.0):
            # 2. Monsoon in Konkan / Coastal Western Ghats
            visibility = 3500.0
            ambient_temp = 27.5
            precipitation = 12.0 + ((lat * 5 + hour * 3) % 45.0)  # Active rain
            solar_radiation = 150.0
        elif 4 <= month <= 6 and 11 <= hour <= 16 and (18.0 <= lat <= 27.0):
            # 3. Summer Heat Wave in Central & Northern India (Vidarbha, Rajasthan, MP, UP)
            visibility = 9000.0
            ambient_temp = 42.0 + ((hour - 11) * 1.2)  # 42°C to 47°C
            precipitation = 0.0
            solar_radiation = 850.0  # Intense midday direct sun
        else:
            # 4. Standard Nominal Clear Weather
            visibility = 8000.0 + ((lat + lon) % 2000.0)
            ambient_temp = 24.0 + (math_sin_temp := 5.0)
            precipitation = 0.0
            solar_radiation = 350.0 if (7 <= hour <= 17) else 0.0

        # Estimated rail temperature: T_rail = T_air + 0.022 * solar_radiation
        rail_temp = ambient_temp + (0.022 * solar_radiation)

        return {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "timestamp": dt.strftime("%Y-%m-%dT%H:00:00+05:30"),
            "visibility_meters": round(visibility, 1),
            "precipitation_mm": round(precipitation, 2),
            "ambient_temp_c": round(ambient_temp, 1),
            "direct_solar_radiation_w_m2": round(solar_radiation, 1),
            "estimated_rail_temp_c": round(rail_temp, 1),
            "data_source": "MOCK_OFFLINE_SYNTHETIC",
        }
