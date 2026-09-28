"""
Comprehensive test suite for Indian Railways Station & Halt Scraper.
Validates production-grade schemas, NSG/SG/HG categories, platform counts,
virtual chord detection, SQLite indices, and live timetable scraping.
"""

import sys
import unittest
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.station_dataset_loader import StationDatasetLoader, _calc_halt_minutes
from scrapers.station_live_scraper import StationLiveScraper
from storage.db import StationDatabase
from storage.exporter import StationExporter


class TestStationHaltScraper(unittest.TestCase):
    """Test suite covering parser, scraper, database, and export operations."""

    def test_calc_halt_minutes(self):
        """Test halt minute calculations across different schedule timings."""
        # Standard daytime halt
        self.assertEqual(_calc_halt_minutes("03:45", "04:00"), 15)
        self.assertEqual(_calc_halt_minutes("14:10", "14:15"), 5)
        self.assertEqual(_calc_halt_minutes("06:00:00", "06:12:00"), 12)

        # Dot separator support
        self.assertEqual(_calc_halt_minutes("00.02", "00.07"), 5)
        self.assertEqual(_calc_halt_minutes("14.15", "14.30"), 15)

        # Midnight crossover
        self.assertEqual(_calc_halt_minutes("23:55", "00:10"), 15)
        self.assertEqual(_calc_halt_minutes("23:50:00", "00:05:00"), 15)

        # Origin or terminating stations (None/Source/Destinat)
        self.assertEqual(_calc_halt_minutes(None, "06:00"), 0)
        self.assertEqual(_calc_halt_minutes("None", "06:00"), 0)
        self.assertEqual(_calc_halt_minutes("Source", "06:00"), 0)
        self.assertEqual(_calc_halt_minutes("12:00", "Destinat"), 0)
        self.assertEqual(_calc_halt_minutes("12:00", None), 0)

    def test_station_geojson_parsing(self):
        """Test GeoJSON station feature parsing and production-grade classification."""
        sample_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [77.2227, 28.6429]},
                    "properties": {
                        "code": "NDLS",
                        "name": "New Delhi",
                        "state": "Delhi",
                        "zone": "NR",
                        "address": "Ajmeri Gate, New Delhi",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [80.3533, 26.4539]},
                    "properties": {
                        "code": "CNB",
                        "name": "Kanpur Central",
                        "state": "Uttar Pradesh",
                        "zone": "NCR",
                        "address": "Kanpur, Uttar Pradesh",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [88.3575, 22.5855]},
                    "properties": {
                        "code": "HWH",
                        "name": "Howrah Junction",
                        "state": "West Bengal",
                        "zone": "ER",
                        "address": "Howrah, West Bengal",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [75.4516, 27.2520]},
                    "properties": {
                        "code": "BDHL",
                        "name": "Badhal Halt",
                        "state": "Rajasthan",
                        "zone": "NWR",
                        "address": "Kishangarh Renwal, Rajasthan",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": None,  # Virtual chord with no coords
                    "properties": {
                        "code": "XX-BSPY",
                        "name": "Bilaspur Yard Cabin",
                        "state": None,
                        "zone": None,
                    },
                },
            ],
        }

        loader = StationDatasetLoader()
        stations = loader._parse_stations_geojson(sample_geojson)

        self.assertEqual(len(stations), 5)

        # Check NDLS (Major Terminal + NSG-1 + 16 Platforms)
        ndls = next(s for s in stations if s["code"] == "NDLS")
        self.assertEqual(ndls["state"], "Delhi")
        self.assertEqual(ndls["zone"], "NR")
        self.assertEqual(ndls["division"], "Delhi")
        self.assertEqual(ndls["is_terminal"], 1)
        self.assertEqual(ndls["ir_category"], "NSG-1")
        self.assertEqual(ndls["platform_count"], 16)
        self.assertEqual(ndls["amrit_bharat_station"], 1)
        self.assertEqual(ndls["passenger_service"], 1)

        # Check HWH (Junction + Terminal + NSG-1 + 23 Platforms)
        hwh = next(s for s in stations if s["code"] == "HWH")
        self.assertEqual(hwh["is_junction"], 1)
        self.assertEqual(hwh["is_terminal"], 1)
        self.assertEqual(hwh["platform_count"], 23)
        self.assertEqual(hwh["division"], "Howrah")

        # Check BDHL (Halt)
        bdhl = next(s for s in stations if s["code"] == "BDHL")
        self.assertEqual(bdhl["is_halt"], 1)
        self.assertEqual(bdhl["ir_category"], "HG-2 (Halt)")
        self.assertEqual(bdhl["platform_count"], 1)

        # Check XX-BSPY (Virtual operational chord)
        bspy = next(s for s in stations if s["code"] == "XX-BSPY")
        self.assertEqual(bspy["is_virtual_chord"], 1)
        self.assertEqual(bspy["passenger_service"], 0)
        self.assertEqual(bspy["operational_status"], "Interlocking / Block Post / Virtual Chord")

    def test_database_and_search(self):
        """Test SQLite database operations, indexing, and station search."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            test_db_path = Path(tmpdir) / "test_stations.db"
            db = StationDatabase(db_path=test_db_path)

            stations_data = [
                {
                    "code": "NDLS",
                    "official_name": "New Delhi",
                    "state": "Delhi",
                    "zone": "NR",
                    "division": "Delhi",
                    "latitude": 28.6429,
                    "longitude": 77.2227,
                    "is_junction": 0,
                    "is_terminal": 1,
                    "is_halt": 0,
                    "ir_category": "NSG-1",
                    "platform_count": 16,
                    "operational_status": "Active Passenger Station",
                    "passenger_service": 1,
                },
                {
                    "code": "CNB",
                    "official_name": "Kanpur Central",
                    "state": "Uttar Pradesh",
                    "zone": "NCR",
                    "division": "Prayagraj",
                    "latitude": 26.4539,
                    "longitude": 80.3533,
                    "is_junction": 1,
                    "is_terminal": 1,
                    "is_halt": 0,
                    "ir_category": "NSG-1",
                    "platform_count": 10,
                    "operational_status": "Active Passenger Station",
                    "passenger_service": 1,
                },
            ]

            db.upsert_stations(stations_data)
            self.assertIsNotNone(db.get_station("NDLS"))
            self.assertEqual(db.get_station("CNB")["official_name"], "Kanpur Central")
            self.assertEqual(db.get_station("CNB")["division"], "Prayagraj")

            # Search by division
            res = db.search_stations("Prayagraj")
            self.assertTrue(any(s["code"] == "CNB" for s in res))

            # Halts
            halts_data = [
                {
                    "station_code": "NDLS",
                    "train_number": "12043",
                    "train_name": "NDLS-MOGA SHATABDI EXP",
                    "arrival_time": "",
                    "departure_time": "07:05",
                    "halt_minutes": 0,
                    "day": 1,
                    "days_of_run": "M S",
                    "classes": "CC EC",
                    "source": "test",
                },
                {
                    "station_code": "CNB",
                    "train_number": "12301",
                    "train_name": "Howrah Rajdhani",
                    "arrival_time": "04:50",
                    "departure_time": "04:55",
                    "halt_minutes": 5,
                    "day": 2,
                    "days_of_run": "Daily",
                    "classes": "1A 2A 3A",
                    "source": "test",
                },
            ]
            db.upsert_halts(halts_data)

            # Query halts
            cnb_halts = db.get_station_halts("CNB")
            self.assertEqual(len(cnb_halts), 1)
            self.assertEqual(cnb_halts[0]["halt_minutes"], 5)

            # Verify stats
            stats = db.get_summary_stats()
            self.assertEqual(stats["total_stations"], 2)
            self.assertEqual(stats["passenger_stations"], 2)
            self.assertEqual(stats["total_train_halts"], 2)

    def test_live_scraper_table_parser(self):
        """Test station page HTML parser logic."""
        sample_html = """
        <!DOCTYPE html>
        <html>
        <body>
          <table>
            <tr class="heading">
              <th>TRAIN No</th>
              <th>TRAIN NAME</th>
              <th>CLASSES</th>
              <th>DAYS OF RUN</th>
              <th>ARRIVAL TIME</th>
              <th>DEPARTURE TIME</th>
            </tr>
            <tr>
              <td><a href="/train-schedule/12043">12043</a></td>
              <td>NDLS-MOGA SHATABDI EXP</td>
              <td>CC EC</td>
              <td>Daily</td>
              <td>--</td>
              <td>07:05</td>
            </tr>
            <tr>
              <td><a href="/train-schedule/12004">12004</a></td>
              <td>LUCKNOW SHATABDI</td>
              <td>CC EC</td>
              <td>Daily</td>
              <td>06:10</td>
              <td>06:25</td>
            </tr>
          </table>
        </body>
        </html>
        """

        scraper = StationLiveScraper()
        result = scraper._parse_with_regex("NDLS", sample_html)

        self.assertEqual(result["station_code"], "NDLS")
        self.assertEqual(result["total_trains"], 2)

        trains = result["trains"]
        t1 = next(t for t in trains if t["train_number"] == "12043")
        self.assertEqual(t1["departure_time"], "07:05")

        t2 = next(t for t in trains if t["train_number"] == "12004")
        self.assertEqual(t2["halt_minutes"], 15)

    def test_exporter_pipeline(self):
        """Test exporting SQLite records to CSV and JSON."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            test_db_path = Path(tmpdir) / "test_stations.db"
            export_dir = Path(tmpdir) / "exports"

            db = StationDatabase(db_path=test_db_path)
            db.upsert_stations([
                {
                    "code": "HWH",
                    "official_name": "Howrah Junction",
                    "state": "West Bengal",
                    "zone": "ER",
                    "division": "Howrah",
                    "latitude": 22.5855,
                    "longitude": 88.3575,
                    "is_junction": 1,
                    "is_terminal": 1,
                    "is_halt": 0,
                    "ir_category": "NSG-1",
                    "platform_count": 23,
                }
            ])

            exporter = StationExporter(db=db, export_dir=export_dir)
            files = exporter.export_all()

            for key, file_path in files.items():
                self.assertTrue(file_path.exists(), f"File {file_path} should exist")
                self.assertGreater(file_path.stat().st_size, 0, f"File {file_path} should not be empty")


if __name__ == "__main__":
    unittest.main()
