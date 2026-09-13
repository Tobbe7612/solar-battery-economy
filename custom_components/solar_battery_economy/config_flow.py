"""Config flow for Solar Battery Economy."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import selector

from .const import (
    DOMAIN,
    DEFAULT_NAME,
    CONF_SOLAR_POWER,
    CONF_GRID_POWER,
    CONF_BATTERY_POWER,
    CONF_PRICE_SOURCE,
    CONF_PRICE_PERIOD_MINUTES,
    CONF_PRICE_SELECTION_MODE,
    CONF_INVESTMENT,
    DEFAULT_VERY_CHEAP_LIMIT,
    DEFAULT_CHEAP_LIMIT,
    DEFAULT_NORMAL_LIMIT,
    DEFAULT_EXPENSIVE_LIMIT,
    CONF_VERY_CHEAP_LIMIT,
    CONF_CHEAP_LIMIT,
    CONF_NORMAL_LIMIT,
    CONF_EXPENSIVE_LIMIT,
)


class SolarBatteryEconomyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Battery Economy."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    def async_get_options_flow(config_entry):
        return SolarBatteryEconomyOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step."""
        errors = {}

        if user_input is not None:
            # Prevent duplicate configuration.
            user_input = dict(user_input)

            if CONF_PRICE_PERIOD_MINUTES in user_input:
                user_input[CONF_PRICE_PERIOD_MINUTES] = int(
                    user_input[CONF_PRICE_PERIOD_MINUTES]
                )
            unique_id = DOMAIN
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Basic validation: prevent identical power sensors.
            sensors = {
                user_input[CONF_SOLAR_POWER],
                user_input[CONF_GRID_POWER],
                user_input[CONF_BATTERY_POWER],
            }

            if len(sensors) < 3:
                errors["base"] = "duplicate_power_sensors"
            else:
                threshold_error = _validate_price_thresholds(user_input)

                if threshold_error is not None:
                    errors["base"] = threshold_error
                else:
                    return self.async_create_entry(
                        title=DEFAULT_NAME,
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(),
            errors=errors,
        )


class SolarBatteryEconomyOptionsFlow(config_entries.OptionsFlow):
    """Handle options updates for Solar Battery Economy."""

    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        """Handle options update."""
        errors = {}

        if user_input is not None:
            user_input = dict(user_input)

            if CONF_PRICE_PERIOD_MINUTES in user_input:
                user_input[CONF_PRICE_PERIOD_MINUTES] = int(
                    user_input[CONF_PRICE_PERIOD_MINUTES]
                )

            threshold_error = _validate_price_thresholds(user_input)

            if threshold_error is not None:
                errors["base"] = threshold_error
            else:
                # Save options first. The entry will then be reloaded using
                # the newly saved configuration.
                return self.async_create_entry(
                    title="",
                    data=user_input,
                )

        defaults = self.entry.options or self.entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(defaults),
            errors=errors,
        )


# ======================================================
# Validation
# ======================================================


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


def _build_schema(defaults=None):
    defaults = defaults or {}

    power_selector = selector(
        {
            "entity": {
                "domain": "sensor",
            }
        }
    )

    price_selector = selector(
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

            # ----- Price source -----
            vol.Required(
                CONF_PRICE_SOURCE,
                default=defaults.get(CONF_PRICE_SOURCE),
            ): price_selector,

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

            vol.Optional("currency", default="SEK"): vol.In(
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