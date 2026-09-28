"""
Network Anomalies Exporter
Exports disruption tables to CSV and JSON formats for the ETA Prediction Engine feature store.
"""

import csv
import json
import sqlite3
from pathlib import Path
from typing import Optional

from config import DEFAULT_DB_PATH, EXPORTS_DIR


class AnomalyExporter:
    """
    Exports anomaly incident tables to CSV and JSON.
    """

    def __init__(self, db_path: Optional[Path] = None, output_dir: Optional[Path] = None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self.output_dir = output_dir or EXPORTS_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_csv(self, filename: str = "anomalies.csv") -> Path:
        out_path = self.output_dir / filename
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute("""
            SELECT 
                incident_id, timestamp, train_number, section_id,
                category, detention_minutes, speed_restriction_kmh,
                severity, is_active, description
            FROM network_incidents
            ORDER BY detention_minutes DESC;
        """)
        rows = cur.fetchall()
        headers = [d[0] for d in cur.description]
        conn.close()

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

        return out_path

    def export_json(self, filename: str = "anomalies.json") -> Path:
        out_path = self.output_dir / filename
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT * FROM network_incidents ORDER BY detention_minutes DESC;")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2)

        return out_path
