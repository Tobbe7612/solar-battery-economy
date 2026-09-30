import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "recorder_data.py"
)
spec = importlib.util.spec_from_file_location("sbe_recorder_data", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("Could not load recorder_data module")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


clamp_history_window = module.clamp_history_window
normalize_history_window = module.normalize_history_window
dashboard_calendar_boundaries = module.dashboard_calendar_boundaries


def test_clamp_history_window_limits_to_24_hours():
    end = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)
    start = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)

    actual_start, actual_end = clamp_history_window(start=start, end=end)

    assert actual_end == end
    assert actual_start == datetime(2026, 9, 18, 12, tzinfo=timezone.utc)


def test_normalize_history_window_preserves_extended_period():
    start = datetime(2026, 9, 28, 22, tzinfo=timezone.utc)
    end = datetime(2026, 9, 30, 8, tzinfo=timezone.utc)

    actual_start, actual_end = normalize_history_window(start=start, end=end)

    assert actual_start == start
    assert actual_end == end
    assert actual_end - actual_start > module.MAX_HISTORY


def _elapsed_hours(start: datetime, end: datetime) -> float:
    elapsed = end.astimezone(timezone.utc) - start.astimezone(timezone.utc)
    return elapsed.total_seconds() / 3600


def test_dashboard_calendar_boundaries_use_stockholm_local_midnights():
    now = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)

    boundaries = dashboard_calendar_boundaries(now=now)

    assert boundaries.yesterday_start.isoformat() == "2026-09-29T00:00:00+02:00"
    assert boundaries.today_start.isoformat() == "2026-09-30T00:00:00+02:00"
    assert boundaries.tomorrow_start.isoformat() == "2026-10-01T00:00:00+02:00"
    assert _elapsed_hours(boundaries.yesterday_start, boundaries.today_start) == 24


def test_dashboard_calendar_boundaries_cover_23_hour_spring_dst_day():
    now = datetime(2026, 3, 30, 12, tzinfo=timezone.utc)

    boundaries = dashboard_calendar_boundaries(now=now)

    assert boundaries.yesterday_start.isoformat() == "2026-03-29T00:00:00+01:00"
    assert boundaries.today_start.isoformat() == "2026-03-30T00:00:00+02:00"
    assert _elapsed_hours(boundaries.yesterday_start, boundaries.today_start) == 23


def test_dashboard_calendar_boundaries_cover_25_hour_autumn_dst_day():
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)

    boundaries = dashboard_calendar_boundaries(now=now)

    assert boundaries.yesterday_start.isoformat() == "2026-10-25T00:00:00+02:00"
    assert boundaries.today_start.isoformat() == "2026-10-26T00:00:00+01:00"
    assert _elapsed_hours(boundaries.yesterday_start, boundaries.today_start) == 25


def test_dashboard_calendar_boundaries_ignore_input_timezone():
    utc_now = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)
    other_zone_now = utc_now.astimezone(timezone(timedelta(hours=9)))

    utc_boundaries = dashboard_calendar_boundaries(now=utc_now)
    other_zone_boundaries = dashboard_calendar_boundaries(now=other_zone_now)

    assert other_zone_boundaries == utc_boundaries
    assert other_zone_boundaries.today_start.isoformat() == "2026-09-30T00:00:00+02:00"
