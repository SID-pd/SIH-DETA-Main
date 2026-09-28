"""
Comprehensive test suite for Indian Railways Live Journey & Telemetry Tracker.
Validates telemetry parsing, intermediate cabin extraction, sectional speed & drift math,
SQLite persistence, and export pipelines.
"""

import sys
import unittest
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from storage.telemetry_db import TelemetryDatabase
from storage.telemetry_exporter import TelemetryExporter
from trackers.live_journey_scraper import LiveJourneyScraper, _parse_delay_mins
from trackers.telemetry_analyzer import TelemetryAnalyzer


class TestLiveJourneyTracker(unittest.TestCase):
    """Test suite covering parser, kinematics analyzer, database, and exports."""

    def test_parse_delay_mins(self):
        """Test delay string extraction across formats."""
        self.assertEqual(_parse_delay_mins("07 Min"), 7)
        self.assertEqual(_parse_delay_mins("15 min"), 15)
        self.assertEqual(_parse_delay_mins("-"), 0)
        self.assertEqual(_parse_delay_mins("--"), 0)
        self.assertEqual(_parse_delay_mins("RT"), 0)
        self.assertEqual(_parse_delay_mins("05 Min Early"), -5)
        self.assertEqual(_parse_delay_mins(12), 12)

    def test_telemetry_html_parser(self):
        """Test extraction of JavaScript JSON payload, platforms, and cabins from HTML."""
        sample_html = """
        <!DOCTYPE html>
        <html>
        <body>
        <script>
          var trainNum = "12004";
          var trainName = "Shatabdi Express";
          var currentStnCode = "CNB";
          var currentStnName = "Kanpur Central";
          var latestDelay = 8;
          var data = {
            "TrainName": "Shatabdi Express",
            "TrainNo": 12004,
            "TrainType": "SHATABDI",
            "SourceCode": "NDLS",
            "Source": "New Delhi",
            "DestinationCode": "LJN",
            "Destination": "Lucknow Ne",
            "TotalDuration": "6:50",
            "Schedule": [
              {
                "StationCode": "NDLS",
                "StationName": "New Delhi",
                "StopNumber": 1,
                "ArrivalTime": "",
                "DepartureTime": "06:10",
                "Distance": "0.0",
                "ExpectedPlatformNo": "9",
                "arrivalDelay": "-",
                "departureDelay": "-",
                "Latitude": 28.642,
                "Longitude": 77.2202,
                "intermediateStations": [
                  {
                    "StationCode": "CSB",
                    "StationName": "Shivaji Bridge",
                    "ArrivalTime": "06:11",
                    "DepartureTime": "06:11",
                    "Distance": "1.0",
                    "Latitude": 28.6335,
                    "Longitude": 77.2262,
                    "stopNumberDisplay": "1"
                  },
                  {
                    "StationCode": "TKJ",
                    "StationName": "Tilak Bridge",
                    "ArrivalTime": "06:13",
                    "DepartureTime": "06:13",
                    "Distance": "2.0",
                    "Latitude": 28.6282,
                    "Longitude": 77.2371,
                    "stopNumberDisplay": "2"
                  }
                ]
              },
              {
                "StationCode": "CNB",
                "StationName": "Kanpur Central",
                "StopNumber": 2,
                "ArrivalTime": "11:23",
                "DepartureTime": "11:28",
                "Distance": "439.0",
                "ExpectedPlatformNo": "9",
                "arrivalDelay": "05 Min",
                "departureDelay": "08 Min",
                "Latitude": 26.4545,
                "Longitude": 80.3515,
                "intermediateStations": [
                  {
                    "StationCode": "CNJO",
                    "StationName": "Juhi Outer Cabin",
                    "ArrivalTime": "11:21",
                    "DepartureTime": "11:21",
                    "Distance": "436.0",
                    "Latitude": 26.4523,
                    "Longitude": 80.3312,
                    "stopNumberDisplay": "1"
                  }
                ]
              },
              {
                "StationCode": "LJN",
                "StationName": "Lucknow Ne",
                "StopNumber": 3,
                "ArrivalTime": "13:00",
                "DepartureTime": "",
                "Distance": "512.0",
                "ExpectedPlatformNo": "5",
                "arrivalDelay": "02 Min",
                "departureDelay": "-",
                "Latitude": 26.832,
                "Longitude": 80.921,
                "intermediateStations": []
              }
            ]
          };
        </script>
        </body>
        </html>
        """

        scraper = LiveJourneyScraper()
        result = scraper._parse_telemetry_html("12004", sample_html)

        self.assertIsNotNone(result)
        self.assertEqual(result["train_number"], "12004")
        self.assertEqual(result["train_name"], "Shatabdi Express")
        self.assertEqual(result["current_station_code"], "CNB")
        self.assertEqual(result["current_station_name"], "Kanpur Central")
        self.assertEqual(result["latest_delay_minutes"], 8)
        self.assertEqual(result["total_stops"], 3)
        self.assertEqual(result["total_intermediate_cabins"], 3)

        # Check NDLS
        ndls = result["schedule"][0]
        self.assertEqual(ndls["expected_platform"], "9")
        self.assertEqual(len(ndls["intermediate_stations"]), 2)

        # Check CNB
        cnb = result["schedule"][1]
        self.assertEqual(cnb["arrival_delay_mins"], 5)
        self.assertEqual(cnb["departure_delay_mins"], 8)
        self.assertTrue(cnb["is_current"])
        self.assertEqual(cnb["intermediate_stations"][0]["station_name"], "Juhi Outer Cabin")

    def test_telemetry_analyzer(self):
        """Test progress percentage, delay drift rate, and outer bottleneck detector."""
        mock_telemetry = {
            "train_number": "12004",
            "train_name": "Shatabdi Express",
            "train_type": "SHATABDI",
            "current_station_code": "CNB",
            "latest_delay_minutes": 8,
            "destination_code": "LJN",
            "destination_name": "Lucknow Ne",
            "timestamp": "2026-09-08T15:00:00Z",
            "schedule": [
                {
                    "station_code": "NDLS",
                    "station_name": "New Delhi",
                    "departure_delay_mins": 0,
                    "distance_km": 0.0,
                    "is_current": False,
                },
                {
                    "station_code": "CNB",
                    "station_name": "Kanpur Central",
                    "arrival_delay_mins": 5,
                    "departure_delay_mins": 25,  # Surge of 20m delay at CNB
                    "distance_km": 439.0,
                    "expected_platform": "9",
                    "is_current": True,
                },
                {
                    "station_code": "LJN",
                    "station_name": "Lucknow Ne",
                    "arrival_delay_mins": 20,
                    "departure_delay_mins": 0,
                    "distance_km": 512.0,
                    "scheduled_arrival": "13:00",
                    "expected_platform": "5",
                    "is_current": False,
                },
            ],
        }

        analyzer = TelemetryAnalyzer()
        analysis = analyzer.analyze_snapshot(mock_telemetry)

        # Check progress
        self.assertAlmostEqual(analysis["journey_progress_pct"], 85.7, places=1)
        self.assertEqual(analysis["instantaneous_delay_mins"], 8)

        # Next stop checks
        self.assertEqual(analysis["next_station"]["code"], "LJN")
        self.assertAlmostEqual(analysis["next_station"]["distance_km"], 73.0, places=1)

        # Delay drift trend
        self.assertIn("ACCUMULATING_DELAY", analysis["delay_trend"])
        self.assertGreater(analysis["delay_drift_rate_per_100km"], 0)

        # Outer signal bottleneck check (delay surge of 20m at CNB)
        self.assertTrue(analysis["outer_signal_bottlenecks_detected"])
        self.assertEqual(len(analysis["bottleneck_events"]), 1)
        self.assertEqual(analysis["bottleneck_events"][0]["station_code"], "CNB")
        self.assertEqual(analysis["bottleneck_events"][0]["delay_surge_mins"], 20)

    def test_database_and_export(self):
        """Test SQLite telemetry persistence and CSV/JSON export."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            test_db = Path(tmpdir) / "test_telemetry.db"
            export_dir = Path(tmpdir) / "exports"

            db = TelemetryDatabase(db_path=test_db)

            raw = {
                "train_number": "12301",
                "train_name": "Howrah Rajdhani",
                "train_type": "RAJDHANI",
                "schedule": [
                    {
                        "station_code": "HWH",
                        "station_name": "Howrah Jn",
                        "stop_number": 1,
                        "scheduled_arrival": "",
                        "scheduled_departure": "16:55",
                        "arrival_delay_mins": 0,
                        "departure_delay_mins": 0,
                        "expected_platform": "9",
                        "distance_km": 0.0,
                        "latitude": 22.585,
                        "longitude": 88.357,
                    },
                    {
                        "station_code": "CNB",
                        "station_name": "Kanpur Central",
                        "stop_number": 2,
                        "scheduled_arrival": "04:50",
                        "scheduled_departure": "04:55",
                        "arrival_delay_mins": 5,
                        "departure_delay_mins": 5,
                        "expected_platform": "1",
                        "distance_km": 1000.0,
                        "latitude": 26.454,
                        "longitude": 80.351,
                    },
                ],
                "intermediate_cabins": [
                    {
                        "station_code": "LLH",
                        "station_name": "Liluah Cabin",
                        "parent_station": "HWH",
                        "distance_km": 5.0,
                        "latitude": 22.61,
                        "longitude": 88.34,
                    }
                ],
            }

            analysis = {
                "current_station": {"code": "HWH", "name": "Howrah Jn", "distance_from_origin_km": 0.0},
                "next_station": {"code": "CNB", "name": "Kanpur Central"},
                "instantaneous_delay_mins": 0,
                "total_journey_distance_km": 1450.0,
                "journey_progress_pct": 0.0,
                "delay_trend": "MAINTAINING_PACE",
                "delay_drift_rate_per_100km": 0.0,
            }

            # Save snapshot
            snap_id = db.save_telemetry(raw, analysis)
            self.assertGreater(snap_id, 0)

            # Retrieve
            snap = db.get_latest_snapshot("12301")
            self.assertIsNotNone(snap)
            self.assertEqual(snap["current_station_code"], "HWH")

            # Stops
            stops = db.get_stops_telemetry("12301")
            self.assertEqual(len(stops), 2)

            # Cabins
            cabins = db.get_intermediate_cabins("12301")
            self.assertEqual(len(cabins), 1)
            self.assertEqual(cabins[0]["station_code"], "LLH")

            # Stats
            stats = db.get_summary_stats()
            self.assertEqual(stats["total_monitored_trains"], 1)

            # Export
            exporter = TelemetryExporter(db=db, export_dir=export_dir)
            files = exporter.export_all()

            for name, path in files.items():
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
