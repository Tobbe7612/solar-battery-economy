def calculate_flows(solar_w, grid_w, battery_w):
    """
    Calculate directional power flows (all positive W).

    INPUT CONVENTION:
    solar_w   > 0 = solar producing
    battery_w > 0 = battery discharging
                < 0 = battery charging
    grid_w    < 0 = importing from grid
                > 0 = exporting to grid
    """

    # --- Sanitize inputs ---
    solar_w = solar_w or 0
    grid_w = grid_w or 0
    battery_w = battery_w or 0

    solar = max(solar_w, 0)

    battery_discharge = max(battery_w, 0)
    battery_charge = max(-battery_w, 0)

    grid_import = max(-grid_w, 0)
    grid_export = max(grid_w, 0)

    # ---------------------------------------------------------
    # Estimate house load using power balance
    # ---------------------------------------------------------
    house_load = (
        solar
        + battery_discharge
        + grid_import
        - battery_charge
        - grid_export
    )

    house_load = max(house_load, 0)
    remaining_load = house_load

    # =========================================================
    # SUPPLY HOUSE LOAD (priority order)
    # =========================================================

    # Solar → House
    solar_to_house = min(solar, remaining_load)
    remaining_load -= solar_to_house
    solar_remaining = solar - solar_to_house

    # Battery → House
    battery_to_house = min(battery_discharge, remaining_load)
    remaining_load -= battery_to_house
    battery_remaining = battery_discharge - battery_to_house

    # Grid → House
    grid_to_house = remaining_load

    # =========================================================
    # BATTERY CHARGING SOURCES
    # =========================================================

    # Solar → Battery first
    solar_to_battery = min(solar_remaining, battery_charge)
    solar_remaining -= solar_to_battery
    battery_charge -= solar_to_battery

    # Grid → Battery next
    grid_to_battery = min(grid_import, battery_charge)

    # =========================================================
    # EXPORTS
    # =========================================================

    remaining_export = grid_export

    # Solar → Grid
    solar_export = min(solar_remaining, remaining_export)
    remaining_export -= solar_export

    # Battery → Grid
    battery_to_grid = min(battery_remaining, remaining_export)
    remaining_export -= battery_to_grid

    # Residual export (unknown / house)
    house_to_grid = remaining_export

    return {
        # Solar flows
        "solar_house_power": solar_to_house,
        "solar_battery_power": solar_to_battery,
        "solar_export_power": solar_export,

        # Battery flows
        "battery_house_power": battery_to_house,
        "battery_grid_power": battery_to_grid,

        # Grid flows
        "grid_house_power": grid_to_house,
        "grid_battery_power": grid_to_battery,

        # Residual export
        "house_grid_power": house_to_grid,
    }