from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN, DEFAULT_NAME


class EconomySensor(CoordinatorEntity, SensorEntity):
    """Base sensor for Solar Battery Economy."""

    def __init__(self, coordinator, hass, entry, name, key, sensor_type="generic"):
        super().__init__(coordinator)

        self._hass = hass
        self._entry = entry
        self._key = key
        self._sensor_type = sensor_type
        self._attr_name = name
        self._value = 0.0

        # Stable unique ID
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{sensor_type}_{key}"

        # Device grouping (2 devices total)
        if sensor_type in ("power", "energy"):
            device_group = "energy_system"
            device_name = f"{DEFAULT_NAME} - Energy System"
        else:
            device_group = "financial_system"
            device_name = f"{DEFAULT_NAME} - Financial"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{entry.entry_id}_{device_group}")},
            "name": device_name,
            "manufacturer": "Tobbe",
            "model": "Solar Battery Economy",
            "sw_version": entry.version,
        }

    @property
    def native_value(self):
        return self._value

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self):
        self.async_write_ha_state()