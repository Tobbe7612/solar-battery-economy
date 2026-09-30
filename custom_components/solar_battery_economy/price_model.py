"""Nord Pool price-model and price-intelligence helpers for SBE."""

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

IMPORT_SURCHARGE = 0.1267
ENERGY_TAX = 0.36
VAT_RATE = 0.25
VARIABLE_GRID_FEE = 0.14875
EXPORT_GRID_BENEFIT = 0.033
TAX_REDUCTION = 0.0
EXPORT_SURCHARGE = 0.0


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


def find_cheapest_future_period(
    forecast: list[dict[str, Any]],
    *,
    now: datetime,
    duration_minutes: int = 15,
    selection_mode: str = "consecutive",
) -> dict[str, Any] | None:
    """Find the cheapest future period in a normalized price forecast.

    Args:
        forecast:
            Normalized 15-minute forecast intervals.
        duration_minutes:
            Requested duration in minutes. Must be a multiple of 15.
        selection_mode:
            "consecutive" selects one continuous block.
            "cheapest_quarters" selects the cheapest individual quarters.

    Returns:
        A structured result describing the cheapest period, or None when
        no suitable future intervals are available.
    """
    if duration_minutes <= 0 or duration_minutes % 15 != 0:
        raise ValueError("duration_minutes must be a positive multiple of 15")

    if selection_mode not in ("consecutive", "cheapest_quarters"):
        raise ValueError(
            "selection_mode must be 'consecutive' or 'cheapest_quarters'"
        )

    required_intervals = duration_minutes // 15

    valid_forecast = [
        interval
        for interval in forecast
        if interval.get("import") is not None
        and interval.get("start") is not None
        and interval.get("end") is not None
    ]

    if not valid_forecast:
        return None

    # The forecast is expected to be ordered chronologically.
    valid_forecast = sorted(
        valid_forecast,
        key=lambda interval: interval["start"],
    )

    # Only future intervals are eligible.
    # The currently active interval is deliberately excluded.
    candidates = [
        interval
        for interval in valid_forecast
        if interval["start"] >= now
    ]

    if len(candidates) < required_intervals:
        return None

    if selection_mode == "cheapest_quarters":
        selected = sorted(
            candidates,
            key=lambda interval: float(interval["import"]),
        )[:required_intervals]

        selected = sorted(
            selected,
            key=lambda interval: interval["start"],
        )

    else:
        windows = []

        for index in range(
            len(candidates) - required_intervals + 1
        ):
            window = candidates[
                index : index + required_intervals
            ]

            # A consecutive period must contain uninterrupted 15-minute
            # intervals.
            is_continuous = all(
                window[i]["end"] == window[i + 1]["start"]
                for i in range(len(window) - 1)
            )

            if not is_continuous:
                continue

            average_import = sum(
                float(interval["import"])
                for interval in window
            ) / required_intervals

            windows.append(
                (
                    average_import,
                    window,
                )
            )

        if not windows:
            return None

        _, selected = min(
            windows,
            key=lambda item: (
                item[0],
                item[1][0]["start"],
            ),
        )

    average_import = sum(
        float(interval["import"])
        for interval in selected
    ) / len(selected)

    return {
        "duration_minutes": duration_minutes,
        "selection_mode": selection_mode,
        "start": selected[0]["start"],
        "end": selected[-1]["end"],
        "average_import_price": round(average_import, 4),
        "intervals": selected,
    }


def calculate_today_import_price_statistics(
    forecast: list[dict[str, Any]],
    *,
    now: datetime,
) -> dict[str, Any] | None:
    """Calculate today's total-import-price statistics from midnight through now.

    Only intervals belonging to the current calendar day and already started
    before ``now`` are included. The current 15-minute interval is included
    because its known total import price is already available.
    """
    local_now = now
    day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

    intervals = [
        interval
        for interval in forecast
        if interval.get("import") is not None
        and interval.get("start") is not None
        and day_start <= interval["start"] <= local_now
    ]

    if not intervals:
        return None

    values = [float(interval["import"]) for interval in intervals]
    minimum = min(values)
    maximum = max(values)
    average = sum(values) / len(values)

    return {
        "lowest_import_price": round(minimum, 4),
        "highest_import_price": round(maximum, 4),
        "average_import_price": round(average, 4),
        "interval_count": len(intervals),
    }


def normalize_nordpool_price_indices(
    price_indices: Any,
) -> list[dict[str, Any]]:
    """Convert Nord Pool price-index results to SBE spot intervals.

    ``nordpool.get_price_indices_for_date`` returns prices in SEK/MWh.
    This pure adapter converts them to SEK/kWh and preserves the existing
    interval timestamp representation (``datetime``). Import and export
    prices are intentionally not calculated here; a later SBE layer can
    enrich these spot intervals with those values.

    Malformed rows are skipped, matching the legacy adapter's
    behavior for invalid source intervals. A missing or non-list
    result produces an empty list.
    """
    if not isinstance(price_indices, list):
        return []

    intervals: list[dict[str, Any]] = []

    for item in price_indices:
        if not isinstance(item, dict):
            continue

        try:
            start = datetime.fromisoformat(str(item["start"]))
            end = datetime.fromisoformat(str(item["end"]))
            spot = float(item["price"]) / 1000
        except (KeyError, TypeError, ValueError):
            continue

        intervals.append({"start": start, "end": end, "spot": spot})

    return intervals


def build_nordpool_price_model(
    prices_by_day: dict[str, list[dict[str, Any]]],
    *,
    now: datetime,
    very_cheap_limit: float = DEFAULT_VERY_CHEAP_LIMIT,
    cheap_limit: float = DEFAULT_CHEAP_LIMIT,
    normal_limit: float = DEFAULT_NORMAL_LIMIT,
    expensive_limit: float = DEFAULT_EXPENSIVE_LIMIT,
) -> dict[str, Any]:
    """Build the existing current/forecast model from spot intervals."""
    spot_forecast = sorted(
        [
            interval
            for day in ("today", "tomorrow")
            for interval in prices_by_day.get(day, [])
        ],
        key=lambda interval: interval["start"],
    )
    forecast = enrich_nordpool_price_intervals(
        spot_forecast,
        very_cheap_limit=very_cheap_limit,
        cheap_limit=cheap_limit,
        normal_limit=normal_limit,
        expensive_limit=expensive_limit,
    )
    current = next(
        (
            interval
            for interval in forecast
            if interval["start"] <= now < interval["end"]
        ),
        None,
    )
    return {"current": current, "forecast": forecast}


def enrich_nordpool_price_intervals(
    intervals: list[dict[str, Any]],
    *,
    very_cheap_limit: float = DEFAULT_VERY_CHEAP_LIMIT,
    cheap_limit: float = DEFAULT_CHEAP_LIMIT,
    normal_limit: float = DEFAULT_NORMAL_LIMIT,
    expensive_limit: float = DEFAULT_EXPENSIVE_LIMIT,
) -> list[dict[str, Any]]:
    """Add SBE import/export prices and price intelligence to spot intervals."""
    enriched: list[dict[str, Any]] = []
    for interval in intervals:
        spot = float(interval["spot"])
        import_price = (
            (spot + IMPORT_SURCHARGE + ENERGY_TAX) * (1 + VAT_RATE)
            + VARIABLE_GRID_FEE
        )
        export_price = (
            spot + EXPORT_GRID_BENEFIT + TAX_REDUCTION + EXPORT_SURCHARGE
        )
        price_class = classify_price(
            import_price,
            very_cheap_limit=very_cheap_limit,
            cheap_limit=cheap_limit,
            normal_limit=normal_limit,
            expensive_limit=expensive_limit,
        )
        price_quality = calculate_price_quality(
            import_price,
            very_cheap_limit=very_cheap_limit,
            cheap_limit=cheap_limit,
            normal_limit=normal_limit,
            expensive_limit=expensive_limit,
        )
        enriched.append(
            {
                **interval,
                "import": import_price,
                "export": export_price,
                "price_class": price_class,
                "price_quality": price_quality,
            }
        )
    return enriched
