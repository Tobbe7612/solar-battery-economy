import asyncio
import importlib.util
import sys
import types
from datetime import date, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "nordpool_runtime.py"
)
PACKAGE_PATH = MODULE_PATH.parent

# Provide only the Home Assistant symbols imported by the runtime helper.
ha = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
core = sys.modules.setdefault("homeassistant.core", types.ModuleType("homeassistant.core"))
core.HomeAssistant = type("HomeAssistant", (), {})
util = sys.modules.setdefault("homeassistant.util", types.ModuleType("homeassistant.util"))
dt = types.ModuleType("homeassistant.util.dt")
dt.now = lambda: datetime(2026, 9, 28, 8, tzinfo=timezone(timedelta(hours=2)))
dt.utcnow = lambda: datetime(2026, 9, 28, 6, tzinfo=timezone.utc)


class _OsloTestTimezone(tzinfo):
    """Small 2026 Oslo timezone fixture, including both DST transitions."""

    @staticmethod
    def _last_sunday(year, month):
        last = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
        return last - timedelta(days=(last.weekday() + 1) % 7)

    def utcoffset(self, value):
        spring = self._last_sunday(value.year, 3)
        autumn = self._last_sunday(value.year, 10)
        summer_time = (
            spring < value.date() < autumn
            or (value.date() == spring and value.hour >= 3)
            or (value.date() == autumn and value.hour < 3)
        )
        return timedelta(hours=2 if summer_time else 1)

    def dst(self, value):
        return self.utcoffset(value) - timedelta(hours=1)

    def tzname(self, value):
        return "CEST" if self.dst(value) else "CET"


OSLO_TZ = _OsloTestTimezone()
dt.get_time_zone = lambda _name: OSLO_TZ
util.dt = dt
ha.core = core
ha.util = util
sys.modules["homeassistant.util.dt"] = dt

package = types.ModuleType("custom_components.solar_battery_economy")
package.__path__ = [str(PACKAGE_PATH)]
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
sys.modules[package.__name__] = package

price_model_spec = importlib.util.spec_from_file_location(
    "custom_components.solar_battery_economy.price_model",
    PACKAGE_PATH / "price_model.py",
)
assert price_model_spec is not None and price_model_spec.loader is not None
price_model = importlib.util.module_from_spec(price_model_spec)
sys.modules[price_model_spec.name] = price_model
price_model_spec.loader.exec_module(price_model)

spec = importlib.util.spec_from_file_location(
    "custom_components.solar_battery_economy.nordpool_runtime", MODULE_PATH
)
assert spec is not None and spec.loader is not None
runtime = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runtime
spec.loader.exec_module(runtime)


class FakeServices:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def async_call(self, domain, action, data, **kwargs):
        self.calls.append((domain, action, data, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _hass(responses, *, tomorrow_available=False, entries=None):
    services = FakeServices(responses)
    config_entry = SimpleNamespace(
        entry_id="arbitrary-config-entry-id",
        domain="nordpool",
        data={"areas": ["SE3", "SE4"], "currency": "SEK"},
        runtime_data=SimpleNamespace(has_tomorrow_data=tomorrow_available),
    )
    entries = entries or [config_entry]
    by_id = {entry.entry_id: entry for entry in entries}
    hass = SimpleNamespace(
        services=services,
        config_entries=SimpleNamespace(
            async_entries=lambda domain: [entry for entry in entries if entry.domain == domain],
            async_get_entry=lambda entry_id: by_id.get(entry_id),
        ),
        config=SimpleNamespace(time_zone="Europe/Stockholm"),
    )
    return hass, services, config_entry


def _period(start, end, price, area="SE3"):
    return {"start": start, "end": end, "price": price}


def _complete_day(price_date, price=500, *, area="SE3"):
    market_timezone = OSLO_TZ
    local_start = datetime.combine(
        price_date, datetime.min.time(), market_timezone
    ).astimezone(timezone.utc)
    local_end = datetime.combine(
        price_date + timedelta(days=1), datetime.min.time(), market_timezone
    ).astimezone(timezone.utc)
    result = []
    cursor = local_start
    while cursor < local_end:
        next_cursor = cursor + timedelta(minutes=15)
        result.append(_period(cursor.isoformat(), next_cursor.isoformat(), price, area))
        cursor = next_cursor
    return result


def _response(rows, area="SE3"):
    return {area: rows}


def _fetch_calls(services):
    return [call for call in services.calls if call[1] == "get_price_indices_for_date"]


def test_tomorrow_unavailable_does_not_call_api_and_keeps_today():
    today_rows = [_period("2026-09-28T08:00:00+00:00", "2026-09-28T08:15:00+00:00", 600)]
    hass, services, entry = _hass([_response(today_rows)])
    cache = runtime.NordPoolPriceCache()

    result = asyncio.run(
        runtime.async_get_nordpool_prices(
            hass,
            entry.entry_id,
            area="SE3",
            cache=cache,
            now=datetime(2026, 9, 28, 8, tzinfo=timezone.utc),
        )
    )

    assert result["today"][0]["spot"] == pytest.approx(0.6)
    assert result["tomorrow"] == []
    assert len(_fetch_calls(services)) == 1


def test_simultaneous_cache_misses_share_one_nordpool_request():
    class GatedServices:
        def __init__(self):
            self.calls = []
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def async_call(self, domain, action, data, **kwargs):
            self.calls.append((domain, action, data, kwargs))
            self.started.set()
            await self.release.wait()
            return _response([
                _period("2026-09-28T08:00:00+00:00", "2026-09-28T08:15:00+00:00", 600)
            ])

    async def run():
        hass, _, entry = _hass([])
        services = GatedServices()
        hass.services = services
        cache = runtime.NordPoolPriceCache()
        now = datetime(2026, 9, 28, 8, tzinfo=timezone.utc)
        first = asyncio.create_task(runtime.async_get_nordpool_prices(
            hass, entry.entry_id, area="SE3", cache=cache, now=now
        ))
        await services.started.wait()
        second = asyncio.create_task(runtime.async_get_nordpool_prices(
            hass, entry.entry_id, area="SE3", cache=cache, now=now
        ))
        await asyncio.sleep(0)
        assert len(services.calls) == 1
        services.release.set()
        results = await asyncio.gather(first, second)
        assert results[0] == results[1]
        assert len(services.calls) == 1

    asyncio.run(run())


def test_simultaneous_failed_cache_miss_is_not_cached_and_retries():
    class GatedServices:
        def __init__(self):
            self.calls = []
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def async_call(self, domain, action, data, **kwargs):
            self.calls.append((domain, action, data, kwargs))
            if len(self.calls) == 1:
                self.started.set()
                await self.release.wait()
                raise RuntimeError("temporary failure")
            return _response([
                _period("2026-09-28T08:00:00+00:00", "2026-09-28T08:15:00+00:00", 600)
            ])

    async def run():
        hass, _, entry = _hass([])
        services = GatedServices()
        hass.services = services
        cache = runtime.NordPoolPriceCache()
        now = datetime(2026, 9, 28, 8, tzinfo=timezone.utc)
        first = asyncio.create_task(runtime.async_get_nordpool_prices(
            hass, entry.entry_id, area="SE3", cache=cache, now=now
        ))
        await services.started.wait()
        second = asyncio.create_task(runtime.async_get_nordpool_prices(
            hass, entry.entry_id, area="SE3", cache=cache, now=now
        ))
        await asyncio.sleep(0)
        assert len(services.calls) == 1
        services.release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        assert all(isinstance(result, runtime.NordPoolPriceError) for result in results)
        key = (entry.entry_id, "SE3", "SEK", date(2026, 9, 28))
        assert key not in cache.days
        retried = await runtime.async_get_nordpool_prices(
            hass, entry.entry_id, area="SE3", cache=cache, now=now
        )
        assert retried["today"][0]["spot"] == pytest.approx(0.6)
        assert len(services.calls) == 2

    asyncio.run(run())


def test_tomorrow_available_fetches_tomorrow_once_and_reuses_cached_data():
    today_rows = [_period("2026-09-28T08:00:00+00:00", "2026-09-28T08:15:00+00:00", 600)]
    tomorrow_rows = [_period("2026-09-29T08:00:00+00:00", "2026-09-29T08:15:00+00:00", 700)]
    hass, services, entry = _hass(
        [_response(today_rows), _response(tomorrow_rows)], tomorrow_available=True
    )
    cache = runtime.NordPoolPriceCache()
    now = datetime(2026, 9, 28, 8, tzinfo=timezone.utc)

    first = asyncio.run(
        runtime.async_get_nordpool_prices(hass, entry.entry_id, area="SE3", cache=cache, now=now)
    )
    entry.runtime_data.has_tomorrow_data = False
    second = asyncio.run(
        runtime.async_get_nordpool_prices(hass, entry.entry_id, area="SE3", cache=cache, now=now)
    )

    assert first["tomorrow"][0]["spot"] == second["tomorrow"][0]["spot"] == 0.7
    assert [call[2]["date"] for call in _fetch_calls(services)] == [
        date(2026, 9, 28),
        date(2026, 9, 29),
    ]
    assert all(call[2]["areas"] == ["SE3"] for call in _fetch_calls(services))
    assert all(call[2]["currency"] == "SEK" for call in _fetch_calls(services))


def test_failed_tomorrow_does_not_discard_today_and_retries_next_refresh():
    today_rows = [_period("2026-09-28T08:00:00+00:00", "2026-09-28T08:15:00+00:00", 600)]
    tomorrow_rows = [_period("2026-09-29T08:00:00+00:00", "2026-09-29T08:15:00+00:00", 700)]
    hass, services, entry = _hass(
        [_response(today_rows), RuntimeError("temporary error"), _response(tomorrow_rows)],
        tomorrow_available=True,
    )
    cache = runtime.NordPoolPriceCache()
    now = datetime(2026, 9, 28, 8, tzinfo=timezone.utc)

    failed = asyncio.run(
        runtime.async_get_nordpool_prices(hass, entry.entry_id, area="SE3", cache=cache, now=now)
    )
    retried = asyncio.run(
        runtime.async_get_nordpool_prices(hass, entry.entry_id, area="SE3", cache=cache, now=now)
    )

    assert failed["today"][0]["spot"] == pytest.approx(0.6)
    assert failed["tomorrow"] == []
    assert retried["today"] == failed["today"]
    assert retried["tomorrow"][0]["spot"] == pytest.approx(0.7)
    assert [call[2]["date"] for call in _fetch_calls(services)] == [
        date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 29)
    ]


def test_cached_tomorrow_becomes_today_after_date_rollover():
    today_rows = [_period("2026-09-28T08:00:00+00:00", "2026-09-28T08:15:00+00:00", 600)]
    tomorrow_rows = _complete_day(date(2026, 9, 29), 700)
    next_tomorrow = [_period("2026-09-30T08:00:00+00:00", "2026-09-30T08:15:00+00:00", 800)]
    hass, services, entry = _hass(
        [_response(today_rows), _response(tomorrow_rows), _response(next_tomorrow)],
        tomorrow_available=True,
    )
    cache = runtime.NordPoolPriceCache()

    asyncio.run(
        runtime.async_get_nordpool_prices(
            hass, entry.entry_id, area="SE3", cache=cache,
            now=datetime(2026, 9, 28, 8, tzinfo=timezone.utc),
        )
    )
    next_day = asyncio.run(
        runtime.async_get_nordpool_prices(
            hass, entry.entry_id, area="SE3", cache=cache,
            now=datetime(2026, 9, 29, 8, tzinfo=timezone.utc),
        )
    )

    assert len(next_day["today"]) == 96
    assert next_day["today"][0]["spot"] == pytest.approx(0.7)
    assert next_day["tomorrow"][0]["spot"] == pytest.approx(0.8)
    assert [call[2]["date"] for call in _fetch_calls(services)] == [
        date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30)
    ]


def test_historical_single_date_is_cached_and_keeps_spot_payload():
    price_date = date(2026, 9, 27)
    hass, services, entry = _hass([_response(_complete_day(price_date))])
    cache = runtime.NordPoolPriceCache()
    start = datetime(2026, 9, 27, 10, tzinfo=timezone(timedelta(hours=2)))
    end = start + timedelta(minutes=30)

    first = asyncio.run(runtime.async_get_nordpool_price_history(
        hass, config_entry_id=entry.entry_id, area="SE3", start=start, end=end, cache=cache
    ))
    second = asyncio.run(runtime.async_get_nordpool_price_history(
        hass, config_entry_id=entry.entry_id, area="SE3", start=start, end=end, cache=cache
    ))

    assert first == second
    assert len(first) == 2
    assert set(first[0]) == {"start", "end", "spot", "recorded_at"}
    assert first[0]["spot"] == pytest.approx(0.5)
    assert len(_fetch_calls(services)) == 1


def test_simultaneous_historical_requests_share_one_date_fetch():
    class GatedServices:
        def __init__(self):
            self.calls = []
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def async_call(self, domain, action, data, **kwargs):
            self.calls.append((domain, action, data, kwargs))
            self.started.set()
            await self.release.wait()
            return _response(_complete_day(date(2026, 9, 27)))

    async def run():
        hass, _, entry = _hass([])
        services = GatedServices()
        hass.services = services
        cache = runtime.NordPoolPriceCache()
        base = datetime(2026, 9, 27, 10, tzinfo=timezone(timedelta(hours=2)))
        first = asyncio.create_task(runtime.async_get_nordpool_price_history(
            hass, config_entry_id=entry.entry_id, area="SE3", start=base,
            end=base + timedelta(minutes=15), cache=cache,
        ))
        await services.started.wait()
        second = asyncio.create_task(runtime.async_get_nordpool_price_history(
            hass, config_entry_id=entry.entry_id, area="SE3",
            start=base + timedelta(minutes=15),
            end=base + timedelta(minutes=30), cache=cache,
        ))
        await asyncio.sleep(0)
        assert len(services.calls) == 1
        services.release.set()
        first_result, second_result = await asyncio.gather(first, second)
        assert len(first_result) == len(second_result) == 1
        assert len(services.calls) == 1

    asyncio.run(run())


def test_historical_range_crossing_local_midnight_fetches_two_dates():
    hass, services, entry = _hass([
        _response(_complete_day(date(2026, 9, 27), 500)),
        _response(_complete_day(date(2026, 9, 28), 600)),
    ])
    local_tz = timezone(timedelta(hours=2))
    start = datetime(2026, 9, 27, 23, 45, tzinfo=local_tz)
    end = datetime(2026, 9, 28, 0, 15, tzinfo=local_tz)
    result = asyncio.run(runtime.async_get_nordpool_price_history(
        hass, config_entry_id=entry.entry_id, area="SE3", start=start, end=end,
        cache=runtime.NordPoolPriceCache(),
    ))

    assert [call[2]["date"] for call in _fetch_calls(services)] == [
        date(2026, 9, 27), date(2026, 9, 28)
    ]
    assert len(result) == 2
    assert result[0]["end"] == result[1]["start"]


def test_historical_utc_local_boundary_uses_home_assistant_timezone():
    hass, services, entry = _hass([_response(_complete_day(date(2026, 9, 28)))])
    # 22:00 UTC is local midnight on the following calendar date in Stockholm.
    start = datetime(2026, 9, 27, 22, tzinfo=timezone.utc)
    end = start + timedelta(minutes=15)
    result = asyncio.run(runtime.async_get_nordpool_price_history(
        hass, config_entry_id=entry.entry_id, area="SE3", start=start, end=end,
        cache=runtime.NordPoolPriceCache(),
    ))

    assert _fetch_calls(services)[0][2]["date"] == date(2026, 9, 28)
    assert len(result) == 1


def test_historical_delivery_date_uses_market_timezone_not_ha_timezone():
    hass, services, entry = _hass([_response(_complete_day(date(2026, 9, 28)))])
    hass.config.time_zone = "America/Los_Angeles"
    # This instant is Sep 27 in Los Angeles and Sep 28 in Nord Pool's market zone.
    start = datetime(2026, 9, 27, 22, 30, tzinfo=timezone.utc)
    result = asyncio.run(runtime.async_get_nordpool_price_history(
        hass, config_entry_id=entry.entry_id, area="SE3", start=start,
        end=start + timedelta(minutes=15), cache=runtime.NordPoolPriceCache(),
    ))

    assert _fetch_calls(services)[0][2]["date"] == date(2026, 9, 28)
    assert len(result) == 1


def test_historical_market_timezone_dst_day_has_92_quarters():
    price_date = date(2026, 3, 29)
    rows = _complete_day(price_date)
    assert len(rows) == 92
    hass, services, entry = _hass([_response(rows)])
    start = datetime.combine(price_date, datetime.min.time(), OSLO_TZ)
    end = datetime.combine(price_date + timedelta(days=1), datetime.min.time(), OSLO_TZ)
    original_now = dt.now
    dt.now = lambda: datetime(2026, 5, 28, 8, tzinfo=OSLO_TZ)
    try:
        result = asyncio.run(runtime.async_get_nordpool_price_history(
            hass, config_entry_id=entry.entry_id, area="SE3", start=start,
            end=end, cache=runtime.NordPoolPriceCache(),
        ))
    finally:
        dt.now = original_now

    assert _fetch_calls(services)[0][2]["date"] == price_date
    assert len(result) == 92


def test_historical_filters_intervals_to_requested_overlapping_window():
    price_date = date(2026, 9, 27)
    hass, _, entry = _hass([_response(_complete_day(price_date))])
    local_tz = timezone(timedelta(hours=2))
    start = datetime(2026, 9, 27, 10, 7, tzinfo=local_tz)
    end = datetime(2026, 9, 27, 10, 31, tzinfo=local_tz)
    result = asyncio.run(runtime.async_get_nordpool_price_history(
        hass, config_entry_id=entry.entry_id, area="SE3", start=start, end=end,
        cache=runtime.NordPoolPriceCache(),
    ))

    assert len(result) == 3
    assert result[0]["start"] == datetime(2026, 9, 27, 8, tzinfo=timezone.utc)
    assert result[-1]["end"] == datetime(2026, 9, 27, 8, 45, tzinfo=timezone.utc)


def test_historical_action_failure_is_not_cached_and_can_retry():
    price_date = date(2026, 9, 27)
    hass, services, entry = _hass([RuntimeError("offline"), _response(_complete_day(price_date))])
    cache = runtime.NordPoolPriceCache()
    start = datetime(2026, 9, 27, 10, tzinfo=timezone(timedelta(hours=2)))
    end = start + timedelta(minutes=15)

    failed_result = asyncio.run(runtime.async_get_nordpool_price_history(
        hass, config_entry_id=entry.entry_id, area="SE3", start=start, end=end, cache=cache
    ))
    result = asyncio.run(runtime.async_get_nordpool_price_history(
        hass, config_entry_id=entry.entry_id, area="SE3", start=start, end=end, cache=cache
    ))

    assert failed_result == []
    assert len(result) == 1
    assert len(_fetch_calls(services)) == 2


def test_incomplete_historical_response_is_not_cached_and_can_retry():
    price_date = date(2026, 9, 27)
    partial = _complete_day(price_date)[:-1]
    hass, services, entry = _hass([_response(partial), _response(_complete_day(price_date))])
    cache = runtime.NordPoolPriceCache()
    start = datetime(2026, 9, 27, 10, tzinfo=timezone(timedelta(hours=2)))
    end = start + timedelta(minutes=15)

    first = asyncio.run(runtime.async_get_nordpool_price_history(
        hass, config_entry_id=entry.entry_id, area="SE3", start=start, end=end, cache=cache
    ))
    second = asyncio.run(runtime.async_get_nordpool_price_history(
        hass, config_entry_id=entry.entry_id, area="SE3", start=start, end=end, cache=cache
    ))
    assert first == []
    assert len(second) == 1
    assert len(_fetch_calls(services)) == 2


def test_historical_two_month_boundary_skips_older_date():
    hass, services, entry = _hass([])
    start = datetime(2026, 7, 27, 10, tzinfo=timezone(timedelta(hours=2)))
    result = asyncio.run(runtime.async_get_nordpool_price_history(
        hass, config_entry_id=entry.entry_id, area="SE3", start=start,
        end=start + timedelta(minutes=15), cache=runtime.NordPoolPriceCache(),
    ))

    assert result == []
    assert _fetch_calls(services) == []


def test_historical_two_month_lower_bound_is_allowed():
    boundary_date = date(2026, 7, 28)
    hass, services, entry = _hass([_response(_complete_day(boundary_date))])
    start = datetime(2026, 7, 28, 10, tzinfo=timezone(timedelta(hours=2)))
    result = asyncio.run(runtime.async_get_nordpool_price_history(
        hass, config_entry_id=entry.entry_id, area="SE3", start=start,
        end=start + timedelta(minutes=15), cache=runtime.NordPoolPriceCache(),
    ))

    assert len(result) == 1
    assert _fetch_calls(services)[0][2]["date"] == boundary_date


def test_config_entry_area_currency_and_id_are_not_hardcoded():
    other_entry = SimpleNamespace(
        entry_id="another-entry",
        domain="nordpool",
        data={"areas": ["FI"], "currency": "EUR"},
        runtime_data=SimpleNamespace(has_tomorrow_data=False),
    )
    unrelated_entry = SimpleNamespace(
        entry_id="unrelated-entry",
        domain="nordpool",
        data={"areas": ["SE3"], "currency": "SEK"},
        runtime_data=SimpleNamespace(has_tomorrow_data=False),
    )
    rows = [_period("2026-09-28T08:00:00+00:00", "2026-09-28T08:15:00+00:00", 125)]
    hass, services, _ = _hass(
        [_response(rows, "FI")], entries=[other_entry, unrelated_entry]
    )

    prices = asyncio.run(runtime.async_get_nordpool_prices(
        hass, other_entry.entry_id, area="FI",
        now=datetime(2026, 9, 28, 8, tzinfo=timezone.utc),
    ))

    assert prices["today"][0]["spot"] == pytest.approx(0.125)
    assert _fetch_calls(services)[0][2]["config_entry"] == "another-entry"
    assert _fetch_calls(services)[0][2]["areas"] == ["FI"]
    assert _fetch_calls(services)[0][2]["currency"] == "EUR"
