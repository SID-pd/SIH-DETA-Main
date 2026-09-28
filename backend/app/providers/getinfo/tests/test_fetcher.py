"""
Unit and regression test suite for Get-info information fetcher.
"""

import sys
from pathlib import Path

# Add Get-info package to path
PACKAGE_DIR = Path(__file__).resolve().parent.parent
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

import pytest
from client.cache import TieredCache
from client.http import CircuitBreaker
from engines.coach_engine import CoachEngine
from engines.live_engine import LiveEngine
from engines.pnr_engine import PNREngine
from fetcher import InfoFetcher
from models.schemas import (
    CoachInfo,
    CoachRakeResponse,
    LiveStatusResponse,
    PassengerRecord,
    PNRResponse,
    TimelineResponse,
    TimelineStop,
)
from providers.offline_fallback import OfflineFallbackProvider


def test_seat_layout_modulo_formulas():
    """Validates mathematical seat layout calculations for all IR coach categories."""
    calc = OfflineFallbackProvider.calculate_seat_layout

    # 3A / Sleeper tests
    s1 = calc("3A", 1)
    assert s1.berth_code == "LB"
    assert s1.bay_number == 1

    s2 = calc("3A", 2)
    assert s2.berth_code == "MB"

    s3 = calc("3A", 3)
    assert s3.berth_code == "UB"

    s7 = calc("SL", 7)
    assert s7.berth_code == "SL"

    s8 = calc("SL", 8)
    assert s8.berth_code == "SU"

    s9 = calc("3A", 9)
    assert s9.berth_code == "LB"
    assert s9.bay_number == 2

    # 3E Economy tests
    s_3e_8 = calc("3E", 8)
    assert s_3e_8.berth_code == "SM"  # Side Middle in 3E!
    assert s_3e_8.bay_number == 1

    s_3e_9 = calc("3E", 9)
    assert s_3e_9.berth_code == "SU"

    # 2A 2-Tier tests (6 berths per bay)
    s_2a_1 = calc("2A", 1)
    assert s_2a_1.berth_code == "LB"

    s_2a_5 = calc("2A", 5)
    assert s_2a_5.berth_code == "SL"

    s_2a_6 = calc("2A", 6)
    assert s_2a_6.berth_code == "SU"

    s_2a_7 = calc("2A", 7)
    assert s_2a_7.berth_code == "LB"
    assert s_2a_7.bay_number == 2

    # Chair Car (CC)
    s_cc_1 = calc("CC", 1)
    assert s_cc_1.berth_code == "WS"  # Window
    s_cc_3 = calc("CC", 3)
    assert s_cc_3.berth_code == "AS"  # Aisle


def test_circuit_breaker():
    """Verifies that circuit breaker opens after failure threshold and protects downstream callers."""
    cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=2.0)
    provider_id = "test_failing_provider"

    assert cb.is_available(provider_id) is True

    cb.record_failure(provider_id)
    assert cb.is_available(provider_id) is True

    cb.record_failure(provider_id)
    assert cb.is_available(provider_id) is True

    # 3rd failure trips the breaker
    cb.record_failure(provider_id)
    assert cb.is_available(provider_id) is False

    # Success resets it
    cb.record_success(provider_id)
    assert cb.is_available(provider_id) is True


def test_tiered_cache(tmp_path):
    """Tests Level 1 (memory) and Level 2 (SQLite) TTL caching."""
    db_file = tmp_path / "test_cache.sqlite"
    t_cache = TieredCache(db_path=db_file)

    # Set key with 10s TTL
    t_cache.set("test_key", {"status": "ok", "value": 42}, ttl_seconds=10.0)

    val = t_cache.get("test_key")
    assert val is not None
    assert val["status"] == "ok"
    assert val["value"] == 42

    # Non-existent key
    assert t_cache.get("non_existent") is None


def test_offline_coach_fallback():
    """Tests deterministic rake templates for premier trains."""
    provider = OfflineFallbackProvider()

    # Tejas Rajdhani
    res_raj = provider.get_coach_position("12951")
    assert res_raj.success is True
    assert "Rajdhani" in res_raj.rake_type or "LHB" in res_raj.rake_type
    assert len(res_raj.coach_sequence) >= 18
    codes = [c.coach_code for c in res_raj.coach_sequence]
    assert "H1" in codes
    assert "B1" in codes
    assert "A1" in codes

    # Vande Bharat
    res_vb = provider.get_coach_position("22436")
    assert res_vb.success is True
    assert "Vande Bharat" in res_vb.rake_type
    codes_vb = [c.coach_code for c in res_vb.coach_sequence]
    assert "DTC" in codes_vb


def test_pnr_validation():
    """Verifies that invalid PNR lengths or letters are gracefully rejected."""
    engine = PNREngine()

    r1 = engine.get_pnr_status("123")
    assert r1.success is False
    assert "10 digits" in r1.error_message

    r2 = engine.get_pnr_status("12345ABCDE")
    assert r2.success is False


def test_info_fetcher_facade():
    """Tests unified InfoFetcher interface initialization and helper calls."""
    fetcher = InfoFetcher()

    # Seat layout calculation
    layout = fetcher.get_seat_layout("3A", 21)
    assert layout.seat_number == 21
    assert layout.berth_code in ("LB", "MB", "UB", "SL", "SU")
    assert layout.layout_diagram is not None
