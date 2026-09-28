"""
Unit and regression tests for scraper-erail parsers, validator, normalizer, and database.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRAPER_ROOT = Path(__file__).resolve().parent.parent
if str(SCRAPER_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRAPER_ROOT))

import sqlite3
import pytest

from core.parser_erail import ErailParser
from core.parser_ntes import NtesParser
from pipeline.normalizer import DataNormalizer
from pipeline.validator import DataValidator
from storage.database import Database


def test_erail_train_list_delimited():
    sample = "12301~HOWRAH RAJDHANI~HWH~NDLS~1111101~RAJ^12002~BHOPAL SHATABDI~NDLS~RKMP~1111111~SHT^22436~VANDE BHARAT~NDLS~BSB~1010101~VB"
    trains = ErailParser.parse_train_list(sample)
    assert len(trains) == 3
    assert trains[0]["number"] == "12301"
    assert trains[0]["name"] == "HOWRAH RAJDHANI"
    assert trains[0]["from_code"] == "HWH"
    assert trains[0]["to_code"] == "NDLS"
    assert trains[2]["number"] == "22436"
    assert trains[2]["type"] == "VB"


def test_erail_station_list():
    sample = "NDLS~NEW DELHI~DELHI~NR^HWH~HOWRAH JN~WEST BENGAL~ER^CNB~KANPUR CENTRAL~UTTAR PRADESH~NCR"
    stations = ErailParser.parse_station_list(sample)
    assert len(stations) == 3
    assert stations[0]["code"] == "NDLS"
    assert stations[0]["zone"] == "NR"
    assert stations[1]["code"] == "HWH"
    assert stations[2]["name"] == "KANPUR CENTRAL"


def test_erail_route_delimited():
    sample = (
        "1~HWH~HOWRAH JN~00:00:00~16:50:00~0~0~1~9^"
        "2~ASN~ASANSOL JN~18:57:00~19:00:00~3m~200~1~5^"
        "3~NDLS~NEW DELHI~10:05:00~00:00:00~0~1449~2~16"
    )
    meta, stops = ErailParser.parse_train_route(sample, "12301")
    assert meta is not None
    assert meta["number"] == "12301"
    assert meta["from_code"] == "HWH"
    assert meta["to_code"] == "NDLS"
    assert len(stops) == 3
    assert stops[0]["station_code"] == "HWH"
    assert stops[0]["departure"] == "16:50:00"
    assert stops[1]["halt_mins"] == 3
    assert stops[1]["distance_km"] == 200.0
    assert stops[2]["station_code"] == "NDLS"
    assert stops[2]["arrival"] == "10:05:00"


def test_erail_coach_composition_lhb():
    sample = "LOCO^EOG^B1^B2^B3^B4^B5^B6^B7^B8^A1^A2^H1^PC^EOG"
    rake_type, coaches = ErailParser.parse_coach_composition(sample, "12301")
    assert rake_type == "LHB"
    assert len(coaches) == 15
    assert coaches[0]["coach_type"] == "Locomotive"
    assert coaches[2]["coach_code"] == "B1"
    assert coaches[2]["class_type"] == "3A"
    assert coaches[10]["class_type"] == "2A"
    assert coaches[12]["class_type"] == "1A"


def test_erail_coach_composition_vande_bharat():
    sample = "C1^C2^C3^C4^C5^C6^C7^E1^E2^C8^C9^C10"
    rake_type, coaches = ErailParser.parse_coach_composition(sample, "22436")
    assert rake_type == "TRAIN18"
    assert len(coaches) == 12
    assert coaches[7]["class_type"] == "EC"


def test_ntes_live_status_html():
    sample_html = """
    <html>
      <div class="status-banner">Train departed CNB at 01:25 (Delay 15 mins)</div>
      <table>
        <tr><th>Station</th><th>Sch Arr</th><th>Act Arr</th><th>Sch Dep</th><th>Act Dep</th><th>Delay</th><th>PF</th></tr>
        <tr><td>NEW DELHI (NDLS)</td><td>--</td><td>--</td><td>16:50</td><td>16:50</td><td>Right Time</td><td>16</td></tr>
        <tr><td>KANPUR CENTRAL (CNB)</td><td>21:35</td><td>21:40</td><td>21:40</td><td>21:45</td><td>5 mins late</td><td>4</td></tr>
        <tr><td>HOWRAH JN (HWH)</td><td>10:05</td><td>10:20</td><td>--</td><td>--</td><td>15 mins late</td><td>9</td></tr>
      </table>
    </html>
    """
    obs = NtesParser.parse_live_status(sample_html, "12301", "03-09-2026")
    assert len(obs) == 3
    assert obs[0]["station_code"] == "NDLS"
    assert obs[0]["platform"] == "16"
    assert obs[1]["station_code"] == "CNB"
    assert obs[1]["arrival_delay_mins"] == 5
    assert obs[2]["station_code"] == "HWH"
    assert obs[2]["arrival_delay_mins"] == 15


def test_derive_segments():
    stops = [
        {"station_code": "NDLS", "departure": "16:50:00", "distance_km": 0.0, "day": 1},
        {"station_code": "CNB", "arrival": "21:35:00", "distance_km": 440.0, "day": 1},
        {"station_code": "HWH", "arrival": "10:05:00", "distance_km": 1449.0, "day": 2},
    ]
    segments = DataNormalizer.derive_segments_from_stops(stops)
    assert len(segments) == 2
    assert segments[0]["from_code"] == "NDLS"
    assert segments[0]["to_code"] == "CNB"
    assert segments[0]["distance_km"] == 440.0
    # 16:50 to 21:35 = 4 hrs 45 mins = 285 mins
    assert segments[0]["sched_minutes_p50"] == 285.0
    assert segments[1]["from_code"] == "CNB"
    assert segments[1]["to_code"] == "HWH"
    assert segments[1]["distance_km"] == 1009.0


def test_database_in_memory_upserts():
    db = Database(db_path=":memory:")
    # Stations
    stations = [{"code": "NDLS", "name": "NEW DELHI", "state": "DELHI", "zone": "NR", "address": None, "lat": 28.61, "lon": 77.20, "updated_at": "2026-09-03"}]
    db.upsert_stations(stations)

    # Trains
    trains = [{"number": "12301", "name": "HWH RAJDHANI", "type": "Rajdhani", "from_code": "HWH", "from_name": "HOWRAH", "to_code": "NDLS", "to_name": "NEW DELHI", "departure": "16:50:00", "arrival": "10:05:00", "duration_min": 1035, "distance_km": 1449.0, "zone": "ER", "classes": "1A,2A,3A", "running_days": "1111101", "rake_type": "LHB", "total_coaches": 18, "pantry_status": "Yes", "return_train": "12302", "source": "erail", "updated_at": "2026-09-03"}]
    db.upsert_trains(trains)

    with db.get_connection() as conn:
        stn = conn.execute("SELECT * FROM stations WHERE code = 'NDLS';").fetchone()
        assert stn["name"] == "NEW DELHI"
        trn = conn.execute("SELECT * FROM trains WHERE number = '12301';").fetchone()
        assert trn["rake_type"] == "LHB"
        assert trn["from_code"] == "HWH"


def test_dataset_builder(tmp_path):
    from pipeline.dataset_builder import DatasetBuilder, IR_TRAIN_COLUMNS

    db = Database(db_path=":memory:")
    # Seed stations, trains, stops, delays
    db.upsert_stations([
        {"code": "HWH", "name": "HOWRAH JN", "state": "WB", "zone": "ER", "address": None, "lat": 22.58, "lon": 88.34, "updated_at": "2026-09-03"},
        {"code": "NDLS", "name": "NEW DELHI", "state": "DL", "zone": "NR", "address": None, "lat": 28.61, "lon": 77.20, "updated_at": "2026-09-03"},
    ])
    db.upsert_trains([{
        "number": "12301",
        "name": "HWH RAJDHANI",
        "type": "Rajdhani",
        "from_code": "HWH",
        "from_name": "HOWRAH",
        "to_code": "NDLS",
        "to_name": "NEW DELHI",
        "departure": "16:50:00",
        "arrival": "10:05:00",
        "duration_min": 1035,
        "distance_km": 1449.0,
        "zone": "ER",
        "classes": "1A,2A,3A",
        "running_days": "1111101",
        "rake_type": "LHB",
        "total_coaches": 18,
        "pantry_status": "Yes",
        "return_train": "12302",
        "source": "erail",
        "updated_at": "2026-09-03",
    }])
    db.upsert_schedule_stops([
        {"train_number": "12301", "seq": 1, "station_code": "HWH", "station_name": "HOWRAH JN", "day": 1, "arrival": None, "departure": "16:50:00", "halt_mins": 0, "distance_km": 0.0, "platform": "9", "speed_kmph": None, "is_commercial_halt": 1, "source": "erail", "updated_at": "2026-09-03"},
        {"train_number": "12301", "seq": 2, "station_code": "NDLS", "station_name": "NEW DELHI", "day": 2, "arrival": "10:05:00", "departure": None, "halt_mins": 0, "distance_km": 1449.0, "platform": "16", "speed_kmph": None, "is_commercial_halt": 1, "source": "erail", "updated_at": "2026-09-03"},
    ])
    db.upsert_historical_delays([
        {"train_number": "12301", "station_code": "HWH", "avg_delay_mins": 2.0, "pct_on_time": 95.0, "pct_slight_delay": 5.0, "pct_moderate_delay": 0.0, "pct_severe_delay": 0.0, "sample_days": 365, "source": "erail", "scraped_at": "2026-09-03"},
        {"train_number": "12301", "station_code": "NDLS", "avg_delay_mins": 14.0, "pct_on_time": 82.0, "pct_slight_delay": 15.0, "pct_moderate_delay": 3.0, "pct_severe_delay": 0.0, "sample_days": 365, "source": "erail", "scraped_at": "2026-09-03"},
    ])

    builder = DatasetBuilder(db=db, output_dir=tmp_path)
    # Test journey dataset
    journey_csv = tmp_path / "test_ir_train.csv"
    count = builder.build_journey_dataset(output_file=journey_csv, days_history=5)
    assert count == 5  # 1 train x 5 days
    assert journey_csv.exists()

    import csv
    with open(journey_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == IR_TRAIN_COLUMNS
        row = next(reader)
        assert row["train_number"] == "12301"
        assert row["has_lhb_coaches"] == "1"
        assert row["zone_abbr"] in ("ER", "NR")
        assert float(row["distance_km"]) == 1449.0

    # Test point delays dataset
    point_csv = tmp_path / "test_point_delays.csv"
    p_count = builder.build_point_delays_dataset(output_file=point_csv)
    assert p_count == 2
    assert point_csv.exists()
