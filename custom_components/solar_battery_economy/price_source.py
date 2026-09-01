"""Price source normalization for Solar Battery Economy."""

from __future__ import annotations

from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Price classification
# ---------------------------------------------------------------------------

DEFAULT_VERY_CHEAP_LIMIT = 1.00
DEFAULT_CHEAP_LIMIT = 1.40
DEFAULT_NORMAL_LIMIT = 1.80
DEFAULT_EXPENSIVE_LIMIT = 2.20


VERY_CHEAP = "VERY_CHEAP"
CHEAP = "CHEAP"
NORMAL = "NORMAL"
EXPENSIVE = "EXPENSIVE"
VERY_EXPENSIVE = "VERY_EXPENSIVE"


def classify_price(
    price: float,
    *,
    very_cheap_limit: float = DEFAULT_VERY_CHEAP_LIMIT,
    cheap_limit: float = DEFAULT_CHEAP_LIMIT,
    normal_limit: float = DEFAULT_NORMAL_LIMIT,
    expensive_limit: float = DEFAULT_EXPENSIVE_LIMIT,
) -> str:
    """Classify an electricity import price using absolute thresholds.

    The thresholds are intentionally absolute rather than relative to the
    current day's price distribution.
    """
    if very_cheap_limit >= cheap_limit:
        raise ValueError("very_cheap_limit must be below cheap_limit")

    if cheap_limit >= normal_limit:
        raise ValueError("cheap_limit must be below normal_limit")

    if normal_limit >= expensive_limit:
        raise ValueError("normal_limit must be below expensive_limit")

    if price < very_cheap_limit:
        return VERY_CHEAP

    if price < cheap_limit:
        return CHEAP

    if price < normal_limit:
        return NORMAL

    if price <= expensive_limit:
        return EXPENSIVE

    return VERY_EXPENSIVE

def normalize_price_source(
    attributes: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Normalize price data from a Home Assistant sensor.

    The input is expected to contain an ``all_prices`` attribute
    consisting of 15-minute price intervals.

    No price calculations are performed here. The values supplied
    by the source are preserved.
    """
    all_prices = attributes.get("all_prices")

    if not isinstance(all_prices, list):
        return {
            "current": None,
            "forecast": [],
        }

    forecast: list[dict[str, Any]] = []

    for item in all_prices:
        if not isinstance(item, dict):
            continue

        try:
            start = datetime.fromisoformat(str(item["start"]))
            end = datetime.fromisoformat(str(item["end"]))

            spot = item["spot"]
            import_price = item["import"]
            export_price = item["export"]
        except (KeyError, TypeError, ValueError):
            continue

        forecast.append(
            {
                "start": start,
                "end": end,
                "spot": spot,
                "import": import_price,
                "export": export_price,
            }
        )

    current = None

    if now is not None:
        for interval in forecast:
            if interval["start"] <= now < interval["end"]:
                current = interval
                break

    return {
        "current": current,
        "forecast": forecast,
    }