"""
Unit Tests for Network Anomalies & Stochastic Disruptions Module
"""

import sys
import unittest
from pathlib import Path

# Add module root to sys.path
MODULE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MODULE_DIR))

from analytics.historical_anomaly_miner import HistoricalAnomalyMiner
from models.anomaly_simulator import IncidentSimulator
from models.incident_types import NetworkIncident, calculate_severity
from models.outer_queue_model import OuterSignalQueueModel
from storage.anomaly_db import AnomalyDatabase
from storage.anomaly_exporter import AnomalyExporter


class TestOuterSignalQueueModel(unittest.TestCase):
    """Verifies queuing delays at bottleneck junction throats."""

    def test_major_junction_peak_wait(self):
        # CNB at 08:00 AM (morning peak) for Mail/Exp (Priority 3)
        wait_min, status = OuterSignalQueueModel.estimate_outer_delay("CNB", arrival_hour=8, priority_tier=3)
        self.assertGreater(wait_min, 15.0)
        self.assertIn(status, ["SEVERE_PLATFORM_STARVATION", "MODERATE_OUTER_QUEUING"])

    def test_dispatching_precedence(self):
        # Vande Bharat (P1) vs Mail/Exp (P3) at PRYJ
        p1_wait, _ = OuterSignalQueueModel.estimate_outer_delay("PRYJ", arrival_hour=8, priority_tier=1)
        p3_wait, _ = OuterSignalQueueModel.estimate_outer_delay("PRYJ", arrival_hour=8, priority_tier=3)
        self.assertLess(p1_wait, p3_wait)

    def test_minor_station_zero_wait(self):
        # Non-bottleneck station
        wait_min, status = OuterSignalQueueModel.estimate_outer_delay("UNKNOWN_STN", arrival_hour=8)
        self.assertEqual(wait_min, 0.0)
        self.assertEqual(status, "NOMINAL_CLEAR")


class TestIncidentSimulator(unittest.TestCase):
    """Verifies calibrated incident sampling."""

    def test_acp_detention_distribution(self):
        # 50 samples of ACP should fall between 8 and 45 mins
        for _ in range(50):
            detention = IncidentSimulator.sample_detention("ALARM_CHAIN_PULLING")
            self.assertGreaterEqual(detention, 8.0)
            self.assertLessEqual(detention, 45.0)

    def test_cro_generation(self):
        inc = IncidentSimulator.generate_incident("CATTLE_RUN_OVER", "GZB-ALJN", train_number="12301")
        self.assertEqual(inc.category, "CATTLE_RUN_OVER")
        self.assertEqual(inc.section_id, "GZB-ALJN")
        self.assertEqual(inc.train_number, "12301")
        self.assertTrue(inc.is_active)

    def test_severity_classification(self):
        self.assertEqual(calculate_severity(10.0), "LOW")
        self.assertEqual(calculate_severity(20.0), "MEDIUM")
        self.assertEqual(calculate_severity(45.0), "HIGH")
        self.assertEqual(calculate_severity(75.0), "CRITICAL")


class TestPersistenceAndMining(unittest.TestCase):
    """Verifies SQLite storage, export, and miner availability."""

    def test_database_and_exporter(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "test_anomalies.db"
            db = AnomalyDatabase(db_path=tmp_db)

            inc = IncidentSimulator.generate_incident("SIGNAL_FAILURE_AUTO", "CNB-PRYJ", "12302")
            db.save_incident(inc)
            self.assertEqual(db.get_total_incidents_count(), 1)

            retrieved = db.get_active_incidents(section_id="CNB-PRYJ")
            self.assertEqual(len(retrieved), 1)
            self.assertEqual(retrieved[0]["train_number"], "12302")

            exporter = AnomalyExporter(db_path=tmp_db, output_dir=Path(tmpdir))
            csv_path = exporter.export_csv("test_anomalies.csv")
            self.assertTrue(csv_path.exists())
            self.assertGreater(csv_path.stat().st_size, 30)

    def test_miner_interface(self):
        miner = HistoricalAnomalyMiner()
        # Even if DB is absent in unit test, it should gracefully return empty list without crashing
        anomalies = miner.mine_sectional_anomalies(limit=5)
        self.assertIsInstance(anomalies, list)


if __name__ == "__main__":
    unittest.main()
