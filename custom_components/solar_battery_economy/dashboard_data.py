"""Pure helpers for the Energy Dashboard data contract."""

from __future__ import annotations

from datetime import datetime
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
