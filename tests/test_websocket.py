import ast
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "websocket.py"
)

COORDINATOR_PATH = MODULE_PATH.parent / "coordinator.py"


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


def test_coordinator_imports_dashboard_energy_sample_builder():
    source = COORDINATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported_names = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "analytics"
        and node.level == 1
        for alias in node.names
    }

    assert "build_statistics_energy_samples_with_price_history" in imported_names


def test_coordinator_dashboard_uses_shared_price_reference_and_battery_house():
    source = COORDINATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_house_analysis"
    ]
    assert len(calls) == 1
    keywords = {keyword.arg for keyword in calls[0].keywords}
    assert {"reference_price", "battery_house_samples"}.issubset(keywords)

    assert 'self._get_energy_entity_id("battery_house")' in source
    assert 'calculate_shared_import_price_median(\n            analysis_price_states' in source


def test_dashboard_payload_includes_deterministic_insights_builder():
    source = Path("custom_components/solar_battery_economy/coordinator.py").read_text(encoding="utf-8")
    assert "build_deterministic_insights(house, consumers)" in source


def test_dashboard_payload_uses_total_import_price_as_primary_price_basis():
    source = COORDINATOR_PATH.read_text(encoding="utf-8")
    assert '"today_import_price_statistics": calculate_today_import_price_statistics(' in source
    assert '"import_intervals": [' in source
    assert '"today_spot_statistics"' not in source
