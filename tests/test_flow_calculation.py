"""Regression tests for the Solar Battery Economy flow calculation."""

import importlib.util
from pathlib import Path


# Load flow_calculation.py directly.
#
# This intentionally avoids importing the complete Home Assistant
# integration package. The flow calculation itself has no Home Assistant
# dependency and should therefore be testable in isolation.
MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "flow_calculation.py"
)

SPEC = importlib.util.spec_from_file_location(
    "solar_battery_economy_flow_calculation",
    MODULE_PATH,
)

if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Could not load module from {MODULE_PATH}")

flow_calculation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(flow_calculation)

calculate_flows = flow_calculation.calculate_flows


def test_solar_to_house():
    flows = calculate_flows(
        solar_w=5000,
        grid_w=0,
        battery_w=0,
    )

    assert flows["solar_house_power"] == 5000
    assert flows["solar_battery_power"] == 0
    assert flows["solar_export_power"] == 0


def test_solar_to_battery():
    flows = calculate_flows(
        solar_w=5000,
        grid_w=0,
        battery_w=-3000,
    )

    assert flows["solar_battery_power"] == 3000
    assert flows["solar_house_power"] == 2000
    assert flows["solar_export_power"] == 0


def test_solar_to_grid():
    flows = calculate_flows(
        solar_w=5000,
        grid_w=2000,
        battery_w=0,
    )

    assert flows["solar_export_power"] == 2000
    assert flows["solar_house_power"] == 3000
    assert flows["solar_battery_power"] == 0


def test_battery_to_house():
    flows = calculate_flows(
        solar_w=0,
        grid_w=0,
        battery_w=3000,
    )

    assert flows["battery_house_power"] == 3000
    assert flows["battery_grid_power"] == 0


def test_battery_to_grid():
    flows = calculate_flows(
        solar_w=0,
        grid_w=2000,
        battery_w=3000,
    )

    assert flows["battery_grid_power"] == 2000
    assert flows["battery_house_power"] == 1000


def test_grid_to_house():
    flows = calculate_flows(
        solar_w=0,
        grid_w=-3000,
        battery_w=0,
    )

    assert flows["grid_house_power"] == 3000
    assert flows["grid_battery_power"] == 0


def test_grid_to_battery():
    flows = calculate_flows(
        solar_w=0,
        grid_w=-5000,
        battery_w=-3000,
    )

    assert flows["grid_battery_power"] == 3000
    assert flows["grid_house_power"] == 2000


def test_house_to_grid():
    flows = calculate_flows(
        solar_w=0,
        grid_w=2000,
        battery_w=0,
    )

    assert flows["house_grid_power"] == 2000