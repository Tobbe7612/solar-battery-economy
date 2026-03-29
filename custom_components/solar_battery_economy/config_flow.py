"""Config flow for Solar Battery Economy."""
from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import selector
from homeassistant.helpers import config_validation as cv
from .const import (
    DOMAIN,
    DEFAULT_NAME,
    CONF_SOLAR_POWER,
    CONF_GRID_POWER,
    CONF_BATTERY_POWER,
    CONF_IMPORT_PRICE,
    CONF_EXPORT_PRICE,
    CONF_INVESTMENT,
)


class SolarBatteryEconomyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Battery Economy."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH
    @staticmethod
    def async_get_options_flow(config_entry):
        return SolarBatteryEconomyOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Initial step for user setup."""
        errors = {}

        if user_input is not None:
            # Prevent duplicate configuration
            unique_id = DOMAIN
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Basic validation: prevent identical sensors
            sensors = {
                user_input[CONF_SOLAR_POWER],
                user_input[CONF_GRID_POWER],
                user_input[CONF_BATTERY_POWER],
            }
            if len(sensors) < 3:
                errors["base"] = "duplicate_power_sensors"
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
    """Options flow for Solar Battery Economy."""

    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        """Handle options update."""
        if user_input is not None:
            await self.hass.config_entries.async_reload(self.entry.entry_id)
            return self.async_create_entry(title="", data=user_input)

        defaults = self.entry.options or self.entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(defaults),
        )


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

            # ----- Price sensors -----
            vol.Required(
                CONF_IMPORT_PRICE,
                default=defaults.get(CONF_IMPORT_PRICE),
            ): price_selector,

            vol.Required(
                CONF_EXPORT_PRICE,
                default=defaults.get(CONF_EXPORT_PRICE),
            ): price_selector,

            # ----- Optional investment -----
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