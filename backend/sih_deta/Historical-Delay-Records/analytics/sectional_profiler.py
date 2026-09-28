"""
Sectional Profiler: Computes historical baseline distributions, delay drift variance,
and engineering slack absorption profiles for railway track corridors across sub-windows.
"""

import math
from typing import Any, Dict, List, Optional


class SectionalProfiler:
    """Profiles delay behavior across railway sections over historical time windows."""

    def profile_all_sections(
        self,
        sectional_records: List[Dict[str, Any]],
        train_number: str,
        window_tag: Optional[str] = None,
        horizon_type: str = "90d",
    ) -> List[Dict[str, Any]]:
        """
        Aggregate section-level statistics across historical records for a train.
        Optionally filtered by a specific 15-day sub-window tag.
        """
        # Group records by (from_station, to_station, order)
        groups: Dict[tuple, List[Dict[str, Any]]] = {}
        for r in sectional_records:
            if window_tag and r.get("window_tag") != window_tag:
                continue
            key = (r["from_station"], r["to_station"], r.get("section_order", 0))
            if key not in groups:
                groups[key] = []
            groups[key].append(r)

        profiles = []
        for (from_stn, to_stn, order), recs in groups.items():
            deltas = [r["delay_delta"] for r in recs]
            arr_delays = [r["arrival_delay"] for r in recs]
            n = len(deltas)

            if n == 0:
                continue

            mean_delta = sum(deltas) / n
            variance = sum((x - mean_delta) ** 2 for x in deltas) / n if n > 1 else 0.0
            std_delta = math.sqrt(variance)

            sorted_deltas = sorted(deltas)
            median_delta = sorted_deltas[n // 2]

            absorbed_count = sum(1 for d in deltas if d <= -2)
            accumulated_count = sum(1 for d in deltas if d >= 3)
            on_time_arr_count = sum(1 for a in arr_delays if a <= 15)

            absorption_rate = (absorbed_count / n) * 100.0
            accumulation_rate = (accumulated_count / n) * 100.0
            punctuality_rate = (on_time_arr_count / n) * 100.0

            # Classification
            if mean_delta < -2.0:
                corridor_type = "SLACK_BUFFER (Absorbs Delay)"
            elif mean_delta > 3.0:
                corridor_type = "BOTTLENECK (Compounds Delay)"
            else:
                corridor_type = "NEUTRAL (Maintains Pace)"

            profiles.append({
                "train_number": train_number,
                "section_order": order,
                "from_station": from_stn,
                "to_station": to_stn,
                "window_tag": window_tag or "macro",
                "horizon_type": horizon_type,
                "sample_size_days": n,
                "mean_delay_delta": round(mean_delta, 2),
                "std_delay_delta": round(std_delta, 2),
                "median_delay_delta": median_delta,
                "min_delay_delta": min(deltas),
                "max_delay_delta": max(deltas),
                "absorption_rate_pct": round(absorption_rate, 1),
                "accumulation_rate_pct": round(accumulation_rate, 1),
                "punctuality_rate_pct": round(punctuality_rate, 1),
                "corridor_type": corridor_type,
            })

        profiles.sort(key=lambda p: p["section_order"])
        return profiles
