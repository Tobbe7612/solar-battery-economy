# coordinator.py
import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import callback
from homeassistant.util import dt as dt_util
from homeassistant.helpers.storage import Store

from .sensor_helpers import _float_state
from .flow_calculation import calculate_flows
from .const import DOMAIN
from .economy_calculations import calculate_savings

_LOGGER = logging.getLogger(__name__)


class SolarBatteryEconomyCoordinator(DataUpdateCoordinator):
    """Coordinator for Solar & Battery Economy integration."""

    def __init__(self, hass, entry):
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=None,
        )

        self.entry = entry
        conf = entry.options or entry.data

        self.solar_entity = conf["solar_power"]
        self.grid_entity = conf["grid_power"]
        self.battery_entity = conf["battery_power"]
        self.import_price_entity = conf["import_price"]
        self.export_price_entity = conf["export_price"]
        self.investment = conf.get("investment", 0)
        self.co2_factor = conf.get("co2_factor", 0.4)

        self._last_update = None
        self._unsub_listeners = []

        # Persistent storage
        self._store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")

        self.data = {
            "power": {},
            "energy": {},
            "money": {},
            "savings": {},
        }

    # ---------------------------------------------------------
    # STORAGE RESTORE
    # ---------------------------------------------------------

    async def async_restore(self):
        """Restore energy and money totals from storage."""
        stored = await self._store.async_load()

        if not stored:
            return

        self.data["energy"] = stored.get("energy", {})
        self.data["money"] = stored.get("money", {})

    async def _save_state(self):
        """Save current totals to storage."""
        try:
            await self._store.async_save(
                {
                    "energy": self.data["energy"],
                    "money": self.data["money"],
                }
            )
        except Exception as err:
            _LOGGER.warning("Failed to save Solar Battery Economy state: %s", err)

    # ---------------------------------------------------------
    # LISTENERS
    # ---------------------------------------------------------

    async def async_setup_listeners(self):
        self.async_unload_listeners()

        entities = [
            self.solar_entity,
            self.grid_entity,
            self.battery_entity,
            self.import_price_entity,
            self.export_price_entity,
        ]

        unsub = async_track_state_change_event(
            self.hass,
            entities,
            self._async_update_from_event,
        )

        self._unsub_listeners.append(unsub)

    def async_unload_listeners(self):
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

    @callback
    def _async_update_from_event(self, event):
        self.hass.async_create_task(self._handle_event_update())

    async def _handle_event_update(self):
        data = await self._async_update_data()
        self.async_set_updated_data(data)

    # ---------------------------------------------------------
    # MAIN UPDATE
    # ---------------------------------------------------------

    async def _async_update_data(self):

        try:
            now = dt_util.utcnow()

            solar_w = _float_state(self.hass, self.solar_entity)
            grid_w = _float_state(self.hass, self.grid_entity)
            battery_w = _float_state(self.hass, self.battery_entity)

            flows = calculate_flows(solar_w, grid_w, battery_w)
            self.data["power"] = flows

            if self._last_update is None:
                self._last_update = now
                return self.data
            dt_hours = max(
                (now - self._last_update).total_seconds() / 3600,
                0,
            )

            self._last_update = now

            import_price = _float_state(self.hass, self.import_price_entity) or 0
            export_price = _float_state(self.hass, self.export_price_entity) or 0

            energy = self.data["energy"]
            money = self.data["money"]

            for flow_key, power in flows.items():

                base_key = flow_key.replace("_power", "")
                delta_kwh = max(power, 0) * dt_hours / 1000

                # ENERGY
                energy[base_key] = round(energy.get(base_key, 0) + delta_kwh, 6)

                # MONEY
                if flow_key in ("solar_house_power", "battery_house_power"):
                    money[base_key] = round(money.get(base_key, 0) + delta_kwh * import_price, 6)

                elif flow_key in ("solar_export_power", "battery_grid_power"):
                    money[base_key] = round(money.get(base_key, 0) + delta_kwh * export_price, 6)

                elif flow_key in ("grid_house_power", "grid_battery_power"):
                    money[base_key] = round(money.get(base_key, 0) + delta_kwh * import_price, 6)

                elif flow_key == "house_grid_power":
                    money[base_key] = round(money.get(base_key, 0) + delta_kwh * export_price, 6)

            self.data["savings"] = calculate_savings(money)

            # Save totals to storage
            await self._save_state()

        except Exception as err:
            _LOGGER.warning("Coordinator update failed: %s", err)

        return self.data