"""Regression tests for Solar Battery Economy calculations."""

import importlib.util
from pathlib import Path


# Load economy_calculations.py directly.
#
# This intentionally avoids importing the complete Home Assistant
# integration package. The calculation functions themselves have no
# Home Assistant dependency and should therefore be testable in isolation.
MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "economy_calculations.py"
)

SPEC = importlib.util.spec_from_file_location(
    "solar_battery_economy_economy_calculations",
    MODULE_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Could not load module from {MODULE_PATH}")

economy_calculations = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(economy_calculations)

calculate_savings = economy_calculations.calculate_savings
battery_solar_share = economy_calculations.battery_solar_share


def test_calculate_savings_with_empty_money():
    result = calculate_savings({})

    assert result["baseline_cost"] == 0
    assert result["actual_grid_cost"] == 0
    assert result["export_income"] == 0
    assert result["solar_house"] == 0
    assert result["battery_house"] == 0
    assert result["total"] == 0


def test_calculate_savings_basic_values():
    result = calculate_savings(
        {
            "solar_house": 100,
            "battery_house": 50,
            "solar_export": 30,
            "battery_grid": 20,
            "grid_house": 40,
            "grid_battery": 10,
        }
    )

    assert result["actual_grid_cost"] == 50
    assert result["baseline_cost"] == 200
    assert result["export_income"] == 50
    assert result["solar_house"] == 100
    assert result["battery_house"] == 50

    # Existing implementation:
    # total = avoided_cost + export_income - grid_battery
    #       = (100 + 50) + (30 + 20) - 10
    #       = 190
    assert result["total"] == 190


def test_calculate_savings_separates_grid_cost_components():
    result = calculate_savings(
        {
            "solar_house": 0,
            "battery_house": 0,
            "solar_export": 0,
            "battery_grid": 0,
            "grid_house": 125,
            "grid_battery": 75,
        }
    )

    assert result["actual_grid_cost"] == 200
    assert result["baseline_cost"] == 200
    assert result["export_income"] == 0
    assert result["total"] == -75


def test_calculate_savings_export_income():
    result = calculate_savings(
        {
            "solar_house": 0,
            "battery_house": 0,
            "solar_export": 250,
            "battery_grid": 50,
            "grid_house": 0,
            "grid_battery": 0,
        }
    )

    assert result["export_income"] == 300
    assert result["total"] == 300


def test_battery_solar_share_empty():
    assert battery_solar_share({}) == 0


def test_battery_solar_share_no_battery_charge():
    assert (
        battery_solar_share(
            {
                "solar_battery": 0,
                "grid_battery": 0,
            }
        )
        == 0
    )


def test_battery_solar_share_all_solar():
    assert (
        battery_solar_share(
            {
                "solar_battery": 100,
                "grid_battery": 0,
            }
        )
        == 1
    )


def test_battery_solar_share_all_grid():
    assert (
        battery_solar_share(
            {
                "solar_battery": 0,
                "grid_battery": 100,
            }
        )
        == 0
    )


def test_battery_solar_share_mixed_charge():
    result = battery_solar_share(
        {
            "solar_battery": 300,
            "grid_battery": 100,
        }
    )

    assert result == 0.75


def test_battery_solar_share_uses_cumulative_energy():
    result = battery_solar_share(
        {
            "solar_battery": 1657.824,
            "grid_battery": 349.986,
        }
    )

    expected = 1657.824 / (1657.824 + 349.986)

    assert result == expected