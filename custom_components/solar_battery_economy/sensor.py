from homeassistant.util import dt as dt_util
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .sensor_base import EconomySensor
from .coordinator import SolarBatteryEconomyCoordinator
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from datetime import timedelta
from homeassistant.components.sensor import SensorDeviceClass

# -----------------------------
# async_setup_entry
# -----------------------------
async def async_setup_entry(hass, entry, async_add_entities):
    advanced_mode = entry.options.get("advanced_mode", False)
    coordinator: SolarBatteryEconomyCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    # --- build all sensors first ---
    power_keys = [
        ("solar_house_power", "Power Solar-House"),
        ("solar_battery_power", "Power Solar-Battery"),
        ("solar_export_power", "Power Solar-Export"),
        ("battery_house_power", "Power Battery-House"),
        ("battery_grid_power", "Power Battery-Grid"),
        ("grid_house_power", "Power Grid-House"),
        ("grid_battery_power", "Power Grid-Battery"),
        ("house_grid_power", "Power House-Grid"),
    ]
    for key, name in power_keys:
        sensors.append(FlowPowerSensor(coordinator, hass, entry, name, key, sensor_type="power"))

    energy_keys = [
        ("solar_house", "Energy Solar-House"),
        ("solar_battery", "Energy Solar-Battery"),
        ("solar_export", "Energy Solar-Export"),
        ("battery_house", "Energy Battery-House"),
        ("battery_grid", "Energy Battery-Grid"),
        ("grid_house", "Energy Grid-House"),
        ("grid_battery", "Energy Grid-Battery"),
        ("house_grid", "Energy House-Grid"),
    ]
    for key, name in energy_keys:
        sensors.append(EnergySensor(coordinator, hass, entry, name, key, sensor_type="energy"))
    money_keys = [
        ("solar_house", "Money Solar-House"),
        ("solar_export", "Money Solar-Export"),
        ("battery_house", "Money Battery-House"),
        ("battery_grid", "Money Battery-Grid"),
        ("grid_house", "Money Grid-House"),
        ("grid_battery", "Money Grid-Battery"),
        ("house_grid", "Money House-Grid"),
    ]
    if advanced_mode:
        for key, name in money_keys:
            sensors.append(
                MoneySensor(coordinator, hass, entry, name, key, sensor_type="money")
            )
    savings_keys = [
        ("solar_house", "Savings Solar-House"),
        ("battery_house", "Savings Battery-House"),
        ("baseline_cost", "Baseline Cost (No System)"),
        ("actual_grid_cost", "Actual Grid Cost"),
        ("export_income", "24 Export Income"),
        ("total", "01 Total Savings"),
    ]
    for key, name in savings_keys:
        # Always create main financial sensors
        if key in ("baseline_cost", "actual_grid_cost", "export_income", "total"):
            sensors.append(
                SavingsSensor(coordinator, hass, entry, name, key)
            )
        # Only create breakdown sensors in advanced mode
        elif advanced_mode:
            sensors.append(
                SavingsSensor(coordinator, hass, entry, name, key)
            )

    # ----------------------
    # High-level economy sensors
    # ----------------------
    sensors.append(PaybackSensor(coordinator, hass, entry))
    sensors.append(PaybackDateSensor(coordinator, hass, entry))
    sensors.append(ROISensor(coordinator, hass, entry))
    sensors.append(AnnualSavingsSensor(coordinator, hass, entry))
    sensors.append(EffectiveElectricityPriceSensor(coordinator, hass, entry))
    sensors.append(ImportElectricityPriceSensor(coordinator, hass, entry))
    sensors.append(ExportElectricityPriceSensor(coordinator, hass, entry))
    sensors.append(SolarSavingsSensor(coordinator, hass, entry))
    sensors.append(BatterySavingsSensor(coordinator, hass, entry))
    sensors.append(GridIndependenceSensor(coordinator, hass, entry))
    sensors.append(SolarSelfConsumptionSensor(coordinator, hass, entry))
    sensors.append(CO2SavedSensor(coordinator, hass, entry))
    sensors.append(PeriodEconomySensor(coordinator, hass, entry, "03 Savings Today", "day"))
    sensors.append(PeriodEconomySensor(coordinator, hass, entry, "04 Savings This Month", "month"))
    sensors.append(PeriodEconomySensor(coordinator, hass, entry, "05 Savings This Year", "year"))
    if advanced_mode:
        sensors.append(BatteryUtilizationSensor(coordinator, hass, entry))
        sensors.append(BatteryArbitrageSensor(coordinator, hass, entry))
        sensors.append(BatterySelfConsumptionSensor(coordinator, hass, entry))

    async_add_entities(sensors, update_before_add=True)
#    await coordinator.async_restore_from_hass()
    if not coordinator._unsub_listeners:
        await coordinator.async_setup_listeners()
    await coordinator.async_refresh()

# -----------------------------
# FlowPowerSensor – Power (W)
# -----------------------------
class FlowPowerSensor(EconomySensor):
    _attr_native_unit_of_measurement = "W"
    _attr_state_class = "measurement"

    def __init__(self, coordinator, hass, entry, name, key, sensor_type="power"):
        super().__init__(coordinator, hass, entry, name, key, sensor_type)

        if "solar" in key:
            self._attr_icon = "mdi:solar-power"
        elif "battery" in key:
            self._attr_icon = "mdi:battery-high"
        elif "grid" in key:
            self._attr_icon = "mdi:transmission-tower"
        else:
            self._attr_icon = "mdi:home-lightning-bolt"

    def _handle_coordinator_update(self):
        self._value = self.coordinator.data["power"].get(self._key, 0)
        self.async_write_ha_state()


# -----------------------------
# EnergySensor – kWh
# -----------------------------
class EnergySensor(EconomySensor, RestoreEntity):
    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = "energy"
    _attr_state_class = "total_increasing"

    def __init__(self, coordinator, hass, entry, name, key, sensor_type="energy"):
        super().__init__(coordinator, hass, entry, name, key, sensor_type)

        if "solar" in key:
            self._attr_icon = "mdi:solar-power"
        elif "battery" in key:
            self._attr_icon = "mdi:battery"
        elif "grid" in key:
            self._attr_icon = "mdi:transmission-tower"
        else:
            self._attr_icon = "mdi:flash"

    async def async_added_to_hass(self):
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._value = float(last_state.state)
            except ValueError:
                self._value = 0
        await super().async_added_to_hass()

    def _handle_coordinator_update(self):
        self._value = round(self.coordinator.data["energy"].get(self._key, 0), 3)
        self.async_write_ha_state()


# -----------------------------
# MoneySensor – SEK
# -----------------------------
class MoneySensor(EconomySensor, RestoreEntity):
    @property
    def native_unit_of_measurement(self):
        return self.coordinator.currency
    _attr_device_class = "monetary"
    _attr_state_class = "total"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, hass, entry, name, key, sensor_type="money"):
        super().__init__(coordinator, hass, entry, name, key, sensor_type)
        self._attr_icon = "mdi:cash"

    async def async_added_to_hass(self):
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._value = float(last_state.state)
            except ValueError:
                self._value = 0
        await super().async_added_to_hass()

    def _handle_coordinator_update(self):
        self._value = round(self.coordinator.data["money"].get(self._key, 0), 2)
        self.async_write_ha_state()

def _calculate_total_economy(money: dict) -> float:
    return (
        money.get("solar_house", 0)
        + money.get("battery_house", 0)
        + money.get("solar_export", 0)
        + money.get("battery_grid", 0)
        + money.get("house_grid", 0)
        - money.get("grid_battery", 0)
        - money.get("grid_house", 0)
    )

# -----------------------------
# PeriodEconomySensor
# -----------------------------
class PeriodEconomySensor(EconomySensor, RestoreEntity):
    @property
    def native_unit_of_measurement(self):
        return self.coordinator.currency
    _attr_device_class = "monetary"
    _attr_state_class = "total"
    def __init__(self, coordinator, hass, entry, name, period):
        super().__init__(coordinator, hass, entry, name, f"period_{period}", sensor_type="period")
        self._attr_icon = "mdi:calendar-month"
        self._period = period
        self._baseline = None
        self._last_reset = None
    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._value = float(last_state.state)
            except ValueError:
                self._value = 0
            self._baseline = float(last_state.attributes.get("baseline", 0))
            last_reset = last_state.attributes.get("last_reset")
            if last_reset:
                from homeassistant.util.dt import parse_datetime
                self._last_reset = parse_datetime(last_reset)
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )
    def _needs_reset(self, now):
        if self._last_reset is None:
            return False
        if self._period == "day":
            return now.date() != self._last_reset.date()
        if self._period == "month":
            return (now.year, now.month) != (self._last_reset.year, self._last_reset.month)
        if self._period == "year":
            return now.year != self._last_reset.year
        return False
    def _handle_coordinator_update(self):
        savings = self.coordinator.data.get("savings", {})
        total = savings.get("total", 0)
        now = dt_util.now()
        # Initialize baseline once
        if self._baseline is None:
            self._baseline = total
            self._last_reset = now
        # Reset when period changes
        elif self._needs_reset(now):
            self._baseline = total
            self._last_reset = now
        value = max(0, total - self._baseline)
        self._value = round(value, 2)
        self._attr_extra_state_attributes = {
            "baseline": self._baseline,
            "last_reset": self._last_reset.isoformat() if self._last_reset else None,
        }
        self.async_write_ha_state()

# -----------------------------
# SavingsSensor – SEK
# -----------------------------
class SavingsSensor(EconomySensor):
    @property
    def native_unit_of_measurement(self):
        return self.coordinator.currency
    _attr_device_class = "monetary"
    _attr_state_class = "total"
    def __init__(self, coordinator, hass, entry, name, key):
        super().__init__(coordinator, hass, entry, name, key, sensor_type="savings")
        # MAIN VISIBLE FINANCIAL SENSORS
        if key == "total":
            self._attr_icon = "mdi:trending-up"
        elif key == "baseline_cost":
            self._attr_icon = "mdi:cash-multiple"
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif key == "actual_grid_cost":
            self._attr_icon = "mdi:transmission-tower"
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif key == "export_income":
            self._attr_icon = "mdi:cash-plus"
        # DIAGNOSTIC BREAKDOWN SENSORS
        else:
            self._attr_icon = "mdi:piggy-bank"
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
    def _handle_coordinator_update(self):
        self._value = round(
            self.coordinator.data["savings"].get(self._key, 0),
            2,
        )
        self.async_write_ha_state()

# -----------------------------
# PaybackSensor
# -----------------------------
class PaybackSensor(EconomySensor, RestoreEntity):
    _attr_native_unit_of_measurement = "years"
    _attr_icon = "mdi:calendar-sync"
    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "10 Payback Time",
            "payback_time",
            sensor_type="payback",
        )
    async def async_added_to_hass(self):
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._value = float(last_state.state)
            except ValueError:
                self._value = None
        await super().async_added_to_hass()
    def _handle_coordinator_update(self):
        savings = self.coordinator.data.get("savings", {})
        total = savings.get("total", 0)
        investment = self.coordinator.investment
        if investment <= 0 or total <= 0:
            self._value = None
            self.async_write_ha_state()
            return
        # Same logic as PaybackDateSensor
        days_running = 2  # fixed stabilization
        annual_estimate = (total / days_running) * 365
        if annual_estimate <= 0:
            self._value = None
        else:
            self._value = round(investment / annual_estimate, 2)
        self._attr_extra_state_attributes = {
            "annual_estimate": round(annual_estimate, 2),
            "assumed_days": days_running,
        }
        self.async_write_ha_state()

# -----------------------------
# PayBack Date
# -----------------------------
class PaybackDateSensor(EconomySensor):
    _attr_icon = "mdi:calendar-check"
    _attr_device_class = SensorDeviceClass.DATE
    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "11 Estimated Payback Date",
            "payback_date",
            sensor_type="payback_date",
        )
        self._value = None
    @property
    def native_value(self):
        return self._value
    def _handle_coordinator_update(self):
        savings = self.coordinator.data.get("savings", {})
        total = savings.get("total", 0)
        investment = self.coordinator.investment
        now = dt_util.now()
        if investment <= 0 or total <= 0:
            self._value = None
            self.async_write_ha_state()
            return
        # Same logic as PaybackSensor
        days_running = 2  # fixed stabilization
        annual_estimate = (total / days_running) * 365
        if annual_estimate <= 0:
            self._value = None
            self.async_write_ha_state()
            return
        remaining = investment - total
        if remaining <= 0:
            self._value = now.date()
            self.async_write_ha_state()
            return
        days_remaining = (remaining / annual_estimate) * 365
        if days_remaining <= 0 or days_remaining > 365 * 50:
            self._value = None
            self.async_write_ha_state()
            return
        self._value = (now + timedelta(days=days_remaining)).date()
        self.async_write_ha_state()

# -----------------------------
# Return Of Investment - %
# -----------------------------
class ROISensor(EconomySensor):
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:percent"
    _attr_state_class = "measurement"
    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "12 Return On Investment",
            "roi_percent",
            sensor_type="roi",
        )
    def _handle_coordinator_update(self):
        savings = self.coordinator.data.get("savings", {})
        total = savings.get("total", 0)
        investment = self.coordinator.investment
        if investment <= 0:
            self._value = 0
        else:
            self._value = round((total / investment) * 100, 2)
        self.async_write_ha_state()

# -----------------------------
# Estimated Annual Savings – SEK
# -----------------------------
class AnnualSavingsSensor(EconomySensor):
    @property
    def native_unit_of_measurement(self):
        return self.coordinator.currency
    _attr_icon = "mdi:calendar-star"
    _attr_state_class = "measurement"
    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "02 Estimated Annual Savings",
            "annual_savings",
            sensor_type="annual",
        )
        self._start_date = None
    async def async_added_to_hass(self):
        # restore start date from PaybackSensor if available
        payback = self.hass.states.get("sensor.payback_time")
        if payback and "start_date" in payback.attributes:
            from homeassistant.util.dt import parse_datetime
            self._start_date = parse_datetime(payback.attributes["start_date"])
        await super().async_added_to_hass()
    def _handle_coordinator_update(self):
        savings = self.coordinator.data.get("savings", {})
        total = savings.get("total", 0)
        if total <= 0:
            self._value = 0
            self.async_write_ha_state()
            return
        if self._start_date is None:
            self._start_date = dt_util.now()
        days_running = max(
            (dt_util.now() - self._start_date).total_seconds() / 86400,
            0.01,
        )
        # Stabilize estimate during early runtime
        effective_days = max(days_running, 3)
        daily_average = total / effective_days
        self._value = round(daily_average * 365, 2)
        self.async_write_ha_state()

# -----------------------------
# Effective Electricity Price – SEK/kWh
# -----------------------------
class EffectiveElectricityPriceSensor(EconomySensor):
    @property
    def native_unit_of_measurement(self):
        return f"{self.coordinator.currency}/kWh"
    _attr_icon = "mdi:cash-clock"
    _attr_state_class = "measurement"

    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "06 Effective Electricity Price",
            "effective_price",
            sensor_type="effective_price",
        )

    def _handle_coordinator_update(self):

        energy = self.coordinator.data.get("energy", {})
        money = self.coordinator.data.get("money", {})

        grid_house_energy = energy.get("grid_house", 0)
        grid_house_cost = money.get("grid_house", 0)

        if grid_house_energy <= 0:
            self._value = 0
        else:
            self._value = round(grid_house_cost / grid_house_energy, 3)

        self.async_write_ha_state()

# -----------------------------
# Import Electricity Price – currency/kWh
# -----------------------------
class ImportElectricityPriceSensor(EconomySensor):
    _attr_state_class = "measurement"
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "07 Import Electricity Price",
            "import_electricity_price",
            sensor_type="import_price",
        )

    @property
    def native_unit_of_measurement(self):
        return f"{self.coordinator.currency}/kWh"

    def _handle_coordinator_update(self):
        state = self.hass.states.get(self.coordinator.import_price_entity)

        try:
            value = float(state.state) if state else 0
        except (ValueError, TypeError):
            value = 0

        self._value = round(value, 3)
        self.async_write_ha_state()


# -----------------------------
# Export Electricity Price – currency/kWh
# -----------------------------
class ExportElectricityPriceSensor(EconomySensor):
    _attr_state_class = "measurement"
    _attr_icon = "mdi:cash"

    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "08 Export Electricity Price",
            "export_electricity_price",
            sensor_type="export_price",
        )

    @property
    def native_unit_of_measurement(self):
        return f"{self.coordinator.currency}/kWh"

    def _handle_coordinator_update(self):
        state = self.hass.states.get(self.coordinator.export_price_entity)

        try:
            value = float(state.state) if state else 0
        except (ValueError, TypeError):
            value = 0

        self._value = round(value, 3)
        self.async_write_ha_state()

# -----------------------------
# Grid Independence – %
# -----------------------------
class GridIndependenceSensor(EconomySensor):
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:home-battery-outline"
    _attr_state_class = "measurement"
    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "30 Grid Independence",
            "grid_independence",
            sensor_type="independence",
        )
    def _handle_coordinator_update(self):
        energy = self.coordinator.data.get("energy", {})
        solar_house = energy.get("solar_house", 0)
        battery_house = energy.get("battery_house", 0)
        grid_house = energy.get("grid_house", 0)
        total_house = solar_house + battery_house + grid_house
        if total_house <= 0:
            self._value = 0
        else:
            self._value = round(
                ((solar_house + battery_house) / total_house) * 100,
                1,
            )
        self.async_write_ha_state()

# -----------------------------
# Solar Self-Consumption Rate – %
# -----------------------------
class SolarSelfConsumptionSensor(EconomySensor):
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:solar-power"
    _attr_state_class = "measurement"

    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "32 Solar Self-Consumption Rate",
            "solar_self_consumption",
            sensor_type="solar_self_consumption",
        )

    def _handle_coordinator_update(self):

        energy = self.coordinator.data.get("energy", {})

        solar_house = energy.get("solar_house", 0)
        solar_battery = energy.get("solar_battery", 0)
        solar_export = energy.get("solar_export", 0)

        solar_total = solar_house + solar_battery + solar_export
        solar_used = solar_house + solar_battery

        if solar_total <= 0:
            self._value = 0
        else:
            self._value = round((solar_used / solar_total) * 100, 1)

        self.async_write_ha_state()

# -----------------------------
# Battery Utilization – %
# -----------------------------
class BatteryUtilizationSensor(EconomySensor):
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:battery-sync"
    _attr_state_class = "measurement"
    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "31 Battery Utilization",
            "battery_utilization",
            sensor_type="battery_util",
        )
    def _handle_coordinator_update(self):
        energy = self.coordinator.data.get("energy", {})
        battery_house = energy.get("battery_house", 0)
        battery_grid = energy.get("battery_grid", 0)
        solar_battery = energy.get("solar_battery", 0)
        grid_battery = energy.get("grid_battery", 0)
        battery_discharge = battery_house + battery_grid
        battery_charge = solar_battery + grid_battery
        # Prevent unrealistic values when history is very small
        if battery_charge < 0.1:
            self._value = 0
        else:
            self._value = round((battery_discharge / battery_charge) * 100, 1)
        self.async_write_ha_state()

# -----------------------------
# CO2 Saved – kg
# -----------------------------
class CO2SavedSensor(EconomySensor):
    _attr_native_unit_of_measurement = "kg"
    _attr_icon = "mdi:molecule-co2"
    _attr_state_class = "total"
    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "33 CO2 Saved",
            "co2_saved",
            sensor_type="co2",
        )
    def _handle_coordinator_update(self):
        energy = self.coordinator.data.get("energy", {})
        solar_house = energy.get("solar_house", 0)
        battery_house = energy.get("battery_house", 0)
        total_kwh = solar_house + battery_house
        co2_factor = self.coordinator.co2_factor
        self._value = round(total_kwh * co2_factor, 2)
        self.async_write_ha_state()

# -----------------------------
# Solar Savings – SEK
# -----------------------------
class SolarSavingsSensor(EconomySensor):
    @property
    def native_unit_of_measurement(self):
        return self.coordinator.currency
    _attr_icon = "mdi:solar-power"

    def __init__(self, coordinator, hass, entry):
        super().__init__(coordinator, hass, entry, "20 Solar Savings", "solar_savings", sensor_type="solar")

    def _handle_coordinator_update(self):
        money = self.coordinator.data.get("money", {})

        solar_house = money.get("solar_house", 0)
        solar_export = money.get("solar_export", 0)

        self._value = round(solar_house + solar_export, 2)

        self.async_write_ha_state()

# -----------------------------
# Battery Savings – SEK
# -----------------------------
class BatterySavingsSensor(EconomySensor):
    @property
    def native_unit_of_measurement(self):
        return self.coordinator.currency
    _attr_icon = "mdi:battery"

    def __init__(self, coordinator, hass, entry):
        super().__init__(coordinator, hass, entry, "21 Battery Savings", "battery_savings", sensor_type="battery")

    def _handle_coordinator_update(self):
        money = self.coordinator.data.get("money", {})

        battery_house = money.get("battery_house", 0)
        battery_grid = money.get("battery_grid", 0)

        self._value = round(battery_house + battery_grid, 2)

        self.async_write_ha_state()

# -----------------------------
# Battery Arbitrage Profit – SEK
# -----------------------------
class BatteryArbitrageSensor(EconomySensor):
    @property
    def native_unit_of_measurement(self):
        return self.coordinator.currency
    _attr_icon = "mdi:scale-balance"
    _attr_state_class = "total"
    _attr_device_class = "monetary"

    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "23 Battery Arbitrage Profit",
            "battery_arbitrage_profit",
            sensor_type="battery_arbitrage",
        )

    def _handle_coordinator_update(self):
        money = self.coordinator.data.get("money", {})

        grid_charge_cost = money.get("grid_battery", 0)
        battery_export_income = money.get("battery_grid", 0)

        value = battery_export_income - grid_charge_cost

        self._value = round(value, 2)

        self.async_write_ha_state()

# -----------------------------
# Battery Self-Consumption Gain – SEK
# -----------------------------
class BatterySelfConsumptionSensor(EconomySensor):
    @property
    def native_unit_of_measurement(self):
        return self.coordinator.currency
    _attr_icon = "mdi:home-battery"
    _attr_state_class = "total"
    _attr_device_class = "monetary"

    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "22 Battery Self-Consumption Gain",
            "battery_self_consumption_gain",
            sensor_type="battery_self_consumption",
        )

    def _handle_coordinator_update(self):
        money = self.coordinator.data.get("money", {})

        battery_house = money.get("battery_house", 0)

        self._value = round(battery_house, 2)

        self.async_write_ha_state()
