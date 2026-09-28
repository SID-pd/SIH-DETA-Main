"""
Unit and integration tests for Indian Railways scraper modules.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.confirmtkt_scraper import ConfirmTktScraper
from scrapers.etrain_scraper import ETrainScraper
from storage.db import Database
from storage.exporter import export_to_csv, export_to_json


def test_confirmtkt_search():
    print("Testing ConfirmTkt search API...")
    scraper = ConfirmTktScraper()
    results = scraper.search_trains("1204")
    assert isinstance(results, list), "Expected list output"
    assert len(results) > 0, "Expected at least 1 train for query '1204'"
    print(f"  ✓ Search successful: Found {len(results)} trains for '1204'")
    for t in results[:3]:
        print(f"    - {t['number']}: {t['name']}")


def test_etrain_suggest():
    print("\nTesting eTrain suggest API...")
    scraper = ETrainScraper()
    results = scraper.search_trains("120")
    assert isinstance(results, list), "Expected list output"
    assert len(results) > 0, "Expected at least 1 train for query '120'"
    print(f"  ✓ eTrain suggest successful: Found {len(results)} trains for '120'")
    for t in results[:3]:
        print(f"    - {t['number']}: {t['name']}")


def test_confirmtkt_schedule():
    print("\nTesting ConfirmTkt schedule parser for train 12043...")
    scraper = ConfirmTktScraper()
    sched = scraper.scrape_schedule("12043")
    assert sched is not None, "Failed to scrape schedule for 12043"
    assert sched["number"] == "12043", "Train number mismatch"
    assert len(sched["stops"]) > 0, "Expected stops in timetable"
    print(f"  ✓ Schedule parsed successfully:")
    print(f"    - Name: {sched.get('name')}")
    print(f"    - Route: {sched.get('route')}")
    print(f"    - Type: {sched.get('type')}")
    print(f"    - Days: {sched.get('service_days')}")
    print(f"    - Total Stops: {len(sched.get('stops'))}")
    first_stop = sched["stops"][0]
    last_stop = sched["stops"][-1]
    print(f"    - First Stop: {first_stop['station_name']} ({first_stop['station_code']}) @ {first_stop['departure']}")
    print(f"    - Last Stop:  {last_stop['station_name']} ({last_stop['station_code']}) @ {last_stop['arrival']}")


def test_database_and_exports(tmp_path: Path):
    print("\nTesting SQLite database and export pipelines...")
    db_file = tmp_path / "test_trains.db"
    db = Database(db_path=db_file)

    sample_trains = [
        {"number": "12043", "name": "NDLS-MOGA SHATABDI EXP", "type": "SHATABDI", "route": "New Delhi → Moga"},
        {"number": "12044", "name": "MOGA-NDLS SHATABDI EXP", "type": "SHATABDI", "route": "Moga → New Delhi"},
        {"number": "22436", "name": "VANDE BHARAT EXP", "type": "VANDE BHARAT", "route": "New Delhi → Varanasi"},
    ]

    saved = db.upsert_trains(sample_trains)
    assert saved == 3, "Failed to save 3 trains"
    assert db.count_trains() == 3, "Train count mismatch"

    search_res = db.search_trains("Vande")
    assert len(search_res) == 1, "Expected 1 search match for 'Vande'"
    assert search_res[0]["number"] == "22436"
    print("  ✓ SQLite upsert and search verified")

    json_file = tmp_path / "test_export.json"
    csv_file = tmp_path / "test_export.csv"

    export_to_json(sample_trains, json_file)
    assert json_file.exists() and json_file.stat().st_size > 0
    print("  ✓ JSON export verified")

    export_to_csv(sample_trains, csv_file)
    assert csv_file.exists() and csv_file.stat().st_size > 0
    print("  ✓ CSV export verified")


def run_all_tests():
    print("=" * 60)
    print("RUNNING INDIAN RAILWAYS SCRAPER TESTS")
    print("=" * 60)
    test_confirmtkt_search()
    test_etrain_suggest()
    test_confirmtkt_schedule()

    tmp_dir = Path(__file__).resolve().parent / "tmp_test"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        test_database_and_exports(tmp_dir)
    finally:
        # Cleanup temp test files
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY! ✓")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
