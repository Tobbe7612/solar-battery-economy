import importlib.util
from datetime import datetime, timezone
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


def test_clamp_history_window_limits_to_24_hours():
    end = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)
    start = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)

    actual_start, actual_end = clamp_history_window(start=start, end=end)

    assert actual_end == end
    assert actual_start == datetime(2026, 9, 18, 12, tzinfo=timezone.utc)
