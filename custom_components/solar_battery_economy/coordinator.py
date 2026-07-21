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
from .economy_calculations import calculate_savings, battery_solar_share

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
        self.solar_investment = conf.get("solar_investment", 0)
        self.battery_investment = conf.get("battery_investment", 0)
        self.co2_factor = conf.get("co2_factor", 0.4)
        self.currency = entry.options.get(
            "currency",
            conf.get("currency", "SEK"),
)
        self._last_update = None
        self._unsub_listeners = []
        self.install_date = None
        self._battery_split_migrated = False

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
        """Restore energy, money and install date from storage."""
        stored = await self._store.async_load()

        if not stored:
            self.install_date = dt_util.utcnow()
            return

        self.data["energy"] = stored.get("energy", {})
        self.data["money"] = stored.get("money", {})

        install_date_str = stored.get("install_date")
        if install_date_str:
            self.install_date = dt_util.parse_datetime(install_date_str)
        else:
            self.install_date = dt_util.utcnow()

        # One-time migration: backfill the solar/grid split for existing
        # installs. Tracked with a persisted flag rather than "does the key
        # exist", since the live accumulation loop creates these keys itself
        # (starting near-zero) as soon as the battery discharges once - which
        # would otherwise block this backfill from ever running.
        if not stored.get("battery_split_migrated"):
            money = self.data["money"]
            energy = self.data["energy"]
            share = battery_solar_share(energy)

            bh_total = money.get("battery_house", 0)
            money["battery_house_from_solar"] = round(bh_total * share, 6)
            money["battery_house_from_grid"] = round(bh_total * (1 - share), 6)

            bg_total = money.get("battery_grid", 0)
            money["battery_grid_from_solar"] = round(bg_total * share, 6)
            money["battery_grid_from_grid"] = round(bg_total * (1 - share), 6)

            self._battery_split_migrated = True
        else:
            self._battery_split_migrated = True

    async def _save_state(self):
        """Save current totals to storage."""
        try:
            await self._store.async_save(
                {
                    "energy": self.data["energy"],
                    "money": self.data["money"],
                    "install_date": self.install_date.isoformat()
                        if self.install_date else None,
                    "battery_split_migrated": self._battery_split_migrated,
                }
            )
        except Exception as err:
            _LOGGER.warning("Failed to save Solar Battery Economy state: %s", err)

    def annual_estimate(self, total):
        """Calculate annualized estimate using the persisted install date."""
        if total <= 0 or self.install_date is None:
            return 0
        days_running = max(
            (dt_util.utcnow() - self.install_date).total_seconds() / 86400,
            0.01,
        )
        effective_days = max(days_running, 3)
        daily_average = total / effective_days
        return daily_average * 365

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
            if self.install_date is None:
                self.install_date = dt_util.utcnow()
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

            import_price_raw = _float_state(self.hass, self.import_price_entity)
            export_price_raw = _float_state(self.hass, self.export_price_entity)

            energy = self.data["energy"]
            money = self.data["money"]

            # Energy always accumulates, regardless of price availability
            for flow_key, power in flows.items():
                base_key = flow_key.replace("_power", "")
                delta_kwh = max(power, 0) * dt_hours / 1000
                energy[base_key] = round(energy.get(base_key, 0) + delta_kwh, 6)

            if import_price_raw is None or export_price_raw is None:
                # Price source unavailable this cycle - skip money booking
                # entirely rather than treating the energy as free.
                self.data["price_unavailable_count"] = (
                    self.data.get("price_unavailable_count", 0) + 1
                )
                _LOGGER.debug(
                    "Skipped money accumulation: import or export price unavailable"
                )
            else:
                import_price = import_price_raw
                export_price = export_price_raw
                solar_share = battery_solar_share(energy)

                for flow_key, power in flows.items():
                    base_key = flow_key.replace("_power", "")
                    delta_kwh = max(power, 0) * dt_hours / 1000

                    if flow_key == "solar_house_power":
                        money[base_key] = round(
                            money.get(base_key, 0) + delta_kwh * import_price, 6
                        )

                    elif flow_key == "battery_house_power":
                        value = delta_kwh * import_price
                        money[base_key] = round(money.get(base_key, 0) + value, 6)
                        money["battery_house_from_solar"] = round(
                            money.get("battery_house_from_solar", 0)
                            + value * solar_share, 6,
                        )
                        money["battery_house_from_grid"] = round(
                            money.get("battery_house_from_grid", 0)
                            + value * (1 - solar_share), 6,
                        )

                    elif flow_key == "solar_export_power":
                        money[base_key] = round(
                            money.get(base_key, 0) + delta_kwh * export_price, 6
                        )

                    elif flow_key == "battery_grid_power":
                        value = delta_kwh * export_price
                        money[base_key] = round(money.get(base_key, 0) + value, 6)
                        money["battery_grid_from_solar"] = round(
                            money.get("battery_grid_from_solar", 0)
                            + value * solar_share, 6,
                        )
                        money["battery_grid_from_grid"] = round(
                            money.get("battery_grid_from_grid", 0)
                            + value * (1 - solar_share), 6,
                        )

                    elif flow_key in ("grid_house_power", "grid_battery_power"):
                        money[base_key] = round(
                            money.get(base_key, 0) + delta_kwh * import_price, 6
                        )

                    elif flow_key == "house_grid_power":
                        money[base_key] = round(
                            money.get(base_key, 0) + delta_kwh * export_price, 6
                        )

            self.data["savings"] = calculate_savings(money)

            # Save totals to storage
            await self._save_state()

        except Exception as err:
            _LOGGER.warning("Coordinator update failed: %s", err)

        return self.data