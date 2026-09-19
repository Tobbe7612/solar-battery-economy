"""Pure helpers for the Energy Dashboard data contract."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .analytics import (
    build_statistics_energy_samples_with_price_history,
    calculate_consumer_analysis,
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


def extract_spot_price_history(
    price_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract actual spot price for the interval containing each price state.

    The price sensor stores the structured ``all_prices`` schedule as an
    attribute. Historical states therefore let the dashboard reconstruct the
    recorded spot-price timeline without creating another price sensor.
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
            if start is None or end is None:
                continue
            if not start <= timestamp < end:
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
            break

    # The template updates every 15 minutes, so duplicate interval snapshots
    # are possible. Keep the latest recorded state for each interval.
    deduped: dict[datetime, dict[str, Any]] = {}
    for item in result:
        existing = deduped.get(item["start"])
        if existing is None or item["recorded_at"] > existing["recorded_at"]:
            deduped[item["start"]] = item

    return [deduped[key] for key in sorted(deduped)]


def build_house_analysis(
    house_total_history: list[dict[str, Any]],
    grid_house_samples: list[dict[str, Any]],
    *,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    """Build the canonical 24-hour house energy/economy summary."""
    house_energy = calculate_positive_cumulative_delta(
        house_total_history,
        start=start,
        end=end,
    )
    cost_analysis = calculate_consumer_analysis(grid_house_samples)

    return {
        "consumption_kwh": house_energy,
        "imported_energy_kwh": cost_analysis["energy_kwh"],
        "cost": cost_analysis["cost"],
        "average_import_price": cost_analysis["average_import_price"],
        "cheap_usage_percent": cost_analysis["cheap_usage_percent"],
        "expensive_usage_percent": cost_analysis["expensive_usage_percent"],
        "sample_count": cost_analysis["sample_count"],
    }


def build_consumer_dashboard_data(
    *,
    name: str,
    energy_entity: str,
    samples: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build one generic consumer's canonical dashboard payload."""
    return {
        "name": name,
        "energy_entity": energy_entity,
        "analysis": calculate_consumer_analysis(samples),
        "history": samples,
    }
