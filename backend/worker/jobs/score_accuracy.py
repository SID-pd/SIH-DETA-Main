"""
Accuracy scoring  (plan §7.2)
=============================
Joins what we PREDICTED (`eta_snapshots`) against what HAPPENED
(`live_observations`) and reports our real error distribution.

This is the number that decides whether Phase 2's M2 model is allowed to replace M0
(plan §7.1 promotion gate), and it is also the strongest thing we can put in front of a
judge: a system claiming "better ETA than the schedule" should be able to show its own
error bars, including when they are unflattering.

Three baselines are scored on identical rows, which is what makes the comparison mean
anything:

    schedule   — assume the train arrives exactly on time (the incumbent to beat)
    provider   — the provider's own projection for that stop
    m0         — our deterministic propagation engine

If M0 does not beat `schedule`, the project has no claim. If it does not beat
`provider`, we are adding no value over simply forwarding their number. Both are worth
knowing early rather than at demo time.

Run:  python services/worker/jobs/score_accuracy.py [--days 7] [--by horizon|zone|type]
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "..", ".."))
DB_PATH = os.environ.get("DARPAN_DB", os.path.join(REPO_ROOT, "data", "darpan.sqlite"))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def mae(vals: list[float]) -> float:
    return sum(abs(v) for v in vals) / len(vals) if vals else float("nan")


def bias(vals: list[float]) -> float:
    """Mean signed error. Positive = we predict later than reality (pessimistic)."""
    return sum(vals) / len(vals) if vals else float("nan")


def pctile(vals: list[float], q: float) -> float:
    if not vals:
        return float("nan")
    s = sorted(abs(v) for v in vals)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def horizon_bucket(minutes: int | None) -> str:
    if minutes is None:
        return "unknown"
    for hi, label in ((30, "0-30m"), (60, "30-60m"), (120, "1-2h"), (240, "2-4h")):
        if minutes <= hi:
            return label
    return "4h+"


def main() -> int:
    ap = argparse.ArgumentParser(description="Score DARPAN ETA accuracy")
    ap.add_argument("--days", type=int, default=7, help="scoring window")
    ap.add_argument("--by", choices=["horizon", "zone", "type"], default="horizon")
    args = ap.parse_args()

    print("=" * 78)
    print("  DARPAN ETA ACCURACY  —  predictions vs. what actually happened")
    print("=" * 78)

    if not os.path.exists(DB_PATH):
        print(f"FATAL: {DB_PATH} not found")
        return 1
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    n_snap = conn.execute("SELECT COUNT(*) c FROM eta_snapshots").fetchone()["c"] \
        if conn.execute("SELECT name FROM sqlite_master WHERE name='eta_snapshots'").fetchone() else 0
    n_obs = conn.execute("SELECT COUNT(*) c FROM live_observations").fetchone()["c"]
    print(f"predictions recorded : {n_snap:,}")
    print(f"observations recorded: {n_obs:,}")

    if n_snap == 0 or n_obs == 0:
        print("\nNothing to score yet.")
        print("This job becomes meaningful once both are populated:")
        print("  * predictions accumulate whenever /v1/trains/{no}/live is called")
        print("  * observations accumulate from harvest_live.py")
        print("Both need the provider quota restored (finding F-1).")
        return 0

    cutoff = (datetime.now(IST) - timedelta(days=args.days)).isoformat()

    # Latest observed arrival per (train, date, station) = ground truth.
    truth: dict[tuple, dict] = {}
    for r in conn.execute(
        "SELECT train_number, journey_date, station_code, sched_arrival, actual_arrival,"
        " delay_minutes, MAX(observed_at) AS observed_at"
        " FROM live_observations WHERE actual_arrival IS NOT NULL"
        " GROUP BY train_number, journey_date, station_code"
    ):
        truth[(r["train_number"], r["journey_date"], r["station_code"])] = dict(r)

    # Score every prediction that now has a matching outcome.
    groups: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    matched = unmatched = 0

    zones = {r["code"]: r["zone"] for r in conn.execute("SELECT code, zone FROM stations")}
    types = {r["number"]: r["type"] for r in conn.execute("SELECT number, type FROM trains")}

    for s in conn.execute(
        "SELECT * FROM eta_snapshots WHERE predicted_at >= ? ORDER BY predicted_at", (cutoff,)
    ):
        key = (s["train_number"], s["journey_date"], s["station_code"])
        t = truth.get(key)
        if not t:
            unmatched += 1
            continue
        actual = parse(t["actual_arrival"])
        predicted = parse(s["eta"])
        scheduled = parse(t["sched_arrival"])
        if actual is None or predicted is None:
            unmatched += 1
            continue
        matched += 1

        if args.by == "horizon":
            g = horizon_bucket(s["horizon_minutes"])
        elif args.by == "zone":
            g = zones.get(s["station_code"]) or "unknown"
        else:
            g = types.get(s["train_number"]) or "unknown"

        err_m0 = (predicted - actual).total_seconds() / 60.0
        groups[g]["m0"].append(err_m0)

        if scheduled is not None:
            groups[g]["schedule"].append((scheduled - actual).total_seconds() / 60.0)
        prov = parse(s["provider_eta"])
        if prov is not None:
            groups[g]["provider"].append((prov - actual).total_seconds() / 60.0)

        # Interval coverage: did reality land inside our stated p10-p90 band?
        p10, p90 = parse(s["band_p10"]), parse(s["band_p90"])
        if p10 and p90:
            groups[g]["coverage"].append(1.0 if p10 <= actual <= p90 else 0.0)

    print(f"\nscored: {matched:,} predictions matched to outcomes"
          f"  ({unmatched:,} awaiting an outcome)")
    if matched == 0:
        print("\nNo prediction has a matching observation yet. Predictions are scoreable")
        print("only after the train has actually passed the stop, so this fills in with time.")
        return 0

    print(f"\nGrouped by {args.by}. MAE / bias in minutes; lower MAE is better.")
    print("-" * 78)
    print(f"{'group':<12}{'n':>7}{'M0 MAE':>10}{'sched MAE':>11}{'prov MAE':>10}"
          f"{'M0 bias':>10}{'p90 err':>9}{'cover':>8}")
    print("-" * 78)

    for g in sorted(groups):
        d = groups[g]
        n = len(d["m0"])
        cov = (sum(d["coverage"]) / len(d["coverage"]) * 100) if d["coverage"] else float("nan")
        print(f"{g:<12}{n:>7}{mae(d['m0']):>10.1f}{mae(d['schedule']):>11.1f}"
              f"{mae(d['provider']):>10.1f}{bias(d['m0']):>+10.1f}"
              f"{pctile(d['m0'], 0.9):>9.1f}{cov:>7.0f}%")

    # Headline verdict across all groups.
    all_m0 = [v for d in groups.values() for v in d["m0"]]
    all_sched = [v for d in groups.values() for v in d["schedule"]]
    all_prov = [v for d in groups.values() for v in d["provider"]]
    print("-" * 78)
    print(f"{'ALL':<12}{len(all_m0):>7}{mae(all_m0):>10.1f}{mae(all_sched):>11.1f}"
          f"{mae(all_prov):>10.1f}{bias(all_m0):>+10.1f}{pctile(all_m0,0.9):>9.1f}")

    print("\nverdict:")
    if all_sched:
        d = mae(all_sched) - mae(all_m0)
        print(f"  vs timetable : M0 is {abs(d):.1f} min {'BETTER' if d > 0 else 'WORSE'}"
              f" — {'the core claim holds' if d > 0 else 'THE CORE CLAIM DOES NOT HOLD YET'}")
    if all_prov:
        d = mae(all_prov) - mae(all_m0)
        print(f"  vs provider  : M0 is {abs(d):.1f} min {'BETTER' if d > 0 else 'WORSE'}"
              f" — {'we add value over forwarding their number' if d > 0 else 'we are not yet adding value over the provider'}")
    cov_all = [v for d in groups.values() for v in d["coverage"]]
    if cov_all:
        c = sum(cov_all) / len(cov_all) * 100
        print(f"  interval     : {c:.0f}% of outcomes fell inside our p10-p90 band "
              f"(target ~80%; {'well calibrated' if 70 <= c <= 90 else 'MISCALIBRATED — bands are too ' + ('wide' if c > 90 else 'narrow')})")
    print("\nNote: M0 is pure persistence until segments have history. These numbers are")
    print("the baseline Phase 2's M2 model must beat to be promoted (plan §7.1).")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
