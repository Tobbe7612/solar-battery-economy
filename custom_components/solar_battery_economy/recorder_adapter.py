"""Home Assistant Recorder adapter for Energy Dashboard data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.core import HomeAssistant

from .recorder_data import clamp_history_window

STATISTICS_PERIOD = "5minute"


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
