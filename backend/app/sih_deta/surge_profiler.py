"""
Station Passenger Capacity, NSG Classification & Event Surge Profiler (`surge_profiler.py`).

Implements Section 7 of `Server/Server.md` and Section 3 of `Server/impl.md`:
1. Official Ministry of Railways Non-Suburban Group (NSG 1–6) station categorization.
2. Event Surge Calendar (Prayagraj Maha Kumbh, Chhath Puja, Diwali Rush, Puri Rath Yatra).
3. Dwell Time Inflation Equation:
   T_dwell_actual = T_dwell_sched * (1 + alpha * (Footfall_NSG / PlatformCount) + beta * (S_event - 1)) + delta_ACP_risk
4. M/M/c Outer Home Signal Platform Starvation Queue estimator.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .data_bridge import bridge, canonical_modern_code

# Official Ministry of Railways NSG Categorization Metrics
NSG_TIER_PROFILES: Dict[str, Dict[str, Any]] = {
    "NSG_1": {
        "tier": "NSG-1",
        "annual_earnings": "> ₹500 Crore",
        "annual_footfall_millions": 24.0,
        "footfall_index": 1.85,
        "acp_risk_mins": 2.5,
        "description": "Mega Terminal / Hub (>20M passengers/yr); extreme doorway boarding crush",
    },
    "NSG_2": {
        "tier": "NSG-2",
        "annual_earnings": "₹100 – ₹500 Crore",
        "annual_footfall_millions": 14.0,
        "footfall_index": 1.35,
        "acp_risk_mins": 1.5,
        "description": "Major Divisional Junction (10–20M passengers/yr); high parcel & platform exchange",
    },
    "NSG_3": {
        "tier": "NSG-3",
        "annual_earnings": "₹20 – ₹100 Crore",
        "annual_footfall_millions": 7.0,
        "footfall_index": 0.90,
        "acp_risk_mins": 0.8,
        "description": "District Headquarter Station (5–10M passengers/yr); moderate dwell variation",
    },
    "NSG_4": {
        "tier": "NSG-4",
        "annual_earnings": "₹10 – ₹20 Crore",
        "annual_footfall_millions": 3.5,
        "footfall_index": 0.55,
        "acp_risk_mins": 0.3,
        "description": "Standard Express Halt (2–5M passengers/yr); minor dwell fluctuation",
    },
    "NSG_5": {
        "tier": "NSG-5",
        "annual_earnings": "₹1 – ₹10 Crore",
        "annual_footfall_millions": 1.5,
        "footfall_index": 0.25,
        "acp_risk_mins": 0.0,
        "description": "Secondary Town Station (1–2M passengers/yr); strict timetable adherence",
    },
    "NSG_6": {
        "tier": "NSG-6",
        "annual_earnings": "≤ ₹1 Crore",
        "annual_footfall_millions": 0.4,
        "footfall_index": 0.10,
        "acp_risk_mins": 0.0,
        "description": "Wayside Local Halt (≤1M passengers/yr); minimal passenger boarding",
    },
}

# Known NSG-1 and NSG-2 Railway Hubs
KNOWN_NSG1_STATIONS = {
    "NDLS", "HWH", "CSMT", "CSTM", "MAS", "SBC", "SC", "ADI", "PNBE",
    "CNB", "PRYJ", "ALD", "DDU", "MGS", "BSB", "LKO", "JP", "NGP",
    "BCT", "MMCT", "ANVT", "NZM", "GKP", "PUNE", "ST", "BZA", "VSKP",
}

KNOWN_NSG2_STATIONS = {
    "VGLJ", "JHS", "RKMP", "HBJ", "BPL", "ET", "JBP", "STA", "KTE",
    "TDL", "ALJN", "GZB", "MB", "BE", "GWL", "AGC", "MTJ", "KOTA",
    "RTM", "BRC", "DNR", "MFP", "DBG", "BJU", "ASN", "DGR", "KGP",
    "BBS", "PURI", "KUR", "TATA", "RNC", "DHN", "GAYA",
}

# Macro-Event & Pilgrimage Surge Calendar Presets
EVENT_SURGE_PRESETS: Dict[str, Dict[str, Any]] = {
    "NOMINAL": {
        "event_id": "NOMINAL",
        "event_name": "Normal Daily Operations",
        "surge_multiplier": 1.0,
        "waitlist_load_factor": 1.0,
        "special_trains_injected": 0,
        "affected_stations": [],
        "description": "Standard diurnal passenger demand without festival surge.",
    },
    "MAHA_KUMBH": {
        "event_id": "MAHA_KUMBH",
        "event_name": "Prayagraj Maha Kumbh / Magh Mela Shahi Snan",
        "surge_multiplier": 3.2,
        "waitlist_load_factor": 2.4,
        "special_trains_injected": 45,
        "affected_stations": ["PRYJ", "ALD", "NYN", "PCOI", "ACOI", "PFM", "SFG", "PYGS", "BSB", "DDU", "MGS", "CNB", "AYC", "FD"],
        "description": "Extreme pilgrimage surge (S_event = 3.2) across Prayagraj ring junctions; 45+ Mela Specials active.",
    },
    "CHHATH_PUJA": {
        "event_id": "CHHATH_PUJA",
        "event_name": "Bihar / Purvanchal Chhath Puja Rush",
        "surge_multiplier": 2.8,
        "waitlist_load_factor": 2.2,
        "special_trains_injected": 38,
        "affected_stations": ["PNBE", "DNR", "PPTA", "RJPB", "GKP", "MFP", "DBG", "BJU", "CPR", "ARA", "BXR", "DDU", "MGS", "GAYA"],
        "description": "High-density East Central / North Eastern corridor rush (S_event = 2.8) with unreserved coach crush.",
    },
    "DIWALI_RUSH": {
        "event_id": "DIWALI_RUSH",
        "event_name": "Pan-India Diwali & Festival Exodus",
        "surge_multiplier": 2.2,
        "waitlist_load_factor": 1.85,
        "special_trains_injected": 30,
        "affected_stations": ["NDLS", "ANVT", "NZM", "CSMT", "BCT", "ST", "ADI", "PUNE", "CNB", "LKO", "HWH", "MAS"],
        "description": "Major origin-terminal platform saturation and heavy luggage boarding delays (S_event = 2.2).",
    },
    "RATH_YATRA": {
        "event_id": "RATH_YATRA",
        "event_name": "Puri Jagannath Rath Yatra Surge",
        "surge_multiplier": 2.6,
        "waitlist_load_factor": 2.0,
        "special_trains_injected": 25,
        "affected_stations": ["PURI", "KUR", "BBS", "CTC", "VSKP", "KGP", "HWH"],
        "description": "East Coast Railway terminal saturation at Puri, Khurda Road, and Bhubaneswar (S_event = 2.6).",
    },
}


class StationSurgeProfiler:
    """
    Computes station NSG classification, festival surge multipliers, dilated dwell times,
    and M/M/c platform starvation probabilities.
    """

    ALPHA_PAX = 0.60
    BETA_EVENT = 0.80

    @classmethod
    def resolve_nsg_tier(cls, station_code: str, db_ir_category: Optional[str] = None, is_junction: bool = False) -> str:
        mod = canonical_modern_code(station_code)
        if mod in KNOWN_NSG1_STATIONS or station_code.upper() in KNOWN_NSG1_STATIONS:
            return "NSG_1"
        if mod in KNOWN_NSG2_STATIONS or station_code.upper() in KNOWN_NSG2_STATIONS:
            return "NSG_2"
        if db_ir_category:
            cat = db_ir_category.upper().replace("-", "_")
            if cat in NSG_TIER_PROFILES:
                return cat
        return "NSG_2" if is_junction else "NSG_4"

    @classmethod
    def evaluate_station_surge(
        cls,
        station_code: str,
        scheduled_dwell_mins: int = 5,
        active_event_id: str = "NOMINAL",
        custom_surge_multiplier: Optional[float] = None,
        arrival_hour: int = 10,
    ) -> Dict[str, Any]:
        """
        Evaluate the Dwell Time Inflation Equation and M/M/c Outer Hold probability for a station.
        """
        meta = bridge.get_station_metadata(station_code)
        mod_code = meta["code"]
        platforms = max(1, int(meta.get("platforms") or 2))
        nsg_key = cls.resolve_nsg_tier(mod_code, meta.get("ir_category"), meta.get("is_junction", False))
        nsg_profile = NSG_TIER_PROFILES[nsg_key]

        event = EVENT_SURGE_PRESETS.get(active_event_id.upper(), EVENT_SURGE_PRESETS["NOMINAL"])
        affected = [canonical_modern_code(s) for s in event["affected_stations"]]

        if custom_surge_multiplier is not None:
            s_event = max(1.0, min(4.0, float(custom_surge_multiplier)))
            is_event_hotspot = s_event > 1.05
        elif active_event_id.upper() != "NOMINAL" and (mod_code in affected or nsg_key == "NSG_1"):
            # Primary affected stations get full multiplier; other NSG-1 hubs get partial ripple
            s_event = float(event["surge_multiplier"]) if mod_code in affected else max(1.3, float(event["surge_multiplier"]) * 0.55)
            is_event_hotspot = True
        else:
            s_event = 1.0
            is_event_hotspot = False

        footfall_ratio = (nsg_profile["footfall_index"] * 4.5) / max(2.0, float(platforms))
        acp_risk_mins = nsg_profile["acp_risk_mins"] * (1.8 if s_event > 1.5 else 1.0)

        sched_dwell = max(1, int(scheduled_dwell_mins or 2))
        inflation_factor = 1.0 + (cls.ALPHA_PAX * footfall_ratio) + (cls.BETA_EVENT * (s_event - 1.0))
        raw_dilated = (sched_dwell * inflation_factor) + (acp_risk_mins if s_event > 1.2 or nsg_key in ("NSG_1", "NSG_2") else 0.0)
        dilated_dwell_mins = int(round(raw_dilated))
        dwell_added_mins = max(0, dilated_dwell_mins - sched_dwell)

        # M/M/c Platform Saturation & Outer Home Signal Starvation Probability
        diurnal_peak = 1.35 if (6 <= arrival_hour <= 10 or 17 <= arrival_hour <= 22) else 0.85
        utilization_rho = min(0.98, (0.42 * nsg_profile["footfall_index"] * diurnal_peak * (0.7 + 0.3 * s_event)) / math.sqrt(platforms / 2.0))
        outer_hold_prob = round(min(0.96, max(0.04, utilization_rho ** 1.6)), 2)

        return {
            "station_code": mod_code,
            "station_name": meta.get("name", mod_code),
            "zone": meta.get("zone", "IR"),
            "platforms": platforms,
            "nsg_category": nsg_profile["tier"],
            "nsg_details": nsg_profile,
            "active_event": event["event_name"] if is_event_hotspot else "Normal Daily Operations",
            "event_id": active_event_id.upper() if is_event_hotspot else "NOMINAL",
            "surge_multiplier_s_event": round(s_event, 2),
            "scheduled_dwell_mins": sched_dwell,
            "dilated_dwell_mins": dilated_dwell_mins,
            "dwell_inflation_added_mins": dwell_added_mins,
            "acp_risk_added_mins": round(acp_risk_mins, 1),
            "platform_saturation_rho": round(utilization_rho, 2),
            "outer_signal_starvation_prob": outer_hold_prob,
            "formula_trace": (
                f"T_actual = {sched_dwell}m × (1 + {cls.ALPHA_PAX}·{footfall_ratio:.2f} + "
                f"{cls.BETA_EVENT}·({s_event:.1f} - 1)) + {acp_risk_mins:.1f}m = {dilated_dwell_mins}m"
            ),
        }
