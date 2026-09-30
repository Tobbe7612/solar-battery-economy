"""Home Assistant runtime access to Nord Pool price indices."""

from __future__ import annotations

import calendar
import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .price_model import (
    DEFAULT_CHEAP_LIMIT,
    DEFAULT_EXPENSIVE_LIMIT,
    DEFAULT_NORMAL_LIMIT,
    DEFAULT_VERY_CHEAP_LIMIT,
    build_nordpool_price_model,
    normalize_nordpool_price_indices,
)

NORDPOOL_DOMAIN = "nordpool"
PRICE_INDICES_ACTION = "get_price_indices_for_date"
NORDPOOL_TIMEZONE = dt_util.get_time_zone("Europe/Oslo")


class NordPoolPriceError(Exception):
    """Raised when required Nord Pool price indices cannot be retrieved."""


@dataclass
class CachedPriceDay:
    """A successful Nord Pool date response and when SBE fetched it."""

    intervals: list[dict[str, Any]]
    fetched_at: datetime


@dataclass
class NordPoolPriceCache:
    """In-memory cache shared by forecast and dashboard history requests."""

    days: dict[tuple[str, str, str, date], CachedPriceDay] = field(
        default_factory=dict
    )
    in_flight: dict[tuple[str, str, str, date], asyncio.Task[CachedPriceDay]] = field(
        default_factory=dict
    )

    def get(
        self, config_entry_id: str, area: str, currency: str, price_date: date
    ) -> CachedPriceDay | None:
        return self.days.get((config_entry_id, area, currency, price_date))

    def put(
        self,
        config_entry_id: str,
        area: str,
        currency: str,
        price_date: date,
        intervals: list[dict[str, Any]],
        fetched_at: datetime,
    ) -> None:
        self.days[(config_entry_id, area, currency, price_date)] = CachedPriceDay(
            intervals=list(intervals), fetched_at=fetched_at
        )

    def prune(self, today: date) -> None:
        """Keep the API-supported history window plus a small boundary margin."""
        minimum = _subtract_months(today, 2) - timedelta(days=2)
        self.days = {
            key: value for key, value in self.days.items() if key[3] >= minimum
        }


def get_nordpool_config_entry(
    hass: HomeAssistant,
    config_entry_id: str | None = None,
    area: str | None = None,
) -> tuple[Any, str, str]:
    """Resolve the selected Nord Pool entry, area, and configured currency."""
    if config_entry_id:
        entry = hass.config_entries.async_get_entry(config_entry_id)
        entries = [entry] if entry is not None else []
    else:
        entries = hass.config_entries.async_entries(NORDPOOL_DOMAIN)

    if len(entries) != 1 or entries[0].domain != NORDPOOL_DOMAIN:
        raise NordPoolPriceError(
            "Open Solar Battery Economy Options and select a valid Nord Pool config entry"
        )

    entry = entries[0]
    areas = entry.data.get("areas", [])
    if area is None:
        if len(areas) != 1:
            raise NordPoolPriceError(
                "Open Solar Battery Economy Options and select a market area from the Nord Pool entry"
            )
        area = areas[0]
    if area not in areas:
        raise NordPoolPriceError(
            f"Market area {area} is not configured in the selected Nord Pool entry"
        )

    currency = entry.data.get("currency")
    if not isinstance(currency, str) or not currency:
        raise NordPoolPriceError("Nord Pool entry has no configured currency")
    return entry, area, currency


def get_nordpool_config_entry_id(hass: HomeAssistant) -> str:
    """Find the sole configured Nord Pool entry, failing if ambiguous."""
    entries = hass.config_entries.async_entries(NORDPOOL_DOMAIN)
    if len(entries) != 1:
        raise NordPoolPriceError(
            "Expected exactly one Nord Pool config entry; "
            f"found {len(entries)}"
        )
    return entries[0].entry_id


async def _fetch_price_day(
    hass: HomeAssistant,
    *,
    entry: Any,
    area: str,
    currency: str,
    price_date: date,
    cache: NordPoolPriceCache,
    require_complete_day: bool = False,
) -> CachedPriceDay:
    key = (entry.entry_id, area, currency, price_date)
    cached = cache.get(entry.entry_id, area, currency, price_date)
    if cached is not None:
        if not require_complete_day or _is_complete_day(cached.intervals):
            return cached
        # A date first fetched for the live forecast may have been partial.
        # Do not let it masquerade as complete historical data.
        cache.days.pop(key, None)

    task = cache.in_flight.get(key)
    if task is None:
        task = asyncio.create_task(
            _fetch_price_day_from_api(
                hass,
                entry=entry,
                area=area,
                currency=currency,
                price_date=price_date,
                cache=cache,
            )
        )
        cache.in_flight[key] = task

    try:
        cached = await asyncio.shield(task)
    finally:
        if task.done() and cache.in_flight.get(key) is task:
            cache.in_flight.pop(key, None)

    if require_complete_day and not _is_complete_day(cached.intervals):
        cache.days.pop(key, None)
        raise NordPoolPriceError(
            f"Nord Pool returned an incomplete 15-minute day for {area} on {price_date}"
        )
    return cached


async def _fetch_price_day_from_api(
    hass: HomeAssistant,
    *,
    entry: Any,
    area: str,
    currency: str,
    price_date: date,
    cache: NordPoolPriceCache,
) -> CachedPriceDay:
    """Fetch and cache a date once for all concurrent consumers."""

    try:
        response = await hass.services.async_call(
            NORDPOOL_DOMAIN,
            PRICE_INDICES_ACTION,
            {
                "config_entry": entry.entry_id,
                "date": price_date,
                "areas": [area],
                "currency": currency,
                "resolution": 15,
            },
            blocking=True,
            return_response=True,
        )
    except Exception as err:
        raise NordPoolPriceError(
            f"Nord Pool action failed for {area} on {price_date}: {err}"
        ) from err

    rows = response.get(area) if isinstance(response, dict) else None
    if not isinstance(rows, list) or not rows:
        raise NordPoolPriceError(
            f"Nord Pool action returned no {area} prices for {price_date}"
        )
    intervals = normalize_nordpool_price_indices(rows)
    if len(intervals) != len(rows) or not intervals:
        raise NordPoolPriceError(
            f"Nord Pool returned incomplete {area} prices for {price_date}"
        )
    intervals.sort(key=lambda item: item["start"])
    fetched_at = dt_util.utcnow()
    cache.put(
        entry.entry_id, area, currency, price_date, intervals, fetched_at
    )
    cached = cache.get(entry.entry_id, area, currency, price_date)
    assert cached is not None
    return cached


def _is_complete_day(intervals: list[dict[str, Any]]) -> bool:
    """Check for a plausible full 15-minute delivery day, including DST days."""
    # Nord Pool's API returns UTC timestamps and its documented examples do
    # not guarantee whether the delivery-day boundary is represented as UTC
    # midnight or the market timezone's midnight. Validate full-day cardinality
    # and continuity without assuming either boundary convention.
    if len(intervals) not in {92, 96, 100}:
        return False

    for index, item in enumerate(intervals[1:], start=1):
        interval_start = item["start"].astimezone(timezone.utc)
        interval_end = item["end"].astimezone(timezone.utc)
        previous_end = intervals[index - 1]["end"].astimezone(timezone.utc)
        if (
            interval_start != previous_end
            or interval_end - interval_start != timedelta(minutes=15)
        ):
            return False
    return intervals[0]["end"] - intervals[0]["start"] == timedelta(minutes=15)


async def async_get_nordpool_prices(
    hass: HomeAssistant,
    config_entry_id: str,
    *,
    area: str | None = None,
    cache: NordPoolPriceCache | None = None,
    now: datetime | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch today's spot data and tomorrow only after HA reports it available."""
    entry, area, currency = get_nordpool_config_entry(hass, config_entry_id, area)
    cache = cache or NordPoolPriceCache()
    today = (now or dt_util.now()).astimezone(NORDPOOL_TIMEZONE).date()
    cache.prune(today)

    today_day = await _fetch_price_day(
        hass,
        entry=entry,
        area=area,
        currency=currency,
        price_date=today,
        cache=cache,
    )

    tomorrow: list[dict[str, Any]] = []
    tomorrow_date = today + timedelta(days=1)
    cached_tomorrow = cache.get(entry.entry_id, area, currency, tomorrow_date)
    runtime_data = getattr(entry, "runtime_data", None)
    tomorrow_available = bool(getattr(runtime_data, "has_tomorrow_data", False))
    if cached_tomorrow is not None:
        tomorrow = cached_tomorrow.intervals
    elif tomorrow_available:
        try:
            tomorrow_day = await _fetch_price_day(
                hass,
                entry=entry,
                area=area,
                currency=currency,
                price_date=tomorrow_date,
                cache=cache,
            )
            tomorrow = tomorrow_day.intervals
        except NordPoolPriceError:
            # Tomorrow is optional. No cache entry is written on failure, so a
            # later coordinator refresh can retry without discarding today's data.
            tomorrow = []

    return {"today": today_day.intervals, "tomorrow": tomorrow}


async def async_get_nordpool_price_history(
    hass: HomeAssistant,
    *,
    config_entry_id: str | None,
    area: str | None,
    start: datetime,
    end: datetime,
    cache: NordPoolPriceCache,
) -> list[dict[str, Any]]:
    """Fetch and filter cached 15-minute spot history for the requested window."""
    entry, area, currency = get_nordpool_config_entry(hass, config_entry_id, area)
    start = start.astimezone(timezone.utc)
    end = end.astimezone(timezone.utc)
    # The action's `date` is a Nord Pool delivery date. Resolve the UTC
    # request window against the market timezone, independently of HA's zone.
    first_date = start.astimezone(NORDPOOL_TIMEZONE).date()
    last_date = (end - timedelta(microseconds=1)).astimezone(NORDPOOL_TIMEZONE).date()
    today = dt_util.now().astimezone(NORDPOOL_TIMEZONE).date()
    earliest_date = _subtract_months(today, 2)
    latest_date = today + timedelta(days=1)
    cache.prune(today)

    result: list[dict[str, Any]] = []
    current_date = first_date
    while current_date <= last_date:
        if earliest_date <= current_date <= latest_date:
            try:
                day = await _fetch_price_day(
                    hass,
                    entry=entry,
                    area=area,
                    currency=currency,
                    price_date=current_date,
                    cache=cache,
                    require_complete_day=True,
                )
            except NordPoolPriceError:
                # Keep partial history available to the caller; a later
                # request can retry this day.
                day = None
            if day is not None:
                result.extend(
                    {
                        **interval,
                        "recorded_at": day.fetched_at,
                    }
                    for interval in day.intervals
                    if interval["start"].astimezone(timezone.utc) < end
                    and interval["end"].astimezone(timezone.utc) > start
                )
        current_date += timedelta(days=1)

    result.sort(key=lambda item: item["start"])
    return result


def _subtract_months(value: date, months: int) -> date:
    """Subtract calendar months, clamping the day to month length."""
    month_index = value.year * 12 + value.month - 1 - months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


async def async_get_nordpool_price_model(
    hass: HomeAssistant,
    *,
    now: datetime,
    config_entry_id: str | None = None,
    area: str | None = None,
    cache: NordPoolPriceCache | None = None,
    very_cheap_limit: float = DEFAULT_VERY_CHEAP_LIMIT,
    cheap_limit: float = DEFAULT_CHEAP_LIMIT,
    normal_limit: float = DEFAULT_NORMAL_LIMIT,
    expensive_limit: float = DEFAULT_EXPENSIVE_LIMIT,
) -> dict[str, Any]:
    """Fetch cached Nord Pool data and assemble SBE's current/forecast model."""
    if config_entry_id is None:
        config_entry_id = get_nordpool_config_entry_id(hass)
    prices_by_day = await async_get_nordpool_prices(
        hass,
        config_entry_id,
        area=area,
        cache=cache,
        now=now,
    )
    return build_nordpool_price_model(
        prices_by_day,
        now=now,
        very_cheap_limit=very_cheap_limit,
        cheap_limit=cheap_limit,
        normal_limit=normal_limit,
        expensive_limit=expensive_limit,
    )
