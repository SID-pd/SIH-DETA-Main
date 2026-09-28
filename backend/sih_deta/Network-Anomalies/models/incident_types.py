"""
Operational Incident Data Structures & Schemas
"""

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Optional


@dataclass
class NetworkIncident:
    """Represents a stochastic operational disruption on the railway network."""

    incident_id: str
    timestamp: str
    train_number: str
    section_id: str  # e.g., 'CNB-PRYJ' or station 'CNB'
    category: str    # e.g., 'SIGNAL_FAILURE_AUTO', 'ALARM_CHAIN_PULLING'
    detention_minutes: float
    speed_restriction_kmh: Optional[int]
    description: str
    is_active: bool = True
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_severity(detention_minutes: float) -> str:
    """Classifies disruption severity based on lost headway."""
    if detention_minutes >= 60.0:
        return "CRITICAL"
    elif detention_minutes >= 30.0:
        return "HIGH"
    elif detention_minutes >= 15.0:
        return "MEDIUM"
    return "LOW"
