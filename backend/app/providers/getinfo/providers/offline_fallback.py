"""
Offline Fallback Provider & Exact Mathematical Seat Layout Engine.
Guarantees 100% availability even during total internet outage or upstream vendor downtime.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from models.schemas import (
    CoachInfo,
    CoachRakeResponse,
    SeatLayoutInfo,
)
from providers.base import BaseProvider

logger = logging.getLogger("getinfo.providers.offline")

# Deterministic standard rake compositions for top train categories
OFFLINE_RAKE_TEMPLATES = {
    "RAJDHANI_TEJAS_21": [
        ("EOG", "End On Generation / Generator Van", None),
        ("B1", "AC 3-Tier (Air Conditioned)", "3A"),
        ("B2", "AC 3-Tier (Air Conditioned)", "3A"),
        ("B3", "AC 3-Tier (Air Conditioned)", "3A"),
        ("B4", "AC 3-Tier (Air Conditioned)", "3A"),
        ("B5", "AC 3-Tier (Air Conditioned)", "3A"),
        ("B6", "AC 3-Tier (Air Conditioned)", "3A"),
        ("B7", "AC 3-Tier (Air Conditioned)", "3A"),
        ("B8", "AC 3-Tier (Air Conditioned)", "3A"),
        ("B9", "AC 3-Tier (Air Conditioned)", "3A"),
        ("B10", "AC 3-Tier (Air Conditioned)", "3A"),
        ("B11", "AC 3-Tier (Air Conditioned)", "3A"),
        ("PC", "Pantry Car / Dining Car", None),
        ("H1", "First Class AC", "1A"),
        ("A1", "AC 2-Tier (Air Conditioned)", "2A"),
        ("A2", "AC 2-Tier (Air Conditioned)", "2A"),
        ("A3", "AC 2-Tier (Air Conditioned)", "2A"),
        ("A4", "AC 2-Tier (Air Conditioned)", "2A"),
        ("A5", "AC 2-Tier (Air Conditioned)", "2A"),
        ("EOG", "End On Generation / Generator Van", None),
    ],
    "VANDE_BHARAT_16": [
        ("DTC", "Driving Trailer Coach (AC Chair Car)", "CC"),
        ("MC", "Motor Coach (AC Chair Car)", "CC"),
        ("TC", "Trailer Coach (AC Chair Car)", "CC"),
        ("MC2", "Motor Coach (AC Chair Car)", "CC"),
        ("NDTC", "Non-Driving Trailer Coach (AC Chair Car)", "CC"),
        ("MC3", "Motor Coach (AC Chair Car)", "CC"),
        ("TC2", "Trailer Coach (Executive Chair Car)", "EC"),
        ("MC4", "Motor Coach (Executive Chair Car)", "EC"),
        ("MC5", "Motor Coach (Executive Chair Car)", "EC"),
        ("TC3", "Trailer Coach (Executive Chair Car)", "EC"),
        ("MC6", "Motor Coach (AC Chair Car)", "CC"),
        ("NDTC2", "Non-Driving Trailer Coach (AC Chair Car)", "CC"),
        ("MC7", "Motor Coach (AC Chair Car)", "CC"),
        ("TC4", "Trailer Coach (AC Chair Car)", "CC"),
        ("MC8", "Motor Coach (AC Chair Car)", "CC"),
        ("DTC2", "Driving Trailer Coach (AC Chair Car)", "CC"),
    ],
    "STANDARD_EXPRESS_22": [
        ("SLR", "Seating-cum-Luggage Rake / Guard Van", None),
        ("GS1", "General Second Class (Unreserved)", "GEN"),
        ("GS2", "General Second Class (Unreserved)", "GEN"),
        ("S1", "Sleeper Class (Non-AC)", "SL"),
        ("S2", "Sleeper Class (Non-AC)", "SL"),
        ("S3", "Sleeper Class (Non-AC)", "SL"),
        ("S4", "Sleeper Class (Non-AC)", "SL"),
        ("S5", "Sleeper Class (Non-AC)", "SL"),
        ("S6", "Sleeper Class (Non-AC)", "SL"),
        ("PC", "Pantry Car", None),
        ("B1", "AC 3-Tier", "3A"),
        ("B2", "AC 3-Tier", "3A"),
        ("B3", "AC 3-Tier", "3A"),
        ("B4", "AC 3-Tier", "3A"),
        ("B5", "AC 3-Tier", "3A"),
        ("B6", "AC 3-Tier", "3A"),
        ("A1", "AC 2-Tier", "2A"),
        ("A2", "AC 2-Tier", "2A"),
        ("GS3", "General Second Class (Unreserved)", "GEN"),
        ("GS4", "General Second Class (Unreserved)", "GEN"),
        ("SLR", "Seating-cum-Luggage Rake / Guard Van", None),
    ],
}


class OfflineFallbackProvider(BaseProvider):
    """Deterministic offline fallback provider and seat layout calculation engine."""

    @property
    def provider_id(self) -> str:
        return "offline_knowledge_base"

    def get_coach_position(self, train_number: str) -> Optional[CoachRakeResponse]:
        """Provides deterministic standard rake compositions when live scrapers are unavailable."""
        t_clean = train_number.strip().lstrip("0")

        # Select template based on known prefixes or defaults
        if t_clean in ("12951", "12952", "12301", "12302", "12431", "12432", "12433", "12434"):
            template_name = "RAJDHANI_TEJAS_21"
            rake_type = "LHB (Tejas Rajdhani Rake)"
        elif t_clean.startswith("20") or t_clean.startswith("22") and int(t_clean) in (22436, 22435, 20607, 20608):
            template_name = "VANDE_BHARAT_16"
            rake_type = "Vande Bharat Express (16-Car Trainset)"
        else:
            template_name = "STANDARD_EXPRESS_22"
            rake_type = "LHB / Standard Broad Gauge"

        template = OFFLINE_RAKE_TEMPLATES[template_name]
        coaches = [
            CoachInfo(
                position_index=idx,
                coach_code=code,
                coach_category=cat,
                class_code=cls_code,
            )
            for idx, (code, cat, cls_code) in enumerate(template, start=1)
        ]

        return CoachRakeResponse(
            success=True,
            train_number=train_number,
            train_name="Standard Indian Railways Rake",
            rake_type=rake_type,
            total_coaches=len(coaches),
            coach_sequence=coaches,
            provider=self.provider_id,
        )

    @staticmethod
    def calculate_seat_layout(coach_type: str, seat_number: int) -> SeatLayoutInfo:
        """
        Calculates exact Berth Type, Bay Number, and generates ASCII layout diagram
        using Indian Railways standard modulo arithmetic formulas.
        """
        c_type = coach_type.upper().strip()

        # Handle Sleeper (SL) & AC 3-Tier (3A) - 8 berths per bay
        if c_type in ("SL", "3A", "B", "S"):
            bay_no = ((seat_number - 1) // 8) + 1
            rem = seat_number % 8
            if rem in (1, 4):
                b_type, b_code = "Lower Berth", "LB"
            elif rem in (2, 5):
                b_type, b_code = "Middle Berth", "MB"
            elif rem in (3, 6):
                b_type, b_code = "Upper Berth", "UB"
            elif rem == 7:
                b_type, b_code = "Side Lower Berth", "SL"
            else:  # rem == 0
                b_type, b_code = "Side Upper Berth", "SU"

            ascii_diagram = f"""
┌───────── Compartment Bay #{bay_no} ─────────┐
│ [UB: {bay_no*8-5:>2}]  [MB: {bay_no*8-6:>2}]  [LB: {bay_no*8-7:>2}]  (Window)  │
│ ────────────────────────────── Aisle ─────── │
│ [SU: {bay_no*8:>2}]               [SL: {bay_no*8-1:>2}] (Track Side)│
└──────────────────────────────────────────────┘
"""
            return SeatLayoutInfo(
                coach_type="3A / Sleeper" if c_type in ("3A", "B") else "Sleeper Class (SL)",
                seat_number=seat_number,
                berth_type=b_type,
                berth_code=b_code,
                bay_number=bay_no,
                layout_diagram=ascii_diagram.strip(),
            )

        # Handle AC 3-Tier Economy (3E / M) - 9 berths per bay
        elif c_type in ("3E", "M"):
            bay_no = ((seat_number - 1) // 9) + 1
            rem = seat_number % 9
            if rem in (1, 4):
                b_type, b_code = "Lower Berth", "LB"
            elif rem in (2, 5):
                b_type, b_code = "Middle Berth", "MB"
            elif rem in (3, 6):
                b_type, b_code = "Upper Berth", "UB"
            elif rem == 7:
                b_type, b_code = "Side Lower Berth", "SL"
            elif rem == 8:
                b_type, b_code = "Side Middle Berth", "SM"
            else:  # rem == 0
                b_type, b_code = "Side Upper Berth", "SU"

            return SeatLayoutInfo(
                coach_type="AC 3-Tier Economy (3E)",
                seat_number=seat_number,
                berth_type=b_type,
                berth_code=b_code,
                bay_number=bay_no,
            )

        # Handle AC 2-Tier (2A / A) - 6 berths per bay
        elif c_type in ("2A", "A"):
            bay_no = ((seat_number - 1) // 6) + 1
            rem = seat_number % 6
            if rem in (1, 3):
                b_type, b_code = "Lower Berth", "LB"
            elif rem in (2, 4):
                b_type, b_code = "Upper Berth", "UB"
            elif rem == 5:
                b_type, b_code = "Side Lower Berth", "SL"
            else:  # rem == 0
                b_type, b_code = "Side Upper Berth", "SU"

            ascii_diagram = f"""
┌───────── 2-Tier Bay #{bay_no} ──────────────┐
│ [UB: {bay_no*6-2:>2}]          [LB: {bay_no*6-5:>2}]  (Window)     │
│ ────────────────────────────── Aisle ─────── │
│ [SU: {bay_no*6:>2}]          [SL: {bay_no*6-1:>2}] (Track Side)│
└──────────────────────────────────────────────┘
"""
            return SeatLayoutInfo(
                coach_type="AC 2-Tier (2A)",
                seat_number=seat_number,
                berth_type=b_type,
                berth_code=b_code,
                bay_number=bay_no,
                layout_diagram=ascii_diagram.strip(),
            )

        # Handle First Class AC (1A / H) - Cabin / Coupe
        elif c_type in ("1A", "H"):
            # Cabins have 4 berths (A, B, C, D); Coupes have 2 berths (A, B)
            bay_no = ((seat_number - 1) // 4) + 1
            rem = seat_number % 4
            cabin_letter = chr(64 + bay_no)
            b_type = "Lower Berth" if rem in (1, 3) else "Upper Berth"
            b_code = f"Cabin {cabin_letter} (LB)" if rem in (1, 3) else f"Cabin {cabin_letter} (UB)"

            return SeatLayoutInfo(
                coach_type="First Class AC (1A)",
                seat_number=seat_number,
                berth_type=b_type,
                berth_code=b_code,
                bay_number=bay_no,
            )

        # Handle Chair Car (CC / C) - 3x2 layout (5 seats per row)
        elif c_type in ("CC", "C"):
            row_no = ((seat_number - 1) // 5) + 1
            rem = seat_number % 5
            if rem in (1, 0):
                b_type, b_code = "Window Seat", "WS"
            elif rem in (2, 4):
                b_type, b_code = "Middle Seat", "MS"
            else:
                b_type, b_code = "Aisle Seat", "AS"

            return SeatLayoutInfo(
                coach_type="AC Chair Car (CC)",
                seat_number=seat_number,
                berth_type=b_type,
                berth_code=b_code,
                bay_number=row_no,
            )

        # Handle Executive Chair Car (EC / E) - 2x2 layout (4 seats per row)
        elif c_type in ("EC", "E"):
            row_no = ((seat_number - 1) // 4) + 1
            rem = seat_number % 4
            if rem in (1, 0):
                b_type, b_code = "Window Seat", "WS"
            else:
                b_type, b_code = "Aisle Seat", "AS"

            return SeatLayoutInfo(
                coach_type="Executive Chair Car (EC)",
                seat_number=seat_number,
                berth_type=b_type,
                berth_code=b_code,
                bay_number=row_no,
            )

        # Default fallback
        bay_no = ((seat_number - 1) // 8) + 1
        return SeatLayoutInfo(
            coach_type=c_type,
            seat_number=seat_number,
            berth_type="Standard Seat",
            berth_code="ST",
            bay_number=bay_no,
        )
