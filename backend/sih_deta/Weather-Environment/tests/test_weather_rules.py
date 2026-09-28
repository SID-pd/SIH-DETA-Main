"""
Unit & Integration Tests for Weather & Environmental Constraints Module
Verifies Indian Railways G&SR compliance, spatial clustering, and database persistence.
"""

import sys
import unittest
from datetime import datetime
from pathlib import Path

# Add module root to sys.path
MODULE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MODULE_DIR))

from collectors.mock_weather_data import MockWeatherGenerator
from collectors.station_geo_resolver import StationGeoResolver
from rules.gsr_rules_engine import GSRRulesEngine
from storage.weather_db import WeatherDatabase
from storage.weather_exporter import WeatherExporter


class TestGSRRulesEngine(unittest.TestCase):
    """Verifies statutory operational constraints under G&SR rules."""

    def test_clear_visibility(self):
        is_foggy, cap = GSRRulesEngine.evaluate_fog_constraint(12000.0)
        self.assertFalse(is_foggy)
        self.assertIsNone(cap)

    def test_standard_fog_without_fog_pass(self):
        # 450m visibility with regular loco -> 60 km/h cap
        is_foggy, cap = GSRRulesEngine.evaluate_fog_constraint(450.0, has_fog_pass=False)
        self.assertTrue(is_foggy)
        self.assertEqual(cap, 60)

    def test_fog_with_gps_fog_pass_unit(self):
        # 450m visibility with GPS FOG-PASS unit -> 75 km/h cap
        is_foggy, cap = GSRRulesEngine.evaluate_fog_constraint(450.0, has_fog_pass=True)
        self.assertTrue(is_foggy)
        self.assertEqual(cap, 75)

    def test_severe_zero_visibility_fog(self):
        # 80m visibility (< 100m) -> 30 km/h emergency caution
        is_foggy, cap = GSRRulesEngine.evaluate_fog_constraint(80.0, has_fog_pass=True)
        self.assertTrue(is_foggy)
        self.assertEqual(cap, 30)

    def test_fog_exact_boundary_conditions(self):
        # Exactly 600m is clear; 599.9m triggers fog
        clear_fog, _ = GSRRulesEngine.evaluate_fog_constraint(600.0)
        self.assertFalse(clear_fog)

        fog_active, _ = GSRRulesEngine.evaluate_fog_constraint(599.9)
        self.assertTrue(fog_active)

    def test_konkan_monsoon_timetable_active(self):
        # Station MAO on July 15 (inside June 10 - Oct 31 window)
        dt = datetime(2026, 7, 15, 14, 0, 0)
        active, cap = GSRRulesEngine.evaluate_monsoon_constraint("MAO", dt, precipitation_mm=5.0)
        self.assertTrue(active)
        self.assertEqual(cap, 75)

    def test_konkan_monsoon_timetable_winter(self):
        # Station MAO on January 10 (outside monsoon window)
        dt = datetime(2026, 1, 10, 14, 0, 0)
        active, cap = GSRRulesEngine.evaluate_monsoon_constraint("MAO", dt, precipitation_mm=0.0)
        self.assertFalse(active)
        self.assertIsNone(cap)

    def test_extreme_downpour_water_above_rail_flange(self):
        # Rainfall >= 50 mm/hr anywhere enforces 10 km/h flange limit
        dt = datetime(2026, 8, 5, 16, 0, 0)
        active, cap = GSRRulesEngine.evaluate_monsoon_constraint("NDLS", dt, precipitation_mm=65.0)
        self.assertTrue(active)
        self.assertEqual(cap, 10)

    def test_thermal_buckling_caution(self):
        # Ambient 45°C + 800 W/m² direct solar radiation -> T_rail > 60°C
        rail_temp, warning, cap = GSRRulesEngine.evaluate_thermal_buckling(45.0, direct_solar_radiation_w_m2=800.0)
        self.assertGreaterEqual(rail_temp, 60.0)
        self.assertTrue(warning)
        self.assertEqual(cap, 40)

    def test_thermal_nominal(self):
        # Ambient 28°C + 200 W/m² solar -> T_rail ~ 32.4°C (Safe)
        rail_temp, warning, cap = GSRRulesEngine.evaluate_thermal_buckling(28.0, direct_solar_radiation_w_m2=200.0)
        self.assertLess(rail_temp, 60.0)
        self.assertFalse(warning)
        self.assertIsNone(cap)

    def test_effective_mps_minimization(self):
        # When multiple weather throttles exist, the most restrictive wins
        obs = {
            "timestamp": "2026-07-20T14:00:00+05:30",
            "visibility_meters": 400.0,      # Fog cap: 75
            "precipitation_mm": 55.0,        # Flange water cap: 10
            "ambient_temp_c": 30.0,
            "direct_solar_radiation_w_m2": 100.0,
        }
        res = GSRRulesEngine.evaluate_weather_observation("MAO", obs, nominal_mps=130, has_fog_pass=True)
        self.assertEqual(res["effective_mps_cap"], 10)
        self.assertEqual(res["throttle_reason"], "MONSOON_OR_FLANGE_WATER")


class TestSpatialClusteringAndStorage(unittest.TestCase):
    """Verifies spatial clustering resolver, database upserts, and exporter."""

    def test_spatial_clustering(self):
        resolver = StationGeoResolver()
        self.assertGreater(resolver.get_total_stations_count(), 10)
        clusters = resolver.get_all_clusters()
        self.assertGreater(len(clusters), 0)

        # NDLS should map to a valid cluster
        ndls = resolver.get_station("NDLS")
        self.assertIsNotNone(ndls)
        cl = resolver.get_cluster_for_station("NDLS")
        self.assertIsNotNone(cl)
        self.assertIn("NDLS", cl["stations"])

    def test_mock_weather_generation(self):
        mock_winter = MockWeatherGenerator.generate(28.64, 77.22, datetime(2026, 1, 15, 6, 0))
        self.assertLess(mock_winter["visibility_meters"], 600.0)
        self.assertIn("data_source", mock_winter)

    def test_storage_and_export(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "test_weather.db"
            db = WeatherDatabase(db_path=tmp_db)

            sample_obs = {
                "station_code": "TEST1",
                "observation_time": "2026-09-24T06:00:00+05:30",
                "latitude": 28.6415,
                "longitude": 77.2207,
                "visibility_meters": 450.0,
                "is_foggy": 1,
                "fog_speed_cap": 75,
                "precipitation_mm": 0.0,
                "monsoon_active": 0,
                "monsoon_speed_cap": None,
                "ambient_temp_c": 18.0,
                "estimated_rail_temp_c": 20.0,
                "heat_buckling_warning": 0,
                "nominal_mps": 130,
                "effective_mps_cap": 75,
                "throttle_reason": "FOG_VISIBILITY_RESTRICTION",
                "data_source": "TEST_UNIT",
            }
            db.save_observation(sample_obs)
            self.assertEqual(db.get_total_observations_count(), 1)

            retrieved = db.get_latest_observation("TEST1")
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved["effective_mps_cap"], 75)

            exporter = WeatherExporter(db_path=tmp_db, output_dir=Path(tmpdir))
            csv_path = exporter.export_csv("test_export.csv")
            self.assertTrue(csv_path.exists())
            self.assertGreater(csv_path.stat().st_size, 50)


if __name__ == "__main__":
    unittest.main()
