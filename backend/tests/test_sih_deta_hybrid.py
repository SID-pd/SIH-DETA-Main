from __future__ import annotations

from app.sih_deta.controller_ops import controller_ops
from app.sih_deta.data_bridge import bridge, canonical_modern_code, resolve_station_variants
from app.sih_deta.dsa_scheduler import PlatformIntervalScheduler, YenKShortestRerouter
from app.sih_deta.quantile_engine import GSRWeatherEvaluator, quantile_engine
from app.sih_deta.surge_profiler import StationSurgeProfiler


def test_station_alias_resolution() -> None:
    assert canonical_modern_code("ALD") == "PRYJ"
    assert canonical_modern_code("MGS") == "DDU"
    assert canonical_modern_code("JHS") == "VGLJ"
    assert set(resolve_station_variants("PRYJ")) >= {"PRYJ", "ALD"}


def test_database_inventory_and_remediation() -> None:
    inv = bridge.get_database_inventory()
    assert "modules" in inv
    assert len(inv["modules"]) >= 6
    assert inv["audit_remediation"]["issue_1_station_alias_engine"]["recovered_records"] == 72508


def test_gsr_weather_speed_caps() -> None:
    fog = GSRWeatherEvaluator.evaluate_section_weather(
        station_code="CNB",
        visibility_meters=90.0,
        precipitation_mm=0.0,
        ambient_temp_c=16.0,
    )
    assert fog["effective_mps_cap_kmh"] == 30
    assert fog["is_foggy"] is True

    normal = GSRWeatherEvaluator.evaluate_section_weather(
        station_code="CNB",
        visibility_meters=4000.0,
        precipitation_mm=0.0,
        ambient_temp_c=28.0,
    )
    assert normal["effective_mps_cap_kmh"] == 130
    assert normal["is_foggy"] is False


def test_station_surge_profiler_maha_kumbh() -> None:
    profile = StationSurgeProfiler.evaluate_station_surge(
        station_code="PRYJ",
        scheduled_dwell_mins=5,
        active_event_id="MAHA_KUMBH",
    )
    assert profile["nsg_category"] in ("NSG-1", "NSG-2")
    assert profile["dilated_dwell_mins"] > profile["scheduled_dwell_mins"]
    assert profile["surge_multiplier_s_event"] == 3.2


def test_platform_interval_scheduler_and_outer_hold() -> None:
    res = PlatformIntervalScheduler.build_station_intervals(
        station_code="CNB",
        center_mins=840,
        active_event_id="MAHA_KUMBH",
    )
    assert res["station_code"] == "CNB"
    assert res["platform_count"] >= 2
    assert len(res["intervals"]) >= 1
    assert res["saturation_summary"]["mutual_exclusion_verified"] is True


def test_yen_k_shortest_rerouter() -> None:
    detour = YenKShortestRerouter.find_detour("CNB", "PRYJ")
    assert detour["edge_weight"] == "INFINITY (TOTAL_BLOCK)"
    assert detour["detour_via_stations"][0] == "CNB"
    assert detour["detour_via_stations"][-1] == "PRYJ"
    assert detour["estimated_detour_penalty_mins"] > 0


def test_quantile_engine_monotonic_and_dual_mode() -> None:
    res = quantile_engine.compute_hybrid_eta(
        train_number="12301",
        target_station="NDLS",
        current_delay_override=45,
        active_event_id="MAHA_KUMBH",
        visibility_meters=420.0,
    )
    assert len(res["stop_predictions"]) >= 2
    for st in res["stop_predictions"]:
        assert st["p10_delay_mins"] <= st["p50_delay_mins"] <= st["p90_delay_mins"]
        assert "LOCKED" in st["dag_lock_status"]
    assert res["predictions"]["monotonic_bounds_verified"] is True
    assert len(res["micro_traversal_nodes"]) >= 3


def test_controller_ops_incident_lifecycle() -> None:
    created = controller_ops.report_incident(
        incident_type="ACP",
        section_from="CNB",
        section_to="PRYJ",
        affected_train_number="12301",
    )
    inc_id = created["incident_id"]
    state = controller_ops.get_control_room_state()
    active_ids = [i["incident_id"] for i in state["active_incidents"]]
    assert inc_id in active_ids

    resolved = controller_ops.resolve_incident(inc_id)
    assert resolved["status"] == "RESOLVED"
