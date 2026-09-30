"""Deterministic Energy Dashboard analytical calculations.

The functions in this module are deliberately independent of Home Assistant's
Recorder implementation.  The dashboard/backend adapter supplies historical
samples from Recorder; these functions perform the canonical calculations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any


def _valid_samples(samples: list[dict[str, Any]]) -> list[dict[str, float]]:
    valid = []
    for sample in samples:
        try:
            energy = float(sample["energy_kwh"])
            import_price = float(sample["import_price"])
        except (KeyError, TypeError, ValueError):
            continue
        if energy < 0:
            continue
        valid.append({"energy_kwh": energy, "import_price": import_price})
    return valid


def calculate_import_price_median(samples: list[dict[str, Any]]) -> float | None:
    """Return the median total-import price for valid samples."""
    valid = _valid_samples(samples)
    if not valid:
        return None
    return round(float(median(item["import_price"] for item in valid)), 4)


def calculate_consumption_cost(samples: list[dict[str, Any]]) -> float:
    """Calculate actual purchase cost from energy and total import price."""
    return round(
        sum(
            item["energy_kwh"] * item["import_price"]
            for item in _valid_samples(samples)
        ),
        6,
    )


def calculate_weighted_average_import_price(
    samples: list[dict[str, Any]],
) -> float | None:
    """Calculate the energy-weighted average total import price."""
    valid = _valid_samples(samples)
    total_energy = sum(item["energy_kwh"] for item in valid)
    if total_energy <= 0:
        return None
    return round(
        sum(item["energy_kwh"] * item["import_price"] for item in valid)
        / total_energy,
        4,
    )


def calculate_consumption_share_below_median(
    samples: list[dict[str, Any]],
    *,
    reference_price: float | None = None,
) -> float | None:
    """Return the share of energy consumed below a shared price median."""
    valid = _valid_samples(samples)
    if not valid:
        return None
    reference = (
        float(reference_price)
        if reference_price is not None
        else median(item["import_price"] for item in valid)
    )
    total_energy = sum(item["energy_kwh"] for item in valid)
    if total_energy <= 0:
        return None
    below = sum(
        item["energy_kwh"]
        for item in valid
        if item["import_price"] < reference
    )
    return round(below / total_energy * 100, 2)


def calculate_consumption_share_above_median(
    samples: list[dict[str, Any]],
    *,
    reference_price: float | None = None,
) -> float | None:
    """Return the share of energy consumed above a shared price median."""
    valid = _valid_samples(samples)
    if not valid:
        return None
    reference = (
        float(reference_price)
        if reference_price is not None
        else median(item["import_price"] for item in valid)
    )
    total_energy = sum(item["energy_kwh"] for item in valid)
    if total_energy <= 0:
        return None
    above = sum(
        item["energy_kwh"]
        for item in valid
        if item["import_price"] > reference
    )
    return round(above / total_energy * 100, 2)


def _timestamped_states(
    history: list[dict[str, Any]],
) -> list[tuple[datetime, float]]:
    """Normalize Recorder-style history states into sorted numeric samples."""
    result: list[tuple[datetime, float]] = []
    for item in history:
        timestamp = item.get("timestamp")
        if timestamp is None:
            timestamp = item.get("last_changed")
        state = item.get("state")
        if not isinstance(timestamp, datetime):
            continue
        try:
            value = float(state)
        except (TypeError, ValueError):
            continue
        result.append((timestamp, value))
    result.sort(key=lambda item: item[0])
    return result


def calculate_positive_cumulative_delta(
    history: list[dict[str, Any]],
    *,
    start: datetime,
    end: datetime,
) -> float | None:
    """Calculate positive cumulative-state consumption inside a time window.

    The latest state at or before ``start`` establishes the baseline. This is
    not interpolation: cumulative energy remains valid until its next state
    change.
    """
    if end <= start:
        return None

    states = _timestamped_states(history)
    if not states:
        return None

    baseline: float | None = None
    samples: list[tuple[datetime, float]] = []
    for timestamp, value in states:
        if timestamp <= start:
            baseline = value
        elif timestamp <= end:
            samples.append((timestamp, value))

    if baseline is None or not samples:
        return None

    total = 0.0
    previous = baseline
    for _, value in samples:
        delta = value - previous
        if delta >= 0:
            total += delta
        previous = value

    return round(total, 6)

def calculate_cumulative_cost_from_history(
    history: list[dict[str, Any]],
    *,
    start: datetime,
    end: datetime,
) -> float | None:
    """Calculate a 24h cost from a cumulative monetary Recorder history."""
    return calculate_positive_cumulative_delta(history, start=start, end=end)


def build_price_aligned_energy_samples(
    energy_history: list[dict[str, Any]],
    price_history: list[dict[str, Any]],
    *,
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Build energy/total-import-price samples from two Recorder histories.

    Each energy delta is valued using the latest price state at the start of
    that energy interval.  An interval is omitted when a price change is
    recorded inside the interval because the available cumulative energy
    history cannot split that energy delta accurately at the price boundary.
    """
    energies = _timestamped_states(energy_history)
    prices = _timestamped_states(price_history)
    if not energies or not prices or end <= start:
        return []

    baseline_energy: tuple[datetime, float] | None = None
    energy_samples: list[tuple[datetime, float]] = []
    for timestamp, value in energies:
        if timestamp <= start:
            baseline_energy = (start, value)
        elif timestamp <= end:
            energy_samples.append((timestamp, value))

    if baseline_energy is None:
        return []

    price_at_start: list[tuple[datetime, float]] = []
    for timestamp, value in prices:
        if timestamp <= end:
            price_at_start.append((timestamp, value))
    if not price_at_start:
        return []

    result: list[dict[str, Any]] = []
    previous_time, previous_energy = baseline_energy
    price_index = 0

    for current_time, current_energy in energy_samples:
        if current_time <= previous_time:
            continue

        while (
            price_index + 1 < len(price_at_start)
            and price_at_start[price_index + 1][0] <= previous_time
        ):
            price_index += 1

        if price_at_start[price_index][0] > previous_time:
            previous_time, previous_energy = current_time, current_energy
            continue

        next_price_index = price_index + 1
        price_changes_inside = (
            next_price_index < len(price_at_start)
            and price_at_start[next_price_index][0] < current_time
        )
        if price_changes_inside:
            previous_time, previous_energy = current_time, current_energy
            continue

        delta = current_energy - previous_energy
        if delta >= 0:
            result.append(
                {
                    "start": previous_time,
                    "end": current_time,
                    "energy_kwh": round(delta, 6),
                    "import_price": price_at_start[price_index][1],
                }
            )

        previous_time, previous_energy = current_time, current_energy

    return result


def calculate_cost_period(
    samples: list[dict[str, Any]],
    *,
    highest: bool,
) -> dict[str, Any] | None:
    """Return the highest- or lowest-cost valid energy interval.

    Cost is actual consumption valued at total import price for the interval.
    Zero-energy intervals are excluded. Missing/invalid prices are excluded.
    Ties are resolved deterministically by choosing the earliest interval.
    """
    candidates: list[dict[str, Any]] = []
    for sample in samples:
        try:
            energy = float(sample["energy_kwh"])
            import_price = float(sample["import_price"])
        except (KeyError, TypeError, ValueError):
            continue
        if energy <= 0:
            continue

        start = sample.get("start")
        end = sample.get("end")
        if not isinstance(start, datetime) or not isinstance(end, datetime) or end <= start:
            continue

        candidates.append(
            {
                "start": start,
                "end": end,
                "energy_kwh": round(energy, 6),
                "import_price": import_price,
                "cost": round(energy * import_price, 6),
            }
        )

    if not candidates:
        return None

    # Sorting by start first makes the tie-break deterministic. Python's min/max
    # retain the first equal item, so equal costs resolve to the earliest period.
    candidates.sort(key=lambda item: item["start"])
    key = lambda item: item["cost"]
    return (max if highest else min)(candidates, key=key)


def calculate_highest_cost_period(
    samples: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return the 15-minute interval with the highest actual consumption cost."""
    return calculate_cost_period(samples, highest=True)


def calculate_lowest_cost_period(
    samples: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return the 15-minute interval with the lowest actual cost among intervals with energy > 0."""
    return calculate_cost_period(samples, highest=False)


def calculate_battery_contribution_percent(
    house_total_samples: list[dict[str, Any]],
    battery_house_samples: list[dict[str, Any]],
) -> float | None:
    """Return battery-to-house energy as a percentage of house consumption.

    The denominator is total house energy in the same analysis window. A
    valid zero battery contribution therefore returns 0.0. If house energy
    is zero, the contribution is undefined.
    """
    house_energy = sum(
        item["energy_kwh"] for item in _valid_samples(house_total_samples)
    )
    if house_energy <= 0:
        return None

    battery_energy = sum(
        item["energy_kwh"] for item in _valid_samples(battery_house_samples)
    )
    return round(battery_energy / house_energy * 100, 2)


def calculate_consumer_share_percent(
    consumer_samples: list[dict[str, Any]],
    house_total_samples: list[dict[str, Any]],
) -> float | None:
    """Return a consumer's share of total house energy.

    This is an energy share, not a cost share. Both inputs must represent the
    same dashboard analysis window.
    """
    house_energy = sum(
        item["energy_kwh"] for item in _valid_samples(house_total_samples)
    )
    if house_energy <= 0:
        return None

    consumer_energy = sum(
        item["energy_kwh"] for item in _valid_samples(consumer_samples)
    )
    return round(consumer_energy / house_energy * 100, 2)


def calculate_consumer_price_alignment(
    house_average_import_price: float | None,
    consumer_average_import_price: float | None,
) -> float | None:
    """Return house-average minus consumer-average import price.

    Positive values mean the consumer used electricity at a lower average
    import price than the house as a whole. This is a transparent delta, not
    a score and is not part of Smart Score V1.
    """
    if house_average_import_price is None or consumer_average_import_price is None:
        return None
    return round(
        float(house_average_import_price) - float(consumer_average_import_price),
        4,
    )


def calculate_smart_score(
    cheap_usage_percent: float | None,
    expensive_usage_percent: float | None,
    battery_contribution_percent: float | None,
) -> float | None:
    """Calculate the deterministic V1 Smart Score.

    The score combines cheap usage (40%), avoidance of expensive usage (40%)
    and battery contribution to house consumption (20%). Missing price data
    or missing battery data makes the score unavailable rather than treating
    missing values as zero.
    """
    if (
        cheap_usage_percent is None
        or expensive_usage_percent is None
        or battery_contribution_percent is None
    ):
        return None

    score = (
        0.40 * float(cheap_usage_percent)
        + 0.40 * (100.0 - float(expensive_usage_percent))
        + 0.20 * float(battery_contribution_percent)
    )

    # Smart Score is contractually bounded to 0–100.
    return round(max(0.0, min(100.0, score)), 2)



def build_consumer_events(
    samples: list[dict[str, Any]],
    *,
    consumer_id: str | None = None,
) -> list[dict[str, Any]]:
    """Build consumer activity events from recorder-resolved energy intervals.

    Event boundaries are derived only from the supplied energy intervals. A
    positive-energy interval starts or continues an event; a zero-energy or
    missing/invalid interval does not. Consecutive positive intervals are
    merged when they touch or overlap. No event timing is inferred outside
    the resolution represented by the samples.
    """
    intervals: list[dict[str, Any]] = []
    for sample in samples:
        start = sample.get("start")
        end = sample.get("end")
        try:
            energy = float(sample["energy_kwh"])
        except (KeyError, TypeError, ValueError):
            continue
        if (
            not isinstance(start, datetime)
            or not isinstance(end, datetime)
            or end <= start
            or energy <= 0
        ):
            continue
        intervals.append(
            {
                "start": start,
                "end": end,
                "energy_kwh": energy,
            }
        )

    intervals.sort(key=lambda item: item["start"])
    events: list[dict[str, Any]] = []

    for interval in intervals:
        if not events or interval["start"] > events[-1]["end"]:
            event = {
                "consumer_id": consumer_id,
                "start": interval["start"],
                "end": interval["end"],
                "energy_kwh": round(interval["energy_kwh"], 6),
            }
            events.append(event)
            continue

        event = events[-1]
        event["end"] = max(event["end"], interval["end"])
        event["energy_kwh"] = round(
            event["energy_kwh"] + interval["energy_kwh"],
            6,
        )

    return events


def calculate_consumer_analysis(
    samples: list[dict[str, Any]],
    *,
    reference_price: float | None = None,
) -> dict[str, Any]:
    """Calculate the canonical V1 analysis for one configured consumer."""
    valid = _valid_samples(samples)
    energy = round(sum(item["energy_kwh"] for item in valid), 6)
    return {
        "energy_kwh": energy,
        "cost": calculate_consumption_cost(valid),
        "average_import_price": calculate_weighted_average_import_price(valid),
        "cheap_usage_percent": calculate_consumption_share_below_median(
            valid, reference_price=reference_price
        ),
        "expensive_usage_percent": calculate_consumption_share_above_median(
            valid, reference_price=reference_price
        ),
        "sample_count": len(valid),
    }


def build_statistics_energy_samples_with_price_history(
    energy_statistics: list[dict[str, Any]],
    price_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Value Recorder energy changes using normalized price interval states.

    Energy statistics provide the measured cumulative change for each bucket.
    Nord Pool intervals are represented as timestamped total-import-price
    states. A bucket is included only when one price state covers the whole
    bucket; otherwise it is omitted rather than splitting or estimating the
    energy change.
    """
    prices = _timestamped_states(price_history)
    if not prices:
        return []

    result: list[dict[str, Any]] = []
    for stat in energy_statistics:
        start = stat_start_value(stat, "start")
        end = stat_start_value(stat, "end")
        if start is None or end is None or end <= start:
            continue
        try:
            energy_kwh = float(stat["change"])
        except (KeyError, TypeError, ValueError):
            continue
        if energy_kwh < 0:
            continue

        price_index = None
        for index, (timestamp, value) in enumerate(prices):
            if timestamp <= start:
                price_index = index
            elif timestamp > start:
                break
        if price_index is None:
            continue

        price_start, import_price = prices[price_index]
        next_price = prices[price_index + 1][0] if price_index + 1 < len(prices) else None
        if price_start > start or (next_price is not None and next_price < end):
            continue

        result.append(
            {
                "start": start,
                "end": end,
                "energy_kwh": energy_kwh,
                "import_price": import_price,
            }
        )

    result.sort(key=lambda item: item["start"])
    return result


def stat_start_value(stat: dict[str, Any], key: str) -> datetime | None:
    """Normalize a statistics timestamp from a generic statistics mapping."""
    value = stat.get(key)
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    return None


def build_deterministic_insights(
    house_analysis: dict[str, Any],
    consumers: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build deterministic dashboard facts from canonical analysis values.

    Insights are descriptive facts only. They do not contain recommendations,
    optimization decisions, thresholds invented by the dashboard, or ranking.
    The order is stable so the payload is deterministic.
    """
    insights: list[dict[str, Any]] = []

    cheap = house_analysis.get("cheap_usage_percent")
    if cheap is not None:
        insights.append({
            "type": "cheap_consumption",
            "cheap_usage_percent": float(cheap),
        })

    expensive = house_analysis.get("expensive_usage_percent")
    if expensive is not None:
        insights.append({
            "type": "expensive_consumption",
            "expensive_usage_percent": float(expensive),
        })

    for period_type, key in (
        ("highest_cost_period", "highest_cost_period"),
        ("lowest_cost_period", "lowest_cost_period"),
    ):
        period = house_analysis.get(key)
        if period is not None:
            insights.append({
                "type": period_type,
                **period,
            })

    for entity_id, consumer in (consumers or {}).items():
        analysis = consumer.get("analysis", {})
        name = consumer.get("name", entity_id)
        cost = analysis.get("cost")
        if cost is not None:
            insights.append({
                "type": "consumer_cost",
                "consumer_id": entity_id,
                "name": name,
                "energy_kwh": analysis.get("energy_kwh"),
                "cost": cost,
                "average_import_price": analysis.get("average_import_price"),
            })

        share_percent = analysis.get("share_percent")
        if share_percent is not None:
            insights.append({
                "type": "consumer_share",
                "consumer_id": entity_id,
                "name": name,
                "share_percent": share_percent,
            })

        price_alignment_delta = analysis.get("price_alignment_delta")
        if price_alignment_delta is not None:
            insights.append({
                "type": "consumer_price_alignment",
                "consumer_id": entity_id,
                "name": name,
                "price_alignment_delta": price_alignment_delta,
            })

    return insights
