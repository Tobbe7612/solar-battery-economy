from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "websocket.py"
)


def test_dashboard_websocket_command_is_registered_and_bounded():
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert 'WS_TYPE_GET_DASHBOARD_DATA = f"{DOMAIN}/get_dashboard_data"' in source
    assert 'vol.Required("config_entry_id"): cv.string' in source
    assert 'end - timedelta(hours=24)' in source
    assert 'async_register_command(hass, ws_get_dashboard_data)' in source


def test_integration_registers_websocket_commands_in_global_setup():
    source = (
        MODULE_PATH.parent / "__init__.py"
    ).read_text(encoding="utf-8")

    assert "async def async_setup(hass: HomeAssistant, config: dict) -> bool:" in source
    assert "async_register_websocket_commands(hass)" in source
