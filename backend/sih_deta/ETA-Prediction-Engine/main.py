"""
SIH-DETA Module 07: Unified Hybrid ML + Discrete DSA ETA Prediction Engine CLI
==============================================================================
Can be run standalone for inspection or via FastAPI (`app/sih_deta/*`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.sih_deta.controller_ops import controller_ops
from app.sih_deta.data_bridge import bridge
from app.sih_deta.quantile_engine import quantile_engine


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SIH-DETA Hybrid ML (P10/P50/P90) + Discrete DSA ETA Engine"
    )
    parser.add_argument("--train", default="12951", help="5-digit Indian Railways train number")
    parser.add_argument("--station", default="NDLS", help="Target station code")
    parser.add_argument("--delay", type=int, default=42, help="Current arrival delay in minutes")
    parser.add_argument(
        "--surge",
        choices=["NOMINAL", "MAHA_KUMBH", "CHHATH_PUJA", "DIWALI_RUSH", "RATH_YATRA"],
        default="NOMINAL",
        help="Active festival surge preset",
    )
    parser.add_argument("--audit", action="store_true", help="Print 6-database audit summary")
    args = parser.parse_args()

    if args.audit:
        print(json.dumps(bridge.get_database_inventory(), indent=2))
        return

    state = controller_ops.set_environment_and_surge(event_id=args.surge)
    result = quantile_engine.compute_hybrid_eta(
        train_number=args.train,
        target_station=args.station,
        current_delay_override=args.delay,
        active_event_id=args.surge,
        active_incidents=state["active_incidents"],
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
