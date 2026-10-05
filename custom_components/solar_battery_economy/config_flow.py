"""Config flow for Solar Battery Economy."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import ConfigEntrySelector, selector

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    CONF_SOLAR_POWER,
    CONF_GRID_POWER,
    CONF_BATTERY_POWER,
    CONF_NORDPOOL_CONFIG_ENTRY,
    CONF_NORDPOOL_AREA,
    CONF_PRICE_PERIOD_MINUTES,
    CONF_PRICE_SELECTION_MODE,
    CONF_CONSUMERS,
    CONF_INVESTMENT,
    DEFAULT_VERY_CHEAP_LIMIT,
    DEFAULT_CHEAP_LIMIT,
    DEFAULT_NORMAL_LIMIT,
    DEFAULT_EXPENSIVE_LIMIT,
    CONF_VERY_CHEAP_LIMIT,
    CONF_CHEAP_LIMIT,
    CONF_NORMAL_LIMIT,
    CONF_EXPENSIVE_LIMIT,
    get_effective_config,
)


class SolarBatteryEconomyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Battery Economy."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    def async_get_options_flow(config_entry):
        return SolarBatteryEconomyOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Start the initial setup wizard."""
        self._flow_data = {}
        return await self.async_step_energy_system()

    async def async_step_energy_system(self, user_input=None):
        """Collect the three power entities."""
        fields = (CONF_SOLAR_POWER, CONF_GRID_POWER, CONF_BATTERY_POWER)
        schema = _schema_fields(self._flow_data, self.hass, fields)
        errors = {}

        if user_input is not None:
            values = schema(dict(user_input))
            self._flow_data.update(values)
            sensors = {
                values[CONF_SOLAR_POWER],
                values[CONF_GRID_POWER],
                values[CONF_BATTERY_POWER],
            }
            if len(sensors) < 3:
                errors["base"] = "duplicate_power_sensors"
            else:
                return await self.async_step_nordpool_entry()

        return self.async_show_form(
            step_id="energy_system",
            data_schema=_schema_fields(self._flow_data, self.hass, fields),
            errors=errors,
        )

    async def async_step_nordpool_entry(self, user_input=None):
        """Select or automatically preselect a configured Nord Pool entry."""
        entries = self.hass.config_entries.async_entries("nordpool")
        default_entry = self._flow_data.get(CONF_NORDPOOL_CONFIG_ENTRY)
        if default_entry is None and len(entries) == 1:
            default_entry = entries[0].entry_id
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_NORDPOOL_CONFIG_ENTRY, default=default_entry
                ): ConfigEntrySelector({"integration": "nordpool"})
            }
        )
        errors = {}

        if user_input is not None:
            values = schema(dict(user_input))
            entry = self.hass.config_entries.async_get_entry(
                values.get(CONF_NORDPOOL_CONFIG_ENTRY)
            )
            if entry is None or entry.domain != "nordpool":
                errors["base"] = "invalid_nordpool_entry"
            else:
                self._flow_data.update(values)
                return await self.async_step_nordpool_area()

        return self.async_show_form(
            step_id="nordpool_entry", data_schema=schema, errors=errors
        )

    async def async_step_nordpool_area(self, user_input=None):
        """Select an area belonging to the chosen Nord Pool entry."""
        config_entry_id = self._flow_data.get(CONF_NORDPOOL_CONFIG_ENTRY)
        entry = self.hass.config_entries.async_get_entry(config_entry_id)
        areas = (
            sorted(set(entry.data.get("areas", [])))
            if entry is not None and entry.domain == "nordpool"
            else []
        )
        default_area = self._flow_data.get(CONF_NORDPOOL_AREA)
        if default_area is None and len(areas) == 1:
            default_area = areas[0]
        schema = vol.Schema(
            {
                vol.Required(CONF_NORDPOOL_AREA, default=default_area): selector(
                    {"select": {"options": areas, "multiple": False}}
                )
            }
        )
        errors = {}

        if user_input is not None:
            values = schema(dict(user_input))
            selection = {
                CONF_NORDPOOL_CONFIG_ENTRY: config_entry_id,
                CONF_NORDPOOL_AREA: values.get(CONF_NORDPOOL_AREA),
            }
            error = _validate_nordpool_selection(self.hass, selection)
            if error is not None:
                errors["base"] = error
            else:
                self._flow_data.update(values)
                return await self.async_step_prices()

        return self.async_show_form(
            step_id="nordpool_area", data_schema=schema, errors=errors
        )

    async def async_step_prices(self, user_input=None):
        """Collect price period, selection method, and market currency."""
        fields = (
            CONF_PRICE_PERIOD_MINUTES,
            CONF_PRICE_SELECTION_MODE,
            "currency",
        )
        schema = _schema_fields(self._flow_data, self.hass, fields)

        if user_input is not None:
            values = schema(dict(user_input))
            if CONF_PRICE_PERIOD_MINUTES in values:
                values[CONF_PRICE_PERIOD_MINUTES] = int(
                    values[CONF_PRICE_PERIOD_MINUTES]
                )
            self._flow_data.update(values)
            return await self.async_step_features()

        return self.async_show_form(step_id="prices", data_schema=schema)

    async def async_step_features(self, user_input=None):
        """Ask whether to configure energy consumers in a separate step."""
        configure_consumers_key = "_configure_consumers"
        schema = vol.Schema(
            {
                vol.Required(configure_consumers_key, default=False): selector(
                    {"boolean": {}}
                )
            }
        )

        if user_input is not None:
            values = schema(dict(user_input))
            if values.get(configure_consumers_key, False):
                return await self.async_step_consumers()
            self._flow_data[CONF_CONSUMERS] = []
            return await self.async_step_economy()

        return self.async_show_form(step_id="features", data_schema=schema)

    async def async_step_consumers(self, user_input=None):
        """Collect the existing list of energy consumer entities."""
        schema = _schema_fields(self._flow_data, self.hass, (CONF_CONSUMERS,))

        if user_input is not None:
            values = schema(dict(user_input))
            consumers = values.get(CONF_CONSUMERS, [])
            if isinstance(consumers, str):
                consumers = [consumers]
            self._flow_data[CONF_CONSUMERS] = list(consumers or [])
            return await self.async_step_economy()

        return self.async_show_form(step_id="consumers", data_schema=schema)

    async def async_step_economy(self, user_input=None):
        """Collect price classification limits and investment values."""
        fields = (
            CONF_VERY_CHEAP_LIMIT,
            CONF_CHEAP_LIMIT,
            CONF_NORMAL_LIMIT,
            CONF_EXPENSIVE_LIMIT,
            CONF_INVESTMENT,
            "solar_investment",
            "battery_investment",
            "co2_factor",
        )
        schema = _schema_fields(self._flow_data, self.hass, fields)
        errors = {}

        if user_input is not None:
            values = schema(dict(user_input))
            candidate = {**self._flow_data, **values}
            threshold_error = _validate_price_thresholds(candidate)
            self._flow_data.update(values)
            if threshold_error is not None:
                errors["base"] = threshold_error
            else:
                return await self.async_step_advanced()

        return self.async_show_form(
            step_id="economy",
            data_schema=_schema_fields(self._flow_data, self.hass, fields),
            errors=errors,
        )

    async def async_step_advanced(self, user_input=None):
        """Collect the existing SBE-specific advanced sensor option."""
        schema = _schema_fields(self._flow_data, self.hass, ("advanced_mode",))

        if user_input is not None:
            values = schema(dict(user_input))
            self._flow_data.update(values)

            unique_id = DOMAIN
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            config = _normalize_initial_config(self._flow_data)
            return self.async_create_entry(title=DEFAULT_NAME, data=config)

        return self.async_show_form(step_id="advanced", data_schema=schema)


class SolarBatteryEconomyOptionsFlow(config_entries.OptionsFlow):
    """Handle options updates for Solar Battery Economy."""

    def __init__(self, entry):
        self.entry = entry
        self._changes = {}

    async def async_step_init(self, user_input=None):
        """Start the categorized options editor."""
        self._changes = {}
        return await self.async_step_energy_system()

    def _effective(self):
        return {**get_effective_config(self.entry), **self._changes}

    def _form(self, step_id, fields, errors=None):
        return self.async_show_form(
            step_id=step_id,
            data_schema=_schema_fields(self._effective(), self.hass, fields),
            errors=errors or {},
        )

    async def async_step_energy_system(self, user_input=None):
        fields = (CONF_SOLAR_POWER, CONF_GRID_POWER, CONF_BATTERY_POWER)
        if user_input is not None:
            values = _schema_fields(self._effective(), self.hass, fields)(dict(user_input))
            self._changes.update(values)
            candidate = {**self._effective(), **values}
            if len({candidate.get(key) for key in fields}) < 3:
                return self._form("energy_system", fields, {"base": "duplicate_power_sensors"})
            return await self.async_step_nordpool_entry()
        return self._form("energy_system", fields)

    async def async_step_nordpool_entry(self, user_input=None):
        fields = (CONF_NORDPOOL_CONFIG_ENTRY,)
        if user_input is not None:
            values = dict(user_input)
            selected = self.hass.config_entries.async_get_entry(values.get(CONF_NORDPOOL_CONFIG_ENTRY))
            if selected is None or selected.domain != "nordpool":
                return self._form("nordpool_entry", fields, {"base": "invalid_nordpool_entry"})
            self._changes.update(values)
            return await self.async_step_nordpool_area()
        defaults = self._effective()
        schema = _schema_fields(defaults, self.hass, fields)
        # Keep the existing one-entry autodetection behavior.
        return self.async_show_form(step_id="nordpool_entry", data_schema=schema)

    async def async_step_nordpool_area(self, user_input=None):
        effective = self._effective()
        entry_id = effective.get(CONF_NORDPOOL_CONFIG_ENTRY)
        selected = self.hass.config_entries.async_get_entry(entry_id)
        areas = sorted(set(selected.data.get("areas", []))) if selected and selected.domain == "nordpool" else []
        old_area = effective.get(CONF_NORDPOOL_AREA)
        area_default = old_area if old_area in areas else (areas[0] if len(areas) == 1 else None)
        schema = vol.Schema({
            vol.Required(CONF_NORDPOOL_AREA, default=area_default): selector(
                {"select": {"options": areas, "multiple": False}}
            )
        })
        if user_input is not None:
            values = schema(dict(user_input))
            candidate = {**effective, **values}
            error = _validate_nordpool_selection(self.hass, candidate)
            if error:
                return self.async_show_form(step_id="nordpool_area", data_schema=schema, errors={"base": error})
            self._changes.update(values)
            return await self.async_step_prices()
        return self.async_show_form(step_id="nordpool_area", data_schema=schema)

    async def async_step_prices(self, user_input=None):
        fields = (CONF_PRICE_PERIOD_MINUTES, CONF_PRICE_SELECTION_MODE, "currency")
        if user_input is not None:
            values = _schema_fields(self._effective(), self.hass, fields)(dict(user_input))
            if CONF_PRICE_PERIOD_MINUTES in values:
                values[CONF_PRICE_PERIOD_MINUTES] = int(values[CONF_PRICE_PERIOD_MINUTES])
            self._changes.update(values)
            return await self.async_step_features()
        return self._form("prices", fields)

    async def async_step_features(self, user_input=None):
        key = "_configure_consumers"
        schema = vol.Schema({vol.Required(key, default=bool(self._effective().get(CONF_CONSUMERS, []))): selector({"boolean": {}})})
        if user_input is not None:
            values = schema(dict(user_input))
            if values.get(key):
                return await self.async_step_consumers()
            self._changes[CONF_CONSUMERS] = []
            return await self.async_step_economy()
        return self.async_show_form(step_id="features", data_schema=schema)

    async def async_step_consumers(self, user_input=None):
        fields = (CONF_CONSUMERS,)
        if user_input is not None:
            values = _schema_fields(self._effective(), self.hass, fields)(dict(user_input))
            consumers = values.get(CONF_CONSUMERS, [])
            self._changes[CONF_CONSUMERS] = [consumers] if isinstance(consumers, str) else list(consumers or [])
            return await self.async_step_economy()
        return self._form("consumers", fields)

    async def async_step_economy(self, user_input=None):
        fields = (CONF_VERY_CHEAP_LIMIT, CONF_CHEAP_LIMIT, CONF_NORMAL_LIMIT,
                  CONF_EXPENSIVE_LIMIT, CONF_INVESTMENT, "solar_investment",
                  "battery_investment", "co2_factor")
        if user_input is not None:
            values = _schema_fields(self._effective(), self.hass, fields)(dict(user_input))
            candidate = {**self._effective(), **values}
            error = _validate_price_thresholds(candidate)
            self._changes.update(values)
            if error:
                return self._form("economy", fields, {"base": error})
            return await self.async_step_advanced()
        return self._form("economy", fields)

    async def async_step_advanced(self, user_input=None):
        fields = ("advanced_mode",)
        if user_input is not None:
            self._changes.update(_schema_fields(self._effective(), self.hass, fields)(dict(user_input)))
            # Persist the complete effective mapping as flat options. Never alter entry.data.
            return self.async_create_entry(title="", data=self._effective())
        return self._form("advanced", fields)


# ======================================================
# Validation
# ======================================================


def _schema_fields(defaults, hass, field_names):
    """Build a schema subset while retaining the existing selectors/defaults."""
    full_schema = _build_schema(defaults, hass=hass)
    selected_fields = {
        marker: validator
        for marker, validator in full_schema.schema.items()
        if getattr(marker, "schema", None) in field_names
    }
    return vol.Schema(selected_fields)


def _normalize_initial_config(flow_data):
    """Return only the existing flat config keys for a new config entry."""
    config_keys = (
        CONF_SOLAR_POWER,
        CONF_GRID_POWER,
        CONF_BATTERY_POWER,
        CONF_NORDPOOL_CONFIG_ENTRY,
        CONF_NORDPOOL_AREA,
        CONF_PRICE_PERIOD_MINUTES,
        CONF_PRICE_SELECTION_MODE,
        CONF_CONSUMERS,
        CONF_VERY_CHEAP_LIMIT,
        CONF_CHEAP_LIMIT,
        CONF_NORMAL_LIMIT,
        CONF_EXPENSIVE_LIMIT,
        CONF_INVESTMENT,
        "solar_investment",
        "battery_investment",
        "advanced_mode",
        "co2_factor",
        "currency",
    )
    return {key: flow_data[key] for key in config_keys}


def _validate_price_thresholds(user_input) -> str | None:
    """Validate that price classification thresholds are strictly increasing."""
    very_cheap = float(
        user_input.get(
            CONF_VERY_CHEAP_LIMIT,
            DEFAULT_VERY_CHEAP_LIMIT,
        )
    )
    cheap = float(
        user_input.get(
            CONF_CHEAP_LIMIT,
            DEFAULT_CHEAP_LIMIT,
        )
    )
    normal = float(
        user_input.get(
            CONF_NORMAL_LIMIT,
            DEFAULT_NORMAL_LIMIT,
        )
    )
    expensive = float(
        user_input.get(
            CONF_EXPENSIVE_LIMIT,
            DEFAULT_EXPENSIVE_LIMIT,
        )
    )

    if very_cheap >= cheap:
        return "invalid_price_thresholds"

    if cheap >= normal:
        return "invalid_price_thresholds"

    if normal >= expensive:
        return "invalid_price_thresholds"

    return None


# ======================================================
# Shared schema builder
# ======================================================


def _validate_nordpool_selection(hass, user_input) -> str | None:
    """Validate the selected Nord Pool entry and one of its market areas."""
    config_entry_id = user_input.get(CONF_NORDPOOL_CONFIG_ENTRY)
    area = user_input.get(CONF_NORDPOOL_AREA)
    nordpool_entry = hass.config_entries.async_get_entry(config_entry_id)
    if nordpool_entry is None or nordpool_entry.domain != "nordpool":
        return "invalid_nordpool_entry"
    if area not in nordpool_entry.data.get("areas", []):
        return "invalid_nordpool_area"
    return None


def _build_schema(defaults=None, *, hass=None):
    defaults = defaults or {}
    nordpool_entries = (
        hass.config_entries.async_entries("nordpool") if hass is not None else []
    )
    default_nordpool_entry = defaults.get(CONF_NORDPOOL_CONFIG_ENTRY)
    if default_nordpool_entry is None and len(nordpool_entries) == 1:
        default_nordpool_entry = nordpool_entries[0].entry_id
    selected_entry = next(
        (entry for entry in nordpool_entries if entry.entry_id == default_nordpool_entry),
        None,
    )
    default_nordpool_area = defaults.get(CONF_NORDPOOL_AREA)
    if (
        default_nordpool_area is None
        and selected_entry is not None
        and len(selected_entry.data.get("areas", [])) == 1
    ):
        default_nordpool_area = selected_entry.data["areas"][0]
    area_options = sorted(
        {
            area
            for entry in nordpool_entries
            for area in entry.data.get("areas", [])
        }
    )

    power_selector = selector(
        {
            "entity": {
                "domain": "sensor",
            }
        }
    )

    return vol.Schema(
        {
            # ----- Power sensors -----
            vol.Required(
                CONF_SOLAR_POWER,
                default=defaults.get(CONF_SOLAR_POWER),
            ): power_selector,

            vol.Required(
                CONF_GRID_POWER,
                default=defaults.get(CONF_GRID_POWER),
            ): power_selector,

            vol.Required(
                CONF_BATTERY_POWER,
                default=defaults.get(CONF_BATTERY_POWER),
            ): power_selector,

            vol.Required(
                CONF_NORDPOOL_CONFIG_ENTRY,
                default=default_nordpool_entry,
            ): ConfigEntrySelector({"integration": "nordpool"}),

            vol.Required(
                CONF_NORDPOOL_AREA,
                default=default_nordpool_area,
            ): selector(
                {
                    "select": {
                        "options": area_options,
                        "multiple": False,
                    }
                }
            ),

            # ----- Future price period -----
            vol.Optional(
                CONF_PRICE_PERIOD_MINUTES,
                default=str(defaults.get(CONF_PRICE_PERIOD_MINUTES, 15)),
            ): selector(
                {
                    "select": {
                        "options": [
                            {"value": "15", "label": "15 minutes"},
                            {"value": "30", "label": "30 minutes"},
                            {"value": "60", "label": "1 hour"},
                            {"value": "120", "label": "2 hours"},
                            {"value": "240", "label": "4 hours"},
                        ]
                    }
                }
            ),

            # ----- Future price selection mode -----
            vol.Optional(
                CONF_PRICE_SELECTION_MODE,
                default=defaults.get(CONF_PRICE_SELECTION_MODE, "consecutive"),
            ): selector(
                {
                    "select": {
                        "options": [
                            {
                                "value": "consecutive",
                                "label": "Consecutive period",
                            },
                            {
                                "value": "cheapest_quarters",
                                "label": "Cheapest quarters",
                            },
                        ]
                    }
                }
            ),

            # ----- Energy Dashboard consumers -----
            vol.Optional(
                CONF_CONSUMERS,
                default=defaults.get(CONF_CONSUMERS, []),
            ): selector(
                {
                    "entity": {
                        "domain": "sensor",
                        "device_class": "energy",
                        "multiple": True,
                    }
                }
            ),

            # ----- Price classification thresholds -----
            vol.Optional(
                CONF_VERY_CHEAP_LIMIT,
                default=defaults.get(
                    CONF_VERY_CHEAP_LIMIT,
                    DEFAULT_VERY_CHEAP_LIMIT,
                ),
            ): selector(
                {
                    "number": {
                        "min": 0,
                        "max": 100,
                        "step": 0.01,
                        "mode": "box",
                        "unit_of_measurement": "SEK/kWh",
                    }
                }
            ),

            vol.Optional(
                CONF_CHEAP_LIMIT,
                default=defaults.get(
                    CONF_CHEAP_LIMIT,
                    DEFAULT_CHEAP_LIMIT,
                ),
            ): selector(
                {
                    "number": {
                        "min": 0,
                        "max": 100,
                        "step": 0.01,
                        "mode": "box",
                        "unit_of_measurement": "SEK/kWh",
                    }
                }
            ),

            vol.Optional(
                CONF_NORMAL_LIMIT,
                default=defaults.get(
                    CONF_NORMAL_LIMIT,
                    DEFAULT_NORMAL_LIMIT,
                ),
            ): selector(
                {
                    "number": {
                        "min": 0,
                        "max": 100,
                        "step": 0.01,
                        "mode": "box",
                        "unit_of_measurement": "SEK/kWh",
                    }
                }
            ),

            vol.Optional(
                CONF_EXPENSIVE_LIMIT,
                default=defaults.get(
                    CONF_EXPENSIVE_LIMIT,
                    DEFAULT_EXPENSIVE_LIMIT,
                ),
            ): selector(
                {
                    "number": {
                        "min": 0,
                        "max": 100,
                        "step": 0.01,
                        "mode": "box",
                        "unit_of_measurement": "SEK/kWh",
                    }
                }
            ),

            # ----- Optional total investment -----
            vol.Optional(
                CONF_INVESTMENT,
                default=defaults.get(CONF_INVESTMENT, 0),
            ): selector(
                {
                    "number": {
                        "min": 0,
                        "max": 1_000_000,
                        "step": 100,
                        "mode": "box",
                    }
                }
            ),

            # ----- Optional solar investment -----
            vol.Optional(
                "solar_investment",
                default=defaults.get("solar_investment", 0),
            ): selector(
                {
                    "number": {
                        "min": 0,
                        "max": 1_000_000,
                        "step": 100,
                        "mode": "box",
                    }
                }
            ),

            # ----- Optional battery investment -----
            vol.Optional(
                "battery_investment",
                default=defaults.get("battery_investment", 0),
            ): selector(
                {
                    "number": {
                        "min": 0,
                        "max": 1_000_000,
                        "step": 100,
                        "mode": "box",
                    }
                }
            ),

            # ----- Optional Advanced Mode -----
            vol.Optional(
                "advanced_mode",
                default=defaults.get("advanced_mode", False),
            ): cv.boolean,

            # ----- Optional CO2 calculation -----
            vol.Optional(
                "co2_factor",
                default=defaults.get("co2_factor", 0.4),
            ): selector(
                {
                    "number": {
                        "min": 0,
                        "max": 2,
                        "step": 0.01,
                        "mode": "box",
                    }
                }
            ),

            vol.Optional("currency", default=defaults.get("currency", "SEK")): vol.In(
                {
                    "SEK": "SEK (Swedish Krona)",
                    "EUR": "EUR (€ Euro)",
                    "USD": "USD ($ US Dollar)",
                    "NOK": "NOK (Norwegian Krone)",
                    "DKK": "DKK (Danish Krone)",
                    "GBP": "GBP (£ British Pound)",
                }
            ),
        }
    )
