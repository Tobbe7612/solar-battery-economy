"""Pure helpers for the Energy Dashboard data contract."""

from __future__ import annotations

from datetime import datetime, timezone
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
from .recorder_data import stat_end, stat_start


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


def _coerce_datetime(value: Any) -> datetime | None:
    """Convert an ISO timestamp or datetime to an aware datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def extract_import_price_interval_history(
    price_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reconstruct historical total-import-price intervals from Recorder snapshots."""
    result: list[dict[str, Any]] = []

    for state in price_history:
        timestamp = state.get("timestamp")
        attributes = state.get("attributes") or {}
        all_prices = attributes.get("all_prices")

        if not isinstance(timestamp, datetime) or not isinstance(all_prices, list):
            continue

        for interval in all_prices:
            if not isinstance(interval, dict):
                continue

            start = _coerce_datetime(interval.get("start"))
            end = _coerce_datetime(interval.get("end"))
            import_price = interval.get("import")

            if start is None or end is None or end > timestamp:
                continue

            try:
                import_value = float(import_price)
            except (TypeError, ValueError):
                continue

            result.append(
                {
                    "start": start,
                    "end": end,
                    "import": import_value,
                    "recorded_at": timestamp,
                }
            )

    deduped: dict[datetime, dict[str, Any]] = {}
    for item in result:
        existing = deduped.get(item["start"])
        if existing is None or item["recorded_at"] > existing["recorded_at"]:
            deduped[item["start"]] = item

    return [deduped[key] for key in sorted(deduped)]


def extract_spot_price_history(
    price_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Reconstruct historical spot intervals from the price sensor schedule.

    The price sensor stores the published 15-minute market-price schedule in
    ``all_prices``. Each Recorder snapshot contains the schedule available at
    that moment. For historical data, use intervals that had already ended at
    the time of that snapshot, then deduplicate by interval start. This lets
    Recorder snapshots preserve the published price curve without requiring
    a separate historical price sensor.
    """
    result: list[dict[str, Any]] = []

    for state in price_history:
        timestamp = state.get("timestamp")
        attributes = state.get("attributes") or {}
        all_prices = attributes.get("all_prices")

        if not isinstance(timestamp, datetime) or not isinstance(all_prices, list):
            continue

        for interval in all_prices:
            if not isinstance(interval, dict):
                continue

            start = _coerce_datetime(interval.get("start"))
            end = _coerce_datetime(interval.get("end"))
            spot = interval.get("spot")

            if start is None or end is None or end > timestamp:
                continue

            try:
                spot_value = float(spot)
            except (TypeError, ValueError):
                continue

            result.append(
                {
                    "start": start,
                    "end": end,
                    "spot": spot_value,
                    "recorded_at": timestamp,
                }
            )

    # The same completed interval can appear in many Recorder snapshots.
    # Keep the latest snapshot that still contains that published interval.
    deduped: dict[datetime, dict[str, Any]] = {}
    for item in result:
        existing = deduped.get(item["start"])
        if existing is None or item["recorded_at"] > existing["recorded_at"]:
            deduped[item["start"]] = item

    return [deduped[key] for key in sorted(deduped)]


def extract_import_price_history(
    price_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract total-import price states from Recorder history."""
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
