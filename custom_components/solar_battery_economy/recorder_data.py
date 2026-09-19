"""Pure helpers for Home Assistant Recorder history/statistics data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

MAX_HISTORY = timedelta(hours=24)


def normalize_datetime(value: datetime) -> datetime:
    """Return an aware UTC datetime."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def clamp_history_window(
    *,
    start: datetime,
    end: datetime,
) -> tuple[datetime, datetime]:
    """Clamp a requested history window to at most 24 hours."""
    start = normalize_datetime(start)
    end = normalize_datetime(end)
    if end <= start:
        raise ValueError("end must be after start")
    if end - start > MAX_HISTORY:
        start = end - MAX_HISTORY
    return start, end


def normalize_history_states(
    states: list[Any],
    *,
    include_attributes: bool = False,
) -> list[dict[str, Any]]:
    """Convert Recorder State objects or dict responses to plain samples."""
    result: list[dict[str, Any]] = []
    for item in states:
        if isinstance(item, dict):
            timestamp = item.get("last_updated") or item.get("last_changed")
            state = item.get("state")
        else:
            timestamp = getattr(item, "last_updated", None) or getattr(
                item, "last_changed", None
            )
            state = getattr(item, "state", None)

        if not isinstance(timestamp, datetime):
            continue
        sample = {
            "timestamp": normalize_datetime(timestamp),
            "state": state,
        }
        if include_attributes:
            attributes = (
                item.get("attributes")
                if isinstance(item, dict)
                else getattr(item, "attributes", None)
            )
            if isinstance(attributes, dict):
                sample["attributes"] = attributes
        result.append(sample)

    result.sort(key=lambda item: item["timestamp"])
    return result


def build_statistics_samples(
    energy_statistics: list[dict[str, Any]],
    price_statistics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Align 5-minute energy changes with 5-minute import-price means.

    Retained as a pure helper for callers that have Recorder statistics for
    both inputs. The production dashboard path does not require price
    statistics because the user's import-price sensor is not a statistics
    entity; it uses Recorder state history for price instead.
    """
    prices = {
        stat_start(stat): stat.get("mean")
        for stat in price_statistics
        if stat_start(stat) is not None and stat.get("mean") is not None
    }

    samples: list[dict[str, Any]] = []
    for stat in energy_statistics:
        start = stat_start(stat)
        energy_change = stat.get("change")
        price = prices.get(start)
        if start is None or energy_change is None or price is None:
            continue
        try:
            energy_kwh = float(energy_change)
            import_price = float(price)
        except (TypeError, ValueError):
            continue
        if energy_kwh < 0:
            continue
        samples.append(
            {
                "start": start,
                "end": stat_end(stat),
                "energy_kwh": energy_kwh,
                "import_price": import_price,
            }
        )

    samples.sort(key=lambda item: item["start"])
    return samples


def stat_start(stat: dict[str, Any]) -> datetime | None:
    """Normalize a Recorder statistic start timestamp."""
    value = stat.get("start")
    if isinstance(value, datetime):
        return normalize_datetime(value)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    return None


def stat_end(stat: dict[str, Any]) -> datetime | None:
    """Normalize a Recorder statistic end timestamp."""
    value = stat.get("end")
    if isinstance(value, datetime):
        return normalize_datetime(value)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    return None
