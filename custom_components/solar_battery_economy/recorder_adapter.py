"""Home Assistant Recorder adapter for Energy Dashboard data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.recorder import get_instance, history
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.core import HomeAssistant

from .analytics import build_statistics_energy_samples_with_price_history
from .recorder_data import clamp_history_window, normalize_history_states

STATISTICS_PERIOD = "5minute"


async def async_get_history(
    hass: HomeAssistant,
    entity_ids: list[str],
    *,
    start: datetime,
    end: datetime,
    include_attributes: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Read Recorder state history for up to 24 hours."""
    start, end = clamp_history_window(start=start, end=end)
    if not entity_ids:
        return {}

    instance = get_instance(hass)
    states = await instance.async_add_executor_job(
        history.get_significant_states,
        hass,
        start,
        end,
        entity_ids,
        None,
        True,
        False,
        False,
        not include_attributes,
        False,
    )

    return {
        entity_id: normalize_history_states(
            entity_states, include_attributes=include_attributes
        )
        for entity_id, entity_states in states.items()
    }


async def async_get_statistics(
    hass: HomeAssistant,
    statistic_ids: set[str],
    *,
    start: datetime,
    end: datetime,
    types: set[str],
) -> dict[str, list[dict[str, Any]]]:
    """Read Recorder statistics without touching the database directly."""
    start, end = clamp_history_window(start=start, end=end)
    if not statistic_ids:
        return {}

    instance = get_instance(hass)
    return await instance.async_add_executor_job(
        statistics_during_period,
        hass,
        start,
        end,
        statistic_ids,
        STATISTICS_PERIOD,
        None,
        types,
    )


async def async_get_energy_price_samples(
    hass: HomeAssistant,
    energy_entity_ids: list[str],
    price_entity_id: str,
    *,
    start: datetime,
    end: datetime,
) -> dict[str, list[dict[str, Any]]]:
    """Read cumulative energy statistics and price state history together.

    Energy entities use Recorder 5-minute ``change`` statistics. The import
    price sensor is intentionally read through state history because it is
    not a statistics entity in the user's installation. No price entity is
    created and no price value is interpolated.
    """
    start, end = clamp_history_window(start=start, end=end)
    if not energy_entity_ids:
        return {}

    price_history = await async_get_history(
        hass,
        [price_entity_id],
        start=start,
        end=end,
        include_attributes=True,
    )
    price_states = price_history.get(price_entity_id, [])

    statistics = await async_get_statistics(
        hass,
        set(energy_entity_ids),
        start=start,
        end=end,
        types={"change"},
    )

    return {
        entity_id: build_statistics_energy_samples_with_price_history(
            statistics.get(entity_id, []),
            price_states,
        )
        for entity_id in energy_entity_ids
    }
