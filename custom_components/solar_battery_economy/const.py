"""Constants for the Solar Battery Economy integration."""

from typing import Final

DOMAIN: Final = "solar_battery_economy"

# Platforms
PLATFORMS: Final = ["sensor"]

# Default values
DEFAULT_NAME: Final = "Solar Battery Economy"
DEFAULT_INVESTMENT: Final = 0
DEFAULT_VERY_CHEAP_LIMIT: Final = 1.00
DEFAULT_CHEAP_LIMIT: Final = 1.40
DEFAULT_NORMAL_LIMIT: Final = 1.80
DEFAULT_EXPENSIVE_LIMIT: Final = 2.20

# Config keys
CONF_SOLAR_POWER: Final = "solar_power"
CONF_GRID_POWER: Final = "grid_power"
CONF_BATTERY_POWER: Final = "battery_power"
CONF_PRICE_SOURCE: Final = "price_source"
CONF_VERY_CHEAP_LIMIT: Final = "very_cheap_limit"
CONF_CHEAP_LIMIT: Final = "cheap_limit"
CONF_NORMAL_LIMIT: Final = "normal_limit"
CONF_EXPENSIVE_LIMIT: Final = "expensive_limit"
CONF_INVESTMENT: Final = "investment"
INTEGRATION_VERSION = "1.4.0"  # keep in sync with manifest.json's "version" field
