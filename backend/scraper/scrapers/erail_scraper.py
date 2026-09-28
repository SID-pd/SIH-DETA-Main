"""
High-level scraper for erail.in.
Orchestrates master catalog retrieval, route timetable extraction,
coach composition layouts, and historical delay profiles.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

from config.settings import (
    ERAIL_BASE_URL,
    ERAIL_CONCURRENCY,
    ERAIL_RPS_LIMIT,
    SCRAPER_DIR,
)
from core.http_client import ResilientHttpClient
from core.parser_erail import ErailParser
from core.state_manager import StateManager
from pipeline.validator import DataValidator
from storage.database import Database

logger = logging.getLogger("scraper_erail.erail")


class ErailScraper:
    def __init__(
        self,
        db: Optional[Database] = None,
        state_mgr: Optional[StateManager] = None,
        base_url: str = ERAIL_BASE_URL,
    ):
        self.db = db or Database()
        self.state_mgr = state_mgr or StateManager()
        self.base_url = base_url.rstrip("/")

    async def fetch_train_catalog(self) -> List[Dict[str, Any]]:
        """Scrapes master train catalog from erail.in with fallback to all_trains.csv."""
        url = f"{self.base_url}/data.aspx?Action=TRAINLIST"
        logger.info(f"Fetching master train catalog from {url}...")

        valid_trains: List[Dict[str, Any]] = []
        try:
            async with ResilientHttpClient(
                rate_limit_rps=ERAIL_RPS_LIMIT, concurrency_limit=ERAIL_CONCURRENCY
            ) as client:
                raw = await client.get_text(url)
            trains = ErailParser.parse_train_list(raw)
            valid_trains = [t for t in trains if DataValidator.validate_train(t)[0]]
        except Exception as e:
            logger.warning(f"Live train catalog fetch error: {e}")

        # Fallback to rich catalog CSV if endpoint returned empty
        if len(valid_trains) < 100:
            csv_path = SCRAPER_DIR.parent / "railroad-data" / "csv" / "all_trains.csv"
            if csv_path.exists():
                import csv
                import datetime
                logger.info(f"Loading 13,432 train catalog from {csv_path}...")
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        t_num = row.get("train_number", "").strip()
                        t_name = row.get("train_name", "").strip()
                        if t_num and t_name:
                            valid_trains.append({
                                "number": t_num,
                                "name": t_name,
                                "type": "Express",
                                "from_code": None,
                                "from_name": None,
                                "to_code": None,
                                "to_name": None,
                                "departure": None,
                                "arrival": None,
                                "duration_min": None,
                                "distance_km": None,
                                "zone": None,
                                "classes": None,
                                "running_days": None,
                                "rake_type": None,
                                "total_coaches": None,
                                "pantry_status": None,
                                "return_train": None,
                                "source": "railroad_catalog",
                                "updated_at": now_iso,
                            })

        if valid_trains:
            self.db.upsert_trains(valid_trains)
            logger.info(f"Successfully stored {len(valid_trains)} trains in database.")
        return valid_trains

    async def fetch_station_catalog(self) -> List[Dict[str, Any]]:
        """Scrapes master station list from erail.in with fallback to all_stations.csv."""
        url = f"{self.base_url}/data.aspx?Action=STATIONLIST"
        logger.info(f"Fetching master station catalog from {url}...")

        valid_stations: List[Dict[str, Any]] = []
        try:
            async with ResilientHttpClient(
                rate_limit_rps=ERAIL_RPS_LIMIT, concurrency_limit=ERAIL_CONCURRENCY
            ) as client:
                raw = await client.get_text(url)
            stations = ErailParser.parse_station_list(raw)
            valid_stations = [s for s in stations if DataValidator.validate_station(s)[0]]
        except Exception as e:
            logger.warning(f"Live station catalog fetch error: {e}")

        # Fallback to all_stations.csv if endpoint returned empty
        if len(valid_stations) < 100:
            csv_path = SCRAPER_DIR.parent / "railroad-data" / "csv" / "all_stations.csv"
            if csv_path.exists():
                import csv
                import datetime
                logger.info(f"Loading 12,967 station catalog from {csv_path}...")
                now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        s_code = row.get("station_code", "").strip().upper()
                        s_name = row.get("station_name", "").strip()
                        if s_code and s_name:
                            valid_stations.append({
                                "code": s_code,
                                "name": s_name,
                                "state": None,
                                "zone": None,
                                "address": None,
                                "lat": None,
                                "lon": None,
                                "updated_at": now_iso,
                            })

        if valid_stations:
            self.db.upsert_stations(valid_stations)
            logger.info(f"Successfully stored {len(valid_stations)} stations in database.")
        return valid_stations

    async def fetch_train_route(
        self, train_number: str, client: ResilientHttpClient
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """Scrapes complete route stops, halt times, and platforms for a train."""
        # 1. Fetch metadata and coach layout from getTrains.aspx
        get_url = f"{self.base_url}/rail/getTrains.aspx?TrainNo={train_number}"
        try:
            get_raw = await client.get_text(get_url)
            train_meta, rake_type, coaches = ErailParser.parse_get_trains_feed(get_raw, train_number)
            if train_meta:
                self.db.upsert_trains([train_meta])
            if coaches:
                self.db.upsert_coach_compositions(coaches)
        except Exception as e:
            logger.debug(f"getTrains feed error for {train_number}: {e}")

        # 2. Fetch timetable stops and platforms from train-enquiry HTML
        html_url = f"{self.base_url}/train-enquiry/{train_number}"
        meta, stops = None, []
        try:
            raw_html = await client.get_text(html_url)
            meta, stops = ErailParser.parse_train_route(raw_html, train_number)
            if stops and DataValidator.validate_schedule_stops(stops)[0]:
                if meta:
                    self.db.upsert_trains([meta])
                self.db.upsert_schedule_stops(stops)
                return meta, stops
        except Exception as e:
            logger.debug(f"train-enquiry HTML error for {train_number}: {e}")

        # Fallback to data.aspx
        if not stops:
            try:
                url = f"{self.base_url}/data.aspx?Action=TRAINROUTE&TrainNo={train_number}"
                raw = await client.get_text(url)
                meta, stops = ErailParser.parse_train_route(raw, train_number)
                if stops and DataValidator.validate_schedule_stops(stops)[0]:
                    if meta:
                        self.db.upsert_trains([meta])
                    self.db.upsert_schedule_stops(stops)
            except Exception:
                pass

        return meta, stops

    async def fetch_coach_composition(
        self, train_number: str, client: ResilientHttpClient
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Scrapes coach composition layout and identifies rake type (LHB/ICF)."""
        url = f"{self.base_url}/rail/getTrains.aspx?TrainNo={train_number}&Action=CoachPosition"
        raw = await client.get_text(url)
        rake_type, coaches = ErailParser.parse_coach_composition(raw, train_number)

        if coaches:
            self.db.upsert_coach_compositions(coaches)
            # Update rake_type on the train record
            now_iso = coaches[0]["updated_at"]
            self.db.upsert_trains([{
                "number": train_number,
                "name": f"Train {train_number}",
                "rake_type": rake_type,
                "total_coaches": len(coaches),
                "updated_at": now_iso,
                "source": "erail",
            }])

        return rake_type, coaches

    async def fetch_historical_delays(
        self, train_number: str, client: ResilientHttpClient
    ) -> List[Dict[str, Any]]:
        """Scrapes 1-year station-level punctuality distributions."""
        url = f"{self.base_url}/train-running-status/{train_number}"
        raw = await client.get_text(url)
        delays = ErailParser.parse_historical_delays(raw, train_number)

        if delays:
            self.db.upsert_historical_delays(delays)

        return delays

    async def scrape_batch_routes(
        self, train_numbers: List[str], resume: bool = True
    ) -> int:
        """Batch scrapes timetable routes for a list of train numbers concurrently with state checkpoints."""
        targets = train_numbers
        if resume:
            targets = self.state_mgr.filter_pending_targets("route", train_numbers)
            logger.info(f"Resuming route scrape: {len(targets)}/{len(train_numbers)} targets pending.")

        if not targets:
            return 0

        queue: asyncio.Queue[str] = asyncio.Queue()
        for t in targets:
            queue.put_nowait(t)

        success_count = 0
        total_targets = len(targets)
        lock = asyncio.Lock()

        async with ResilientHttpClient(
            rate_limit_rps=ERAIL_RPS_LIMIT, concurrency_limit=ERAIL_CONCURRENCY
        ) as client:
            async def worker():
                nonlocal success_count
                while not queue.empty():
                    try:
                        t_num = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    task_key = f"route:{t_num}"
                    try:
                        meta, stops = await self.fetch_train_route(t_num, client)
                        if stops:
                            self.state_mgr.mark_completed(task_key, "route", t_num)
                            async with lock:
                                success_count += 1
                                cur = success_count
                            logger.info(f"[{cur}/{total_targets}] Saved route for {t_num} ({len(stops)} stops)")
                        else:
                            self.state_mgr.mark_failed(task_key, "route", t_num, "No stops parsed")
                    except Exception as exc:
                        self.state_mgr.mark_failed(task_key, "route", t_num, str(exc))
                        logger.warning(f"Failed to scrape route for {t_num}: {exc}")
                    finally:
                        queue.task_done()

            workers = [asyncio.create_task(worker()) for _ in range(ERAIL_CONCURRENCY)]
            await asyncio.gather(*workers)

        return success_count

    async def scrape_batch_coaches(
        self, train_numbers: List[str], resume: bool = True
    ) -> int:
        """Batch scrapes coach layouts and rake types concurrently."""
        targets = train_numbers
        if resume:
            targets = self.state_mgr.filter_pending_targets("coach", train_numbers)

        if not targets:
            return 0

        queue: asyncio.Queue[str] = asyncio.Queue()
        for t in targets:
            queue.put_nowait(t)

        success_count = 0
        total_targets = len(targets)
        lock = asyncio.Lock()

        async with ResilientHttpClient(
            rate_limit_rps=ERAIL_RPS_LIMIT, concurrency_limit=ERAIL_CONCURRENCY
        ) as client:
            async def worker():
                nonlocal success_count
                while not queue.empty():
                    try:
                        t_num = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    task_key = f"coach:{t_num}"
                    try:
                        rake_type, coaches = await self.fetch_coach_composition(t_num, client)
                        if coaches:
                            self.state_mgr.mark_completed(task_key, "coach", t_num)
                            async with lock:
                                success_count += 1
                                cur = success_count
                            logger.info(f"[{cur}/{total_targets}] Saved {len(coaches)} coaches ({rake_type}) for {t_num}")
                        else:
                            self.state_mgr.mark_failed(task_key, "coach", t_num, "No coaches parsed")
                    except Exception as exc:
                        self.state_mgr.mark_failed(task_key, "coach", t_num, str(exc))
                        logger.warning(f"Failed coach layout for {t_num}: {exc}")
                    finally:
                        queue.task_done()

            workers = [asyncio.create_task(worker()) for _ in range(ERAIL_CONCURRENCY)]
            await asyncio.gather(*workers)

        return success_count

    async def scrape_batch_delays(
        self, train_numbers: List[str], resume: bool = True
    ) -> int:
        """Batch scrapes historical delay profiles concurrently."""
        targets = train_numbers
        if resume:
            targets = self.state_mgr.filter_pending_targets("delays", train_numbers)

        if not targets:
            return 0

        queue: asyncio.Queue[str] = asyncio.Queue()
        for t in targets:
            queue.put_nowait(t)

        success_count = 0
        total_targets = len(targets)
        lock = asyncio.Lock()

        async with ResilientHttpClient(
            rate_limit_rps=ERAIL_RPS_LIMIT, concurrency_limit=ERAIL_CONCURRENCY
        ) as client:
            async def worker():
                nonlocal success_count
                while not queue.empty():
                    try:
                        t_num = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    task_key = f"delays:{t_num}"
                    try:
                        delays = await self.fetch_historical_delays(t_num, client)
                        if delays:
                            self.state_mgr.mark_completed(task_key, "delays", t_num)
                            async with lock:
                                success_count += 1
                                cur = success_count
                            logger.info(f"[{cur}/{total_targets}] Saved {len(delays)} delay rows for {t_num}")
                        else:
                            self.state_mgr.mark_failed(task_key, "delays", t_num, "No delay stats")
                    except Exception as exc:
                        self.state_mgr.mark_failed(task_key, "delays", t_num, str(exc))
                        logger.warning(f"Failed delay stats for {t_num}: {exc}")
                    finally:
                        queue.task_done()

            workers = [asyncio.create_task(worker()) for _ in range(ERAIL_CONCURRENCY)]
            await asyncio.gather(*workers)

        return success_count
