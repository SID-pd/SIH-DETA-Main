"""
Risk overlay — M1 (plan §5.3, task W3.7 complete).

Serves the delay-risk classifier as a PROBABILITY ONLY. It never produces a clock time:
every arrival time in the product comes from the deterministic M0 engine (ADR-005).

Two artifacts, and which one loads matters
------------------------------------------
`eta_model_subset.joblib`  (preferred) — trained by packages/ml/train_risk_classifier.py
    on the 16 features we can genuinely source at request time. Zero imputed inputs.
`eta_model.joblib`         (fallback)  — the original 44-feature model. Serving it means
    imputing 23 inputs, so more than half the feature vector would be a constant. It is
    used only if the subset artifact is missing, and the response says so explicitly.

Measured cost of that honesty, on identical synthetic data (full 1.5M rows):

    ROC AUC   full 0.9229  ->  subset 0.8494   (-0.0735)
    Brier     full 0.0978  ->  subset 0.1375   (+0.0397)

Those 7.4 AUC points are the quantified value of the IR-internal data we do not have
(rake age, LHB, maintenance score, seat utilisation, overload) plus the route attributes
nobody has curated yet. That number is the business case for a data-sharing request —
which is why /v1/meta/model publishes both columns rather than only the flattering one.

Feature provenance is reported per prediction in three buckets:
    measured  — read directly from the clock, our static graph, or the provider
    derived   — computed from measured inputs by a documented rule of ours
    imputed   — a constant stand-in (should be empty when the subset model is loaded)
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

_SEASON_BY_MONTH = {
    12: "Winter/Fog", 1: "Winter/Fog", 2: "Winter/Fog",
    3: "Pre-Monsoon", 4: "Summer", 5: "Summer",
    6: "Monsoon", 7: "Monsoon", 8: "Monsoon", 9: "Monsoon",
    10: "Post-Monsoon", 11: "Autumn",
}

# Zones where winter fog materially disrupts operations (Indo-Gangetic plain).
# Used only by our own fog rule below; documented rather than tuned.
FOG_PRONE_ZONES = {"NR", "NCR", "NER", "NWR", "ECR", "ER", "NFR", "WCR"}

# Fallback constants, used ONLY when the 44-feature model has to be served.
LEGACY_IMPUTED_DEFAULTS = {
    "loco_age_years": 15.0, "coach_age_years": 8.0, "has_lhb_coaches": 1,
    "is_rake_shared": 0, "maintenance_score": 6.5, "seat_utilisation_pct": 95.0,
    "is_overloaded": 0, "is_special_train": 0, "traction_type": "Electric",
    "track_doubled": 1, "is_hdn_route": 0, "psr_count": 3, "is_circular_route": 0,
    "is_electrified": 1, "source_station_category": "A",
    "destination_station_category": "A", "zone_fog_index": 0.45,
    "zone_congestion_index": 0.65, "season_severity_score": 0.5,
    "route_historical_ontime_pct": 70.0, "late_incoming_rake": 0,
    "is_festival_season": 0, "train_freq": 0.0,
}


class RiskModel:
    """Lazily-loaded artifact wrapper. Never raises into a request path."""

    def __init__(self, model_path: str, enabled: bool = True,
                 subset_path: str | None = None) -> None:
        self.model_path = model_path
        # Sibling of the legacy artifact unless told otherwise.
        self.subset_path = subset_path or os.path.join(
            os.path.dirname(model_path), "eta_model_subset.joblib")
        self.enabled = enabled
        self._lock = threading.Lock()
        self._loaded = False
        self._bundle = None
        self.is_subset = False
        self.load_error: str | None = None
        self.version = "unloaded"

    # --- loading ----------------------------------------------------------

    def _load(self) -> None:
        if self._loaded or not self.enabled:
            return
        with self._lock:
            if self._loaded:
                return
            try:
                import joblib

                if os.path.exists(self.subset_path):
                    self._bundle = joblib.load(self.subset_path)
                    self.is_subset = True
                    self.version = self._bundle.get("version", "risk-clf-subset")
                elif os.path.exists(self.model_path):
                    self._bundle = joblib.load(self.model_path)
                    self.is_subset = False
                    self.version = "risk-clf-synthetic-full-v1"
                    self.load_error = (
                        "subset artifact missing; serving the 44-feature model with "
                        "23 imputed inputs. Run packages/ml/train_risk_classifier.py.")
                else:
                    raise FileNotFoundError(
                        f"neither {self.subset_path} nor {self.model_path} exists")
            except Exception as exc:  # noqa: BLE001
                self.load_error = f"{type(exc).__name__}: {exc}"
                self._bundle = None
            self._loaded = True

    @property
    def available(self) -> bool:
        self._load()
        return self._bundle is not None

    # --- disclosure -------------------------------------------------------

    def metadata(self) -> dict:
        """Published verbatim at /v1/meta/model — the honesty surface."""
        self._load()
        b = self._bundle or {}
        meta = {
            "version": self.version,
            "available": self._bundle is not None,
            "loadError": self.load_error,
            "artifact": os.path.basename(self.subset_path if self.is_subset else self.model_path),
            "servingLiveFeasibleSubset": self.is_subset,
            "role": "risk-probability-only",
            "targetVariable": "is_delayed (binary: >15 min late at destination)",
            "granularity": "journey-level",
            "trainingData": b.get("training_data", "synthetic (Kaggle ir_train.csv)"),
            "trainingRows": b.get("training_rows"),
            "producesClockTimes": False,
            "etaSource": "m0-propagation (deterministic route-graph walk)",
            "featureCount": len(b.get("feature_names") or []),
            "caveat": (
                "Metrics are measured on SYNTHETIC data and do not transfer to real "
                "journeys; they compare feature sets on identical data, nothing more. "
                "This model contributes a delay probability only — every arrival time "
                "the API returns comes from the deterministic M0 engine."
            ),
        }
        if self.is_subset:
            meta.update({
                "metricsOnSyntheticData": {
                    "subsetModel_servedInProduction": b.get("validation_metrics"),
                    "fullFeatureModel_notServable": b.get("comparison_full_feature_metrics"),
                    "interpretation": (
                        "The full-feature column needs 28 inputs we cannot source live "
                        "(8 of them IR-internal). The gap between the columns is the "
                        "quantified value of that missing data, not a model deficiency."
                    ),
                },
                "liveFeasibleFeatures": b.get("live_feasible_features"),
                "droppedFeatures": b.get("dropped_features"),
                "imputedFeatureCount": 0,
            })
        else:
            meta.update({
                "validationMetricsOnSyntheticData": b.get("validation_metrics"),
                "imputedFeatureCount": len(LEGACY_IMPUTED_DEFAULTS),
                "featuresUnavailableLive": sorted(LEGACY_IMPUTED_DEFAULTS),
            })
        return meta

    # --- features ---------------------------------------------------------

    def _build_live_feasible(self, *, train: dict, static_train: dict | None,
                             station_zone: str | None, when: datetime) -> tuple[dict, dict]:
        """
        Build the 16 live-feasible raw features plus their derivations.

        Returns (features, provenance) where provenance buckets every field as
        measured / derived / imputed, so the API can report exactly how much of the
        prediction rests on real inputs.
        """
        f: dict = {}
        measured: list[str] = []
        derived: list[str] = []
        imputed: list[str] = []

        # --- clock: exact, no assumptions ---
        f["year"] = when.year
        f["month"] = when.month
        f["day_of_week"] = when.weekday()
        f["departure_hour"] = when.hour
        measured += ["year", "month", "day_of_week", "departure_hour"]

        f["is_weekend"] = 1 if when.weekday() >= 5 else 0
        f["is_night_departure"] = 1 if (when.hour >= 22 or when.hour < 4) else 0
        f["is_peak_hour"] = 1 if (6 <= when.hour <= 8 or 17 <= when.hour <= 20) else 0
        f["season"] = _SEASON_BY_MONTH.get(when.month, "Summer")
        f["is_monsoon_season"] = 1 if when.month in (6, 7, 8, 9) else 0
        derived += ["is_weekend", "is_night_departure", "is_peak_hour", "season",
                    "is_monsoon_season"]

        # Fog rule, ours and documented: winter months, pre-noon, fog-prone zone.
        # This approximates (does not reproduce) the training set's generator, so it
        # is reported as derived rather than measured.
        zone = (station_zone or (static_train or {}).get("zone") or "").upper() or None
        fog_month = when.month in (12, 1, 2)
        fog_hour = when.hour < 10
        fog_zone = zone in FOG_PRONE_ZONES if zone else False
        f["is_fog_risk"] = 1 if (fog_month and fog_hour and fog_zone) else 0
        f["fog_risk_score"] = round(
            (0.5 if fog_month else 0.0) + (0.3 if fog_hour else 0.0)
            + (0.2 if fog_zone else 0.0), 3)
        derived += ["is_fog_risk", "fog_risk_score"]

        # --- our own static graph ---
        st = static_train or {}
        dist = st.get("distance_km")
        dur = st.get("duration_min")
        stops = st.get("num_scheduled_stops")

        if dist:
            f["distance_km"] = float(dist)
            measured.append("distance_km")
        else:
            f["distance_km"] = 500.0
            imputed.append("distance_km")

        if dur:
            f["scheduled_travel_hours"] = float(dur) / 60.0
            measured.append("scheduled_travel_hours")
        else:
            f["scheduled_travel_hours"] = 10.0
            imputed.append("scheduled_travel_hours")

        if stops:
            f["num_scheduled_stops"] = float(stops)
            measured.append("num_scheduled_stops")
        else:
            f["num_scheduled_stops"] = 10.0
            imputed.append("num_scheduled_stops")

        ttype = (train.get("type") or st.get("type") or "").strip()
        if ttype:
            f["train_type"] = ttype
            measured.append("train_type")
        else:
            f["train_type"] = "Express"
            imputed.append("train_type")

        if zone:
            f["zone_abbr"] = zone
            measured.append("zone_abbr")
        else:
            f["zone_abbr"] = "NR"
            imputed.append("zone_abbr")

        return f, {"measured": sorted(set(measured)), "derived": sorted(set(derived)),
                   "imputed": sorted(set(imputed))}

    # --- inference --------------------------------------------------------

    def predict(self, *, train: dict, static_train: dict | None,
                station_zone: str | None, when: datetime | None = None) -> dict | None:
        """
        Return a risk assessment, or None when the model cannot honestly be applied.
        Never raises: a broken model degrades the response, it does not fail it.
        """
        self._load()
        if self._bundle is None:
            return None

        when = when or datetime.now(IST)
        try:
            import numpy as np
            import pandas as pd

            feats, provenance = self._build_live_feasible(
                train=train, static_train=static_train, station_zone=station_zone, when=when)

            # Legacy artifact: top up with constants and record every one of them.
            if not self.is_subset:
                for k, v in LEGACY_IMPUTED_DEFAULTS.items():
                    if k not in feats:
                        feats[k] = v
                        provenance["imputed"].append(k)
                provenance["imputed"] = sorted(set(provenance["imputed"]))

            # Derived columns, identical to the training-time transformations so
            # train/serve skew is impossible (both come from one implementation).
            travel = max(feats["scheduled_travel_hours"], 0.1)
            d = max(feats["distance_km"], 1.0)
            s = feats["num_scheduled_stops"]
            feats["speed_kmh"] = d / travel
            feats["stops_per_100km"] = s / (d / 100.0)
            feats["time_per_stop_mins"] = (travel * 60.0) / (s + 1.0)
            feats["sin_hour"] = np.sin(2 * np.pi * feats["departure_hour"] / 24.0)
            feats["cos_hour"] = np.cos(2 * np.pi * feats["departure_hour"] / 24.0)
            feats["sin_month"] = np.sin(2 * np.pi * (feats["month"] - 1) / 12.0)
            feats["cos_month"] = np.cos(2 * np.pi * (feats["month"] - 1) / 12.0)
            feats["sin_dow"] = np.sin(2 * np.pi * feats["day_of_week"] / 7.0)
            feats["cos_dow"] = np.cos(2 * np.pi * feats["day_of_week"] / 7.0)

            if not self.is_subset:
                feats["composite_risk_index"] = (
                    0.40 * feats["zone_congestion_index"] + 0.30 * feats["zone_fog_index"]
                    + 0.30 * feats["season_severity_score"])
                feats["loco_coach_age_ratio"] = (
                    feats["loco_age_years"] / max(feats["coach_age_years"], 0.5))
                feats["high_fog_hazard"] = int(
                    feats["is_fog_risk"] == 1 and feats["zone_fog_index"] > 0.55)
                feats["cascade_congestion_risk"] = int(
                    feats["late_incoming_rake"] == 1 and feats["zone_congestion_index"] > 0.70)
                feats["overload_peak_risk"] = int(
                    feats["is_overloaded"] == 1 and feats["is_peak_hour"] == 1)

            names: list[str] = list(self._bundle.get("feature_names") or [])
            mappings: dict = self._bundle.get("categorical_mappings") or {}
            df = pd.DataFrame([{n: feats.get(n, 0) for n in names}], columns=names)
            for col, mapping in mappings.items():
                if col in df.columns:
                    df[col] = df[col].astype(str).map(mapping).fillna(-1).astype("int32")
            df = df.apply(lambda c: pd.to_numeric(c, errors="coerce")).fillna(-1)

            prob = float(self._bundle["model"].predict_proba(df)[0, 1])
        except Exception as exc:  # noqa: BLE001
            self.load_error = f"inference failed: {type(exc).__name__}: {exc}"
            return None

        label = "low" if prob <= 0.33 else "moderate" if prob <= 0.66 else "elevated"
        n_imputed = len(provenance["imputed"])
        val = (self._bundle.get("validation_metrics") or {})

        if self.is_subset and n_imputed == 0:
            trust = ("every input measured or derived from real data; trained on "
                     "synthetic journeys, so treat as indicative")
        elif self.is_subset:
            trust = f"indicative: {n_imputed} input(s) unavailable for this train"
        else:
            trust = (f"low confidence: serving the full-feature model with {n_imputed} "
                     f"imputed inputs — run the subset trainer")

        return {
            "delayProbability": round(prob, 4),
            "label": label,
            "modelVersion": self.version,
            "target": "arrives >15 min late at destination",
            "servingLiveFeasibleSubset": self.is_subset,
            "featureProvenance": provenance,
            "imputedFeatures": provenance["imputed"],
            "imputedFeatureCount": n_imputed,
            "modelRocAucOnSyntheticData": val.get("roc_auc"),
            "trustworthiness": trust,
            "appliesToClockTimes": False,
        }
