from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "live_power.py"
)
SPEC = importlib.util.spec_from_file_location("live_power_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
live_power = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(live_power)


CALCULATED_AT = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)
POWER = {
    "solar_house_power": 1000,
    "solar_battery_power": 300,
    "solar_export_power": 200,
    "battery_house_power": 400,
    "battery_grid_power": 100,
    "grid_house_power": 500,
    "grid_battery_power": 50,
    "house_grid_power": 25,
    "house_total": 1900,
}


def _valid_states(*, oldest: datetime | None = None):
    oldest = oldest or CALCULATED_AT - timedelta(seconds=42)
    return {
        key: SimpleNamespace(state="123.4", last_updated=oldest + timedelta(seconds=i))
        for i, key in enumerate(("solar", "grid", "battery"))
    }


def _build(power=None, states=None):
    return live_power.build_live_power_data(
        POWER if power is None else power,
        _valid_states() if states is None else states,
        calculated_at=CALCULATED_AT,
    )


def test_valid_values_reuse_existing_flows_and_emit_canonical_metadata():
    result = _build()

    assert result["timestamp"] == CALCULATED_AT.isoformat()
    assert result["timestamp_kind"] == "calculated_at"
    assert result["freshness"]["age_seconds"] == 42
    assert result["unit"] == "W"
    assert result["input_unit_validation"] == "not_performed"
    assert result["aggregates"]["solar_total"]["value"] == 1500
    assert result["aggregates"]["house_total"]["value"] == POWER["house_total"]
    assert result["aggregates"]["battery_net"]["value"] == -150
    assert result["aggregates"]["grid_net"]["value"] == 225
    assert result["flows"]["unknown_grid_export"] == {
        "source_sbe_key": "house_grid_power",
        "source": "unknown",
        "target": "grid",
        "value": 25,
        "unit": "W",
        "semantics": "residual_export",
        "quality": "valid",
    }
    assert result["flows"]["battery_grid"]["value"] == POWER["battery_grid_power"]


def test_battery_net_sign_supports_charging_and_discharging():
    charging = {**POWER, "battery_house_power": 100, "battery_grid_power": 25}
    exporting = {**POWER, "battery_house_power": 100, "battery_grid_power": 300}

    assert _build(charging)["aggregates"]["battery_net"]["value"] == 225
    assert _build(exporting)["aggregates"]["battery_net"]["value"] == -50


def test_flow_map_covers_all_existing_sbe_flow_keys():
    assert {row[0] for row in live_power.LIVE_POWER_FLOW_MAP} == {
        "solar_house",
        "solar_battery",
        "solar_export",
        "battery_house",
        "battery_grid",
        "grid_house",
        "grid_battery",
        "unknown_grid_export",
    }
    result = _build()
    for canonical_key, sbe_key, source, target, _semantics in live_power.LIVE_POWER_FLOW_MAP:
        flow = result["flows"][canonical_key]
        assert flow["source_sbe_key"] == sbe_key
        assert flow["source"] == source
        assert flow["target"] == target
        assert flow["value"] == POWER[sbe_key]


def test_missing_unavailable_and_invalid_inputs_null_all_derived_values():
    cases = (
        (None, "missing"),
        (SimpleNamespace(state="unknown"), "unavailable"),
        (SimpleNamespace(state="unavailable"), "unavailable"),
        (SimpleNamespace(state="not-a-number"), "invalid"),
        (SimpleNamespace(state="nan"), "invalid"),
        (SimpleNamespace(state="inf"), "invalid"),
        (SimpleNamespace(state="-inf"), "invalid"),
        (SimpleNamespace(state=True), "invalid"),
    )
    for bad_state, expected_quality in cases:
        states = _valid_states()
        states["grid"] = bad_state
        result = _build(states=states)

        assert result["inputs"]["grid"]["quality"] == expected_quality
        assert all(flow["value"] is None for flow in result["flows"].values())
        assert all(
            aggregate["value"] is None
            and aggregate["quality"] == expected_quality
            for aggregate in result["aggregates"].values()
        )


def test_numeric_zero_is_valid_and_missing_timestamp_makes_age_unknown():
    states = _valid_states()
    states["solar"].state = "0"
    assert live_power.classify_power_input(states["solar"]) == "valid"

    states["battery"].last_updated = None
    assert _build(states=states)["freshness"]["age_seconds"] is None


def test_builder_does_not_mutate_existing_power_data():
    power = dict(POWER)
    original = dict(power)

    _build(power=power)

    assert power == original
