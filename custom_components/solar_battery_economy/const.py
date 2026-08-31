"""Constants for the Solar Battery Economy integration."""

from typing import Final

DOMAIN: Final = "solar_battery_economy"

# Platforms
PLATFORMS: Final = ["sensor"]

# Default values
DEFAULT_NAME: Final = "Solar Battery Economy"
DEFAULT_INVESTMENT: Final = 0

# Config keys
CONF_SOLAR_POWER: Final = "solar_power"
CONF_GRID_POWER: Final = "grid_power"
CONF_BATTERY_POWER: Final = "battery_power"
CONF_PRICE_SOURCE: Final = "price_source"
CONF_INVESTMENT: Final = "investment"
INTEGRATION_VERSION = "1.4.0"  # keep in sync with manifest.json's "version" field
