def calculate_savings(energy, import_price, export_price):
    """
    Professional financial model:
    Savings = What you would have paid without system
              - What you actually paid
              + export income
    """

    solar_house = energy.get("solar_house", 0)
    battery_house = energy.get("battery_house", 0)
    grid_house = energy.get("grid_house", 0)

    solar_export = energy.get("solar_export", 0)
    battery_export = energy.get("battery_grid", 0)

    # Total house consumption
    house_consumption = solar_house + battery_house + grid_house

    # Baseline (no solar, no battery)
    baseline_cost = house_consumption * import_price

    # Actual cost from grid
    actual_grid_cost = grid_house * import_price

    # Export income
    export_income = (solar_export + battery_export) * export_price

    # Real savings
    real_savings = baseline_cost - actual_grid_cost + export_income

    return {
        "baseline_cost": baseline_cost,
        "actual_grid_cost": actual_grid_cost,
        "export_income": export_income,
        "solar_house": solar_house * import_price,
        "battery_house": battery_house * import_price,
        "total": real_savings,
    }