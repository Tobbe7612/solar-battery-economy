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
build_statistics_samples = module.build_statistics_samples


def test_clamp_history_window_limits_to_24_hours():
    end = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)
    start = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)

    actual_start, actual_end = clamp_history_window(start=start, end=end)

    assert actual_end == end
    assert actual_start == datetime(2026, 9, 18, 12, tzinfo=timezone.utc)


def test_statistics_samples_align_energy_change_and_price_mean():
    start = datetime(2026, 9, 19, 10, tzinfo=timezone.utc)
    end = datetime(2026, 9, 19, 10, 5, tzinfo=timezone.utc)

    samples = build_statistics_samples(
        [{"start": start, "end": end, "change": 0.25}],
        [{"start": start, "end": end, "mean": 0.83}],
    )

    assert samples == [
        {
            "start": start,
            "end": end,
            "energy_kwh": 0.25,
            "import_price": 0.83,
        }
    ]


def test_statistics_samples_skip_missing_price():
    start = datetime(2026, 9, 19, 10, tzinfo=timezone.utc)
    end = datetime(2026, 9, 19, 10, 5, tzinfo=timezone.utc)

    assert build_statistics_samples(
        [{"start": start, "end": end, "change": 0.25}],
        [],
    ) == []


def test_statistics_samples_skip_negative_energy_change():
    start = datetime(2026, 9, 19, 10, tzinfo=timezone.utc)
    end = datetime(2026, 9, 19, 10, 5, tzinfo=timezone.utc)

    assert build_statistics_samples(
        [{"start": start, "end": end, "change": -1}],
        [{"start": start, "end": end, "mean": 0.83}],
    ) == []


def test_normalize_history_states_accepts_plain_dicts():
    timestamp = datetime(2026, 9, 19, 10, tzinfo=timezone.utc)
    assert module.normalize_history_states(
        [{"last_updated": timestamp, "state": "123.4"}]
    ) == [{"timestamp": timestamp, "state": "123.4"}]


def test_normalize_history_states_sorts_and_ignores_missing_timestamp():
    first = datetime(2026, 9, 19, 10, tzinfo=timezone.utc)
    second = datetime(2026, 9, 19, 11, tzinfo=timezone.utc)
    assert module.normalize_history_states(
        [
            {"last_updated": second, "state": "2"},
            {"state": "bad"},
            {"last_updated": first, "state": "1"},
        ]
    ) == [
        {"timestamp": first, "state": "1"},
        {"timestamp": second, "state": "2"},
    ]
