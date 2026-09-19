"""WebSocket API for Solar Battery Economy dashboard data."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DOMAIN

WS_TYPE_GET_DASHBOARD_DATA = f"{DOMAIN}/get_dashboard_data"


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_GET_DASHBOARD_DATA,
        vol.Required("config_entry_id"): cv.string,
        vol.Optional("start"): cv.datetime,
        vol.Optional("end"): cv.datetime,
    }
)
@websocket_api.async_response
async def ws_get_dashboard_data(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return canonical Energy Dashboard data for an SBE config entry."""
    coordinator = hass.data.get(DOMAIN, {}).get(msg["config_entry_id"])
    if coordinator is None:
        connection.send_error(
            msg["id"],
            "config_entry_not_found",
            "Solar Battery Economy config entry not found",
        )
        return

    end = msg.get("end") or dt_util.utcnow()
    start = msg.get("start") or (end - timedelta(hours=24))

    try:
        data = await coordinator.async_get_dashboard_data(start=start, end=end)
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_period", str(err))
        return
    except Exception as err:  # pragma: no cover - defensive runtime boundary
        connection.send_error(msg["id"], "dashboard_data_failed", str(err))
        return

    connection.send_result(msg["id"], data)


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register Solar Battery Economy WebSocket commands."""
    websocket_api.async_register_command(hass, ws_get_dashboard_data)
