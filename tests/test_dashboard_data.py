import importlib.util
from datetime import datetime, timezone
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "dashboard_data.py"
)

# Load dashboard_data with its package dependencies available through a tiny
# synthetic package so the test remains independent of Home Assistant runtime.
import sys
import types

package = types.ModuleType("custom_components.solar_battery_economy")
package.__path__ = [str(MODULE_PATH.parent)]
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
sys.modules[package.__name__] = package

spec = importlib.util.spec_from_file_location(
    "custom_components.solar_battery_economy.dashboard_data", MODULE_PATH
)
if spec is None or spec.loader is None:
    raise ImportError("Could not load dashboard_data module")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_extract_spot_price_history_accepts_iso_attribute_timestamps():
    recorded = datetime(2026, 9, 19, 10, 2, tzinfo=timezone.utc)
    history = [
        {
            "timestamp": recorded,
            "state": "0.83",
            "attributes": {
                "all_prices": [
                    {
                        "start": "2026-09-19T10:00:00+00:00",
                        "end": "2026-09-19T10:15:00+00:00",
                        "spot": 0.54,
                    }
                ]
            },
        }
    ]

    result = module.extract_spot_price_history(history)

    assert len(result) == 1
    assert result[0]["spot"] == 0.54
    assert result[0]["start"] == datetime(2026, 9, 19, 10, tzinfo=timezone.utc)


def test_extract_spot_price_history_keeps_latest_snapshot_per_interval():
    first = datetime(2026, 9, 19, 10, 1, tzinfo=timezone.utc)
    second = datetime(2026, 9, 19, 10, 14, tzinfo=timezone.utc)
    interval = {
        "start": "2026-09-19T10:00:00+00:00",
        "end": "2026-09-19T10:15:00+00:00",
        "spot": 0.54,
    }
    later_interval = {**interval, "spot": 0.55}

    result = module.extract_spot_price_history(
        [
            {"timestamp": first, "attributes": {"all_prices": [interval]}},
            {"timestamp": second, "attributes": {"all_prices": [later_interval]}},
        ]
    )

    assert len(result) == 1
    assert result[0]["spot"] == 0.55


def test_build_energy_samples_from_statistics_ignores_invalid_change():
    start = datetime(2026, 9, 19, 10, tzinfo=timezone.utc)
    end = datetime(2026, 9, 19, 10, 5, tzinfo=timezone.utc)

    result = module.build_energy_samples_from_statistics(
        [
            {"start": start, "end": end, "change": 0.25},
            {"start": start, "end": end, "change": -1},
            {"start": start, "end": end, "change": "bad"},
        ]
    )

    assert result == [
        {"start": start, "end": end, "energy_kwh": 0.25},
    ]

def test_extract_spot_price_history_reconstructs_intervals_from_all_prices():
    """Spot history should use the recorded all_prices schedule, not state timestamps."""
    schedule = [
        {
            "start": "2026-09-19T00:00:00+02:00",
            "end": "2026-09-19T00:15:00+02:00",
            "spot": 0.10,
            "import": 0.80,
            "export": 0.13,
        },
        {
            "start": "2026-09-19T00:15:00+02:00",
            "end": "2026-09-19T00:30:00+02:00",
            "spot": 0.20,
            "import": 0.90,
            "export": 0.23,
        },
        {
            "start": "2026-09-19T00:30:00+02:00",
            "end": "2026-09-19T00:45:00+02:00",
            "spot": 0.30,
            "import": 1.00,
            "export": 0.33,
        },
        {
            "start": "2026-09-19T00:45:00+02:00",
            "end": "2026-09-19T01:00:00+02:00",
            "spot": 0.40,
            "import": 1.10,
            "export": 0.43,
        },
        {
            "start": "2026-09-19T01:00:00+02:00",
            "end": "2026-09-19T01:15:00+02:00",
            "spot": 0.50,
            "import": 1.20,
            "export": 0.53,
        },
        {
            "start": "2026-09-19T01:15:00+02:00",
            "end": "2026-09-19T01:30:00+02:00",
            "spot": 0.60,
            "import": 1.30,
            "export": 0.63,
        },
    ]

    price_history = [
        {
            "timestamp": datetime.fromisoformat("2026-09-19T00:45:00+02:00"),
            "attributes": {"all_prices": schedule},
        },
        # Deliberately no Recorder state at 01:00.
        {
            "timestamp": datetime.fromisoformat("2026-09-19T01:15:00+02:00"),
            "attributes": {"all_prices": schedule},
        },
    ]

    result = module.extract_spot_price_history(price_history)

    assert len(result) == len(schedule)

    assert [item["start"].isoformat() for item in result] == [
        item["start"] for item in schedule
    ]

    assert [item["spot"] for item in result] == [
        0.10,
        0.20,
        0.30,
        0.40,
        0.50,
        0.60,
    ]

    assert all(
        item["recorded_at"]
        == datetime.fromisoformat("2026-09-19T01:15:00+02:00")
        for item in result
    )


def test_shared_import_price_median_uses_price_history_not_consumer_samples():
    price_history = [
        {"timestamp": datetime(2026, 9, 19, 10, tzinfo=timezone.utc), "state": "0.80"},
        {"timestamp": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc), "state": "1.00"},
        {"timestamp": datetime(2026, 9, 19, 10, 30, tzinfo=timezone.utc), "state": "1.20"},
        {"timestamp": datetime(2026, 9, 19, 10, 45, tzinfo=timezone.utc), "state": "1.40"},
    ]

    assert module.calculate_shared_import_price_median(price_history) == 1.10


def test_build_house_analysis_values_total_house_energy_not_grid_energy():
    house_total_samples = [
        {
            "start": datetime(2026, 9, 19, 10, tzinfo=timezone.utc),
            "end": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
            "energy_kwh": 2.0,
            "import_price": 1.00,
        },
        {
            "start": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
            "end": datetime(2026, 9, 19, 10, 30, tzinfo=timezone.utc),
            "energy_kwh": 3.0,
            "import_price": 2.00,
        },
    ]

    result = module.build_house_analysis(
        house_total_samples,
        reference_price=1.50,
    )

    assert result["consumption_kwh"] == 5.0
    assert result["cost"] == 8.0
    assert result["average_import_price"] == 1.6
    assert result["cheap_usage_percent"] == 40.0
    assert result["expensive_usage_percent"] == 60.0



def test_build_house_analysis_includes_cost_periods():
    samples = [
        {
            "start": datetime(2026, 9, 19, 10, tzinfo=timezone.utc),
            "end": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
            "energy_kwh": 1.0,
            "import_price": 2.0,
        },
        {
            "start": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
            "end": datetime(2026, 9, 19, 10, 30, tzinfo=timezone.utc),
            "energy_kwh": 2.0,
            "import_price": 1.5,
        },
    ]
    result = module.build_house_analysis(samples, reference_price=1.75)
    assert result["highest_cost_period"]["cost"] == 3.0
    assert result["lowest_cost_period"]["cost"] == 2.0


def test_build_house_analysis_includes_battery_contribution():
    house = [{
        "start": datetime(2026, 9, 19, 10, tzinfo=timezone.utc),
        "end": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
        "energy_kwh": 4.0,
        "import_price": 1.0,
    }]
    battery = [{
        "start": datetime(2026, 9, 19, 10, tzinfo=timezone.utc),
        "end": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
        "energy_kwh": 1.0,
        "import_price": 1.0,
    }]
    result = module.build_house_analysis(
        house, reference_price=1.0, battery_house_samples=battery
    )
    assert result["battery_contribution_percent"] == 25.0


def test_build_consumer_dashboard_data_includes_share_and_alignment():
    house = [{"energy_kwh": 10.0, "import_price": 1.0}]
    consumer = [{"energy_kwh": 2.0, "import_price": 0.5}]
    result = module.build_consumer_dashboard_data(
        name="Test",
        energy_entity="sensor.test",
        samples=consumer,
        reference_price=1.0,
        house_total_samples=house,
        house_average_import_price=1.0,
    )
    assert result["analysis"]["share_percent"] == 20.0
    assert result["analysis"]["price_alignment_delta"] == 0.5


def test_build_house_analysis_includes_smart_score():
    house = [
        {
            "start": datetime(2026, 9, 19, 10, tzinfo=timezone.utc),
            "end": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
            "energy_kwh": 4.0,
            "import_price": 0.8,
        },
        {
            "start": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
            "end": datetime(2026, 9, 19, 10, 30, tzinfo=timezone.utc),
            "energy_kwh": 1.0,
            "import_price": 1.2,
        },
    ]
    battery = [
        {
            "start": datetime(2026, 9, 19, 10, tzinfo=timezone.utc),
            "end": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
            "energy_kwh": 1.0,
            "import_price": 0.8,
        },
        {
            "start": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
            "end": datetime(2026, 9, 19, 10, 30, tzinfo=timezone.utc),
            "energy_kwh": 0.0,
            "import_price": 1.2,
        },
    ]

    result = module.build_house_analysis(
        house,
        reference_price=1.0,
        battery_house_samples=battery,
    )

    assert result["cheap_usage_percent"] == 80.0
    assert result["expensive_usage_percent"] == 20.0
    assert result["battery_contribution_percent"] == 20.0
    assert result["smart_score"] == 68.0


def test_build_house_analysis_smart_score_unavailable_without_battery_data():
    house = [
        {
            "start": datetime(2026, 9, 19, 10, tzinfo=timezone.utc),
            "end": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
            "energy_kwh": 1.0,
            "import_price": 1.0,
        }
    ]

    result = module.build_house_analysis(
        house,
        reference_price=1.0,
        battery_house_samples=None,
    )

    assert result["battery_contribution_percent"] is None
    assert result["smart_score"] is None


def test_build_consumer_dashboard_data_includes_recorder_resolved_events():
    house = [{"energy_kwh": 10.0, "import_price": 1.0}]
    consumer = [
        {
            "start": datetime(2026, 9, 19, 10, tzinfo=timezone.utc),
            "end": datetime(2026, 9, 19, 10, 5, tzinfo=timezone.utc),
            "energy_kwh": 0.2,
            "import_price": 1.0,
        },
        {
            "start": datetime(2026, 9, 19, 10, 5, tzinfo=timezone.utc),
            "end": datetime(2026, 9, 19, 10, 10, tzinfo=timezone.utc),
            "energy_kwh": 0.3,
            "import_price": 1.0,
        },
        {
            "start": datetime(2026, 9, 19, 10, 15, tzinfo=timezone.utc),
            "end": datetime(2026, 9, 19, 10, 20, tzinfo=timezone.utc),
            "energy_kwh": 0.4,
            "import_price": 1.0,
        },
    ]

    result = module.build_consumer_dashboard_data(
        name="Test",
        energy_entity="sensor.test",
        samples=consumer,
        reference_price=1.0,
        house_total_samples=house,
        house_average_import_price=1.0,
    )

    assert len(result["events"]) == 2
    assert result["events"][0]["consumer_id"] == "sensor.test"
    assert result["events"][0]["energy_kwh"] == 0.5
    assert result["events"][1]["energy_kwh"] == 0.4
