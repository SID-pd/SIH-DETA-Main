"""
M1 — risk classifier retrained on the LIVE-FEASIBLE feature subset.
====================================================================
Completes plan task W3.7, and answers finding F-6.

The problem this fixes
----------------------
`eta_model.joblib` was trained on all 44 columns of the synthetic Kaggle set. Serving it
in production means supplying all 44 at request time — and we measured that **23 of them
have to be imputed**, because they are either IR-internal (rake age, LHB, maintenance
score, seat utilisation, overload) or route attributes nobody has curated yet (PSR count,
HDN flag, station categories, zone indices, historical on-time %).

A prediction where over half the feature vector is a constant is not a measurement of
that train. It is the model's average opinion, dressed up as a per-train forecast.

What this script does
---------------------
Trains the same estimator on ONLY the features we can genuinely source at request time,
then reports both models side by side so the cost of honesty is visible and quotable
rather than hidden:

    full-feature model    AUC on synthetic data (unusable live: 23 imputed inputs)
    subset model          AUC on synthetic data (every input really available)

The subset AUC will be lower. That is the honest number, and it is the one the API
serves. Publishing both is the point: it quantifies exactly how much predictive power
the missing IR data represents, which is also the business case for requesting access.

Feature-inclusion rule
----------------------
A column is kept only if the running API can populate it for a real train, today, from
the clock, our own static graph, or the provider response. Anything requiring curation
we have not done, or data we do not have, is dropped rather than defaulted.

Run:  python packages/ml/train_risk_classifier.py [--sample 400000] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss,
                            f1_score, log_loss, precision_score, recall_score,
                            roc_auc_score)
from sklearn.model_selection import train_test_split

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
DATA_DIR = os.path.join(REPO_ROOT, "indian-railways-predict-train-delay")
TRAIN_PATH = os.path.join(DATA_DIR, "ir_train.csv")
OUT_PATH = os.path.join(REPO_ROOT, "eta_model_subset.joblib")
CARD_PATH = os.path.join(BASE_DIR, "registry", "risk_clf_subset_card.json")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# The live-feasible feature contract
# ---------------------------------------------------------------------------

# Sourceable at request time, today. Each entry names WHERE it comes from, so this
# list can be audited against the API rather than trusted.
LIVE_FEASIBLE = {
    # --- clock: free, exact ---
    "year": "request time",
    "month": "request time",
    "day_of_week": "request time",
    "departure_hour": "request time",
    "is_weekend": "request time",
    "is_night_departure": "request time",
    "is_peak_hour": "request time",
    "season": "request time (month -> season map)",
    "is_monsoon_season": "request time (month)",
    "is_fog_risk": "request time (month + hour)",
    "fog_risk_score": "request time (month + hour + zone)",
    # --- our own static graph (loaded by etl_static_graph.py) ---
    "distance_km": "trains.distance_km",
    "num_scheduled_stops": "count(schedule_stops)",
    "scheduled_travel_hours": "trains.duration_min",
    "train_type": "trains.type / provider trainInfo.type",
    "zone_abbr": "stations.zone of the current position",
}

# Dropped, with the reason recorded. This list IS the ask for IR data access.
DROPPED = {
    # structurally unavailable: IR-internal asset and occupancy data
    "loco_age_years": "IR-internal (rolling stock register)",
    "coach_age_years": "IR-internal (rolling stock register)",
    "has_lhb_coaches": "IR-internal (rake composition register)",
    "is_rake_shared": "IR-internal (rake link diagram)",
    "maintenance_score": "IR-internal (maintenance system)",
    "seat_utilisation_pct": "IR-internal (booking/occupancy)",
    "is_overloaded": "IR-internal (booking/occupancy)",
    "is_special_train": "IR-internal (timetable classification)",
    "traction_type": "not in our dataset; curatable from OSM later",
    # uncurated route/geography attributes: obtainable, just not done yet
    "track_doubled": "uncurated (OSM/IR route attributes)",
    "is_hdn_route": "uncurated (IR HDN corridor list)",
    "psr_count": "uncurated (IR permanent speed restrictions)",
    "is_circular_route": "uncurated",
    "is_electrified": "uncurated (OSM electrification)",
    "source_station_category": "uncurated (IR station category table)",
    "destination_station_category": "uncurated (IR station category table)",
    # derivable from OUR data, but only once harvesting has accumulated
    "zone_fog_index": "pending: zone_stats needs harvested history",
    "zone_congestion_index": "pending: zone_stats needs harvested history",
    "season_severity_score": "pending: zone_stats needs harvested history",
    "route_historical_ontime_pct": "pending: needs harvested history",
    "late_incoming_rake": "pending: derivable from live_observations",
    "is_festival_season": "uncurated (festival calendar table)",
    # identifiers / leakage
    "journey_id": "identifier",
    "departure_date": "free-text date, superseded by the clock features",
    "train_number": "identifier (frequency-encoded in the full model; drops here to "
                    "avoid memorising specific trains)",
    "zone": "duplicate of zone_abbr",
    "primary_delay_cause": "LEAKAGE (train set only)",
    "delay_minutes": "LEAKAGE (train set only)",
}

CATEGORICAL = ["train_type", "season", "zone_abbr"]


def engineer(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derived features, restricted to what the live-feasible columns can produce.

    Mirrors the transformations in the original training script so the two models are
    compared on equal footing — anything derived from a dropped column is itself
    dropped (e.g. composite_risk_index needs the zone indices; loco_coach_age_ratio
    needs the asset register).
    """
    out = df.copy()
    travel = np.maximum(out["scheduled_travel_hours"].values, 0.1)
    dist = np.maximum(out["distance_km"].values, 1.0)
    stops = out["num_scheduled_stops"].values

    out["speed_kmh"] = (dist / travel).astype(np.float32)
    out["stops_per_100km"] = (stops / (dist / 100.0)).astype(np.float32)
    out["time_per_stop_mins"] = ((travel * 60.0) / (stops + 1.0)).astype(np.float32)

    # Cyclical encodings so 23:00 and 00:00 are adjacent rather than 23 apart.
    hour, month, dow = out["departure_hour"].values, out["month"].values, out["day_of_week"].values
    out["sin_hour"] = np.sin(2 * np.pi * hour / 24.0).astype(np.float32)
    out["cos_hour"] = np.cos(2 * np.pi * hour / 24.0).astype(np.float32)
    out["sin_month"] = np.sin(2 * np.pi * (month - 1) / 12.0).astype(np.float32)
    out["cos_month"] = np.cos(2 * np.pi * (month - 1) / 12.0).astype(np.float32)
    out["sin_dow"] = np.sin(2 * np.pi * dow / 7.0).astype(np.float32)
    out["cos_dow"] = np.cos(2 * np.pi * dow / 7.0).astype(np.float32)
    return out


def encode(train: pd.DataFrame, val: pd.DataFrame) -> tuple:
    mappings, idx = {}, []
    tr, va = train.copy(), val.copy()
    for col in CATEGORICAL:
        if col not in tr.columns:
            continue
        vals = sorted(tr[col].astype(str).unique())
        m = {v: i for i, v in enumerate(vals)}
        mappings[col] = m
        tr[col] = tr[col].astype(str).map(m).fillna(-1).astype(np.int32)
        va[col] = va[col].astype(str).map(m).fillna(-1).astype(np.int32)
        idx.append(tr.columns.get_loc(col))
    return tr, va, idx, mappings


def metrics(y_true, y_prob, thresh: float = 0.5) -> dict:
    y_pred = (y_prob >= thresh).astype(int)
    return {
        "roc_auc": round(float(roc_auc_score(y_true, y_prob)), 4),
        "pr_auc": round(float(average_precision_score(y_true, y_prob)), 4),
        "log_loss": round(float(log_loss(y_true, y_prob)), 4),
        # Brier score matters more than AUC here: we serve a PROBABILITY to users, so
        # calibration (is "59%" really 59%?) matters more than ranking ability.
        "brier": round(float(brier_score_loss(y_true, y_prob)), 4),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
    }


def fit(X_tr, y_tr, cat_idx) -> HistGradientBoostingClassifier:
    """Same anti-overfitting configuration as the original, for a fair comparison."""
    model = HistGradientBoostingClassifier(
        loss="log_loss", learning_rate=0.08, max_iter=300, max_leaf_nodes=45,
        max_depth=7, min_samples_leaf=100, l2_regularization=2.0,
        categorical_features=cat_idx, early_stopping=True, n_iter_no_change=15,
        validation_fraction=0.10, random_state=42,
    )
    model.fit(X_tr, y_tr)
    return model


def main() -> int:
    ap = argparse.ArgumentParser(description="Train the live-feasible risk classifier")
    ap.add_argument("--sample", type=int, default=None, help="row cap (faster iteration)")
    ap.add_argument("--out", type=str, default=OUT_PATH)
    args = ap.parse_args()

    print("=" * 78)
    print("  M1 — RISK CLASSIFIER ON THE LIVE-FEASIBLE FEATURE SUBSET")
    print("=" * 78)
    if not os.path.exists(TRAIN_PATH):
        print(f"FATAL: {TRAIN_PATH} not found")
        return 1

    t0 = time.time()
    print(f"\n[1/5] loading {os.path.basename(TRAIN_PATH)}")
    df = pd.read_csv(TRAIN_PATH)
    if args.sample and args.sample < len(df):
        df = df.sample(n=args.sample, random_state=42).reset_index(drop=True)
        print(f"      sampled {len(df):,} of the full set")
    print(f"      {len(df):,} rows · {df.shape[1]} columns")

    y = df["is_delayed"].astype(np.int8).values
    print(f"      target: {y.mean()*100:.2f}% delayed")

    # --- audit the contract against the actual file -------------------------
    print("\n[2/5] feature audit")
    available = [c for c in LIVE_FEASIBLE if c in df.columns]
    missing = [c for c in LIVE_FEASIBLE if c not in df.columns]
    dataset_cols = set(df.columns) - {"is_delayed"}
    unclassified = dataset_cols - set(LIVE_FEASIBLE) - set(DROPPED)
    print(f"      live-feasible kept : {len(available)}")
    print(f"      dropped            : {len(dataset_cols) - len(available)}")
    if missing:
        print(f"      WARNING: declared live-feasible but absent from the dataset: {missing}")
    if unclassified:
        # Every column must be an explicit decision. An unclassified column means the
        # contract above has drifted from the data and the audit is no longer honest.
        print(f"      WARNING: unclassified columns (decide these): {sorted(unclassified)}")

    # --- subset model -------------------------------------------------------
    print("\n[3/5] training SUBSET model (live-feasible features only)")
    X_sub = engineer(df[available])
    Xtr, Xva, ytr, yva = train_test_split(X_sub, y, test_size=0.15, random_state=42, stratify=y)
    Xtr, Xva, cat_idx, mappings = encode(Xtr, Xva)
    print(f"      {Xtr.shape[1]} features after engineering ({len(cat_idx)} categorical)")
    m_sub = fit(Xtr, ytr, cat_idx)
    print(f"      converged in {m_sub.n_iter_} iterations")
    sub_val = metrics(yva, m_sub.predict_proba(Xva)[:, 1])
    sub_train = metrics(ytr[:100000], m_sub.predict_proba(Xtr.iloc[:100000])[:, 1])

    # --- full model, for the comparison ------------------------------------
    print("\n[4/5] training FULL-feature model (for comparison only — not servable)")
    full_cols = [c for c in df.columns
                 if c not in ("is_delayed", "primary_delay_cause", "delay_minutes",
                              "journey_id", "departure_date", "train_number", "zone")]
    X_full = df[full_cols].copy()
    for c in X_full.columns:
        if X_full[c].dtype == object:
            vals = sorted(X_full[c].astype(str).unique())
            X_full[c] = X_full[c].astype(str).map({v: i for i, v in enumerate(vals)}).astype(np.int32)
    Ftr, Fva, fytr, fyva = train_test_split(X_full, y, test_size=0.15, random_state=42, stratify=y)
    cat_full = [Ftr.columns.get_loc(c) for c in CATEGORICAL if c in Ftr.columns]
    m_full = fit(Ftr, fytr, cat_full)
    full_val = metrics(fyva, m_full.predict_proba(Fva)[:, 1])

    # --- report -------------------------------------------------------------
    print("\n" + "=" * 78)
    print(f"{'metric':<14} | {'FULL (44 cols)':>15} | {'SUBSET (live)':>15} | {'cost of honesty':>17}")
    print("-" * 78)
    for k in ("roc_auc", "pr_auc", "brier", "log_loss", "accuracy", "precision", "recall", "f1"):
        delta = sub_val[k] - full_val[k]
        print(f"{k:<14} | {full_val[k]:>15.4f} | {sub_val[k]:>15.4f} | {delta:>+17.4f}")
    print("=" * 78)
    gap = sub_train["roc_auc"] - sub_val["roc_auc"]
    print(f"subset generalisation gap (train-val ROC AUC): {gap:+.4f}"
          f"{'  [OK]' if abs(gap) < 0.02 else '  [CHECK OVERFIT]'}")
    print(f"\nThe SUBSET column is the only one that describes a real prediction: every")
    print(f"input is genuinely available at request time. The FULL column needs {len(DROPPED)}")
    print(f"values we do not have, {sum(1 for v in DROPPED.values() if 'IR-internal' in v)} of")
    print(f"which are IR-internal and cannot be obtained without a data agreement.")

    # --- persist ------------------------------------------------------------
    print("\n[5/5] saving artifact + model card")
    feature_names = list(Xtr.columns)
    bundle = {
        "model": m_sub,
        "feature_names": feature_names,
        "categorical_indices": cat_idx,
        "categorical_mappings": mappings,
        "validation_metrics": sub_val,
        "train_metrics_sample": sub_train,
        "comparison_full_feature_metrics": full_val,
        "live_feasible_features": LIVE_FEASIBLE,
        "dropped_features": DROPPED,
        "version": "risk-clf-subset-2026.09.1",
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "training_rows": int(len(df)),
        "training_data": "synthetic (Kaggle ir_train.csv)",
        "target": "is_delayed (binary: >15 min late at destination)",
        "role": "risk-probability-only; never produces a clock time",
    }
    joblib.dump(bundle, args.out)
    print(f"      artifact: {args.out}  ({os.path.getsize(args.out)/1e6:.2f} MB)")

    os.makedirs(os.path.dirname(CARD_PATH), exist_ok=True)
    card = {k: v for k, v in bundle.items() if k != "model"}
    card["caveats"] = [
        "Trained on SYNTHETIC data. These metrics do not transfer to real journeys; "
        "they only compare the two feature sets on identical data.",
        "Journey-level and binary. Cannot express an arrival time; all clock times in "
        "the product come from the deterministic M0 engine.",
        "Random stratified split, not time-based. The synthetic set has no dependable "
        "temporal ordering; the real M2 model in Phase 2 must use time-based splits.",
        f"{len(DROPPED)} dataset columns are excluded by design — see dropped_features.",
    ]
    with open(CARD_PATH, "w", encoding="utf-8") as fh:
        json.dump(card, fh, indent=2)
    print(f"      model card: {CARD_PATH}")
    print(f"\n[SUCCESS] {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
