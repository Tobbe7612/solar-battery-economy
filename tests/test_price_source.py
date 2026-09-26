from datetime import datetime
import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "price_source.py"
)

spec = importlib.util.spec_from_file_location(
    "solar_battery_economy_price_source",
    MODULE_PATH,
)

if spec is None or spec.loader is None:
    raise ImportError(f"Could not load module from {MODULE_PATH}")

price_source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(price_source)

normalize_price_source = price_source.normalize_price_source
find_cheapest_future_period = price_source.find_cheapest_future_period

def test_normalize_valid_price_intervals():
    attributes = {
        "all_prices": [
            {
                "start": "2026-08-31T18:00:00+02:00",
                "end": "2026-08-31T18:15:00+02:00",
                "spot": 0.50,
                "import": 1.20,
                "export": 0.55,
            },
            {
                "start": "2026-08-31T18:15:00+02:00",
                "end": "2026-08-31T18:30:00+02:00",
                "spot": 0.60,
                "import": 1.32,
                "export": 0.65,
            },
        ]
    }

    result = normalize_price_source(attributes)

    assert len(result["forecast"]) == 2

    first = result["forecast"][0]

    assert first["spot"] == 0.50
    assert first["import"] == 1.20
    assert first["export"] == 0.55

    assert first["start"] == datetime.fromisoformat(
        "2026-08-31T18:00:00+02:00"
    )
    assert first["end"] == datetime.fromisoformat(
        "2026-08-31T18:15:00+02:00"
    )


def test_current_price_is_selected_from_active_interval():
    attributes = {
        "all_prices": [
            {
                "start": "2026-08-31T18:00:00+02:00",
                "end": "2026-08-31T18:15:00+02:00",
                "spot": 0.50,
                "import": 1.20,
                "export": 0.55,
            },
            {
                "start": "2026-08-31T18:15:00+02:00",
                "end": "2026-08-31T18:30:00+02:00",
                "spot": 0.60,
                "import": 1.32,
                "export": 0.65,
            },
        ]
    }

    current_time = datetime.fromisoformat(
        "2026-08-31T18:07:00+02:00"
    )

    result = normalize_price_source(
        attributes,
        now=current_time,
    )

    assert result["current"]["spot"] == 0.50
    assert result["current"]["import"] == 1.20
    assert result["current"]["export"] == 0.55


def test_current_interval_is_end_exclusive():
    attributes = {
        "all_prices": [
            {
                "start": "2026-08-31T18:00:00+02:00",
                "end": "2026-08-31T18:15:00+02:00",
                "spot": 0.50,
                "import": 1.20,
                "export": 0.55,
            },
            {
                "start": "2026-08-31T18:15:00+02:00",
                "end": "2026-08-31T18:30:00+02:00",
                "spot": 0.60,
                "import": 1.32,
                "export": 0.65,
            },
        ]
    }

    current_time = datetime.fromisoformat(
        "2026-08-31T18:15:00+02:00"
    )

    result = normalize_price_source(
        attributes,
        now=current_time,
    )

    assert result["current"]["spot"] == 0.60
    assert result["current"]["import"] == 1.32
    assert result["current"]["export"] == 0.65


def test_forecast_order_is_preserved():
    attributes = {
        "all_prices": [
            {
                "start": "2026-08-31T19:00:00+02:00",
                "end": "2026-08-31T19:15:00+02:00",
                "spot": 0.70,
                "import": 1.45,
                "export": 0.73,
            },
            {
                "start": "2026-08-31T19:15:00+02:00",
                "end": "2026-08-31T19:30:00+02:00",
                "spot": 0.80,
                "import": 1.57,
                "export": 0.83,
            },
        ]
    }

    result = normalize_price_source(attributes)

    assert result["forecast"][0]["spot"] == 0.70
    assert result["forecast"][1]["spot"] == 0.80


def test_empty_all_prices_returns_empty_forecast_and_no_current():
    result = normalize_price_source({"all_prices": []})

    assert result["forecast"] == []
    assert result["current"] is None


def test_missing_all_prices_returns_empty_model():
    result = normalize_price_source({})

    assert result["forecast"] == []
    assert result["current"] is None


def test_unknown_all_prices_returns_empty_model():
    result = normalize_price_source({"all_prices": "unknown"})

    assert result["forecast"] == []
    assert result["current"] is None


def test_invalid_intervals_are_ignored():
    attributes = {
        "all_prices": [
            {
                "start": "not-a-date",
                "end": "2026-08-31T19:15:00+02:00",
                "spot": 0.50,
                "import": 1.20,
                "export": 0.55,
            },
            {
                "start": "2026-08-31T19:15:00+02:00",
                "end": "2026-08-31T19:30:00+02:00",
                "spot": 0.60,
                "import": 1.32,
                "export": 0.65,
            },
        ]
    }

    result = normalize_price_source(attributes)

    assert len(result["forecast"]) == 1
    assert result["forecast"][0]["spot"] == 0.60


def test_missing_price_fields_are_ignored():
    attributes = {
        "all_prices": [
            {
                "start": "2026-08-31T19:00:00+02:00",
                "end": "2026-08-31T19:15:00+02:00",
                "spot": 0.50,
                "import": 1.20,
            },
            {
                "start": "2026-08-31T19:15:00+02:00",
                "end": "2026-08-31T19:30:00+02:00",
                "spot": 0.60,
                "import": 1.32,
                "export": 0.65,
            },
        ]
    }

    result = normalize_price_source(attributes)

    assert len(result["forecast"]) == 1
    assert result["forecast"][0]["export"] == 0.65


def test_future_intervals_are_retained():
    attributes = {
        "all_prices": [
            {
                "start": "2026-09-01T00:00:00+02:00",
                "end": "2026-09-01T00:15:00+02:00",
                "spot": 0.40,
                "import": 1.08,
                "export": 0.43,
            },
        ]
    }

    result = normalize_price_source(attributes)

    assert len(result["forecast"]) == 1
    assert result["forecast"][0]["spot"] == 0.40
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
    calculate_today_import_price_statistics = price_source.calculate_today_import_price_statistics
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
