"""Pure helpers for the Energy Dashboard data contract."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any

from .analytics import (
    build_statistics_energy_samples_with_price_history,
    build_consumer_events,
    calculate_battery_contribution_percent,
    calculate_consumer_analysis,
    calculate_consumer_price_alignment,
    calculate_consumer_share_percent,
    calculate_highest_cost_period,
    calculate_lowest_cost_period,
    calculate_smart_score,
    calculate_import_price_median,
    build_deterministic_insights,
    calculate_positive_cumulative_delta,
)
from .recorder_data import normalize_datetime, stat_end, stat_start


ENERGY_FLOW_KEYS = (
    "solar_house",
    "solar_battery",
    "solar_export",
    "grid_battery",
    "battery_house",
    "battery_grid",
    "grid_house",
    "house_grid",
)

GRID_PERIOD_COMPONENTS = {
    "import": ("grid_house", "grid_battery"),
    "export": ("solar_export", "battery_grid", "house_grid"),
}
STATISTICS_INTERVAL = timedelta(minutes=5)


def select_price_intervals_window(
    intervals: list[dict[str, Any]],
    *,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Select price intervals overlapping a half-open time window."""
    start = normalize_datetime(start)
    end = normalize_datetime(end)
    result = []
    for interval in intervals:
        interval_start = interval.get("start")
        interval_end = interval.get("end")
        if not isinstance(interval_start, datetime) or not isinstance(
            interval_end, datetime
        ):
            continue
        if interval_start < end and interval_end > start:
            result.append(interval)
    return result


def build_energy_samples_from_statistics(
    statistics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert Recorder cumulative-energy change statistics to samples."""
    result: list[dict[str, Any]] = []
    for stat in statistics:
        start = stat_start(stat)
        end = stat_end(stat)
        if start is None or end is None or end <= start:
            continue
        try:
            energy_kwh = float(stat["change"])
        except (KeyError, TypeError, ValueError):
            continue
        if energy_kwh < 0:
            continue
        result.append(
            {
                "start": start,
                "end": end,
                "energy_kwh": round(energy_kwh, 6),
            }
        )
    result.sort(key=lambda item: item["start"])
    return result


def _sum_energy_statistics_in_window(
    statistics: list[dict[str, Any]],
    *,
    start: datetime,
    end: datetime,
) -> float | None:
    """Sum complete Recorder change samples in a half-open time window."""
    start = normalize_datetime(start)
    end = normalize_datetime(end)
    samples = build_energy_samples_from_statistics(statistics)
    values = [
        sample["energy_kwh"]
        for sample in samples
        if sample["start"] >= start
        and sample["start"] < end
        and sample["end"] <= end
    ]
    if not values:
        return None
    return round(sum(values), 6)


def build_grid_period_data(
    statistics_by_entity: dict[str, list[dict[str, Any]]],
    entity_ids: dict[str, str | None],
    *,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    """Build quality-aware, half-open grid flow totals from 5-minute stats.

    Only complete Recorder buckets are counted. A contiguous prefix is
    reported as partial with its actual coverage; an internal gap or invalid
    sample makes the metric unavailable rather than a misleading subtotal.
    """
    start_utc = normalize_datetime(start)
    end_utc = normalize_datetime(end)
    end_complete = end_utc - timedelta(
        seconds=end_utc.timestamp() % STATISTICS_INTERVAL.total_seconds()
    )
    effective_end = min(end_complete, end_utc)

    def component_samples(key: str):
        entity_id = entity_ids.get(key)
        if not entity_id:
            return None, "missing_entity"
        raw = statistics_by_entity.get(entity_id)
        if raw is None or not raw:
            return None, "missing_statistics"
        valid: dict[datetime, tuple[datetime, float]] = {}
        invalid_starts: set[datetime] = set()
        has_unlocated_invalid = False
        for stat in raw:
            sample_start = stat_start(stat)
            sample_end = stat_end(stat)
            if sample_start is None or sample_end is None:
                has_unlocated_invalid = True
                continue
            if sample_end <= sample_start:
                invalid_starts.add(sample_start)
                continue
            try:
                amount = float(stat["change"])
            except (KeyError, TypeError, ValueError):
                invalid_starts.add(sample_start)
                continue
            if not math.isfinite(amount) or amount < 0:
                invalid_starts.add(sample_start)
                continue
            valid[sample_start] = (sample_end, amount)
        return (valid, invalid_starts, has_unlocated_invalid), None

    def metric(kind: str) -> dict[str, Any]:
        component_keys = GRID_PERIOD_COMPONENTS[kind]
        components = {key: component_samples(key) for key in component_keys}
        missing_status = next(
            (error for _, error in components.values() if error), None
        )
        base = {
            "value_kwh": None,
            "unit": "kWh",
            "status": missing_status,
            "complete": False,
            "requested_start": start_utc.isoformat(),
            "requested_end": end_utc.isoformat(),
            "covered_from": None,
            "covered_until": None,
            "source_entities": {
                key: entity_ids.get(key) for key in component_keys
            },
            "definition": (
                "grid_house + grid_battery; SBE signed-net import flow "
                "partition, not a gross meter reading"
                if kind == "import"
                else "solar_export + battery_grid + house_grid; SBE "
                "signed-net export flow partition, not a gross meter reading"
            ),
            "provenance": "Home Assistant Recorder 5-minute change statistics",
        }
        if missing_status:
            return base
        if any(
            samples[0][2]
            for samples in components.values()
        ):
            base["status"] = "invalid_statistics"
            return base
        if effective_end <= start_utc:
            base["status"] = "partial"
            return base

        interval_seconds = STATISTICS_INTERVAL.total_seconds()
        cursor = datetime.fromtimestamp(
            math.ceil(start_utc.timestamp() / interval_seconds) * interval_seconds,
            tz=start_utc.tzinfo,
        )
        if cursor >= effective_end:
            base["status"] = "missing_statistics"
            return base
        first_bucket = cursor
        total = 0.0
        while cursor + STATISTICS_INTERVAL <= effective_end:
            bucket_end = cursor + STATISTICS_INTERVAL
            amounts = []
            for key in component_keys:
                valid, invalid_starts, _ = components[key][0]
                if cursor in invalid_starts:
                    base["status"] = "invalid_statistics"
                    return base
                sample = valid.get(cursor)
                if sample is None:
                    later = any(
                        any(start > cursor and start < effective_end for start in source[0])
                        or any(
                            start > cursor and start < effective_end
                            for start in source[1]
                        )
                        for source, _error in components.values()
                    )
                    if later:
                        base["status"] = "incomplete"
                        return base
                    break
                sample_end, amount = sample
                if sample_end != bucket_end:
                    base["status"] = "invalid_interval"
                    return base
                amounts.append(amount)
            if len(amounts) != len(component_keys):
                break
            total += sum(amounts)
            cursor = bucket_end

        if cursor == first_bucket:
            base["status"] = "missing_statistics"
            return base
        base["covered_from"] = first_bucket.isoformat()
        base["covered_until"] = cursor.isoformat()
        base["value_kwh"] = round(total, 6)
        complete = (
            cursor == effective_end
            and first_bucket == start_utc
            and effective_end == end_utc
        )
        base["complete"] = complete
        base["status"] = "complete" if complete else "partial"
        return base

    return {"import": metric("import"), "export": metric("export")}


def build_periodized_energy_data(
    statistics_by_entity: dict[str, list[dict[str, Any]]],
    entity_ids: dict[str, str | None],
    *,
    yesterday_start: datetime,
    today_start: datetime,
    now: datetime,
) -> dict[str, Any]:
    """Build yesterday/today solar and battery energy from Recorder changes."""
    def period_values(start: datetime, end: datetime) -> dict[str, float | None]:
        return {
            key: (
                _sum_energy_statistics_in_window(
                    statistics_by_entity.get(entity_id, []),
                    start=start,
                    end=end,
                )
                if entity_id is not None
                else None
            )
            for key in ENERGY_FLOW_KEYS
            for entity_id in (entity_ids.get(key),)
        }

    def total(*values: float | None) -> float | None:
        if any(value is None for value in values):
            return None
        return round(sum(value for value in values if value is not None), 6)

    def view(
        values: dict[str, float | None], start: datetime, end: datetime
    ) -> dict[str, Any]:
        solar_house = values["solar_house"]
        solar_battery = values["solar_battery"]
        solar_export = values["solar_export"]
        grid_battery = values["grid_battery"]
        battery_house = values["battery_house"]
        battery_grid = values["battery_grid"]
        return {
            "solar": {
                "total_kwh": total(solar_house, solar_battery, solar_export),
                "to_house_kwh": solar_house,
                "to_battery_kwh": solar_battery,
                "to_grid_kwh": solar_export,
            },
            "battery": {
                "charged_kwh": total(solar_battery, grid_battery),
                "discharged_kwh": total(battery_house, battery_grid),
                "to_house_kwh": battery_house,
                "to_grid_kwh": battery_grid,
            },
            "grid": build_grid_period_data(
                statistics_by_entity,
                entity_ids,
                start=start,
                end=end,
            ),
        }

    tomorrow = {
        "solar": {
            "total_kwh": None,
            "to_house_kwh": None,
            "to_battery_kwh": None,
            "to_grid_kwh": None,
        },
        "battery": {
            "charged_kwh": None,
            "discharged_kwh": None,
            "to_house_kwh": None,
            "to_grid_kwh": None,
        },
        "grid": {
            "import": {
                "value_kwh": None,
                "unit": "kWh",
                "status": "forecast_unavailable",
                "complete": False,
                "source_entities": {
                    key: entity_ids.get(key)
                    for key in GRID_PERIOD_COMPONENTS["import"]
                },
                "definition": "SBE signed-net import flow partition",
                "provenance": "Home Assistant Recorder; no future measurements",
            },
            "export": {
                "value_kwh": None,
                "unit": "kWh",
                "status": "forecast_unavailable",
                "complete": False,
                "source_entities": {
                    key: entity_ids.get(key)
                    for key in GRID_PERIOD_COMPONENTS["export"]
                },
                "definition": "SBE signed-net export flow partition",
                "provenance": "Home Assistant Recorder; no future measurements",
            },
        },
    }
    return {
        "yesterday": view(
            period_values(yesterday_start, today_start),
            yesterday_start,
            today_start,
        ),
        "today": view(period_values(today_start, now), today_start, now),
        "tomorrow": tomorrow,
    }


def extract_import_price_history(
    price_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract total-import prices from normalized interval states."""
    result: list[dict[str, Any]] = []
    for state in price_history:
        timestamp = state.get("timestamp")
        if not isinstance(timestamp, datetime):
            continue
        try:
            import_price = float(state.get("state"))
        except (TypeError, ValueError):
            continue
        result.append({"timestamp": timestamp, "import_price": import_price})
    result.sort(key=lambda item: item["timestamp"])
    return result


def calculate_shared_import_price_median(
    price_history: list[dict[str, Any]],
) -> float | None:
    """Return the rolling 24h median total-import price from price states."""
    samples = [
        {"energy_kwh": 1.0, "import_price": item["import_price"]}
        for item in extract_import_price_history(price_history)
    ]
    return calculate_import_price_median(samples)


def build_house_analysis(
    house_total_samples: list[dict[str, Any]],
    *,
    reference_price: float | None = None,
    battery_house_samples: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the canonical 24-hour house analysis from total-house energy."""
    analysis = calculate_consumer_analysis(
        house_total_samples,
        reference_price=reference_price,
    )
    battery_contribution_percent = (
        calculate_battery_contribution_percent(
            house_total_samples,
            battery_house_samples,
        )
        if battery_house_samples is not None
        else None
    )
    return {
        "consumption_kwh": analysis["energy_kwh"],
        "cost": analysis["cost"],
        "average_import_price": analysis["average_import_price"],
        "cheap_usage_percent": analysis["cheap_usage_percent"],
        "expensive_usage_percent": analysis["expensive_usage_percent"],
        "sample_count": analysis["sample_count"],
        "highest_cost_period": calculate_highest_cost_period(house_total_samples),
        "lowest_cost_period": calculate_lowest_cost_period(house_total_samples),
        "battery_contribution_percent": battery_contribution_percent,
        "smart_score": calculate_smart_score(
            analysis["cheap_usage_percent"],
            analysis["expensive_usage_percent"],
            battery_contribution_percent,
        ),
    }


def build_consumer_dashboard_data(
    *,
    name: str,
    energy_entity: str,
    samples: list[dict[str, Any]],
    reference_price: float | None = None,
    house_total_samples: list[dict[str, Any]] | None = None,
    house_average_import_price: float | None = None,
) -> dict[str, Any]:
    """Build one generic consumer's canonical dashboard payload."""
    analysis = calculate_consumer_analysis(
        samples, reference_price=reference_price
    )
    if house_total_samples is not None:
        analysis["share_percent"] = calculate_consumer_share_percent(
            samples, house_total_samples
        )
    else:
        analysis["share_percent"] = None
    analysis["price_alignment_delta"] = calculate_consumer_price_alignment(
        house_average_import_price,
        analysis["average_import_price"],
    )

    return {
        "name": name,
        "energy_entity": energy_entity,
        "analysis": analysis,
        "history": samples,
        "events": build_consumer_events(
            samples,
            consumer_id=energy_entity,
        ),
    }
