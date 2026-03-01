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
CONF_IMPORT_PRICE: Final = "import_price"
CONF_EXPORT_PRICE: Final = "export_price"
CONF_INVESTMENT: Final = "investment"