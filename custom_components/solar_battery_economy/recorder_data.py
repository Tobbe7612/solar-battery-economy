"""Pure helpers for Home Assistant Recorder history/statistics data."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import NamedTuple
from zoneinfo import ZoneInfo

MAX_HISTORY = timedelta(hours=24)
DASHBOARD_TIMEZONE = ZoneInfo("Europe/Stockholm")


class DashboardCalendarBoundaries(NamedTuple):
    """Local calendar boundaries used by the dashboard's two time views."""

    yesterday_start: datetime
    today_start: datetime
    tomorrow_start: datetime


def dashboard_calendar_boundaries(
    *,
    now: datetime,
) -> DashboardCalendarBoundaries:
    """Return yesterday, today, and tomorrow starts in Europe/Stockholm.

    The returned datetimes are timezone-aware local instants. They are
    deliberately independent of Home Assistant's configured timezone.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    local_date = now.astimezone(DASHBOARD_TIMEZONE).date()
    yesterday = local_date - timedelta(days=1)
    tomorrow = local_date + timedelta(days=1)

    return DashboardCalendarBoundaries(
        yesterday_start=datetime.combine(
            yesterday, time.min, tzinfo=DASHBOARD_TIMEZONE
        ),
        today_start=datetime.combine(
            local_date, time.min, tzinfo=DASHBOARD_TIMEZONE
        ),
        tomorrow_start=datetime.combine(
            tomorrow, time.min, tzinfo=DASHBOARD_TIMEZONE
        ),
    )


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


def normalize_history_window(
    *,
    start: datetime,
    end: datetime,
) -> tuple[datetime, datetime]:
    """Normalize and validate a history window without limiting its length."""
    start = normalize_datetime(start)
    end = normalize_datetime(end)
    if end <= start:
        raise ValueError("end must be after start")
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
