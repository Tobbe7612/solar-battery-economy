"""Pure helpers for Home Assistant Recorder history/statistics data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
