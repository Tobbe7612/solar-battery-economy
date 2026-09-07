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


def calculate_price_quality(
    price: float,
    *,
    very_cheap_limit: float = DEFAULT_VERY_CHEAP_LIMIT,
    cheap_limit: float = DEFAULT_CHEAP_LIMIT,
    normal_limit: float = DEFAULT_NORMAL_LIMIT,
    expensive_limit: float = DEFAULT_EXPENSIVE_LIMIT,
) -> float:
    """Calculate a 0-100 price quality score from configured price limits.

    Higher is better/cheaper.

    The configured price-classification thresholds define the four
    reference points:

        very cheap = 100
        cheap      = 75
        normal     = 50
        expensive  = 25
        above expensive = 0
    """
    if very_cheap_limit >= cheap_limit:
        raise ValueError("very_cheap_limit must be below cheap_limit")

    if cheap_limit >= normal_limit:
        raise ValueError("cheap_limit must be below normal_limit")

    if normal_limit >= expensive_limit:
        raise ValueError("normal_limit must be below expensive_limit")

    def interpolate(
        value: float,
        low_price: float,
        high_price: float,
        low_score: float,
        high_score: float,
    ) -> float:
        if high_price == low_price:
            return high_score

        ratio = (value - low_price) / (high_price - low_price)
        return low_score + ratio * (high_score - low_score)

    if price <= very_cheap_limit:
        return 100.0

    if price <= cheap_limit:
        score = interpolate(
            price,
            very_cheap_limit,
            cheap_limit,
            100.0,
            75.0,
        )
    elif price <= normal_limit:
        score = interpolate(
            price,
            cheap_limit,
            normal_limit,
            75.0,
            50.0,
        )
    elif price <= expensive_limit:
        score = interpolate(
            price,
            normal_limit,
            expensive_limit,
            50.0,
            25.0,
        )
    else:
        return 0.0

    return round(max(0.0, min(100.0, score)), 1)


def normalize_price_source(
    attributes: dict[str, Any],
    now: datetime | None = None,
    *,
    very_cheap_limit: float = DEFAULT_VERY_CHEAP_LIMIT,
    cheap_limit: float = DEFAULT_CHEAP_LIMIT,
    normal_limit: float = DEFAULT_NORMAL_LIMIT,
    expensive_limit: float = DEFAULT_EXPENSIVE_LIMIT,
) -> dict[str, Any]:
    """Normalize price data from a Home Assistant sensor.

    The input is expected to contain an ``all_prices`` attribute
    consisting of 15-minute price intervals.

    Source values are preserved. Each valid interval is enriched with
    classification and price quality based on the configured import-price
    thresholds.
    """
    all_prices = attributes.get("all_prices")

    if not isinstance(all_prices, list):
        return {
            "current": None,
            "forecast": [],
        }

    # Validate the configured thresholds once before processing the forecast.
    if very_cheap_limit >= cheap_limit:
        raise ValueError("very_cheap_limit must be below cheap_limit")

    if cheap_limit >= normal_limit:
        raise ValueError("cheap_limit must be below normal_limit")

    if normal_limit >= expensive_limit:
        raise ValueError("normal_limit must be below expensive_limit")

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

        # The normalized model preserves the original source values.
        interval = {
            "start": start,
            "end": end,
            "spot": spot,
            "import": import_price,
            "export": export_price,
        }

        # Price intelligence is based on the import price because this is
        # the price relevant when deciding when electricity is expensive
        # or cheap for the household.
        try:
            import_price_float = float(import_price)
        except (TypeError, ValueError):
            import_price_float = None

        if import_price_float is not None:
            interval["classification"] = classify_price(
                import_price_float,
                very_cheap_limit=very_cheap_limit,
                cheap_limit=cheap_limit,
                normal_limit=normal_limit,
                expensive_limit=expensive_limit,
            )
            interval["price_quality"] = calculate_price_quality(
                import_price_float,
                very_cheap_limit=very_cheap_limit,
                cheap_limit=cheap_limit,
                normal_limit=normal_limit,
                expensive_limit=expensive_limit,
            )
        else:
            interval["classification"] = None
            interval["price_quality"] = None

        forecast.append(interval)

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