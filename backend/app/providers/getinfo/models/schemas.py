"""
Standardized dataclass models for Get-info transit information fetcher.
Ensures uniform, typed outputs across all scraping providers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class LiveStatusResponse:
    success: bool
    train_number: str
    train_name: str
    current_station_code: Optional[str] = None
    current_station_name: Optional[str] = None
    next_station_code: Optional[str] = None
    next_station_name: Optional[str] = None
    delay_minutes: int = 0
    status_text: str = ""
    distance_covered_km: Optional[float] = None
    total_distance_km: Optional[float] = None
    journey_percentage: Optional[float] = None
    last_updated_time: Optional[str] = None
    provider: str = "unknown"
    cached: bool = False
    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("raw_data", None)
        return d


@dataclass
class PassengerRecord:
    passenger_no: int
    booking_status: str
    current_status: str
    coach: Optional[str] = None
    berth: Optional[int] = None
    berth_type: Optional[str] = None


@dataclass
class PNRResponse:
    success: bool
    pnr: str
    train_number: Optional[str] = None
    train_name: Optional[str] = None
    doj: Optional[str] = None
    booking_date: Optional[str] = None
    from_station: Optional[str] = None
    to_station: Optional[str] = None
    boarding_station: Optional[str] = None
    reservation_upto: Optional[str] = None
    travel_class: Optional[str] = None
    quota: Optional[str] = None
    chart_prepared: bool = False
    passenger_count: int = 0
    passengers: List[PassengerRecord] = field(default_factory=list)
    expected_platform: Optional[str] = None
    coach_position: Optional[str] = None
    has_pantry: bool = False
    error_message: Optional[str] = None
    provider: str = "unknown"
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CoachInfo:
    position_index: int
    coach_code: str
    coach_category: str
    class_code: Optional[str] = None


@dataclass
class CoachRakeResponse:
    success: bool
    train_number: str
    train_name: Optional[str] = None
    rake_type: str = "Unknown"
    total_coaches: int = 0
    coach_sequence: List[CoachInfo] = field(default_factory=list)
    provider: str = "unknown"
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SeatLayoutInfo:
    coach_type: str
    seat_number: int
    berth_type: str
    berth_code: str
    bay_number: int
    layout_diagram: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TimelineStop:
    stop_number: int
    station_code: str
    station_name: str
    scheduled_arrival: Optional[str] = None
    scheduled_departure: Optional[str] = None
    actual_arrival: Optional[str] = None
    actual_departure: Optional[str] = None
    arrival_delay_min: Optional[int] = None
    departure_delay_min: Optional[int] = None
    halt_minutes: Optional[int] = None
    distance_km: float = 0.0
    day: int = 1
    platform: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    has_departed: bool = False


@dataclass
class TimelineResponse:
    success: bool
    train_number: str
    train_name: str
    source: str
    destination: str
    total_stops: int = 0
    stops: List[TimelineStop] = field(default_factory=list)
    provider: str = "unknown"
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RescheduledTrain:
    train_number: str
    train_name: str
    source: str
    destination: str
    original_departure: str
    rescheduled_departure: str
    delay_hours_mins: str


@dataclass
class DivertedTrain:
    train_number: str
    train_name: str
    source: str
    destination: str
    diverted_from: str
    diverted_to: str
    stations_skipped: List[str] = field(default_factory=list)


@dataclass
class CancelledTrain:
    train_number: str
    train_name: str
    cancellation_type: str  # "FULL" or "PARTIAL"
    from_station: str
    to_station: str


@dataclass
class ExceptionsResponse:
    success: bool
    journey_date: str
    exception_type: str
    rescheduled: List[RescheduledTrain] = field(default_factory=list)
    diverted: List[DivertedTrain] = field(default_factory=list)
    cancelled: List[CancelledTrain] = field(default_factory=list)
    provider: str = "unknown"
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
