# coordinator.py
import logging
import asyncio
from datetime import datetime, timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.core import EVENT_HOMEASSISTANT_STOP, callback
from homeassistant.util import dt as dt_util
from homeassistant.helpers.storage import Store
from homeassistant.helpers import entity_registry as er

from .sensor_helpers import _float_state
from .flow_calculation import calculate_flows
from .const import (
    DOMAIN,
    DEFAULT_VERY_CHEAP_LIMIT,
    DEFAULT_CHEAP_LIMIT,
    DEFAULT_NORMAL_LIMIT,
    DEFAULT_EXPENSIVE_LIMIT,
    CONF_VERY_CHEAP_LIMIT,
    CONF_CHEAP_LIMIT,
    CONF_NORMAL_LIMIT,
    CONF_EXPENSIVE_LIMIT,
    CONF_PRICE_PERIOD_MINUTES,
    CONF_PRICE_SELECTION_MODE,
    CONF_CONSUMERS,
    CONF_NORDPOOL_CONFIG_ENTRY,
    CONF_NORDPOOL_AREA,
)
from .economy_calculations import calculate_savings, battery_solar_share
from .price_model import find_cheapest_future_period
from .price_model import calculate_today_import_price_statistics
from .price_model import enrich_nordpool_price_intervals
from .nordpool_runtime import (
    NORDPOOL_TIMEZONE,
    NordPoolPriceError,
    NordPoolPriceCache,
    async_get_nordpool_price_history,
    async_get_nordpool_price_model,
)
from .analytics import build_statistics_energy_samples_with_price_history
from .dashboard_data import (
    build_consumer_dashboard_data,
    build_deterministic_insights,
    build_energy_samples_from_statistics,
    build_house_analysis,
    calculate_shared_import_price_median,
    select_price_intervals_window,
)
from .recorder_adapter import async_get_statistics
from .recorder_data import (
    clamp_history_window,
    dashboard_calendar_boundaries,
    normalize_datetime,
)

_LOGGER = logging.getLogger(__name__)


def _is_numeric(value) -> bool:
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True


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
        self.nordpool_config_entry_id = conf.get(CONF_NORDPOOL_CONFIG_ENTRY)
        self.nordpool_area = conf.get(CONF_NORDPOOL_AREA)
        self._nordpool_price_cache = NordPoolPriceCache()

        self.price_period_minutes = int(
            conf.get(CONF_PRICE_PERIOD_MINUTES, 15)
        )

        self.price_selection_mode = conf.get(
            CONF_PRICE_SELECTION_MODE,
            "consecutive",
        )

        configured_consumers = conf.get(CONF_CONSUMERS, [])
        if isinstance(configured_consumers, str):
            configured_consumers = [configured_consumers]
        self.consumer_entities = list(configured_consumers or [])

        self.investment = conf.get("investment", 0)
        self.solar_investment = conf.get("solar_investment", 0)
        self.battery_investment = conf.get("battery_investment", 0)
        self.co2_factor = conf.get("co2_factor", 0.4)
        self.currency = entry.options.get(
            "currency",
            conf.get("currency", "SEK"),
        )
        # Price classification thresholds (SEK/kWh)
        self.very_cheap_limit = conf.get(
            CONF_VERY_CHEAP_LIMIT,
            DEFAULT_VERY_CHEAP_LIMIT,
        )
        self.cheap_limit = conf.get(
            CONF_CHEAP_LIMIT,
            DEFAULT_CHEAP_LIMIT,
        )
        self.normal_limit = conf.get(
            CONF_NORMAL_LIMIT,
            DEFAULT_NORMAL_LIMIT,
        )
        self.expensive_limit = conf.get(
            CONF_EXPENSIVE_LIMIT,
            DEFAULT_EXPENSIVE_LIMIT,
        )
        self._last_update = None
        self._nordpool_price_model = None
        self._nordpool_price_model_updated = None
        self._nordpool_price_model_date = None
        self._unsub_listeners = []
        self._dashboard_subscribers = {}
        self._dashboard_subscription_cleanup = {}
        self._dashboard_refresh_unsub = None
        self._dashboard_shutdown_unsub = None
        self._dashboard_payload_task = None
        self._dashboard_latest_payload = None
        self.install_date = None
        self._battery_split_migrated = False

        # Persistent storage
        self._store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")

        self.data = {
            # Existing public data — do not rename or remove.
            "power": {},
            "energy": {},
            "money": {},
            "savings": {},

            # Phase 3 data model — populated incrementally in later phases.
            "house": {},
            "price": {},
            "price_intelligence": {},
            "consumers": {},
        }

    def _get_energy_entity_id(self, key: str) -> str | None:
        """Resolve an SBE energy sensor by its stable unique ID."""
        registry = er.async_get(self.hass)
        unique_id = f"{DOMAIN}_{self.entry.entry_id}_energy_{key}"
        return registry.async_get_entity_id("sensor", DOMAIN, unique_id)

    async def async_get_dashboard_data(
        self,
        *,
        start,
        end,
    ) -> dict:
        """Return dashboard data using the existing request/response contract."""
        return await self.async_build_dashboard_payload(start=start, end=end)

    async def async_build_dashboard_payload(
        self,
        *,
        start,
        end,
    ) -> dict:
        """Build a complete dashboard payload from current cached/runtime data."""
        analysis_start, analysis_end = clamp_history_window(
            start=start,
            end=end,
        )
        try:
            price_model = await async_get_nordpool_price_model(
                self.hass,
                now=analysis_end,
                config_entry_id=self.nordpool_config_entry_id,
                area=self.nordpool_area,
                cache=self._nordpool_price_cache,
                very_cheap_limit=self.very_cheap_limit,
                cheap_limit=self.cheap_limit,
                normal_limit=self.normal_limit,
                expensive_limit=self.expensive_limit,
            )
        except NordPoolPriceError as err:
            _LOGGER.debug("Nord Pool dashboard prices unavailable: %s", err)
            price_model = {"current": None, "forecast": []}

        calendar = dashboard_calendar_boundaries(now=analysis_end)
        series_start = normalize_datetime(calendar.yesterday_start)
        series_end = analysis_end

        forecast = price_model.get("forecast", [])
        forecast_ends = [
            item["end"]
            for item in forecast
            if isinstance(item.get("end"), datetime)
        ]
        window_end = max([series_end, *forecast_ends])

        house_total_entity = self._get_energy_entity_id("house_total")
        grid_house_entity = self._get_energy_entity_id("grid_house")
        battery_house_entity = self._get_energy_entity_id("battery_house")
        consumer_entities = list(self.consumer_entities)

        analysis_energy_ids = [
            entity_id
            for entity_id in [
                house_total_entity,
                grid_house_entity,
                battery_house_entity,
                *consumer_entities,
            ]
            if entity_id
        ]
        timeseries_energy_ids = [
            entity_id
            for entity_id in [house_total_entity, *consumer_entities]
            if entity_id
        ]

        try:
            direct_spot_history = await async_get_nordpool_price_history(
                self.hass,
                config_entry_id=self.nordpool_config_entry_id,
                area=self.nordpool_area,
                start=series_start,
                end=series_end,
                cache=self._nordpool_price_cache,
            )
        except NordPoolPriceError as err:
            _LOGGER.debug(
                "Nord Pool historical spot prices unavailable: %s",
                err,
            )
            direct_spot_history = []

        direct_import_intervals = enrich_nordpool_price_intervals(
            direct_spot_history,
            very_cheap_limit=self.very_cheap_limit,
            cheap_limit=self.cheap_limit,
            normal_limit=self.normal_limit,
            expensive_limit=self.expensive_limit,
        )
        # Nord Pool is the sole price-history source. Recorder remains the
        # source for measured energy statistics.
        price_states = [
            {
                "timestamp": item["start"],
                "state": item["import"],
                "attributes": {},
            }
            for item in direct_import_intervals
        ]

        statistics = await async_get_statistics(
            self.hass,
            set(timeseries_energy_ids),
            start=series_start,
            end=series_end,
            types={"change"},
            enforce_max_history=False,
        )
        analysis_statistics = await async_get_statistics(
            self.hass,
            set(analysis_energy_ids),
            start=analysis_start,
            end=analysis_end,
            types={"change"},
        )

        house_total_stats = statistics.get(house_total_entity, []) if house_total_entity else []
        analysis_house_total_stats = analysis_statistics.get(house_total_entity, []) if house_total_entity else []
        analysis_grid_house_stats = analysis_statistics.get(grid_house_entity, []) if grid_house_entity else []
        analysis_battery_house_stats = analysis_statistics.get(battery_house_entity, []) if battery_house_entity else []
        analysis_price_intervals = select_price_intervals_window(
            direct_import_intervals,
            start=analysis_start,
            end=analysis_end,
        )
        analysis_price_states = [
            {
                "timestamp": item["start"],
                "state": item["import"],
                "attributes": {},
            }
            for item in analysis_price_intervals
        ]

        grid_house_samples = build_statistics_energy_samples_with_price_history(
            analysis_grid_house_stats,
            analysis_price_states,
        )
        battery_house_samples = build_statistics_energy_samples_with_price_history(
            analysis_battery_house_stats,
            analysis_price_states,
        )
        analysis_house_total_samples = (
            build_statistics_energy_samples_with_price_history(
                analysis_house_total_stats,
                analysis_price_states,
            )
        )

        shared_reference_price = calculate_shared_import_price_median(
            analysis_price_states
        )
        house = build_house_analysis(
            analysis_house_total_samples,
            reference_price=shared_reference_price,
            battery_house_samples=(
                battery_house_samples
                if battery_house_entity
                else None
            ),
        )

        consumers = {}
        for entity_id in consumer_entities:
            state = self.hass.states.get(entity_id)
            name = state.name if state is not None else entity_id
            samples = build_statistics_energy_samples_with_price_history(
                statistics.get(entity_id, []),
                price_states,
            )
            analysis_samples = build_statistics_energy_samples_with_price_history(
                analysis_statistics.get(entity_id, []),
                analysis_price_states,
            )
            consumer_data = build_consumer_dashboard_data(
                name=name,
                energy_entity=entity_id,
                samples=analysis_samples,
                reference_price=shared_reference_price,
                house_total_samples=analysis_house_total_samples,
                house_average_import_price=house["average_import_price"],
            )
            consumer_data["history"] = samples
            consumers[entity_id] = consumer_data

        current_price = price_model.get("current")
        dashboard_price_intelligence = {
            "current_price_class": (
                current_price.get("price_class")
                if current_price is not None
                else None
            ),
            "price_quality_index": (
                current_price.get("price_quality")
                if current_price is not None
                else None
            ),
            "today_import_price_statistics": calculate_today_import_price_statistics(
                forecast,
                now=analysis_end,
            ),
            "cheapest_future_period": find_cheapest_future_period(
                forecast,
                now=analysis_end,
                duration_minutes=self.price_period_minutes,
                selection_mode=self.price_selection_mode,
            ),
        }

        return {
            "window": {
                "start": series_start.isoformat(),
                "yesterday_start": calendar.yesterday_start.isoformat(),
                "today_start": calendar.today_start.isoformat(),
                "end": window_end.isoformat(),
                "hours": round(
                    (window_end - series_start).total_seconds() / 3600,
                    3,
                ),
            },
            "house": house,
            "house_history": build_energy_samples_from_statistics(
                house_total_stats
            ),
            "grid_house_history": grid_house_samples,
            "price_history": {
                "import": [
                    {
                        "timestamp": item["timestamp"].isoformat(),
                        "import": float(item["state"]),
                    }
                    for item in price_states
                    if _is_numeric(item.get("state"))
                ],
                "spot": [
                    {
                        **item,
                        "start": item["start"].isoformat(),
                        "end": item["end"].isoformat(),
                        "recorded_at": item["recorded_at"].isoformat(),
                    }
                    for item in direct_spot_history
                ],
                "import_intervals": [
                    {
                        **item,
                        "start": item["start"].isoformat(),
                        "end": item["end"].isoformat(),
                        "recorded_at": item["recorded_at"].isoformat(),
                    }
                    for item in direct_import_intervals
                ],
            },
            "price": price_model,
            "price_intelligence": dashboard_price_intelligence,
            "consumers": consumers,
            "insights": build_deterministic_insights(house, consumers),
        }

    async def async_subscribe_dashboard(
        self,
        subscriber_id,
        callback_fn,
        cleanup_fn=None,
    ):
        """Register one websocket client and return the latest full payload."""
        is_first_subscriber = not self._dashboard_subscribers
        self._dashboard_subscribers[subscriber_id] = callback_fn
        if cleanup_fn is not None:
            self._dashboard_subscription_cleanup[subscriber_id] = cleanup_fn
        if is_first_subscriber:
            self._start_dashboard_refresh()

        if (
            self._dashboard_latest_payload is None
            or self._dashboard_payload_task is not None
        ):
            return await self._async_get_shared_dashboard_payload()
        return self._dashboard_latest_payload

    @callback
    def async_unsubscribe_dashboard(self, subscriber_id) -> None:
        """Remove one websocket client and stop shared jobs when none remain."""
        self._dashboard_subscribers.pop(subscriber_id, None)
        self._dashboard_subscription_cleanup.pop(subscriber_id, None)
        if not self._dashboard_subscribers:
            self._stop_dashboard_refresh()

    @callback
    def _start_dashboard_refresh(self) -> None:
        """Start exactly one refresh interval while subscribers are active."""
        if self._dashboard_refresh_unsub is not None:
            return
        self._dashboard_refresh_unsub = async_track_time_interval(
            self.hass,
            self._handle_dashboard_refresh,
            timedelta(minutes=15),
        )
        self._dashboard_shutdown_unsub = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP,
            self._handle_home_assistant_stop,
        )

    @callback
    def _handle_dashboard_refresh(self, now) -> None:
        """Queue one full payload build and broadcast it to all subscribers."""
        self.hass.async_create_task(self._async_refresh_dashboard())

    async def _async_refresh_dashboard(self) -> None:
        if not self._dashboard_subscribers:
            return
        try:
            payload = await self._async_get_shared_dashboard_payload()
        except Exception:
            _LOGGER.exception("Unable to refresh Solar Battery Economy dashboard")
            return

        for subscriber_callback in tuple(self._dashboard_subscribers.values()):
            try:
                subscriber_callback(payload)
            except Exception:
                _LOGGER.exception("Unable to send dashboard update to subscriber")

    async def _async_get_shared_dashboard_payload(self):
        """Build once when concurrent subscribers/ticks need a payload."""
        task = self._dashboard_payload_task
        if task is None:
            end = dt_util.utcnow()
            self._dashboard_latest_payload = None
            task = self.hass.async_create_task(
                self.async_build_dashboard_payload(
                    start=end - timedelta(hours=24),
                    end=end,
                )
            )
            self._dashboard_payload_task = task
        try:
            payload = await asyncio.shield(task)
        finally:
            if self._dashboard_payload_task is task and task.done():
                self._dashboard_payload_task = None
        self._dashboard_latest_payload = payload
        return payload

    @callback
    def _handle_home_assistant_stop(self, event) -> None:
        self._stop_dashboard_refresh()

    @callback
    def async_shutdown_dashboard(self) -> None:
        """Release dashboard subscriptions during config-entry unload."""
        self._stop_dashboard_refresh()

    @callback
    def _stop_dashboard_refresh(self) -> None:
        """Cancel interval/listeners and release the shared payload state."""
        if self._dashboard_refresh_unsub is not None:
            self._dashboard_refresh_unsub()
            self._dashboard_refresh_unsub = None
        if self._dashboard_shutdown_unsub is not None:
            self._dashboard_shutdown_unsub()
            self._dashboard_shutdown_unsub = None
        task = self._dashboard_payload_task
        if task is not None and not task.done():
            task.cancel()
        self._dashboard_payload_task = None
        self._dashboard_latest_payload = None
        self._dashboard_subscribers.clear()
        cleanup_callbacks = tuple(self._dashboard_subscription_cleanup.values())
        self._dashboard_subscription_cleanup.clear()
        for cleanup_callback in cleanup_callbacks:
            cleanup_callback()

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
            # Canonical total house power.
            # Derived directly from the existing directional house flows.
            self.data["power"]["house_total"] = round(
                flows.get("solar_house_power", 0)
                + flows.get("battery_house_power", 0)
                + flows.get("grid_house_power", 0),
                3,
            )

            if self._last_update is None:
                # First update: establish the time baseline without
                # accumulating energy or money for the time before startup.
                dt_hours = 0
            else:
                dt_hours = max(
                    (now - self._last_update).total_seconds() / 3600,
                    0,
                )

            self._last_update = now

            local_date = dt_util.now().astimezone(NORDPOOL_TIMEZONE).date()
            should_refresh_prices = (
                self._nordpool_price_model_updated is None
                or self._nordpool_price_model_date != local_date
                or now - self._nordpool_price_model_updated >= timedelta(minutes=15)
            )
            if should_refresh_prices:
                try:
                    self._nordpool_price_model = await async_get_nordpool_price_model(
                        self.hass,
                        now=now,
                        config_entry_id=self.nordpool_config_entry_id,
                        area=self.nordpool_area,
                        cache=self._nordpool_price_cache,
                        very_cheap_limit=self.very_cheap_limit,
                        cheap_limit=self.cheap_limit,
                        normal_limit=self.normal_limit,
                        expensive_limit=self.expensive_limit,
                    )
                except NordPoolPriceError as err:
                    _LOGGER.warning("Nord Pool prices unavailable: %s", err)
                    if self._nordpool_price_model is None:
                        self._nordpool_price_model = {
                            "current": None,
                            "forecast": [],
                        }
                self._nordpool_price_model_updated = now
                self._nordpool_price_model_date = local_date

            price_model = self._nordpool_price_model or {
                "current": None,
                "forecast": [],
            }

            current_price = price_model["current"]

            if current_price is None:
                import_price_raw = None
                export_price_raw = None
            else:
                import_price_raw = current_price.get("import")
                export_price_raw = current_price.get("export")

            self.data["price"] = price_model

            current_price_class = None
            price_quality_index = None
            if current_price is not None:
                current_price_class = current_price.get("price_class")
                price_quality_index = current_price.get("price_quality")

            self.data["consumers"] = {
                entity_id: {
                    "name": (
                        self.hass.states.get(entity_id).name
                        if self.hass.states.get(entity_id) is not None
                        else entity_id
                    ),
                    "energy_entity": entity_id,
                }
                for entity_id in self.consumer_entities
            }

            self.data["price_intelligence"] = {
                "current_price_class": current_price_class,
                "price_quality_index": price_quality_index,
                "today_import_price_statistics": calculate_today_import_price_statistics(
                    price_model.get("forecast", []),
                    now=now,
                ),
                "cheapest_future_period": find_cheapest_future_period(
                    price_model.get("forecast", []),
                    now=now,
                    duration_minutes=self.price_period_minutes,
                    selection_mode=self.price_selection_mode,
                ),
            }

            energy = self.data["energy"]
            money = self.data["money"]

            # Energy always accumulates, regardless of price availability
            for flow_key, power in flows.items():
                base_key = flow_key.replace("_power", "")
                delta_kwh = max(power, 0) * dt_hours / 1000
                energy[base_key] = round(energy.get(base_key, 0) + delta_kwh, 6)

            if import_price_raw is None or export_price_raw is None:
                # Nord Pool price unavailable this cycle - skip money booking
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
            # Canonical cumulative total house energy.
            # Derived from the three existing accumulated house flows.
            energy["house_total"] = round(
                energy.get("solar_house", 0)
                + energy.get("battery_house", 0)
                + energy.get("grid_house", 0),
                6,
            )
            self.data["savings"] = calculate_savings(money)

            # Save totals to storage
            await self._save_state()

        except Exception as err:
            _LOGGER.warning("Coordinator update failed: %s", err)

        return self.data
