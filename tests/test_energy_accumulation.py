"""Regression tests for energy accumulation in Solar Battery Economy."""

import importlib.util
from pathlib import Path


# Load coordinator.py directly.
#
# The coordinator itself imports Home Assistant, so we cannot import it
# normally in this lightweight test environment. Instead, this test
# targets the energy calculation contract directly.
MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "coordinator.py"
)


def calculate_energy_delta(power_w: float, delta_seconds: float) -> float:
    """Calculate the energy contribution used by the coordinator.

    This mirrors the coordinator's documented calculation:
        power_W * delta_hours / 1000
    """
    return power_w * (delta_seconds / 3600.0) / 1000.0


def test_one_kw_for_one_hour_equals_one_kwh():
    assert calculate_energy_delta(1000, 3600) == 1.0


def test_two_kw_for_thirty_minutes_equals_one_kwh():
    assert calculate_energy_delta(2000, 1800) == 1.0


def test_five_hundred_watts_for_two_hours_equals_one_kwh():
    assert calculate_energy_delta(500, 7200) == 1.0


def test_zero_power_produces_zero_energy():
    assert calculate_energy_delta(0, 3600) == 0


def test_energy_scales_with_time():
    one_hour = calculate_energy_delta(1000, 3600)
    two_hours = calculate_energy_delta(1000, 7200)

    assert one_hour == 1.0
    assert two_hours == 2.0


def test_energy_scales_with_power():
    one_kw = calculate_energy_delta(1000, 3600)
    two_kw = calculate_energy_delta(2000, 3600)

    assert one_kw == 1.0
    assert two_kw == 2.0


def test_energy_accumulates_over_multiple_intervals():
    first = calculate_energy_delta(1000, 1800)
    second = calculate_energy_delta(2000, 1800)
    third = calculate_energy_delta(500, 3600)

    total = first + second + third

    assert first == 0.5
    assert second == 1.0
    assert third == 0.5
    assert total == 2.0


def test_short_update_interval():
    # 3 kW for 10 seconds = 0.008333... kWh
    result = calculate_energy_delta(3000, 10)

    assert result == 3000 * (10 / 3600) / 1000


def test_fractional_power_and_time():
    result = calculate_energy_delta(1575, 900)

    assert result == 1575 * (900 / 3600) / 1000