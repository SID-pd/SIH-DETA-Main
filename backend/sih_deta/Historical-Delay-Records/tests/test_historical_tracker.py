"""
Comprehensive test suite for Indian Railways Historical Delay Records & Punctuality Engine.
Validates HTML/JS date & delay parsing, 15-day windowing, sectional delta math,
Markovian transition matrices, SQLite persistence, and dataset exports.
"""

import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.delay_matrix_engine import DelayMatrixEngine, get_delay_state
from analytics.sectional_profiler import SectionalProfiler
from scrapers.historical_delay_scraper import HistoricalDelayScraper
from storage.historical_db import HistoricalDatabase
from storage.historical_exporter import HistoricalExporter


class TestHistoricalDelayEngine(unittest.TestCase):
    """Test suite covering parser, analytics, database, and exports."""

    def test_delay_state_classifier(self):
        """Test punctuality state classification."""
        self.assertEqual(get_delay_state(0), "ON_TIME")
        self.assertEqual(get_delay_state(-5), "ON_TIME")
        self.assertEqual(get_delay_state(5), "ON_TIME")
        self.assertEqual(get_delay_state(6), "MINOR_DELAY")
        self.assertEqual(get_delay_state(15), "MINOR_DELAY")
        self.assertEqual(get_delay_state(16), "MODERATE_DELAY")
        self.assertEqual(get_delay_state(45), "MODERATE_DELAY")
        self.assertEqual(get_delay_state(46), "SEVERE_DELAY")
        self.assertEqual(get_delay_state(120), "SEVERE_DELAY")
        self.assertEqual(get_delay_state(None), "UNKNOWN")

    def test_parse_history_html(self):
        """Test extraction of embedded JS date objects and delay arrays from etrain HTML."""
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Running History of LJN SWARNA SHATABDI (12004) for this month</title>
        </head>
        <body>
        <script>
            var et = {};
            et.rsStat = [];
            et.rsStat.primaryData = [
                ['Stations','Right Time', 'Slight Delay', 'Significant Delay', 'Cancelled/Unknown', {'type': 'string'}],
                ['NDLS', 28, 1, 1, 0, 3.5],
                ['GZB', 25, 3, 2, 0, 9.2],
                ['CNB', 20, 5, 5, 0, 18.4],
                ['LJN', 22, 6, 2, 0, 11.1]
            ];
            et.rsStat.tooltipData = [
                ['Date',{'label':'NDLS'},{'label':'GZB'},{'label':'CNB'},{'label':'LJN'}]
                ,[new Date(2026,7,20), 0, 5, 15, 10]
                ,[new Date(2026,7,21), 2, 8, 25, 20]
                ,[new Date(2026,7,22), 0, 0, 10, -5]
                ,[new Date(2026,7,23), 1, 10, 30, 28]
                ,[new Date(2026,7,24), 0, 2, 5, 0]
            ];
        </script>
        </body>
        </html>
        """

        scraper = HistoricalDelayScraper()
        res = scraper.parse_history_html("12004", sample_html, days=15)

        self.assertIsNotNone(res)
        self.assertEqual(res["train_number"], "12004")
        self.assertEqual(res["train_name"], "LJN SWARNA SHATABDI")
        self.assertEqual(res["station_sequence"], ["NDLS", "GZB", "CNB", "LJN"])
        self.assertEqual(len(res["daily_runs"]), 5)

        # Check first run (2026-08-20, month 7 in JS = August)
        run0 = res["daily_runs"][0]
        self.assertEqual(run0["journey_date"], "2026-08-20")
        self.assertEqual(run0["delays"]["NDLS"], 0)
        self.assertEqual(run0["delays"]["GZB"], 5)
        self.assertEqual(run0["delays"]["CNB"], 15)
        self.assertEqual(run0["delays"]["LJN"], 10)

        # Check early arrival on 2026-08-22 (-5 at LJN)
        run2 = res["daily_runs"][2]
        self.assertEqual(run2["delays"]["LJN"], -5)

    def test_filter_last_15_days(self):
        """Test strict window filtering to last N days (15 days)."""
        # Create mock 25 daily rows
        row_template = "        ,[new Date(2026,7,{day:02d}), 0, {delay}, 10]\n"
        rows = "".join(row_template.format(day=i, delay=i) for i in range(1, 26))

        html = f"""
        <title>Running History of TEST TRAIN (12345)</title>
        <script>
            et.rsStat = [];
            et.rsStat.primaryData = [];
            et.rsStat.tooltipData = [
                ['Date',{{'label':'STN_A'}},{{'label':'STN_B'}},{{'label':'STN_C'}}]
                {rows}
            ];
        </script>
        """

        scraper = HistoricalDelayScraper()
        res = scraper.parse_history_html("12345", html, days=15)

        self.assertIsNotNone(res)
        self.assertEqual(res["actual_days_retrieved"], 15)
        self.assertEqual(res["date_range"]["start"], "2026-08-11")
        self.assertEqual(res["date_range"]["end"], "2026-08-25")

    def test_sectional_analytics_and_matrices(self):
        """Test sectional delta calculations, absorption classification, and Markovian matrices."""
        station_sequence = ["NDLS", "CNB", "LJN"]
        daily_runs = [
            # Day 1: NDLS dep 0m -> CNB arr 20m (accumulated +20m) -> LJN arr 10m (absorbed -10m)
            {"journey_date": "2026-08-20", "day_of_week": 3, "delays": {"NDLS": 0, "CNB": 20, "LJN": 10}},
            # Day 2: NDLS dep 5m -> CNB arr 15m (accumulated +10m) -> LJN arr 5m (absorbed -10m)
            {"journey_date": "2026-08-21", "day_of_week": 4, "delays": {"NDLS": 5, "CNB": 15, "LJN": 5}},
            # Day 3: NDLS dep 0m -> CNB arr 2m (maintained +2m) -> LJN arr 0m (maintained -2m)
            {"journey_date": "2026-08-22", "day_of_week": 5, "delays": {"NDLS": 0, "CNB": 2, "LJN": 0}},
        ]

        engine = DelayMatrixEngine()
        sec_runs = engine.compute_sectional_runs("12004", station_sequence, daily_runs)

        self.assertEqual(len(sec_runs), 6)  # 2 sections * 3 days

        # NDLS -> CNB Day 1
        ndls_cnb_d1 = sec_runs[0]
        self.assertEqual(ndls_cnb_d1["from_station"], "NDLS")
        self.assertEqual(ndls_cnb_d1["to_station"], "CNB")
        self.assertEqual(ndls_cnb_d1["delay_delta"], 20)
        self.assertEqual(ndls_cnb_d1["status"], "ACCUMULATED_DELAY")

        # CNB -> LJN Day 1 (absorbed delay: 10 - 20 = -10)
        cnb_ljn_d1 = sec_runs[1]
        self.assertEqual(cnb_ljn_d1["from_station"], "CNB")
        self.assertEqual(cnb_ljn_d1["to_station"], "LJN")
        self.assertEqual(cnb_ljn_d1["delay_delta"], -10)
        self.assertEqual(cnb_ljn_d1["status"], "ABSORBED_DELAY")

        # Profiler checks
        profiler = SectionalProfiler()
        profiles = profiler.profile_all_sections(sec_runs, "12004")
        self.assertEqual(len(profiles), 2)

        # Profile 1: NDLS -> CNB (Mean delta = (20+10+2)/3 = 10.67m -> Bottleneck)
        p_ndls_cnb = profiles[0]
        self.assertEqual(p_ndls_cnb["from_station"], "NDLS")
        self.assertAlmostEqual(p_ndls_cnb["mean_delay_delta"], 10.67, places=1)
        self.assertIn("BOTTLENECK", p_ndls_cnb["corridor_type"])

        # Profile 2: CNB -> LJN (Mean delta = (-10 + -10 + -2)/3 = -7.33m -> Slack Buffer)
        p_cnb_ljn = profiles[1]
        self.assertEqual(p_cnb_ljn["from_station"], "CNB")
        self.assertAlmostEqual(p_cnb_ljn["mean_delay_delta"], -7.33, places=1)
        self.assertIn("SLACK_BUFFER", p_cnb_ljn["corridor_type"])
        self.assertAlmostEqual(p_cnb_ljn["absorption_rate_pct"], 100.0, places=1)

        # Markovian Matrix
        matrix = engine.build_transition_matrix(sec_runs)
        self.assertEqual(matrix["sample_runs"], 6)
        probs = matrix["transition_probabilities"]
        # Probabilities from ON_TIME
        self.assertGreaterEqual(probs["ON_TIME"]["MODERATE_DELAY"], 0)

    def test_database_persistence_and_exports(self):
        """Test SQLite storage, querying, and dataset exports in isolated environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db = Path(tmpdir) / "test_hist.db"
            export_dir = Path(tmpdir) / "exports"

            db = HistoricalDatabase(db_path=test_db)

            history = {
                "train_number": "12004",
                "train_name": "Shatabdi Express",
                "station_sequence": ["NDLS", "CNB"],
                "daily_runs": [
                    {
                        "journey_date": "2026-08-20",
                        "day_of_week": 3,
                        "is_weekend": 0,
                        "delays": {"NDLS": 0, "CNB": 15},
                    },
                    {
                        "journey_date": "2026-08-21",
                        "day_of_week": 4,
                        "is_weekend": 0,
                        "delays": {"NDLS": 2, "CNB": 8},
                    },
                ],
            }

            engine = DelayMatrixEngine()
            sec_runs = engine.compute_sectional_runs("12004", history["station_sequence"], history["daily_runs"])

            profiler = SectionalProfiler()
            sec_profiles = profiler.profile_all_sections(sec_runs, "12004")

            # Save
            db.save_train_history(history, sec_runs, sec_profiles)

            # Query
            corridor = db.get_corridor_profile("NDLS", "CNB", train_number="12004")
            self.assertEqual(len(corridor), 1)
            self.assertEqual(corridor[0]["sample_size_days"], 2)

            stats = db.get_summary_stats()
            self.assertEqual(stats["total_trains"], 1)
            self.assertEqual(stats["total_sectional_runs"], 2)

            # Export
            exporter = HistoricalExporter(db=db, export_dir=export_dir)
            files = exporter.export_all()

            for name, p in files.items():
                self.assertTrue(p.exists())
                self.assertGreater(p.stat().st_size, 0)

    def test_timetable_matcher_ideal_vs_real(self):
        """Test ideal scheduled vs real arrival/departure calculations and midnight rollover."""
        from analytics.timetable_matcher import TimetableMatcher, add_minutes_to_time_str

        # Standard calculation
        self.assertEqual(add_minutes_to_time_str("06:10:00", 15), "06:25:00")
        self.assertEqual(add_minutes_to_time_str("06:10:00", -5), "06:05:00")
        # Midnight rollover
        self.assertEqual(add_minutes_to_time_str("23:55:00", 10), "00:05:00")
        self.assertEqual(add_minutes_to_time_str("00:05:00", -10), "23:55:00")

        # Matcher enrichment test
        matcher = TimetableMatcher()
        enriched = matcher.enrich_station_delay("12004", "NDLS", 25)
        self.assertEqual(enriched["station_code"], "NDLS")
        self.assertIn("actual_arrival", enriched)
        self.assertIn("actual_departure", enriched)

    def test_checkpoint_manager_atomic(self):
        """Test atomic checkpoint state recording, filtering, and resuming."""
        from storage.checkpoint_manager import CheckpointManager

        with tempfile.TemporaryDirectory() as tmpdir:
            chk_file = Path(tmpdir) / "checkpoint.json"
            mgr = CheckpointManager(checkpoint_path=chk_file)

            all_trains = ["12004", "12301", "12302", "22436"]
            # Initial state
            pending = mgr.get_pending_trains(all_trains, phase="90d")
            self.assertEqual(len(pending), 4)

            # Record success
            mgr.record_success("12004", phase="90d", runs_count=88, stations_count=10)
            self.assertTrue(mgr.is_completed("12004", phase="90d"))
            self.assertFalse(mgr.is_completed("12301", phase="90d"))

            # Pending after 1 completion
            pending2 = mgr.get_pending_trains(all_trains, phase="90d")
            self.assertEqual(len(pending2), 3)
            self.assertNotIn("12004", pending2)

            # Record skip (e.g. 404)
            mgr.record_skip("12301", phase="90d", reason="NOT_FOUND")
            pending3 = mgr.get_pending_trains(all_trains, phase="90d")
            self.assertEqual(len(pending3), 2)
            self.assertNotIn("12301", pending3)

    def test_crawler_watchdog_timeout(self):
        """Test that watchdog enforces execution timeouts and prevents infinite hangs."""
        import time
        from scrapers.crawler_watchdog import CrawlerWatchdog

        watchdog = CrawlerWatchdog()

        # Fast function completes
        def quick_func():
            return "OK"

        res = watchdog.run_with_timeout(quick_func, timeout=1.0)
        self.assertEqual(res, "OK")

        # Slow function times out
        def slow_func():
            time.sleep(2.0)
            return "STUCK"

        with self.assertRaises(TimeoutError):
            watchdog.run_with_timeout(slow_func, timeout=0.2)

    def test_system_diagnostic(self):
        """Test server hardware capability inspection."""
        from system_check import run_system_diagnostic

        diag = run_system_diagnostic()
        self.assertIn("cpu_cores", diag)
        self.assertGreater(diag["cpu_cores"], 0)
        self.assertIn("hostname", diag)
        self.assertIn("recommended_delay", diag)


if __name__ == "__main__":
    unittest.main()

