"""Tests for canonical house total power and energy calculations."""


def calculate_house_total_power(flows: dict[str, float]) -> float:
    """Calculate total house power from canonical directional flows."""
    return round(
        flows.get("solar_house_power", 0)
        + flows.get("battery_house_power", 0)
        + flows.get("grid_house_power", 0),
        3,
    )


def calculate_house_total_energy(energy: dict[str, float]) -> float:
    """Calculate total house energy from accumulated directional energy."""
    return round(
        energy.get("solar_house", 0)
        + energy.get("battery_house", 0)
        + energy.get("grid_house", 0),
        6,
    )


def test_house_power_from_solar_only():
    flows = {
        "solar_house_power": 5000,
        "battery_house_power": 0,
        "grid_house_power": 0,
    }

    assert calculate_house_total_power(flows) == 5000


def test_house_power_from_battery_only():
    flows = {
        "solar_house_power": 0,
        "battery_house_power": 3000,
        "grid_house_power": 0,
    }

    assert calculate_house_total_power(flows) == 3000


def test_house_power_from_grid_only():
    flows = {
        "solar_house_power": 0,
        "battery_house_power": 0,
        "grid_house_power": 4000,
    }

    assert calculate_house_total_power(flows) == 4000


def test_house_power_mixed_sources():
    flows = {
        "solar_house_power": 5000,
        "battery_house_power": 3000,
        "grid_house_power": 4000,
    }

    assert calculate_house_total_power(flows) == 12000


def test_house_power_ignores_non_house_flows():
    flows = {
        "solar_house_power": 5000,
        "battery_house_power": 3000,
        "grid_house_power": 4000,
        "solar_battery_power": 2000,
        "solar_export_power": 1000,
        "battery_grid_power": 500,
        "grid_battery_power": 700,
        "house_grid_power": 300,
    }

    assert calculate_house_total_power(flows) == 12000


def test_house_energy_from_solar_only():
    energy = {
        "solar_house": 5,
        "battery_house": 0,
        "grid_house": 0,
    }

    assert calculate_house_total_energy(energy) == 5


def test_house_energy_from_battery_only():
    energy = {
        "solar_house": 0,
        "battery_house": 3,
        "grid_house": 0,
    }

    assert calculate_house_total_energy(energy) == 3


def test_house_energy_from_grid_only():
    energy = {
        "solar_house": 0,
        "battery_house": 0,
        "grid_house": 4,
    }

    assert calculate_house_total_energy(energy) == 4


def test_house_energy_mixed_sources():
    energy = {
        "solar_house": 5,
        "battery_house": 3,
        "grid_house": 4,
    }

    assert calculate_house_total_energy(energy) == 12


def test_house_energy_ignores_non_house_flows():
    energy = {
        "solar_house": 5,
        "battery_house": 3,
        "grid_house": 4,
        "solar_battery": 10,
        "solar_export": 20,
        "battery_grid": 30,
        "grid_battery": 40,
        "house_grid": 50,
    }

    assert calculate_house_total_energy(energy) == 12


def test_house_energy_zero_when_no_house_consumption():
    energy = {
        "solar_house": 0,
        "battery_house": 0,
        "grid_house": 0,
    }

    assert calculate_house_total_energy(energy) == 0


def test_house_power_handles_missing_components():
    flows = {
        "solar_house_power": 2500,
    }

    assert calculate_house_total_power(flows) == 2500


def test_house_energy_handles_missing_components():
    energy = {
        "grid_house": 7.25,
    }

    assert calculate_house_total_energy(energy) == 7.25