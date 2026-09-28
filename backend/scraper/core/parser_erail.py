"""
Parsers for erail.in feeds.
Handles compact caret/tilde delimited streams, HTML tables, and JSON payloads.
"""

from __future__ import annotations

import datetime
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

logger = logging.getLogger("scraper_erail.parser_erail")


def clean_time(time_str: Optional[str]) -> Optional[str]:
    """Normalizes time strings to HH:MM:SS or returns None."""
    if not time_str:
        return None
    s = time_str.strip().lower()
    if s in ("none", "--", "-", "null", "00:00:00", "", "first", "last"):
        return None
    s = s.replace(".", ":")
    match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", s)
    if match:
        h, m, sec = match.group(1), match.group(2), match.group(3) or "00"
        return f"{int(h):02d}:{int(m):02d}:{int(sec):02d}"
    return None


def parse_halt_minutes(halt_str: Optional[str]) -> int:
    """Parses halt time text e.g. '5m', '2 min', '15', '00:05' into an integer."""
    if not halt_str:
        return 0
    s = halt_str.strip().lower()
    if "min" in s or "m" in s:
        nums = re.findall(r"\d+", s)
        return int(nums[0]) if nums else 0
    if ":" in s:
        parts = s.split(":")
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except Exception:
            return 0
    try:
        return int(float(s))
    except Exception:
        return 0


class ErailParser:
    """Specialized parser for erail.in data structures."""

    @staticmethod
    def parse_train_list(raw: str) -> List[Dict[str, Any]]:
        """
        Parses erail.in master train directory.
        Format typically: TrainNo~TrainName~FromStn~ToStn~RunningDays~TrainType^...
        Also handles JSON if returned.
        """
        trains: List[Dict[str, Any]] = []
        if not raw or not raw.strip():
            return trains

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Try JSON first
        if raw.strip().startswith("[") and raw.strip().endswith("]"):
            import json
            try:
                data = json.loads(raw)
                for item in data:
                    t_num = str(item.get("trainNo") or item.get("TrainNo") or item.get("number") or "").strip()
                    if not t_num:
                        continue
                    trains.append({
                        "number": t_num,
                        "name": str(item.get("name") or item.get("trainName") or "").strip(),
                        "type": str(item.get("type") or item.get("trainType") or "").strip(),
                        "from_code": str(item.get("from") or item.get("fromStation") or "").strip().upper(),
                        "from_name": str(item.get("fromName") or "").strip(),
                        "to_code": str(item.get("to") or item.get("toStation") or "").strip().upper(),
                        "to_name": str(item.get("toName") or "").strip(),
                        "running_days": str(item.get("days") or item.get("runningDays") or "").strip(),
                        "source": "erail",
                        "updated_at": now_iso,
                    })
                return trains
            except Exception:
                pass

        # Delimited format: records separated by '^'
        records = [r for r in raw.split("^") if r.strip()]
        for rec in records:
            # Fields separated by '~' or ','
            fields = rec.split("~") if "~" in rec else rec.split(",")
            if len(fields) < 2:
                continue

            t_num = fields[0].strip()
            # Must contain alphanumeric train number
            if not t_num or not re.match(r"^\d{4,5}[A-Za-z]?$", t_num):
                continue

            t_name = fields[1].strip() if len(fields) > 1 else ""
            from_code = fields[2].strip().upper() if len(fields) > 2 else None
            to_code = fields[3].strip().upper() if len(fields) > 3 else None
            running_days = fields[4].strip() if len(fields) > 4 else None
            t_type = fields[5].strip() if len(fields) > 5 else None

            trains.append({
                "number": t_num,
                "name": t_name,
                "type": t_type,
                "from_code": from_code,
                "from_name": None,
                "to_code": to_code,
                "to_name": None,
                "departure": None,
                "arrival": None,
                "duration_min": None,
                "distance_km": None,
                "zone": None,
                "classes": None,
                "running_days": running_days,
                "rake_type": None,
                "total_coaches": None,
                "pantry_status": None,
                "return_train": None,
                "source": "erail",
                "updated_at": now_iso,
            })

        return trains

    @staticmethod
    def parse_station_list(raw: str) -> List[Dict[str, Any]]:
        """
        Parses erail.in master station catalog.
        Delimited e.g.: NDLS~NEW DELHI~DELHI~NR^HWH~HOWRAH JN~WEST BENGAL~ER^...
        """
        stations: List[Dict[str, Any]] = []
        if not raw or not raw.strip():
            return stations

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        records = [r for r in raw.split("^") if r.strip()]
        for rec in records:
            fields = rec.split("~") if "~" in rec else rec.split(",")
            if len(fields) < 2:
                continue
            code = fields[0].strip().upper()
            if not code or len(code) > 6:
                continue
            name = fields[1].strip()
            state = fields[2].strip() if len(fields) > 2 and fields[2].strip() else None
            zone = fields[3].strip() if len(fields) > 3 and fields[3].strip() else None

            stations.append({
                "code": code,
                "name": name,
                "state": state,
                "zone": zone,
                "address": None,
                "lat": None,
                "lon": None,
                "updated_at": now_iso,
            })
        return stations

    @staticmethod
    def parse_get_trains_feed(raw: str, train_number: str) -> Tuple[Optional[Dict[str, Any]], str, List[Dict[str, Any]]]:
        """
        Parses erail.in /rail/getTrains.aspx?TrainNo={train_no} feed.
        Returns: (train_meta, rake_type, coaches)
        """
        if not raw or not raw.strip():
            return None, "ICF", []

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        part = raw.split("^")[-1] if "^" in raw else raw
        fields = part.split("~")
        if len(fields) < 14:
            return None, "ICF", []

        t_num = fields[0].strip() or train_number
        t_name = fields[1].strip()
        from_name = fields[2].strip() if len(fields) > 2 else None
        from_code = fields[3].strip().upper() if len(fields) > 3 else None
        to_name = fields[4].strip() if len(fields) > 4 else None
        to_code = fields[5].strip().upper() if len(fields) > 5 else None

        dep_time = clean_time(fields[10]) if len(fields) > 10 else None
        arr_time = clean_time(fields[11]) if len(fields) > 11 else None

        duration_min = None
        if len(fields) > 12 and fields[12].strip():
            try:
                dur_parts = fields[12].replace(".", ":").split(":")
                duration_min = int(dur_parts[0]) * 60 + int(dur_parts[1])
            except Exception:
                pass

        running_days = fields[13].strip() if len(fields) > 13 else None
        t_type = fields[32].strip() if len(fields) > 32 and fields[32].strip() else (fields[50].strip() if len(fields) > 50 else "Express")
        dist_km = float(fields[39]) if len(fields) > 39 and fields[39].replace(".", "", 1).isdigit() else None
        zone = fields[53].strip().upper() if len(fields) > 53 and fields[53].strip() else None
        return_train = fields[56].strip() if len(fields) > 56 and fields[56].strip() else None

        coach_raw = fields[59].strip() if len(fields) > 59 else ""
        rake_type, coaches = ErailParser.parse_coach_composition(coach_raw, t_num)
        classes_str = fields[62].strip() if len(fields) > 62 else None

        train_meta = {
            "number": t_num,
            "name": t_name,
            "type": t_type,
            "from_code": from_code,
            "from_name": from_name,
            "to_code": to_code,
            "to_name": to_name,
            "departure": dep_time,
            "arrival": arr_time,
            "duration_min": duration_min,
            "distance_km": dist_km,
            "zone": zone,
            "classes": classes_str,
            "running_days": running_days,
            "rake_type": rake_type,
            "total_coaches": len(coaches),
            "pantry_status": "Yes" if any(c.get("coach_type") == "Pantry Car" for c in coaches) else None,
            "return_train": return_train,
            "source": "erail",
            "updated_at": now_iso,
        }

        return train_meta, rake_type, coaches

    @staticmethod
    def parse_train_route(raw: str, train_number: str) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Parses train schedule stops from erail.in.
        Supports caret/tilde delimited, HTML table, or JSON.
        Returns: (train_meta_dict, list_of_schedule_stops)
        """
        stops: List[Dict[str, Any]] = []
        train_meta: Optional[Dict[str, Any]] = None
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if not raw or not raw.strip():
            return None, []

        # Check for HTML table
        if "<table" in raw.lower():
            soup = BeautifulSoup(raw, "html.parser")
            tables = soup.find_all("table")
            target_table = None
            for tbl in tables:
                if len(tbl.find_all("tr")) > 2:
                    target_table = tbl
                    break
            if not target_table and tables:
                target_table = tables[0]

            if target_table:
                seq = 1
                for tr in target_table.find_all("tr"):
                    cols = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                    if len(cols) < 5:
                        continue
                    if "Station" in cols[1] or "Arr" in cols[2]:
                        continue

                    # Clean station name (e.g. "Asansol Jn (RL)" -> "Asansol Jn")
                    stn_raw = cols[1]
                    stn_name = re.sub(r"\s*\([^)]*\)", "", stn_raw).strip()
                    stn_code = stn_name.upper()[:6].strip()

                    arr = clean_time(cols[2])
                    dep = clean_time(cols[3])
                    dist = 0.0
                    platform = None

                    if len(cols) > 4:
                        try:
                            nums = re.findall(r"[\d\.]+", cols[4])
                            if nums:
                                dist = float(nums[0])
                        except Exception:
                            pass

                    if len(cols) > 5:
                        platform = cols[5].strip() if cols[5].strip() not in ("--", "-") else None

                    # Halt calculation
                    halt = 0
                    if arr and dep:
                        try:
                            a_p = [int(p) for p in arr.split(":")[:2]]
                            d_p = [int(p) for p in dep.split(":")[:2]]
                            h_diff = (d_p[0] * 60 + d_p[1]) - (a_p[0] * 60 + a_p[1])
                            if h_diff < 0:
                                h_diff += 1440
                            halt = h_diff
                        except Exception:
                            pass

                    stops.append({
                        "train_number": train_number,
                        "seq": seq,
                        "station_code": stn_code,
                        "station_name": stn_name,
                        "day": 1,
                        "arrival": arr,
                        "departure": dep,
                        "halt_mins": halt,
                        "distance_km": dist,
                        "platform": platform,
                        "speed_kmph": None,
                        "is_commercial_halt": 1,
                        "source": "erail",
                        "updated_at": now_iso,
                    })
                    seq += 1

                if stops:
                    train_meta = {
                        "number": train_number,
                        "name": f"Train {train_number}",
                        "from_code": stops[0]["station_code"],
                        "from_name": stops[0]["station_name"],
                        "to_code": stops[-1]["station_code"],
                        "to_name": stops[-1]["station_name"],
                        "departure": stops[0]["departure"],
                        "arrival": stops[-1]["arrival"],
                        "distance_km": stops[-1]["distance_km"],
                        "updated_at": now_iso,
                        "source": "erail",
                    }
                return train_meta, stops

        # Delimited format: row separated by '^'
        # e.g.: Seq~StationCode~StationName~Arrival~Departure~Halt~Distance~Day~Platform
        records = [r for r in raw.split("^") if r.strip()]
        seq = 1
        for rec in records:
            fields = rec.split("~")
            if len(fields) < 4:
                continue

            # Check if fields[0] is seq or station_code
            if fields[0].isdigit() and len(fields) > 4:
                stn_code = fields[1].strip().upper()
                stn_name = fields[2].strip()
                arr = clean_time(fields[3])
                dep = clean_time(fields[4])
                halt = parse_halt_minutes(fields[5]) if len(fields) > 5 else 0
                dist = float(fields[6]) if len(fields) > 6 and fields[6].replace(".", "", 1).isdigit() else 0.0
                day = int(fields[7]) if len(fields) > 7 and fields[7].isdigit() else 1
                platform = fields[8].strip() if len(fields) > 8 else None
            else:
                stn_code = fields[0].strip().upper()
                stn_name = fields[1].strip() if len(fields) > 1 else stn_code
                arr = clean_time(fields[2]) if len(fields) > 2 else None
                dep = clean_time(fields[3]) if len(fields) > 3 else None
                halt = parse_halt_minutes(fields[4]) if len(fields) > 4 else 0
                dist = float(fields[5]) if len(fields) > 5 and fields[5].replace(".", "", 1).isdigit() else 0.0
                day = int(fields[6]) if len(fields) > 6 and fields[6].isdigit() else 1
                platform = fields[7].strip() if len(fields) > 7 else None

            stops.append({
                "train_number": train_number,
                "seq": seq,
                "station_code": stn_code,
                "station_name": stn_name,
                "day": day,
                "arrival": arr,
                "departure": dep,
                "halt_mins": halt,
                "distance_km": dist,
                "platform": platform,
                "speed_kmph": None,
                "is_commercial_halt": 1,
                "source": "erail",
                "updated_at": now_iso,
            })
            seq += 1

        if stops:
            train_meta = {
                "number": train_number,
                "name": f"Train {train_number}",
                "from_code": stops[0]["station_code"],
                "from_name": stops[0]["station_name"],
                "to_code": stops[-1]["station_code"],
                "to_name": stops[-1]["station_name"],
                "departure": stops[0]["departure"],
                "arrival": stops[-1]["arrival"],
                "distance_km": stops[-1]["distance_km"],
                "updated_at": now_iso,
                "source": "erail",
            }

        return train_meta, stops

    @staticmethod
    def parse_coach_composition(raw: str, train_number: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Parses coach position string from erail.in.
        e.g. LOCO^SLR^GS^S1^S2^S3^B1^B2^B3^A1^H1^SLR or delimited tokens.
        Identifies rake type: LHB, ICF, TRAIN18 (Vande Bharat).
        """
        coaches: List[Dict[str, Any]] = []
        rake_type = "ICF"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if not raw or not raw.strip():
            return rake_type, coaches

        # Delimiters can be '^', ',', or '-'
        tokens = [t.strip().upper() for t in re.split(r"[\^,\-]", raw) if t.strip()]

        pos = 1
        has_lhb_indicators = False
        has_vb_indicators = False

        for token in tokens:
            coach_code = token
            coach_type = "Standard"
            class_type = None

            if "LOCO" in token or token in ("ENG", "WAP", "WDP", "WAG"):
                coach_type = "Locomotive"
            elif token.startswith("S") and token[1:].isdigit():
                coach_type = "Sleeper"
                class_type = "SL"
            elif token.startswith("B") and token[1:].isdigit():
                coach_type = "AC 3-Tier"
                class_type = "3A"
                has_lhb_indicators = True
            elif token.startswith("M") and token[1:].isdigit():
                coach_type = "AC 3 Economy"
                class_type = "3E"
                has_lhb_indicators = True
            elif token.startswith("A") and token[1:].isdigit():
                coach_type = "AC 2-Tier"
                class_type = "2A"
            elif token.startswith("H") and token[1:].isdigit():
                coach_type = "AC First Class"
                class_type = "1A"
            elif token.startswith("C") and token[1:].isdigit():
                coach_type = "AC Chair Car"
                class_type = "CC"
            elif token.startswith("E") and token[1:].isdigit():
                coach_type = "Executive Chair Car"
                class_type = "EC"
                has_vb_indicators = True
            elif token.startswith("EA") or token.startswith("EV"):
                coach_type = "Vistadome / Executive Anubhuti"
                class_type = "EA"
            elif token in ("EOG", "PWR"):
                coach_type = "End On Generation / Power Car"
                has_lhb_indicators = True
            elif token in ("SLR", "SLRD"):
                coach_type = "Seating Luggage Rake"
            elif token in ("GEN", "GS", "UR"):
                coach_type = "General Unreserved"
                class_type = "2S"
            elif token in ("PC", "PANTRY"):
                coach_type = "Pantry Car"

            coaches.append({
                "train_number": train_number,
                "position": pos,
                "coach_code": coach_code,
                "coach_type": coach_type,
                "class_type": class_type,
                "rake_type": "PENDING",  # Backfilled below
                "updated_at": now_iso,
            })
            pos += 1

        if has_vb_indicators:
            rake_type = "TRAIN18"
        elif has_lhb_indicators or "EOG" in tokens:
            rake_type = "LHB"
        else:
            rake_type = "ICF"

        for c in coaches:
            c["rake_type"] = rake_type

        return rake_type, coaches

    @staticmethod
    def parse_historical_delays(raw: str, train_number: str) -> List[Dict[str, Any]]:
        """
        Parses historical station delay statistics from erail.in delay profiling page.
        Yields per-station: avg_delay_mins, pct_on_time, pct_slight, pct_moderate, pct_severe.
        """
        delays: List[Dict[str, Any]] = []
        if not raw or not raw.strip():
            return delays

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Check for HTML table
        if "<table" in raw.lower():
            soup = BeautifulSoup(raw, "html.parser")
            rows = soup.find_all("tr")
            for tr in rows:
                cols = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(cols) < 3:
                    continue
                # Expected format: Station | Avg Delay | Right Time % | Slight Delay % | Severe Delay %
                stn_code = cols[0].split("-")[0].strip().upper()
                if not re.match(r"^[A-Z0-9]{2,6}$", stn_code):
                    continue

                avg_delay = 0.0
                pct_on_time = 0.0
                pct_slight = 0.0
                pct_mod = 0.0
                pct_severe = 0.0

                try:
                    nums = re.findall(r"[-+]?\d*\.\d+|\d+", cols[1])
                    if nums:
                        avg_delay = float(nums[0])
                except Exception:
                    pass

                try:
                    if len(cols) > 2:
                        nums = re.findall(r"\d*\.\d+|\d+", cols[2])
                        if nums:
                            pct_on_time = float(nums[0])
                    if len(cols) > 3:
                        nums = re.findall(r"\d*\.\d+|\d+", cols[3])
                        if nums:
                            pct_slight = float(nums[0])
                    if len(cols) > 4:
                        nums = re.findall(r"\d*\.\d+|\d+", cols[4])
                        if nums:
                            pct_mod = float(nums[0])
                    if len(cols) > 5:
                        nums = re.findall(r"\d*\.\d+|\d+", cols[5])
                        if nums:
                            pct_severe = float(nums[0])
                except Exception:
                    pass

                delays.append({
                    "train_number": train_number,
                    "station_code": stn_code,
                    "avg_delay_mins": avg_delay,
                    "pct_on_time": pct_on_time,
                    "pct_slight_delay": pct_slight,
                    "pct_moderate_delay": pct_mod,
                    "pct_severe_delay": pct_severe,
                    "sample_days": 365,
                    "source": "erail",
                    "scraped_at": now_iso,
                })
        return delays
