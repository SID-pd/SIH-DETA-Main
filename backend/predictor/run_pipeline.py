"""
Master CLI Pipeline for Train ETA & Delay Prediction Framework.
SIH Problem Statement 26028.

Usage Examples:
    python -m predictor.run_pipeline build-data
    python -m predictor.run_pipeline train
    python -m predictor.run_pipeline predict --train 12301 --current-station CNB --next-station PRYJ --current-delay 25 --sched-dep 00:55 --sched-arr 02:35
    python -m predictor.run_pipeline scrape-live --train 12301
    python -m predictor.run_pipeline all
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from predictor.config import MASTER_DATASET_CSV, MODEL_ARTIFACT_PATH
from predictor.data.dataset_loader import DatasetLoader
from predictor.models.evaluate import evaluate_models
from predictor.models.inference import StationETAPredictor
from predictor.models.train import train_station_eta_models
from predictor.scrapers.confirmtkt_scraper import ConfirmTktScraper
from predictor.scrapers.etrain_scraper import EtrainScraper
from predictor.scrapers.live_snapshot_daemon import LiveSnapshotDaemon
from predictor.scrapers.railradar_client import RailRadarClient
from predictor.scrapers.weather_client import WeatherClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("predictor.pipeline")


def cmd_build_data(args):
    """Builds the 31-feature ML dataset."""
    logger.info("=== STEP 1: Building 31-Feature Dataset ===")
    loader = DatasetLoader()
    df = loader.generate_master_dataset(
        num_trains=args.num_trains,
        runs_per_train=args.runs_per_train,
        force_rebuild=args.force,
    )
    print(f"\n[SUCCESS] Dataset generated with {len(df):,} rows and {len(df.columns)} columns.")
    print(f"Saved to: {MASTER_DATASET_CSV}\n")
    print(df.head(3).to_string())


def cmd_train(args):
    """Trains the Quantile Regressors for ETA & Delay."""
    logger.info("=== STEP 2: Training Dynamic ETA & Delay Models ===")
    loader = DatasetLoader()
    result = train_station_eta_models(dataset_loader=loader)
    metrics = result["metrics"]

    print("\n================ MODEL PERFORMANCE METRICS ================")
    print(f"  Primary Label:           {metrics['primary_label']}")
    print(f"  Delay MAE:               {metrics['delay_mae_minutes']} minutes")
    print(f"  Delay RMSE:              {metrics['delay_rmse_minutes']} minutes")
    print(f"  Delay R2 Score:          {metrics['delay_r2_score']}")
    print(f"  Secondary Label:         {metrics['secondary_label']}")
    print(f"  Travel Time MAE:         {metrics['travel_time_mae_minutes']} minutes")
    print(f"  Travel Time R2 Score:    {metrics['travel_time_r2_score']}")
    print(f"  Training Samples:        {metrics['train_samples']:,}")
    print(f"  Testing Samples:         {metrics['test_samples']:,}")
    print(f"  Model Saved To:          {MODEL_ARTIFACT_PATH}")
    print("===========================================================\n")

    # Evaluate feature importances
    eval_report = evaluate_models(
        result["bundle"],
        result["X_test"],
        result["y_delay_test"],
    )
    print("=== TOP 10 INFLUENTIAL FEATURES ===")
    for idx, item in enumerate(eval_report["top_feature_importances"][:10], start=1):
        print(f"  {idx:2d}. {item['feature']:<35} (importance: {item['importance']:.4f})")
    print("===================================\n")


def cmd_predict(args):
    """Runs real-time station ETA & delay inference."""
    logger.info("=== STEP 3: Running Dynamic Station ETA Inference ===")
    predictor = StationETAPredictor()

    if not predictor.is_ready():
        print("[NOTICE] Trained model not found. Training model first...")
        train_station_eta_models()
        predictor = StationETAPredictor()

    result = predictor.predict_next_station_eta(
        train_id=args.train,
        current_station=args.current_station,
        next_station=args.next_station,
        current_delay_minutes=args.current_delay,
        scheduled_dep_curr=args.sched_dep,
        scheduled_arr_next=args.sched_arr,
        actual_dep_curr=args.act_dep,
        distance_to_next_km=args.distance,
        train_name=args.train_name,
        month=args.month,
    )

    print("\n================== DYNAMIC ETA PREDICTION ==================")
    print(f"  Train:                     {result['train_id']} ({result['train_type']})")
    print(f"  Current Station:           {result['current_station']} (Delay: {result['current_delay_minutes']} mins)")
    print(f"  Next Station:              {result['next_station']} ({result['distance_km']} km away)")
    print(f"  Scheduled Arrival:         {result['scheduled_arrival_time']}")
    print(f"  PREDICTED ETA:             {result['predicted_eta']}")
    print(f"  90% Confidence Interval:   {result['eta_confidence_interval_90pct']}")
    print(f"  Predicted Next Delay:      {result['predicted_delay_at_next_station_minutes']} mins")
    print(f"  Delay Trend:               {result['delay_trend']}")
    print(f"  Section Travel Time:       {result['predicted_section_travel_time_minutes']} mins")
    if result["risk_factors"]:
        print(f"  Active Risk Factors:       {', '.join(result['risk_factors'])}")
    print("============================================================\n")


def cmd_scrape_live(args):
    """Scrapes live train status from ConfirmTkt / RailRadar."""
    logger.info(f"=== Scraping Live Train Status for {args.train} ===")
    scraper = ConfirmTktScraper()
    live_data = scraper.get_live_status(args.train)

    if not live_data:
        print(f"[WARNING] Could not retrieve live status for {args.train}. Trying RailRadar client fallback...")
        rr = RailRadarClient()
        telemetry = rr.get_live_telemetry(args.train)
        print(json.dumps(telemetry, indent=2))
        return

    print("\n=================== LIVE TRAIN STATUS ===================")
    print(f"  Train:            {live_data['train_number']} — {live_data['train_name']}")
    print(f"  Route:            {live_data['source_code']} -> {live_data['destination_code']} ({live_data['total_distance_km']} km)")
    print(f"  Current Position: {live_data['current_station_code']} ({live_data['current_station_name']})")
    print(f"  Current Delay:    {live_data['current_delay_minutes']} mins")
    print(f"  Next Station:     {live_data['next_station_code']} ({live_data['next_station_name']})")
    print(f"  Distance to Next: {live_data['distance_to_next_station_km']} km")
    print(f"  Stops Count:      {len(live_data['stops'])}")
    print("=========================================================\n")

    if args.predict_next and live_data['current_station_code'] and live_data['next_station_code']:
        # Run inference directly on scraped live position!
        stops = live_data['stops']
        curr_stop = next((s for s in stops if s['station_code'] == live_data['current_station_code']), None)
        next_stop = next((s for s in stops if s['station_code'] == live_data['next_station_code']), None)

        if curr_stop and next_stop:
            print("=== CALCULATING DYNAMIC ETA FROM LIVE SNAPSHOT ===")
            predictor = StationETAPredictor()
            if not predictor.is_ready():
                train_station_eta_models()
                predictor = StationETAPredictor()

            pred = predictor.predict_next_station_eta(
                train_id=live_data['train_number'],
                current_station=live_data['current_station_code'],
                next_station=live_data['next_station_code'],
                current_delay_minutes=float(live_data['current_delay_minutes']),
                scheduled_dep_curr=curr_stop['scheduled_departure'] or curr_stop['scheduled_arrival'],
                scheduled_arr_next=next_stop['scheduled_arrival'] or next_stop['scheduled_departure'],
                distance_to_next_km=live_data['distance_to_next_station_km'],
                train_name=live_data['train_name'],
            )
            print(f"  Scheduled Arrival: {pred['scheduled_arrival_time']}")
            print(f"  DYNAMIC ML ETA:    {pred['predicted_eta']} ({pred['eta_confidence_interval_90pct']})")
            print(f"  Expected Delay:    {pred['predicted_delay_at_next_station_minutes']} mins ({pred['delay_trend']})")
            print("==================================================\n")


def cmd_all(args):
    """Executes the full pipeline: Build data -> Train models -> Run sample inference."""
    cmd_build_data(args)
    cmd_train(args)
    # Run test prediction for Howrah Rajdhani departing Kanpur Central
    args.train = "12301"
    args.train_name = "Howrah - New Delhi Rajdhani Express"
    args.current_station = "CNB"
    args.next_station = "PRYJ"
    args.current_delay = 25.0
    args.sched_dep = "00:55"
    args.sched_arr = "02:35"
    args.act_dep = "01:20"
    args.distance = 194.0
    args.month = 12  # Winter Fog test
    cmd_predict(args)


def main():
    parser = argparse.ArgumentParser(description="Predictor CLI: Data Scraping & Dynamic Station ETA Prediction")
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # build-data
    p_build = subparsers.add_parser("build-data", help="Build 31-feature ML dataset")
    p_build.add_argument("--num-trains", type=int, default=120, help="Number of trains to sample")
    p_build.add_argument("--runs-per-train", type=int, default=10, help="Simulated historical runs per train")
    p_build.add_argument("--force", action="store_true", help="Force rebuild dataset CSV")

    # train
    p_train = subparsers.add_parser("train", help="Train Quantile Regressors for ETA & Delay")

    # predict
    p_pred = subparsers.add_parser("predict", help="Predict dynamic ETA for a station segment")
    p_pred.add_argument("--train", type=str, default="12301", help="Train number")
    p_pred.add_argument("--train-name", type=str, default="Rajdhani Express", help="Train name")
    p_pred.add_argument("--current-station", type=str, default="CNB", help="Current station code")
    p_pred.add_argument("--next-station", type=str, default="PRYJ", help="Next station code")
    p_pred.add_argument("--current-delay", type=float, default=20.0, help="Current delay in minutes")
    p_pred.add_argument("--sched-dep", type=str, default="14:00", help="Scheduled departure from current (HH:MM)")
    p_pred.add_argument("--sched-arr", type=str, default="16:00", help="Scheduled arrival at next (HH:MM)")
    p_pred.add_argument("--act-dep", type=str, default=None, help="Actual departure from current (HH:MM)")
    p_pred.add_argument("--distance", type=float, default=130.0, help="Distance to next station in km")
    p_pred.add_argument("--month", type=int, default=12, help="Month of travel (1-12)")

    # scrape-live
    p_scrape = subparsers.add_parser("scrape-live", help="Scrape live status for a train")
    p_scrape.add_argument("--train", type=str, required=True, help="5-digit train number")
    p_scrape.add_argument("--predict-next", action="store_true", help="Automatically run ML ETA on live position")

    # all
    p_all = subparsers.add_parser("all", help="Run full pipeline: build data, train models, run prediction")
    p_all.add_argument("--num-trains", type=int, default=100, help="Number of trains to sample")
    p_all.add_argument("--runs-per-train", type=int, default=8, help="Historical runs per train")
    p_all.add_argument("--force", action="store_true", help="Force rebuild dataset CSV")

    args = parser.parse_args()
    if not args.subcommand:
        parser.print_help()
        sys.exit(1)

    if args.subcommand == "build-data":
        cmd_build_data(args)
    elif args.subcommand == "train":
        cmd_train(args)
    elif args.subcommand == "predict":
        cmd_predict(args)
    elif args.subcommand == "scrape-live":
        cmd_scrape_live(args)
    elif args.subcommand == "all":
        cmd_all(args)


if __name__ == "__main__":
    main()
