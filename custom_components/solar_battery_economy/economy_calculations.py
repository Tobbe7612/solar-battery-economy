def calculate_savings(money):
    solar_house = money.get("solar_house", 0)
    battery_house = money.get("battery_house", 0)

    solar_export = money.get("solar_export", 0)
    battery_export = money.get("battery_grid", 0)

    grid_house = money.get("grid_house", 0)
    grid_battery = money.get("grid_battery", 0)

    # ✅ Actual cost (what you paid to grid)
    actual_grid_cost = grid_house + grid_battery

    # ✅ Avoided cost (what solar + battery saved you)
    avoided_cost = solar_house + battery_house

    # ✅ Export income
    export_income = solar_export + battery_export

    # ✅ REAL total savings
    total = avoided_cost + export_income - grid_battery

    return {
        "baseline_cost": avoided_cost + actual_grid_cost,
        "actual_grid_cost": actual_grid_cost,
        "export_income": export_income,
        "solar_house": solar_house,
        "battery_house": battery_house,
        "total": total,
    }