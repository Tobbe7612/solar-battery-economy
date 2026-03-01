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
        ("solar_export", "Earnings Solar-Export"),
        ("battery_export", "Earnings Battery-Export"),
        ("baseline_cost", "Baseline Cost (No System)"),
        ("actual_grid_cost", "Actual Grid Cost"),
        ("export_income", "Export Income"),
        ("total", "Total Savings"),
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
    sensors.append(GridIndependenceSensor(coordinator, hass, entry))
    if advanced_mode:
        sensors.append(BatteryUtilizationSensor(coordinator, hass, entry))
    sensors.append(CO2SavedSensor(coordinator, hass, entry))
    sensors.append(PeriodEconomySensor(coordinator, hass, entry, "Economy Today", "day"))
    sensors.append(PeriodEconomySensor(coordinator, hass, entry, "Economy This Month", "month"))
    sensors.append(PeriodEconomySensor(coordinator, hass, entry, "Economy This Year", "year"))

    async_add_entities(sensors)
    await coordinator.async_restore_from_hass()
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
    _attr_native_unit_of_measurement = "SEK"
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
    _attr_native_unit_of_measurement = "SEK"
    _attr_device_class = "monetary"
    _attr_state_class = "total"

    def __init__(self, coordinator, hass, entry, name, period):
        super().__init__(coordinator, hass, entry, name, f"period_{period}", sensor_type="period")
        self._attr_icon = "mdi:calendar-month"
        self._period = period
        self._baseline = 0.0
        self._last_reset = None

    async def async_added_to_hass(self):
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            self._value = float(last_state.state)
            self._baseline = float(last_state.attributes.get("baseline", 0))
            last_reset_str = last_state.attributes.get("last_reset")
            if last_reset_str:
                from homeassistant.util.dt import parse_datetime
                self._last_reset = parse_datetime(last_reset_str)
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))

    def _needs_reset(self, now):
        if self._last_reset is None:
            return True
        last = self._last_reset
        if self._period == "day":
            return now.date() != last.date()
        if self._period == "month":
            return (now.year, now.month) != (last.year, last.month)
        if self._period == "year":
            return now.year != last.year
        return False

    def _handle_coordinator_update(self):
        savings = self.coordinator.data.get("savings", {})
        total = savings.get("total", 0)
        now = dt_util.now()
        if self._needs_reset(now):
            self._baseline = total
            self._last_reset = now
        self._value = round(total - self._baseline, 2)
        self._attr_extra_state_attributes = {
            "baseline": self._baseline,
            "last_reset": self._last_reset.isoformat() if self._last_reset else None,
        }
        self.async_write_ha_state()


# -----------------------------
# PaybackSensor
# -----------------------------
class PaybackSensor(EconomySensor, RestoreEntity):
    _attr_native_unit_of_measurement = "years"
    def __init__(self, coordinator, hass, entry):
        super().__init__(coordinator, hass, entry, "Payback Time", "payback_time", sensor_type="payback")
        self._attr_icon = "mdi:calendar-sync"
        self._start_date = None
    async def async_added_to_hass(self):
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            try:
                self._value = float(last_state.state)
            except ValueError:
                self._value = 0

            start_str = last_state.attributes.get("start_date")
            if start_str:
                from homeassistant.util.dt import parse_datetime
                self._start_date = parse_datetime(start_str)
        await super().async_added_to_hass()
    def _handle_coordinator_update(self):
        savings = self.coordinator.data.get("savings", {})
        total = savings.get("total", 0)
        investment = self.coordinator.investment
        now = dt_util.now()
        if investment <= 0:
            self._value = 0
            self.async_write_ha_state()
            return
        # Start when first positive total appears
        if self._start_date is None and total > 0:
            self._start_date = now
        if self._start_date is None or total <= 0:
            self._value = 0
            self.async_write_ha_state()
            return
        # Calculate daily average based on total savings
        days_running = (now - self._start_date).total_seconds() / 86400
        if days_running <= 0:
            self._value = 0
            self.async_write_ha_state()
            return
        daily_average = total / max(days_running, 1)
        yearly_estimate = daily_average * 365
        if yearly_estimate <= 0:
            self._value = 0
        else:
            self._value = round(investment / yearly_estimate, 2)
        self._attr_extra_state_attributes = {
            "start_date": self._start_date.isoformat() if self._start_date else None,
            "days_running": round(days_running, 2),
            "daily_average": round(daily_average, 2),
            "yearly_estimate": round(yearly_estimate, 2),
        }
        self.async_write_ha_state()

# -----------------------------
# SavingsSensor – SEK
# -----------------------------
class SavingsSensor(EconomySensor):
    _attr_native_unit_of_measurement = "SEK"
    _attr_device_class = "monetary"
    _attr_state_class = "total"
    def __init__(self, coordinator, hass, entry, name, key):
        super().__init__(coordinator, hass, entry, name, key, sensor_type="savings")
        # MAIN VISIBLE FINANCIAL SENSORS
        if key == "total":
            self._attr_icon = "mdi:trending-up"
        elif key == "baseline_cost":
            self._attr_icon = "mdi:cash-multiple"
        elif key == "actual_grid_cost":
            self._attr_icon = "mdi:transmission-tower"
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
            "Return On Investment",
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
    _attr_native_unit_of_measurement = "SEK"
    _attr_icon = "mdi:calendar-star"
    _attr_state_class = "measurement"
    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "Estimated Annual Savings",
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
            1,
        )
        daily_average = total / days_running
        self._value = round(daily_average * 365, 2)
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
            "Grid Independence",
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
# Battery Utilization – %
# -----------------------------
class BatteryUtilizationSensor(EconomySensor):
    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:battery-sync"
    _attr_state_class = "measurement"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "Battery Utilization",
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
        if battery_charge <= 0:
            self._value = 0
        else:
            self._value = round(
                (battery_discharge / battery_charge) * 100,
                1,
            )
        self.async_write_ha_state()

# -----------------------------
# PayBack Date
# -----------------------------
class PaybackDateSensor(EconomySensor):
    _attr_icon = "mdi:calendar-check"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    def __init__(self, coordinator, hass, entry):
        super().__init__(
            coordinator,
            hass,
            entry,
            "Estimated Payback Date",
            "payback_date",
            sensor_type="payback_date",
        )
        # Timestamp sensors must start as None
        self._value = None
        # 🔹 DEFINE THESE HERE (CRITICAL)
        self._start_date = None
        self._last_update_time = None
    @property
    def native_value(self):
        return self._value
    def _handle_coordinator_update(self):
        savings = self.coordinator.data.get("savings", {})
        total = savings.get("total", 0)
        investment = self.coordinator.investment
        now = dt_util.now()
        # Create start date when savings first become positive
        if self._start_date is None and total > 0:
            self._start_date = now
        if self._start_date is None or investment <= 0:
            return
        # Throttle updates to every 12 hours
        if self._last_update_time is not None:
            if now - self._last_update_time < timedelta(hours=12):
                return
        days_running = max(
            (now - self._start_date).total_seconds() / 86400,
            1,
        )
        daily_average = total / days_running
        if daily_average <= 0:
            return
        remaining_amount = investment - total
        if remaining_amount <= 0:
            new_value = now
        else:
            days_remaining = remaining_amount / daily_average
            new_value = now + timedelta(days=days_remaining)
        self._value = new_value
        self._last_update_time = now
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
            "CO2 Saved",
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