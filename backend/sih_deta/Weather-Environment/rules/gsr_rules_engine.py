"""
Indian Railways General and Subsidiary Rules (G&SR) Operational Physics Engine
Translates raw meteorological variables into statutory train speed restrictions,
caution orders, and physical track safety constraints.
"""

from datetime import datetime
from typing import Dict, Optional, Tuple

from config import (
    FLANGE_WATER_RAIN_THRESHOLD_MM,
    FOG_SEVERE_THRESHOLD_METERS,
    FOG_VISIBILITY_THRESHOLD_METERS,
    KONKAN_MONSOON_END,
    KONKAN_MONSOON_START,
    KONKAN_STATIONS,
    NOMINAL_TRACK_MPS,
    RAIL_BUCKLING_THRESHOLD_C,
    RAIL_TEMP_DEFAULT_OFFSET,
    RAIL_TEMP_SOLAR_COEFF,
    SPEED_CAP_FLANGE_WATER,
    SPEED_CAP_FOG_PASS_GPS,
    SPEED_CAP_HEAT_BUCKLING,
    SPEED_CAP_KONKAN_MONSOON,
    SPEED_CAP_SEVERE_FOG,
    SPEED_CAP_STANDARD_FOG,
)


class GSRRulesEngine:
    """
    Statutory operational rules engine for Indian Railways environmental constraints.
    """

    @classmethod
    def evaluate_fog_constraint(
        cls, visibility_meters: float, has_fog_pass: bool = True
    ) -> Tuple[bool, Optional[int]]:
        """
        Evaluates visibility against G&SR 3.61 Fog Signalling rules.

        Returns:
            (is_foggy: bool, fog_speed_cap: Optional[int])
        """
        if visibility_meters < FOG_SEVERE_THRESHOLD_METERS:
            # Blind visibility: emergency stop-and-proceed caution
            return True, SPEED_CAP_SEVERE_FOG
        elif visibility_meters < FOG_VISIBILITY_THRESHOLD_METERS:
            # Standard fog condition (visibility < 600m)
            speed_cap = SPEED_CAP_FOG_PASS_GPS if has_fog_pass else SPEED_CAP_STANDARD_FOG
            return True, speed_cap
        else:
            # Clear line
            return False, None

    @classmethod
    def evaluate_monsoon_constraint(
        cls,
        station_code: str,
        dt: datetime,
        precipitation_mm: float,
        zone: Optional[str] = None,
    ) -> Tuple[bool, Optional[int]]:
        """
        Evaluates monsoon timetable and flash flood flange limits (G&SR 2.11).

        Returns:
            (monsoon_active: bool, monsoon_speed_cap: Optional[int])
        """
        code = station_code.strip().upper()
        month = dt.month
        day = dt.day

        # 1. Flash Flooding / Water Above Rail Flange (Extreme Local Downpour)
        if precipitation_mm >= FLANGE_WATER_RAIN_THRESHOLD_MM:
            return True, SPEED_CAP_FLANGE_WATER

        # 2. Konkan Railway Mandatory Monsoon Timetable (June 10 to October 31)
        is_konkan = (code in KONKAN_STATIONS) or (zone == "KR")
        is_monsoon_window = (
            (month > KONKAN_MONSOON_START[0] or (month == KONKAN_MONSOON_START[0] and day >= KONKAN_MONSOON_START[1]))
            and
            (month < KONKAN_MONSOON_END[0] or (month == KONKAN_MONSOON_END[0] and day <= KONKAN_MONSOON_END[1]))
        )

        if is_konkan and is_monsoon_window:
            return True, SPEED_CAP_KONKAN_MONSOON

        return False, None

    @classmethod
    def evaluate_thermal_buckling(
        cls, ambient_temp_c: float, direct_solar_radiation_w_m2: Optional[float] = None
    ) -> Tuple[float, bool, Optional[int]]:
        """
        Evaluates Continuous Welded Rail (CWR) thermal stress (Track Manual Para 5.2).

        Returns:
            (estimated_rail_temp_c: float, buckling_warning: bool, heat_speed_cap: Optional[int])
        """
        if direct_solar_radiation_w_m2 is not None and direct_solar_radiation_w_m2 > 0:
            rail_temp = ambient_temp_c + (RAIL_TEMP_SOLAR_COEFF * direct_solar_radiation_w_m2)
        else:
            rail_temp = ambient_temp_c + RAIL_TEMP_DEFAULT_OFFSET

        if rail_temp >= RAIL_BUCKLING_THRESHOLD_C:
            # Hot Weather Patrolling caution order
            return round(rail_temp, 1), True, SPEED_CAP_HEAT_BUCKLING

        return round(rail_temp, 1), False, None

    @classmethod
    def evaluate_weather_observation(
        cls,
        station_code: str,
        weather_obs: dict,
        station_info: Optional[dict] = None,
        nominal_mps: int = NOMINAL_TRACK_MPS,
        has_fog_pass: bool = True,
    ) -> dict:
        """
        Full feature fusion evaluating all G&SR rules for a given station weather snapshot.
        """
        vis_m = float(weather_obs.get("visibility_meters", 10000.0))
        precip_mm = float(weather_obs.get("precipitation_mm", 0.0))
        temp_c = float(weather_obs.get("ambient_temp_c", 25.0))
        solar_rad = weather_obs.get("direct_solar_radiation_w_m2")

        # Parse timestamp
        ts_raw = weather_obs.get("timestamp")
        if isinstance(ts_raw, str):
            try:
                # Handle ISO string (e.g. 2026-09-24T06:00:00+05:30)
                clean_ts = ts_raw[:19]
                dt = datetime.strptime(clean_ts, "%Y-%m-%dT%H:%M:%S")
            except Exception:
                dt = datetime.now()
        else:
            dt = datetime.now()

        zone = station_info.get("zone") if station_info else None

        # Evaluate Individual Rules
        is_foggy, fog_cap = cls.evaluate_fog_constraint(vis_m, has_fog_pass=has_fog_pass)
        monsoon_active, monsoon_cap = cls.evaluate_monsoon_constraint(station_code, dt, precip_mm, zone=zone)
        rail_temp, buckling_warn, heat_cap = cls.evaluate_thermal_buckling(temp_c, solar_rad)

        # Compute Effective MPS (minimum allowed line speed)
        active_caps = [nominal_mps]
        if fog_cap is not None:
            active_caps.append(fog_cap)
        if monsoon_cap is not None:
            active_caps.append(monsoon_cap)
        if heat_cap is not None:
            active_caps.append(heat_cap)

        effective_mps = min(active_caps)

        # Primary throttling reason
        throttle_reason = "CLEAR"
        if effective_mps < nominal_mps:
            if effective_mps == fog_cap:
                throttle_reason = "FOG_VISIBILITY_RESTRICTION"
            elif effective_mps == monsoon_cap:
                throttle_reason = "MONSOON_OR_FLANGE_WATER"
            elif effective_mps == heat_cap:
                throttle_reason = "CWR_HEAT_BUCKLING_CAUTION"

        return {
            "station_code": station_code.upper(),
            "observation_time": weather_obs.get("timestamp", dt.isoformat()),
            "latitude": weather_obs.get("latitude", 0.0),
            "longitude": weather_obs.get("longitude", 0.0),
            "visibility_meters": vis_m,
            "is_foggy": 1 if is_foggy else 0,
            "fog_speed_cap": fog_cap if fog_cap is not None else nominal_mps,
            "precipitation_mm": precip_mm,
            "monsoon_active": 1 if monsoon_active else 0,
            "monsoon_speed_cap": monsoon_cap,
            "ambient_temp_c": temp_c,
            "estimated_rail_temp_c": rail_temp,
            "heat_buckling_warning": 1 if buckling_warn else 0,
            "nominal_mps": nominal_mps,
            "effective_mps_cap": effective_mps,
            "throttle_reason": throttle_reason,
            "data_source": weather_obs.get("data_source", "UNKNOWN"),
        }
