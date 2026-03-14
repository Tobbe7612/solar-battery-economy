def calculate_savings(money):
    """
    Professional financial model.

    Uses accumulated monetary values instead of recalculating
    from energy totals to avoid price fluctuation errors.
    """

    solar_house = money.get("solar_house", 0)
    battery_house = money.get("battery_house", 0)

    solar_export = money.get("solar_export", 0)
    battery_export = money.get("battery_grid", 0)

    grid_house = money.get("grid_house", 0)

    # What you would have paid without system
    baseline_cost = solar_house + battery_house + grid_house

    # What you actually paid
    actual_grid_cost = grid_house

    # Export income
    export_income = solar_export + battery_export

    # Real savings
    real_savings = baseline_cost - actual_grid_cost + export_income

    return {
        "baseline_cost": baseline_cost,
        "actual_grid_cost": actual_grid_cost,
        "export_income": export_income,
        "solar_house": solar_house,
        "battery_house": battery_house,
        "total": real_savings,
    }