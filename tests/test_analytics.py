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


def test_consumer_analysis_uses_shared_reference_price_for_classification():
    consumer_samples = [
        {"energy_kwh": 1.0, "import_price": 0.80},
        {"energy_kwh": 1.0, "import_price": 1.00},
    ]

    result = calculate_consumer_analysis(
        consumer_samples,
        reference_price=1.20,
    )

    assert result["cheap_usage_percent"] == 100.0
    assert result["expensive_usage_percent"] == 0.0



def test_highest_cost_period_uses_actual_energy_cost_not_price():
    samples = [
        {"start": datetime(2026, 9, 19, 10, tzinfo=timezone.utc), "end": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc), "energy_kwh": 1.0, "import_price": 2.0},
        {"start": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc), "end": datetime(2026, 9, 19, 10, 30, tzinfo=timezone.utc), "energy_kwh": 2.0, "import_price": 1.5},
    ]
    result = analytics.calculate_highest_cost_period(samples)
    assert result["start"] == datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc)
    assert result["cost"] == 3.0


def test_lowest_cost_period_excludes_zero_energy_and_missing_price():
    samples = [
        {"start": datetime(2026, 9, 19, 10, tzinfo=timezone.utc), "end": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc), "energy_kwh": 0.0, "import_price": 0.01},
        {"start": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc), "end": datetime(2026, 9, 19, 10, 30, tzinfo=timezone.utc), "energy_kwh": 1.0, "import_price": 1.0},
        {"start": datetime(2026, 9, 19, 10, 30, tzinfo=timezone.utc), "end": datetime(2026, 9, 19, 10, 45, tzinfo=timezone.utc), "energy_kwh": 1.0, "import_price": "unknown"},
    ]
    result = analytics.calculate_lowest_cost_period(samples)
    assert result["start"] == datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc)


def test_cost_period_tie_uses_earliest_interval():
    samples = [
        {"start": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc), "end": datetime(2026, 9, 19, 10, 30, tzinfo=timezone.utc), "energy_kwh": 1.0, "import_price": 1.0},
        {"start": datetime(2026, 9, 19, 10, tzinfo=timezone.utc), "end": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc), "energy_kwh": 1.0, "import_price": 1.0},
    ]
    result = analytics.calculate_highest_cost_period(samples)
    assert result["start"] == datetime(2026, 9, 19, 10, tzinfo=timezone.utc)


def test_battery_contribution_is_house_energy_share_and_zero_is_valid():
    house = [{"energy_kwh": 10.0, "import_price": 1.0}]
    battery = [{"energy_kwh": 2.5, "import_price": 1.0}]
    assert analytics.calculate_battery_contribution_percent(house, battery) == 25.0
    assert analytics.calculate_battery_contribution_percent(house, []) == 0.0


def test_battery_contribution_is_unavailable_when_house_energy_is_zero():
    assert analytics.calculate_battery_contribution_percent(
        [{"energy_kwh": 0.0, "import_price": 1.0}],
        [{"energy_kwh": 1.0, "import_price": 1.0}],
    ) is None


def test_consumer_share_is_energy_share_not_cost_share():
    house = [{"energy_kwh": 10.0, "import_price": 2.0}]
    consumer = [{"energy_kwh": 2.0, "import_price": 0.5}]
    assert analytics.calculate_consumer_share_percent(consumer, house) == 20.0


def test_consumer_share_is_unavailable_when_house_energy_is_zero():
    assert analytics.calculate_consumer_share_percent(
        [{"energy_kwh": 1.0, "import_price": 1.0}],
        [{"energy_kwh": 0.0, "import_price": 1.0}],
    ) is None


def test_consumer_price_alignment_is_house_minus_consumer():
    assert analytics.calculate_consumer_price_alignment(1.00, 0.80) == 0.20
    assert analytics.calculate_consumer_price_alignment(0.80, 1.00) == -0.20
    assert analytics.calculate_consumer_price_alignment(1.00, 1.00) == 0.0


def test_consumer_price_alignment_is_unavailable_without_both_averages():
    assert analytics.calculate_consumer_price_alignment(None, 0.8) is None
    assert analytics.calculate_consumer_price_alignment(1.0, None) is None


def test_smart_score_uses_approved_v1_weights():
    assert analytics.calculate_smart_score(50.0, 20.0, 30.0) == 58.0


def test_smart_score_is_unavailable_without_valid_price_data():
    assert analytics.calculate_smart_score(None, 20.0, 30.0) is None
    assert analytics.calculate_smart_score(50.0, None, 30.0) is None


def test_smart_score_is_unavailable_without_battery_data():
    assert analytics.calculate_smart_score(50.0, 20.0, None) is None


def test_smart_score_is_bounded_to_zero_to_hundred():
    assert analytics.calculate_smart_score(100.0, 0.0, 100.0) == 100.0
    assert analytics.calculate_smart_score(0.0, 100.0, 0.0) == 0.0
    assert analytics.calculate_smart_score(100.0, 0.0, 200.0) == 100.0


def test_deterministic_insights_are_descriptive_and_stable():
    house = {
        "cheap_usage_percent": 40.0,
        "expensive_usage_percent": 30.0,
        "highest_cost_period": {"start": datetime(2026, 9, 19, 10, tzinfo=timezone.utc), "end": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc), "energy_kwh": 2.0, "import_price": 2.0, "cost": 4.0},
        "lowest_cost_period": {"start": datetime(2026, 9, 19, 11, tzinfo=timezone.utc), "end": datetime(2026, 9, 19, 11, 15, tzinfo=timezone.utc), "energy_kwh": 0.5, "import_price": 1.0, "cost": 0.5},
    }
    consumers = {
        "sensor.ev": {
            "name": "Elbil",
            "analysis": {
                "energy_kwh": 3.0,
                "cost": 2.5,
                "average_import_price": 0.8333,
                "share_percent": 25.0,
                "price_alignment_delta": 0.1667,
            },
        }
    }
    result = analytics.build_deterministic_insights(house, consumers)
    assert [item["type"] for item in result] == [
        "cheap_consumption", "expensive_consumption",
        "highest_cost_period", "lowest_cost_period", "consumer_cost",
        "consumer_share", "consumer_price_alignment",
    ]
    assert result[-1]["consumer_id"] == "sensor.ev"
    assert result[4] == {
        "type": "consumer_cost",
        "consumer_id": "sensor.ev",
        "name": "Elbil",
        "energy_kwh": 3.0,
        "cost": 2.5,
        "average_import_price": 0.8333,
    }
    assert result[5] == {
        "type": "consumer_share",
        "consumer_id": "sensor.ev",
        "name": "Elbil",
        "share_percent": 25.0,
    }
    assert result[6] == {
        "type": "consumer_price_alignment",
        "consumer_id": "sensor.ev",
        "name": "Elbil",
        "price_alignment_delta": 0.1667,
    }


def test_deterministic_insights_skip_unavailable_consumer_facts():
    consumers = {
        "sensor.ev": {
            "name": "Elbil",
            "analysis": {
                "cost": 2.5,
                "share_percent": None,
                "price_alignment_delta": None,
            },
        }
    }

    result = analytics.build_deterministic_insights({}, consumers)

    assert [item["type"] for item in result] == ["consumer_cost"]


def test_deterministic_insights_do_not_create_missing_facts():
    assert analytics.build_deterministic_insights({}, {}) == []


def test_build_consumer_events_merges_touching_positive_intervals():
    from datetime import datetime, timezone
    from custom_components.solar_battery_economy.analytics import build_consumer_events

    tz = timezone.utc
    samples = [
        {"start": datetime(2026, 9, 20, 10, 0, tzinfo=tz), "end": datetime(2026, 9, 20, 10, 5, tzinfo=tz), "energy_kwh": 0.2},
        {"start": datetime(2026, 9, 20, 10, 5, tzinfo=tz), "end": datetime(2026, 9, 20, 10, 10, tzinfo=tz), "energy_kwh": 0.3},
        {"start": datetime(2026, 9, 20, 10, 10, tzinfo=tz), "end": datetime(2026, 9, 20, 10, 15, tzinfo=tz), "energy_kwh": 0.0},
        {"start": datetime(2026, 9, 20, 10, 20, tzinfo=tz), "end": datetime(2026, 9, 20, 10, 25, tzinfo=tz), "energy_kwh": 0.4},
    ]

    events = build_consumer_events(samples, consumer_id="sensor.test")

    assert len(events) == 2
    assert events[0]["consumer_id"] == "sensor.test"
    assert events[0]["start"] == samples[0]["start"]
    assert events[0]["end"] == samples[1]["end"]
    assert events[0]["energy_kwh"] == 0.5
    assert events[1]["start"] == samples[3]["start"]
    assert events[1]["energy_kwh"] == 0.4


def test_build_consumer_events_does_not_invent_timing_from_invalid_intervals():
    from datetime import datetime, timezone
    from custom_components.solar_battery_economy.analytics import build_consumer_events

    tz = timezone.utc
    samples = [
        {"start": datetime(2026, 9, 20, 10, 0, tzinfo=tz), "end": datetime(2026, 9, 20, 10, 5, tzinfo=tz), "energy_kwh": "unknown"},
        {"start": datetime(2026, 9, 20, 10, 5, tzinfo=tz), "end": datetime(2026, 9, 20, 10, 10, tzinfo=tz), "energy_kwh": -0.1},
    ]

    assert build_consumer_events(samples, consumer_id="sensor.test") == []
