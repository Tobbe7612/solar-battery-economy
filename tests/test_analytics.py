import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "analytics.py"
)
spec = importlib.util.spec_from_file_location("sbe_analytics", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError("Could not load analytics module")
analytics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analytics)

calculate_consumption_cost = analytics.calculate_consumption_cost
calculate_consumption_share_above_median = analytics.calculate_consumption_share_above_median
calculate_consumption_share_below_median = analytics.calculate_consumption_share_below_median
calculate_import_price_median = analytics.calculate_import_price_median
calculate_weighted_average_import_price = analytics.calculate_weighted_average_import_price


def samples():
    return [
        {"energy_kwh": 2, "import_price": 1.0},
        {"energy_kwh": 1, "import_price": 2.0},
        {"energy_kwh": 3, "import_price": 3.0},
    ]


def test_import_price_median():
    assert calculate_import_price_median(samples()) == 2.0


def test_consumption_cost_uses_total_import_price():
    assert calculate_consumption_cost(samples()) == 13.0


def test_weighted_average_import_price():
    assert calculate_weighted_average_import_price(samples()) == 2.1667


def test_share_below_median_is_energy_weighted():
    assert calculate_consumption_share_below_median(samples()) == 33.33


def test_share_above_median_is_energy_weighted():
    assert calculate_consumption_share_above_median(samples()) == 50.0


def test_invalid_samples_are_ignored():
    assert calculate_consumption_cost([{"energy_kwh": "bad", "import_price": 1}]) == 0

from datetime import datetime, timezone

build_price_aligned_energy_samples = analytics.build_price_aligned_energy_samples
calculate_consumer_analysis = analytics.calculate_consumer_analysis
calculate_cumulative_cost_from_history = analytics.calculate_cumulative_cost_from_history


def test_consumer_analysis_uses_total_import_price():
    result = calculate_consumer_analysis(samples())
    assert result["energy_kwh"] == 6.0
    assert result["cost"] == 13.0
    assert result["average_import_price"] == 2.1667
    assert result["cheap_usage_percent"] == 33.33
    assert result["expensive_usage_percent"] == 50.0


def test_cumulative_cost_history_uses_window_delta():
    history = [
        {"timestamp": datetime(2026, 9, 19, 10, 30, tzinfo=timezone.utc), "state": "10"},
        {"timestamp": datetime(2026, 9, 19, 11, 0, tzinfo=timezone.utc), "state": "11.5"},
        {"timestamp": datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc), "state": "13"},
    ]
    assert calculate_cumulative_cost_from_history(
        history,
        start=datetime(2026, 9, 19, 10, 30, tzinfo=timezone.utc),
        end=datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc),
    ) == 3.0


def test_price_aligned_energy_samples_reject_cross_price_boundary():
    energy = [
        {"timestamp": datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc), "state": "10"},
        {"timestamp": datetime(2026, 9, 19, 10, 30, tzinfo=timezone.utc), "state": "10.5"},
    ]
    prices = [
        {"timestamp": datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc), "state": "1.0"},
        {"timestamp": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc), "state": "2.0"},
    ]
    assert build_price_aligned_energy_samples(
        energy,
        prices,
        start=datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc),
        end=datetime(2026, 9, 19, 10, 30, tzinfo=timezone.utc),
    ) == []


def test_price_aligned_energy_samples_values_single_price_interval():
    energy = [
        {"timestamp": datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc), "state": "10"},
        {"timestamp": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc), "state": "10.5"},
    ]
    prices = [
        {"timestamp": datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc), "state": "1.0"},
    ]
    result = build_price_aligned_energy_samples(
        energy,
        prices,
        start=datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc),
        end=datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
    )
    assert result == [{
        "start": datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc),
        "end": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
        "energy_kwh": 0.5,
        "import_price": 1.0,
    }]


def test_price_aligned_energy_uses_latest_baseline_before_start():
    energy_stats = [
        {
            "start": datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc),
            "end": datetime(2026, 9, 19, 10, 5, tzinfo=timezone.utc),
            "change": 0.25,
        }
    ]
    price_history = [
        {
            "timestamp": datetime(2026, 9, 19, 9, 45, tzinfo=timezone.utc),
            "state": "1.0",
        }
    ]
    result = analytics.build_statistics_energy_samples_with_price_history(
        energy_stats, price_history
    )
    assert result[0]["import_price"] == 1.0
    assert result[0]["energy_kwh"] == 0.25


def test_price_aligned_statistics_skip_bucket_crossing_price_change():
    energy_stats = [
        {
            "start": datetime(2026, 9, 19, 10, 10, tzinfo=timezone.utc),
            "end": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
            "change": 0.25,
        }
    ]
    price_history = [
        {
            "timestamp": datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc),
            "state": "1.0",
        },
        {
            "timestamp": datetime(2026, 9, 19, 10, 12, tzinfo=timezone.utc),
            "state": "2.0",
        },
    ]
    assert analytics.build_statistics_energy_samples_with_price_history(
        energy_stats, price_history
    ) == []


def test_stat_start_value_normalizes_numeric_timestamp_as_utc():
    timestamp = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc).timestamp()

    result = analytics.stat_start_value(
        {"start": timestamp},
        "start",
    )

    assert result == datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)
