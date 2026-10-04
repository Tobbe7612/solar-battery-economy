import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

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


ENERGY_KEYS = (
    "solar_house",
    "solar_battery",
    "solar_export",
    "grid_battery",
    "battery_house",
    "battery_grid",
)


def _energy_entities():
    return {key: f"sensor.custom_prefix_energy_{key}" for key in ENERGY_KEYS}


def _energy_stats(entities, intervals):
    return {
        entities[key]: [
            {"start": start, "end": end, "change": amount}
            for start, end, amount in intervals
        ]
        for key in ENERGY_KEYS
    }


def test_periodized_energy_filters_yesterday_today_and_now_boundaries():
    entities = _energy_entities()
    yesterday_start = datetime(2026, 10, 3, 22, tzinfo=timezone.utc)
    today_start = datetime(2026, 10, 4, 22, tzinfo=timezone.utc)
    now = today_start + timedelta(minutes=10)
    intervals = [
        (yesterday_start - timedelta(minutes=5), yesterday_start, 100.0),
        (yesterday_start, yesterday_start + timedelta(minutes=5), 1.0),
        (yesterday_start + timedelta(minutes=5), today_start, 2.0),
        (today_start, today_start + timedelta(minutes=5), 3.0),
        (today_start + timedelta(minutes=5), now, 4.0),
        (now, now + timedelta(minutes=5), 200.0),
    ]

    result = module.build_periodized_energy_data(
        _energy_stats(entities, intervals),
        entities,
        yesterday_start=yesterday_start,
        today_start=today_start,
        now=now,
    )

    assert result["yesterday"]["solar"]["to_house_kwh"] == 3.0
    assert result["today"]["solar"]["to_house_kwh"] == 7.0
    assert result["yesterday"]["solar"]["total_kwh"] == 9.0
    assert result["today"]["battery"]["to_grid_kwh"] == 7.0


def test_periodized_energy_tomorrow_is_null_without_statistics():
    result = module.build_periodized_energy_data(
        {},
        _energy_entities(),
        yesterday_start=datetime(2026, 10, 3, tzinfo=timezone.utc),
        today_start=datetime(2026, 10, 4, tzinfo=timezone.utc),
        now=datetime(2026, 10, 4, 12, tzinfo=timezone.utc),
    )

    assert result["tomorrow"] == {
        "solar": {
            "total_kwh": None,
            "to_house_kwh": None,
            "to_battery_kwh": None,
            "to_grid_kwh": None,
        },
        "battery": {
            "charged_kwh": None,
            "discharged_kwh": None,
            "to_house_kwh": None,
            "to_grid_kwh": None,
        },
    }


def test_periodized_energy_missing_statistics_stay_null_without_zero_fills():
    entities = _energy_entities()
    start = datetime(2026, 10, 3, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    stats = _energy_stats(
        entities,
        [(start, start + timedelta(minutes=5), 2.5)],
    )
    stats[entities["solar_export"]] = []

    result = module.build_periodized_energy_data(
        stats,
        entities,
        yesterday_start=start,
        today_start=end,
        now=end + timedelta(hours=1),
    )

    solar = result["yesterday"]["solar"]
    assert solar["to_house_kwh"] == 2.5
    assert solar["to_grid_kwh"] is None
    assert solar["total_kwh"] is None
    assert result["yesterday"]["battery"]["charged_kwh"] == 5.0


def test_periodized_energy_sums_solar_and_battery_flows_exactly():
    entities = _energy_entities()
    start = datetime(2026, 10, 3, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    amounts = {
        "solar_house": 1.1,
        "solar_battery": 2.2,
        "solar_export": 3.3,
        "grid_battery": 4.4,
        "battery_house": 5.5,
        "battery_grid": 6.6,
    }
    stats = {
        entities[key]: [{"start": start, "end": start + timedelta(minutes=5), "change": value}]
        for key, value in amounts.items()
    }

    result = module.build_periodized_energy_data(
        stats,
        entities,
        yesterday_start=start,
        today_start=end,
        now=end,
    )

    assert result["yesterday"]["solar"] == {
        "total_kwh": 6.6,
        "to_house_kwh": 1.1,
        "to_battery_kwh": 2.2,
        "to_grid_kwh": 3.3,
    }
    assert result["yesterday"]["battery"] == {
        "charged_kwh": 6.6,
        "discharged_kwh": 12.1,
        "to_house_kwh": 5.5,
        "to_grid_kwh": 6.6,
    }


def test_periodized_energy_covers_23_hour_dst_day():
    zone = ZoneInfo("Europe/Stockholm")
    start = datetime(2026, 3, 29, tzinfo=zone)
    end = datetime(2026, 3, 30, tzinfo=zone)
    entities = _energy_entities()
    intervals = []
    cursor = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    while cursor < end_utc:
        next_cursor = cursor + timedelta(minutes=5)
        intervals.append((cursor, next_cursor, 0.01))
        cursor = next_cursor

    result = module.build_periodized_energy_data(
        _energy_stats(entities, intervals),
        entities,
        yesterday_start=start,
        today_start=end,
        now=end,
    )

    assert (end_utc - start.astimezone(timezone.utc)) == timedelta(hours=23)
    assert result["yesterday"]["solar"]["to_house_kwh"] == 2.76


def test_periodized_energy_covers_25_hour_dst_day():
    zone = ZoneInfo("Europe/Stockholm")
    start = datetime(2026, 10, 25, tzinfo=zone)
    end = datetime(2026, 10, 26, tzinfo=zone)
    entities = _energy_entities()
    intervals = []
    cursor = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    while cursor < end_utc:
        next_cursor = cursor + timedelta(minutes=5)
        intervals.append((cursor, next_cursor, 0.01))
        cursor = next_cursor

    result = module.build_periodized_energy_data(
        _energy_stats(entities, intervals),
        entities,
        yesterday_start=start,
        today_start=end,
        now=end,
    )

    assert (end_utc - start.astimezone(timezone.utc)) == timedelta(hours=25)
    assert result["yesterday"]["solar"]["to_house_kwh"] == 3.0


def test_select_price_intervals_window_keeps_overlapping_boundary_interval():
    analysis_start = datetime(2026, 9, 29, 8, tzinfo=timezone.utc)
    analysis_end = datetime(2026, 9, 30, 8, tzinfo=timezone.utc)
    intervals = [
        {
            "start": analysis_start - timedelta(minutes=10),
            "end": analysis_start + timedelta(minutes=5),
            "import": 0.5,
        },
        {
            "start": analysis_start,
            "end": analysis_start + timedelta(minutes=15),
            "import": 1.0,
        },
        {
            "start": analysis_end,
            "end": analysis_end + timedelta(minutes=15),
            "import": 1.5,
        },
    ]

    selected = module.select_price_intervals_window(
        intervals,
        start=analysis_start,
        end=analysis_end,
    )

    assert selected == intervals[:2]


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
