"""
Stochastic Incident Simulator
Generates calibrated operational disruptions modeling Indian Railways field statistics.
"""

import hashlib
import random
from datetime import datetime
from typing import Dict, List, Optional

from config import INCIDENT_CATEGORIES
from models.incident_types import NetworkIncident, calculate_severity
from models.outer_queue_model import OuterSignalQueueModel


class IncidentSimulator:
    """
    Simulates operational disruptions based on Indian Railways empirical distributions.
    """

    @classmethod
    def sample_detention(cls, category: str) -> float:
        """Samples a detention duration from the calibrated category distribution."""
        meta = INCIDENT_CATEGORIES.get(category)
        if not meta:
            return 15.0

        mean = meta["mean_detention_min"]
        std = meta["std_dev_min"]
        min_v = meta["min_detention_min"]
        max_v = meta["max_detention_min"]

        sampled = random.gauss(mean, std)
        return round(max(min_v, min(max_v, sampled)), 1)

    @classmethod
    def generate_incident(
        cls,
        category: str,
        section_id: str,
        train_number: str = "ALL",
        dt: Optional[datetime] = None,
    ) -> NetworkIncident:
        """Creates a single calibrated operational incident."""
        if dt is None:
            dt = datetime.now()

        meta = INCIDENT_CATEGORIES.get(category, {})
        detention = cls.sample_detention(category)
        speed_cap = meta.get("speed_restriction_kmh")
        desc = meta.get("description", "Unspecified operational disruption")
        severity = calculate_severity(detention)

        h = hashlib.sha256(f"{section_id}_{train_number}_{category}_{dt.isoformat()}".encode()).hexdigest()[:10]
        incident_id = f"INC_{h.upper()}"

        return NetworkIncident(
            incident_id=incident_id,
            timestamp=dt.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
            train_number=train_number,
            section_id=section_id.upper(),
            category=category,
            detention_minutes=detention,
            speed_restriction_kmh=speed_cap if speed_cap and speed_cap > 0 else None,
            description=desc,
            is_active=True,
            severity=severity,
        )

    @classmethod
    def simulate_route_anomalies(
        cls,
        train_number: str,
        stop_stations: List[str],
        arrival_hour: int = 8,
        priority_tier: int = 3,
        anomaly_probability: float = 0.15,
    ) -> List[NetworkIncident]:
        """
        Simulates potential stochastic incidents along a train's multi-stop corridor,
        including outer signal waiting at bottleneck junctions.
        """
        incidents: List[NetworkIncident] = []
        now = datetime.now()

        # 1. Check junction outer signal queuing for all stops
        for st in stop_stations:
            wait_min, status = OuterSignalQueueModel.estimate_outer_delay(
                junction_code=st,
                arrival_hour=arrival_hour,
                priority_tier=priority_tier,
            )
            if wait_min > 5.0:
                h = hashlib.sha256(f"{st}_{train_number}_OUTER_{now.date()}".encode()).hexdigest()[:10]
                incidents.append(
                    NetworkIncident(
                        incident_id=f"INC_{h.upper()}",
                        timestamp=now.strftime("%Y-%m-%dT%H:%M:%S+05:30"),
                        train_number=train_number,
                        section_id=st.upper(),
                        category="OUTER_SIGNAL_WAIT",
                        detention_minutes=wait_min,
                        speed_restriction_kmh=None,
                        description=f"Platform starvation queuing at {st} throat ({status})",
                        is_active=True,
                        severity=calculate_severity(wait_min),
                    )
                )

        # 2. Stochastic incidents along intermediate block sections
        candidate_categories = [
            "SIGNAL_FAILURE_AUTO",
            "ALARM_CHAIN_PULLING",
            "CATTLE_RUN_OVER",
        ]

        for i in range(len(stop_stations) - 1):
            if random.random() < anomaly_probability:
                cat = random.choice(candidate_categories)
                section = f"{stop_stations[i]}-{stop_stations[i+1]}"
                inc = cls.generate_incident(cat, section, train_number, now)
                incidents.append(inc)

        return incidents
