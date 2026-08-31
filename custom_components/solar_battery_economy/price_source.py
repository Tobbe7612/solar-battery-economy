"""Price source normalization for Solar Battery Economy."""

from __future__ import annotations

from datetime import datetime
from typing import Any


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