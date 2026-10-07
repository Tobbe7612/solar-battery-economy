"""Build the internal canonical live power contract from existing flows."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any


LIVE_POWER_FLOW_MAP = (
    ("solar_house", "solar_house_power", "solar", "house", "estimated_directional_allocation"),
    ("solar_battery", "solar_battery_power", "solar", "battery", "estimated_directional_allocation"),
    ("solar_export", "solar_export_power", "solar", "grid", "estimated_directional_allocation"),
    ("battery_house", "battery_house_power", "battery", "house", "estimated_directional_allocation"),
    ("battery_grid", "battery_grid_power", "battery", "grid", "estimated_directional_allocation"),
    ("grid_house", "grid_house_power", "grid", "house", "estimated_directional_allocation"),
    ("grid_battery", "grid_battery_power", "grid", "battery", "estimated_directional_allocation"),
    ("unknown_grid_export", "house_grid_power", "unknown", "grid", "residual_export"),
)

_QUALITY_PRECEDENCE = ("invalid", "unavailable", "missing")


def classify_power_input(state: Any) -> str:
    """Classify the Home Assistant state used for one raw power input."""
    if state is None:
        return "missing"

    value = getattr(state, "state", None)
    if value in ("unknown", "unavailable"):
        return "unavailable"

    if value is None or isinstance(value, bool):
        return "invalid"
    try:
        numeric_value = float(value)
    except (TypeError, ValueError, OverflowError):
        return "invalid"
    return "valid" if math.isfinite(numeric_value) else "invalid"


def _sample_quality(input_quality: dict[str, str]) -> str:
    for quality in _QUALITY_PRECEDENCE:
        if quality in input_quality.values():
            return quality
    return "valid"


def _freshness_age_seconds(states: dict[str, Any], calculated_at: datetime) -> float | None:
    timestamps = [getattr(state, "last_updated", None) for state in states.values()]
    if any(not isinstance(value, datetime) for value in timestamps):
        return None
    try:
        oldest = min(timestamps)
        age_seconds = max((calculated_at - oldest).total_seconds(), 0.0)
    except (TypeError, ValueError):
        return None
    return round(age_seconds, 3)


def build_live_power_data(
    power: dict[str, Any],
    input_states: dict[str, Any],
    *,
    calculated_at: datetime,
) -> dict[str, Any]:
    """Build canonical live power values without recalculating any flows."""
    input_quality = {
        key: classify_power_input(input_states.get(key))
        for key in ("solar", "grid", "battery")
    }
    quality = _sample_quality(input_quality)
    valid = quality == "valid"

    inputs = {}
    for key, input_quality_value in input_quality.items():
        state = input_states.get(key)
        last_updated = getattr(state, "last_updated", None)
        inputs[key] = {
            "quality": input_quality_value,
            "last_updated": (
                last_updated.isoformat()
                if isinstance(last_updated, datetime)
                else None
            ),
        }

    flows = {}
    for canonical_key, sbe_key, source, target, semantics in LIVE_POWER_FLOW_MAP:
        flows[canonical_key] = {
            "source_sbe_key": sbe_key,
            "source": source,
            "target": target,
            "value": power.get(sbe_key) if valid else None,
            "unit": "W",
            "semantics": semantics,
            "quality": quality,
        }

    if valid:
        solar_total = sum(
            power[key]
            for key in ("solar_house_power", "solar_battery_power", "solar_export_power")
        )
        battery_net = (
            power["solar_battery_power"] + power["grid_battery_power"]
            - power["battery_house_power"] - power["battery_grid_power"]
        )
        grid_net = (
            power["grid_house_power"] + power["grid_battery_power"]
            - power["solar_export_power"] - power["battery_grid_power"]
            - power["house_grid_power"]
        )
        house_total = power["house_total"]
    else:
        solar_total = house_total = battery_net = grid_net = None

    aggregates = {
        "solar_total": {
            "value": solar_total,
            "unit": "W",
            "semantics": "total_solar_production",
            "quality": quality,
        },
        "house_total": {
            "value": house_total,
            "unit": "W",
            "semantics": "total_house_consumption",
            "quality": quality,
        },
        "battery_net": {
            "value": battery_net,
            "unit": "W",
            "semantics": "positive_charging_negative_discharging",
            "quality": quality,
        },
        "grid_net": {
            "value": grid_net,
            "unit": "W",
            "semantics": "positive_import_negative_export",
            "quality": quality,
        },
    }

    return {
        "timestamp": calculated_at.isoformat(),
        "timestamp_kind": "calculated_at",
        "freshness": {
            "age_seconds": _freshness_age_seconds(input_states, calculated_at),
        },
        "unit": "W",
        "input_unit_validation": "not_performed",
        "inputs": inputs,
        "flows": flows,
        "aggregates": aggregates,
    }
