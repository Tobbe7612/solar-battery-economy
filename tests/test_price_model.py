from datetime import datetime
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "price_model.py"
)

spec = importlib.util.spec_from_file_location(
    "solar_battery_economy_price_model",
    MODULE_PATH,
)

if spec is None or spec.loader is None:
    raise ImportError(f"Could not load module from {MODULE_PATH}")

price_model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(price_model)

find_cheapest_future_period = price_model.find_cheapest_future_period
normalize_nordpool_price_indices = price_model.normalize_nordpool_price_indices
build_nordpool_price_model = price_model.build_nordpool_price_model
enrich_nordpool_price_intervals = price_model.enrich_nordpool_price_intervals


def test_nordpool_adapter_converts_sek_per_mwh_and_preserves_intervals():
    result = normalize_nordpool_price_indices(
        [
            {
                "start": "2026-09-28T10:00:00+02:00",
                "end": "2026-09-28T10:15:00+02:00",
                "price": 669.68,
            },
            {
                "start": "2026-09-28T10:15:00+02:00",
                "end": "2026-09-28T10:30:00+02:00",
                "price": 700.0,
            },
        ]
    )

    assert [interval["start"] for interval in result] == [
        datetime.fromisoformat("2026-09-28T10:00:00+02:00"),
        datetime.fromisoformat("2026-09-28T10:15:00+02:00"),
    ]
    assert [interval["end"] for interval in result] == [
        datetime.fromisoformat("2026-09-28T10:15:00+02:00"),
        datetime.fromisoformat("2026-09-28T10:30:00+02:00"),
    ]
    assert [interval["spot"] for interval in result] == pytest.approx(
        [0.66968, 0.7]
    )
    assert all(set(interval) == {"start", "end", "spot"} for interval in result)


def test_nordpool_adapter_skips_invalid_rows():
    result = normalize_nordpool_price_indices(
        [
            None,
            {"start": "bad", "end": "2026-09-28T10:15:00+02:00", "price": 20},
            {"start": "2026-09-28T10:00:00+02:00", "end": "2026-09-28T10:15:00+02:00"},
            {"start": "2026-09-28T10:15:00+02:00", "end": "2026-09-28T10:30:00+02:00", "price": "bad"},
            {"start": "2026-09-28T10:30:00+02:00", "end": "2026-09-28T10:45:00+02:00", "price": 500},
        ]
    )

    assert len(result) == 1
    assert result[0]["spot"] == 0.5


def test_nordpool_adapter_returns_empty_list_for_empty_or_unexpected_result():
    assert normalize_nordpool_price_indices([]) == []
    assert normalize_nordpool_price_indices(None) == []
    assert normalize_nordpool_price_indices({"price_indices": []}) == []


def test_nordpool_price_model_includes_today_and_tomorrow_spot_intervals():
    today_start = datetime.fromisoformat("2026-09-28T10:00:00+02:00")
    today_end = datetime.fromisoformat("2026-09-28T10:15:00+02:00")
    tomorrow_start = datetime.fromisoformat("2026-09-29T10:00:00+02:00")
    tomorrow_end = datetime.fromisoformat("2026-09-29T10:15:00+02:00")
    today = {"start": today_start, "end": today_end, "spot": 0.5}
    tomorrow = {"start": tomorrow_start, "end": tomorrow_end, "spot": 0.7}

    result = build_nordpool_price_model(
        {"today": [today], "tomorrow": [tomorrow]},
        now=datetime.fromisoformat("2026-09-28T10:07:00+02:00"),
    )

    assert result["current"]["start"] == today_start
    assert result["current"]["end"] == today_end
    assert [item["spot"] for item in result["forecast"]] == [0.5, 0.7]
    assert result["current"]["import"] == pytest.approx(
        ((0.5 + 0.1267 + 0.36) * 1.25) + 0.14875
    )
    assert result["current"]["export"] == pytest.approx(0.5 + 0.033)
    assert result["current"]["price_class"] == "CHEAP"
    assert result["current"]["price_quality"] == 76.1
    assert set(result["current"]) == {
        "start",
        "end",
        "spot",
        "import",
        "export",
        "price_class",
        "price_quality",
    }


def test_spot_enrichment_applies_vat_to_spot_and_import_components():
    result = enrich_nordpool_price_intervals(
        [{"start": datetime(2026, 9, 28, 10), "end": datetime(2026, 9, 28, 10, 15), "spot": 0.5}]
    )[0]

    assert result["import"] == pytest.approx(1.382125)
    assert result["export"] == pytest.approx(0.533)


def test_nordpool_model_selects_current_interval_end_exclusively():
    intervals = [
        {
            "start": datetime(2026, 9, 28, 10),
            "end": datetime(2026, 9, 28, 10, 15),
            "spot": 0.5,
        },
        {
            "start": datetime(2026, 9, 28, 10, 15),
            "end": datetime(2026, 9, 28, 10, 30),
            "spot": 0.6,
        },
    ]
    model = build_nordpool_price_model(
        {"today": intervals, "tomorrow": []},
        now=datetime(2026, 9, 28, 10, 15),
    )

    assert model["current"]["spot"] == 0.6
    assert model["current"]["import"] == pytest.approx(
        ((0.6 + 0.1267 + 0.36) * 1.25) + 0.14875
    )


def test_empty_nordpool_data_builds_empty_price_model():
    result = build_nordpool_price_model(
        {"today": [], "tomorrow": []},
        now=datetime(2026, 9, 28, 10),
    )

    assert result == {"current": None, "forecast": []}


def test_find_cheapest_future_15_minute_period():
    from datetime import datetime

    forecast = [
        {
            "start": datetime(2026, 9, 11, 10, 0),
            "end": datetime(2026, 9, 11, 10, 15),
            "import": 1.20,
        },
        {
            "start": datetime(2026, 9, 11, 10, 15),
            "end": datetime(2026, 9, 11, 10, 30),
            "import": 0.80,
        },
        {
            "start": datetime(2026, 9, 11, 10, 30),
            "end": datetime(2026, 9, 11, 10, 45),
            "import": 1.00,
        },
    ]

    result = find_cheapest_future_period(
        forecast,
        now=datetime(2026, 9, 11, 10, 0),
        duration_minutes=15,
        selection_mode="consecutive",
    )

    assert result is not None
    assert result["duration_minutes"] == 15
    assert result["selection_mode"] == "consecutive"
    assert result["start"] == datetime(2026, 9, 11, 10, 15)
    assert result["end"] == datetime(2026, 9, 11, 10, 30)
    assert result["average_import_price"] == 0.80

def test_find_cheapest_future_two_hours_consecutive():
    forecast = [
        {
            "start": datetime(2026, 9, 11, 10, 0),
            "end": datetime(2026, 9, 11, 10, 15),
            "import": 1.50,
        },
        {
            "start": datetime(2026, 9, 11, 10, 15),
            "end": datetime(2026, 9, 11, 10, 30),
            "import": 1.40,
        },
        {
            "start": datetime(2026, 9, 11, 10, 30),
            "end": datetime(2026, 9, 11, 10, 45),
            "import": 1.30,
        },
        {
            "start": datetime(2026, 9, 11, 10, 45),
            "end": datetime(2026, 9, 11, 11, 0),
            "import": 1.20,
        },
        {
            "start": datetime(2026, 9, 11, 11, 0),
            "end": datetime(2026, 9, 11, 11, 15),
            "import": 0.50,
        },
        {
            "start": datetime(2026, 9, 11, 11, 15),
            "end": datetime(2026, 9, 11, 11, 30),
            "import": 0.40,
        },
        {
            "start": datetime(2026, 9, 11, 11, 30),
            "end": datetime(2026, 9, 11, 11, 45),
            "import": 0.30,
        },
        {
            "start": datetime(2026, 9, 11, 11, 45),
            "end": datetime(2026, 9, 11, 12, 0),
            "import": 0.20,
        },
        {
            "start": datetime(2026, 9, 11, 12, 0),
            "end": datetime(2026, 9, 11, 12, 15),
            "import": 0.90,
        },
    ]

    result = find_cheapest_future_period(
        forecast,
        now=datetime(2026, 9, 11, 10, 0),
        duration_minutes=120,
        selection_mode="consecutive",
    )

    assert result is not None
    assert result["duration_minutes"] == 120
    assert result["selection_mode"] == "consecutive"
    assert result["start"] == datetime(2026, 9, 11, 10, 15)
    assert result["end"] == datetime(2026, 9, 11, 12, 15)
    assert result["average_import_price"] == 0.775
    assert len(result["intervals"]) == 8

def test_find_cheapest_future_two_hours_cheapest_quarters():
    forecast = [
        {
            "start": datetime(2026, 9, 11, 10, 0),
            "end": datetime(2026, 9, 11, 10, 15),
            "import": 1.50,
        },
        {
            "start": datetime(2026, 9, 11, 10, 15),
            "end": datetime(2026, 9, 11, 10, 30),
            "import": 0.90,
        },
        {
            "start": datetime(2026, 9, 11, 10, 30),
            "end": datetime(2026, 9, 11, 10, 45),
            "import": 1.40,
        },
        {
            "start": datetime(2026, 9, 11, 10, 45),
            "end": datetime(2026, 9, 11, 11, 0),
            "import": 0.30,
        },
        {
            "start": datetime(2026, 9, 11, 11, 0),
            "end": datetime(2026, 9, 11, 11, 15),
            "import": 1.20,
        },
        {
            "start": datetime(2026, 9, 11, 11, 15),
            "end": datetime(2026, 9, 11, 11, 30),
            "import": 0.20,
        },
        {
            "start": datetime(2026, 9, 11, 11, 30),
            "end": datetime(2026, 9, 11, 11, 45),
            "import": 1.10,
        },
        {
            "start": datetime(2026, 9, 11, 11, 45),
            "end": datetime(2026, 9, 11, 12, 0),
            "import": 0.40,
        },
        {
            "start": datetime(2026, 9, 11, 12, 0),
            "end": datetime(2026, 9, 11, 12, 15),
            "import": 1.30,
        },
    ]

    result = find_cheapest_future_period(
        forecast,
        now=datetime(2026, 9, 11, 10, 7),
        duration_minutes=120,
        selection_mode="cheapest_quarters",
    )

    assert result is not None
    assert result["duration_minutes"] == 120
    assert result["selection_mode"] == "cheapest_quarters"

    assert len(result["intervals"]) == 8

    assert [interval["import"] for interval in result["intervals"]] == [
        0.90,
        1.40,
        0.30,
        1.20,
        0.20,
        1.10,
        0.40,
        1.30,
    ]

    assert result["start"] == datetime(2026, 9, 11, 10, 15)
    assert result["end"] == datetime(2026, 9, 11, 12, 15)

    assert result["average_import_price"] == 0.85

def test_find_cheapest_future_period_excludes_current_interval():
    forecast = [
        {
            "start": datetime(2026, 9, 11, 10, 0),
            "end": datetime(2026, 9, 11, 10, 15),
            "import": 0.10,
        },
        {
            "start": datetime(2026, 9, 11, 10, 15),
            "end": datetime(2026, 9, 11, 10, 30),
            "import": 0.80,
        },
        {
            "start": datetime(2026, 9, 11, 10, 30),
            "end": datetime(2026, 9, 11, 10, 45),
            "import": 0.90,
        },
    ]

    result = find_cheapest_future_period(
        forecast,
        now=datetime(2026, 9, 11, 10, 7),
        duration_minutes=15,
        selection_mode="consecutive",
    )

    assert result is not None
    assert result["start"] == datetime(2026, 9, 11, 10, 15)
    assert result["end"] == datetime(2026, 9, 11, 10, 30)
    assert result["average_import_price"] == 0.80

def test_calculate_today_import_price_statistics_uses_today_through_now():
    calculate_today_import_price_statistics = price_model.calculate_today_import_price_statistics
    now = datetime.fromisoformat("2026-09-19T12:07:00+02:00")
    forecast = [
        {
            "start": datetime.fromisoformat("2026-09-18T23:45:00+02:00"),
            "end": datetime.fromisoformat("2026-09-19T00:00:00+02:00"),
            "import": 9.0,
        },
        {
            "start": datetime.fromisoformat("2026-09-19T00:00:00+02:00"),
            "end": datetime.fromisoformat("2026-09-19T00:15:00+02:00"),
            "import": 1.0,
        },
        {
            "start": datetime.fromisoformat("2026-09-19T11:45:00+02:00"),
            "end": datetime.fromisoformat("2026-09-19T12:00:00+02:00"),
            "import": 2.0,
        },
        {
            "start": datetime.fromisoformat("2026-09-19T12:00:00+02:00"),
            "end": datetime.fromisoformat("2026-09-19T12:15:00+02:00"),
            "import": 3.0,
        },
        {
            "start": datetime.fromisoformat("2026-09-19T12:15:00+02:00"),
            "end": datetime.fromisoformat("2026-09-19T12:30:00+02:00"),
            "import": 99.0,
        },
    ]
    result = calculate_today_import_price_statistics(forecast, now=now)
    assert result == {
        "lowest_import_price": 1.0,
        "highest_import_price": 3.0,
        "average_import_price": 2.0,
        "interval_count": 3,
    }
