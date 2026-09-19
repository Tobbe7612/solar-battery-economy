import importlib.util
from datetime import datetime, timezone
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "analytics.py"
)
spec = importlib.util.spec_from_file_location("sbe_analytics_cumulative", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("Could not load analytics module")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

calculate_positive_cumulative_delta = module.calculate_positive_cumulative_delta


def test_cumulative_delta_uses_latest_state_at_or_before_start():
    start = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
    end = datetime(2026, 9, 18, 13, tzinfo=timezone.utc)

    history = [
        {"timestamp": datetime(2026, 9, 18, 11, 55, tzinfo=timezone.utc), "state": 100},
        {"timestamp": datetime(2026, 9, 18, 12, 30, tzinfo=timezone.utc), "state": 101.2},
        {"timestamp": datetime(2026, 9, 18, 13, 0, tzinfo=timezone.utc), "state": 102.0},
    ]

    assert calculate_positive_cumulative_delta(history, start=start, end=end) == 2.0
