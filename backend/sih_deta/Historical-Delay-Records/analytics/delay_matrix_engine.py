"""
Delay Transition Matrix Engine: Models sectional delay changes, absorption rates,
Markovian state transition probabilities, and windowed running profiles across railway corridors.
"""

import math
from typing import Any, Dict, List, Optional, Tuple


def get_delay_state(delay_mins: Optional[int]) -> str:
    """Classify a minute delay into operational punctuality states."""
    if delay_mins is None:
        return "UNKNOWN"
    if delay_mins <= 5:
        return "ON_TIME"         # <= 5 mins (includes early arrivals)
    elif delay_mins <= 15:
        return "MINOR_DELAY"     # 6 to 15 mins
    elif delay_mins <= 45:
        return "MODERATE_DELAY"  # 16 to 45 mins
    else:
        return "SEVERE_DELAY"    # > 45 mins


DELAY_STATES = ["ON_TIME", "MINOR_DELAY", "MODERATE_DELAY", "SEVERE_DELAY"]


class DelayMatrixEngine:
    """Calculates sectional delay transition matrices and absorption statistics."""

    def compute_sectional_runs(
        self,
        train_number: str,
        station_sequence: List[str],
        daily_runs: List[Dict[str, Any]],
        horizon_type: str = "90d",
    ) -> List[Dict[str, Any]]:
        """
        Deconstruct daily train runs into consecutive sectional transition records: (S_i -> S_{i+1})
        tagged with their respective 15-day sub-window and macro horizon.
        """
        sectional_records = []

        for run in daily_runs:
            journey_date = run["journey_date"]
            day_of_week = run["day_of_week"]
            window_tag = run.get("window_tag", "15d_w1")
            delays = run.get("delays", {})

            for i in range(len(station_sequence) - 1):
                from_stn = station_sequence[i]
                to_stn = station_sequence[i + 1]

                dep_delay = delays.get(from_stn)
                arr_delay = delays.get(to_stn)

                if dep_delay is None or arr_delay is None:
                    continue

                delta = arr_delay - dep_delay

                if delta <= -2:
                    status = "ABSORBED_DELAY"
                elif delta >= 3:
                    status = "ACCUMULATED_DELAY"
                else:
                    status = "MAINTAINED_SCHEDULE"

                from_state = get_delay_state(dep_delay)
                to_state = get_delay_state(arr_delay)

                sectional_records.append({
                    "train_number": train_number,
                    "journey_date": journey_date,
                    "day_of_week": day_of_week,
                    "from_station": from_stn,
                    "to_station": to_stn,
                    "section_order": i + 1,
                    "departure_delay": dep_delay,
                    "arrival_delay": arr_delay,
                    "delay_delta": delta,
                    "status": status,
                    "from_state": from_state,
                    "to_state": to_state,
                    "window_tag": window_tag,
                    "horizon_type": horizon_type,
                })

        return sectional_records

    def build_transition_matrix(
        self,
        sectional_records: List[Dict[str, Any]],
        from_stn: Optional[str] = None,
        to_stn: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Construct empirical Markov transition probability matrix P(to_state | from_state).
        """
        counts = {s1: {s2: 0 for s2 in DELAY_STATES} for s1 in DELAY_STATES}
        totals = {s1: 0 for s1 in DELAY_STATES}

        for r in sectional_records:
            if from_stn and r["from_station"] != from_stn:
                continue
            if to_stn and r["to_station"] != to_stn:
                continue

            fs = r["from_state"]
            ts = r["to_state"]
            if fs in counts and ts in counts[fs]:
                counts[fs][ts] += 1
                totals[fs] += 1

        probs = {s1: {} for s1 in DELAY_STATES}
        for s1 in DELAY_STATES:
            t = totals[s1]
            for s2 in DELAY_STATES:
                probs[s1][s2] = round(counts[s1][s2] / t, 4) if t > 0 else 0.0

        return {
            "from_station": from_stn or "ALL",
            "to_station": to_stn or "ALL",
            "sample_transitions": sum(totals.values()),
            "state_totals": totals,
            "transition_counts": counts,
            "transition_probabilities": probs,
        }
