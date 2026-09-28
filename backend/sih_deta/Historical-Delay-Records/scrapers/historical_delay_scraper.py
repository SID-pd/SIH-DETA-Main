"""
Historical Delay Scraper: Extracts multi-horizon (90-day & 1-year) operational delay histories,
station sequence topology, and partitions runs into 15-day rolling/tumbling analysis windows.
"""

import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional

from config import (
    DEFAULT_HISTORY_DAYS,
    ETRAIN_HORIZON_URL,
    HORIZON_1Y,
    HORIZON_90D,
    SUB_WINDOW_DAYS,
)
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger("historical_scraper")


class HistoricalDelayScraper(BaseScraper):
    """Scrapes multi-horizon train running histories with 15-day sub-window partitioning."""

    def fetch_train_history(
        self,
        train_number: str,
        horizon: str = HORIZON_90D,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch historical delay records for a train over the specified horizon.
        
        Args:
            train_number: 5-digit train number (e.g. '12004', '12301')
            horizon: '3m' (90 days) or '1y' (365 days)
        """
        train_clean = str(train_number).strip()
        if len(train_clean) == 4 and train_clean.isdigit():
            train_clean = "0" + train_clean

        url = ETRAIN_HORIZON_URL.format(train_no=train_clean, horizon=horizon)
        logger.info(f"Fetching {horizon} historical running history for train {train_clean} from {url}...")

        html = self.get(url)
        if not html:
            logger.warning(f"Failed to fetch running history for train {train_clean}")
            return None

        return self.parse_history_html(train_clean, html, horizon=horizon)

    def parse_history_html(
        self,
        train_number: str,
        html: str,
        horizon: str = HORIZON_90D,
    ) -> Optional[Dict[str, Any]]:
        """
        Parse etrain history HTML, extracting station sequences, daily delay points,
        and slicing runs into 15-day partitioned windows.
        """
        train_clean = str(train_number).strip()
        if len(train_clean) == 4 and train_clean.isdigit():
            train_clean = "0" + train_clean

        # 1. Extract Train Name
        train_name = "Express"
        title_match = re.search(r"Running History of\s+([^(\n<]+)\s*\(", html, re.IGNORECASE)
        if title_match:
            train_name = title_match.group(1).strip()
        else:
            val_match = re.search(r'name=["\']trainname["\']\s+value=["\']([^"\']+)["\']', html)
            if val_match:
                train_name = val_match.group(1).strip()

        # 2. Extract Station Sequence
        station_sequence = re.findall(r"['\"]label['\"]\s*:\s*['\"]([A-Za-z0-9_-]+)['\"]", html)
        if not station_sequence:
            station_sequence = re.findall(r"\[\s*['\"]([A-Za-z0-9_-]+)['\"]\s*,\s*\d+", html)

        if not station_sequence:
            logger.warning(f"No station sequence identified in HTML for train {train_clean}")
            return None

        # 3. Extract Station Summaries from primaryData
        station_summaries = {}
        summary_matches = re.findall(
            r"\[\s*['\"]([A-Z0-9]+)['\"]\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d\.-]+)\s*\]",
            html,
        )
        for stn, rt, slight, sig, cancel, avg_d in summary_matches:
            station_summaries[stn] = {
                "station_code": stn,
                "right_time_runs": int(rt),
                "slight_delay_runs": int(slight),
                "significant_delay_runs": int(sig),
                "cancelled_runs": int(cancel),
                "average_delay_mins": float(avg_d),
            }

        # 4. Extract Daily Runs from tooltipData
        row_matches = re.findall(
            r"\[\s*new\s+Date\s*\(\s*(\d{4})\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*,\s*([^\]]+)\]",
            html,
        )

        all_daily_runs = []
        for y_str, m_str, d_str, delays_str in row_matches:
            year = int(y_str)
            month = int(m_str) + 1  # JS Date months are 0-indexed (0=Jan, 7=Aug)
            day = int(d_str)

            try:
                run_date = date(year, month, day)
            except ValueError:
                continue

            raw_delays = [x.strip() for x in delays_str.split(",")]
            station_delays = {}
            for idx, stn_code in enumerate(station_sequence):
                if idx < len(raw_delays):
                    val = raw_delays[idx]
                    if val.lower() in ("null", "undefined", "na", "-"):
                        station_delays[stn_code] = None
                    else:
                        try:
                            station_delays[stn_code] = int(float(val))
                        except ValueError:
                            station_delays[stn_code] = None
                else:
                    station_delays[stn_code] = None

            all_daily_runs.append({
                "journey_date": run_date.isoformat(),
                "day_of_week": run_date.weekday(),  # 0=Mon, 6=Sun
                "is_weekend": 1 if run_date.weekday() in (5, 6) else 0,
                "delays": station_delays,
            })

        # Sort chronologically
        all_daily_runs.sort(key=lambda r: r["journey_date"])

        # 5. Partition into 15-Day Tumbling Sub-Windows
        # Window 1 is the most recent 15 days, Window 2 is 16-30 days ago, etc.
        n_runs = len(all_daily_runs)
        sub_windows = []
        macro_tag = "90d_macro" if horizon == HORIZON_90D else ("1y_macro" if horizon == HORIZON_1Y else "macro")

        # Assign window tags to each daily run
        # Slicing from most recent backwards
        for w_idx in range((n_runs + SUB_WINDOW_DAYS - 1) // SUB_WINDOW_DAYS):
            end_idx = n_runs - (w_idx * SUB_WINDOW_DAYS)
            start_idx = max(0, end_idx - SUB_WINDOW_DAYS)
            w_tag = f"15d_w{w_idx + 1}"

            window_runs = all_daily_runs[start_idx:end_idx]
            for r in window_runs:
                r["window_tag"] = w_tag
                r["macro_tag"] = macro_tag

            if window_runs:
                sub_windows.append({
                    "window_tag": w_tag,
                    "window_index": w_idx + 1,
                    "start_date": window_runs[0]["journey_date"],
                    "end_date": window_runs[-1]["journey_date"],
                    "runs_count": len(window_runs),
                })

        return {
            "train_number": train_clean,
            "train_name": train_name,
            "horizon": horizon,
            "total_stations": len(station_sequence),
            "station_sequence": station_sequence,
            "station_summaries": station_summaries,
            "total_days_retrieved": n_runs,
            "macro_tag": macro_tag,
            "date_range": {
                "start": all_daily_runs[0]["journey_date"] if all_daily_runs else None,
                "end": all_daily_runs[-1]["journey_date"] if all_daily_runs else None,
            },
            "sub_windows": sub_windows,
            "daily_runs": all_daily_runs,
        }
