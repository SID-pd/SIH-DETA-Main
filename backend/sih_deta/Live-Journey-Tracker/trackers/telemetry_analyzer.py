"""
Telemetry Analyzer: Computes physical and operational features for dynamic ETA prediction.
Calculates sectional speed, delay drift rate (absorption vs accumulation),
and detects outer home signal hold-ups.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("live_tracker")


class TelemetryAnalyzer:
    """Analyzes live telemetry streams to generate real-time features for ETA prediction."""

    @staticmethod
    def analyze_snapshot(telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a raw telemetry payload and extract kinematic & operational features.
        """
        stops = telemetry.get("schedule", [])
        if not stops:
            return {
                "train_number": telemetry.get("train_number"),
                "status": "NO_SCHEDULE_DATA",
            }

        total_distance = stops[-1].get("distance_km", 0.0)
        current_stn_code = telemetry.get("current_station_code", "")

        # Find current and next station indices
        cur_idx = -1
        for idx, stop in enumerate(stops):
            if stop["station_code"] == current_stn_code or stop.get("is_current"):
                cur_idx = idx
                break

        if cur_idx == -1:
            cur_idx = 0

        current_stop = stops[cur_idx]
        next_stop = stops[cur_idx + 1] if cur_idx + 1 < len(stops) else None

        # Distance calculations
        distance_covered = current_stop.get("distance_km", 0.0)
        dist_to_next = (
            (next_stop.get("distance_km", 0.0) - distance_covered) if next_stop else 0.0
        )
        progress_pct = (
            round((distance_covered / total_distance) * 100, 1) if total_distance > 0 else 0.0
        )

        # Delay Drift Analysis (across last 3 traversed stops)
        passed_stops = stops[: cur_idx + 1]
        delay_drift = 0.0
        drift_trend = "STABLE"

        if len(passed_stops) >= 2:
            prev_delay = passed_stops[-2].get("departure_delay_mins", 0)
            curr_delay = passed_stops[-1].get("departure_delay_mins", 0)
            delay_diff = curr_delay - prev_delay

            prev_dist = passed_stops[-2].get("distance_km", 0.0)
            curr_dist = passed_stops[-1].get("distance_km", 0.0)
            dist_diff = curr_dist - prev_dist

            if dist_diff > 0:
                # Minutes of delay change per 100 km
                delay_drift = round((delay_diff / dist_diff) * 100, 2)

            if delay_diff < -3:
                drift_trend = "RECOVERING (Making up time)"
            elif delay_diff > 3:
                drift_trend = "ACCUMULATING_DELAY (Falling behind schedule)"
            else:
                drift_trend = "MAINTAINING_PACE (Stable delay buffer)"

        # Outer Signal & Platform Bottleneck Detection
        outer_bottlenecks = []
        for i, stop in enumerate(stops):
            # Skip terminus station where departure delay is not applicable
            is_terminus = (i == len(stops) - 1) or (stop.get("station_code") == telemetry.get("destination_code"))
            arr_delay = stop.get("arrival_delay_mins") or 0
            dep_delay = stop.get("departure_delay_mins") or 0

            # If delay increases by 15 mins or more while at station (platform hold-up / outer signal wait)
            if not is_terminus and (dep_delay - arr_delay) >= 15:
                outer_bottlenecks.append({
                    "station_code": stop["station_code"],
                    "station_name": stop["station_name"],
                    "delay_surge_mins": dep_delay - arr_delay,
                    "platform": stop.get("expected_platform"),
                })

        return {
            "train_number": telemetry.get("train_number"),
            "train_name": telemetry.get("train_name"),
            "train_type": telemetry.get("train_type"),
            "timestamp": telemetry.get("timestamp"),
            "current_station": {
                "code": current_stop.get("station_code"),
                "name": current_stop.get("station_name"),
                "distance_from_origin_km": distance_covered,
                "platform": current_stop.get("expected_platform"),
                "latitude": current_stop.get("latitude"),
                "longitude": current_stop.get("longitude"),
            },
            "next_station": {
                "code": next_stop.get("station_code") if next_stop else None,
                "name": next_stop.get("station_name") if next_stop else None,
                "distance_km": dist_to_next,
                "scheduled_arrival": next_stop.get("scheduled_arrival") if next_stop else None,
                "platform": next_stop.get("expected_platform") if next_stop else None,
            } if next_stop else None,
            "instantaneous_delay_mins": telemetry.get("latest_delay_minutes", 0),
            "journey_progress_pct": progress_pct,
            "total_journey_distance_km": total_distance,
            "delay_drift_rate_per_100km": delay_drift,
            "delay_trend": drift_trend,
            "outer_signal_bottlenecks_detected": len(outer_bottlenecks) > 0,
            "bottleneck_events": outer_bottlenecks,
            "destination": {
                "code": telemetry.get("destination_code"),
                "name": telemetry.get("destination_name"),
            },
        }
