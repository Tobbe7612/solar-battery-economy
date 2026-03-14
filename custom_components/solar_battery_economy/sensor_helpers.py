import math


def _float_state(hass, entity_id):
    """Safely get a finite float value from another entity."""
    state = hass.states.get(entity_id)

    if state is None:
        return 0.0

    value = state.state

    if value in ("unknown", "unavailable", None):
        return 0.0

    try:
        number = float(value)
    except (ValueError, TypeError):
        return 0.0

    # Reject NaN or infinite values
    if not math.isfinite(number):
        return 0.0

    return number

def calculate_solar_self_consumption(solar_power, grid_power):
    """
    Calculate how much solar power is used in the house.

    If solar production is higher than export, assume export is solar.
    """
    if solar_power <= 0:
        return 0.0

    # If exporting to grid
    if grid_power < 0:
        export = abs(grid_power)
        return max(0.0, solar_power - export)

    return solar_power


def calculate_solar_savings(solar_used, import_price):
    """Money saved by using solar instead of buying from grid."""
    return (solar_used / 1000.0) * import_price


def calculate_battery_savings(battery_power, import_price):
    """Money saved by discharging battery instead of buying from grid."""
    if battery_power <= 0:
        return 0.0

    return (battery_power / 1000.0) * import_price


def calculate_export_income(export_power, export_price):
    """Money earned by exporting electricity."""
    if export_power <= 0:
        return 0.0

    return (export_power / 1000.0) * export_price