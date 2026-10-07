import ast
import asyncio
import importlib.util
from pathlib import Path
import sys
import types

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


def test_dashboard_subscription_is_registered_and_uses_connection_cleanup():
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert 'WS_TYPE_SUBSCRIBE_DASHBOARD_DATA = f"{DOMAIN}/subscribe_dashboard_data"' in source
    assert 'connection.subscriptions[msg["id"]] = _unsubscribe_dashboard' in source
    assert "connection.send_event(msg[\"id\"], payload)" in source
    assert "await coordinator.async_subscribe_dashboard(" in source
    assert "async_register_command(hass, ws_subscribe_dashboard_data)" in source


def test_subscription_sends_initial_payload_as_event_after_empty_ack():
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert 'connection.send_result(msg["id"])' in source
    assert "_send_dashboard_event(payload)" in source
    assert 'connection.send_result(msg["id"], payload)' not in source
    assert 'connection.send_event(msg["id"], payload)' in source
    assert source.index('connection.send_result(msg["id"])') < source.index(
        "_send_dashboard_event(payload)"
    )


def test_each_subscriber_gets_initial_payload_through_its_registered_callback():
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "subscriber_id = (id(connection), msg[\"id\"])" in source
    assert "connection.subscriptions[msg[\"id\"]] = _unsubscribe_dashboard" in source
    assert "await coordinator.async_subscribe_dashboard(" in source
    assert "_send_dashboard_event," in source
    assert "_send_dashboard_event(payload)" in source


def test_initial_dashboard_request_response_stays_registered():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "async def ws_get_dashboard_data(" in source
    assert "await coordinator.async_get_dashboard_data(start=start, end=end)" in source
    assert "async_register_command(hass, ws_get_dashboard_data)" in source
    assert 'connection.send_result(msg["id"], data)' in source


def test_integration_registers_websocket_commands_in_global_setup():
    source = (
        MODULE_PATH.parent / "__init__.py"
    ).read_text(encoding="utf-8")

    assert "async def async_setup(hass: HomeAssistant, config: dict) -> bool:" in source
    assert "async_register_websocket_commands(hass)" in source


def test_config_entry_unload_stops_dashboard_subscription_lifecycle():
    source = (MODULE_PATH.parent / "__init__.py").read_text(encoding="utf-8")
    assert "coordinator.async_shutdown_dashboard()" in source


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


def _load_websocket_module(monkeypatch):
    package = types.ModuleType("sbe_websocket_test")
    package.__path__ = []
    const = types.ModuleType("sbe_websocket_test.const")
    const.DOMAIN = "solar_battery_economy"
    monkeypatch.setitem(sys.modules, package.__name__, package)
    monkeypatch.setitem(sys.modules, const.__name__, const)

    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Required = lambda value: value
    voluptuous.Optional = lambda value: value
    voluptuous.datetime = "datetime"
    monkeypatch.setitem(sys.modules, "voluptuous", voluptuous)

    ha = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    websocket_api = types.ModuleType("homeassistant.components.websocket_api")
    websocket_api.websocket_command = lambda schema: lambda fn: fn
    websocket_api.async_response = lambda fn: fn
    websocket_api.async_register_command = lambda hass, fn: None
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    core.callback = lambda fn: fn
    helpers = types.ModuleType("homeassistant.helpers")
    config_validation = types.ModuleType("homeassistant.helpers.config_validation")
    config_validation.string = str
    config_validation.datetime = "datetime"
    util = types.ModuleType("homeassistant.util")
    dt = types.ModuleType("homeassistant.util.dt")
    dt.utcnow = lambda: None
    util.dt = dt
    modules = {
        "homeassistant": ha,
        "homeassistant.components": components,
        "homeassistant.components.websocket_api": websocket_api,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.config_validation": config_validation,
        "homeassistant.util": util,
        "homeassistant.util.dt": dt,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    spec = importlib.util.spec_from_file_location(
        "sbe_websocket_test.websocket", MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


class _LivePowerCoordinator:
    def __init__(self, snapshot):
        self.data = {"live_power": snapshot}
        self.subscribers = {}
        self.cleanup = {}

    def async_subscribe_live_power(self, subscriber_id, callback_fn, cleanup_fn):
        self.subscribers[subscriber_id] = callback_fn
        self.cleanup[subscriber_id] = cleanup_fn
        return self.data["live_power"]

    def async_unsubscribe_live_power(self, subscriber_id):
        self.subscribers.pop(subscriber_id, None)
        self.cleanup.pop(subscriber_id, None)

    def publish(self, snapshot):
        self.data["live_power"] = snapshot
        for callback_fn in tuple(self.subscribers.values()):
            callback_fn(snapshot)

    def disconnect_all(self):
        callbacks = tuple(self.cleanup.values())
        self.subscribers.clear()
        self.cleanup.clear()
        for callback_fn in callbacks:
            callback_fn()


class _Connection:
    def __init__(self):
        self.subscriptions = {}
        self.results = []
        self.events = []
        self.errors = []

    def send_result(self, msg_id, result=None):
        self.results.append((msg_id, result))

    def send_event(self, msg_id, payload):
        self.events.append((msg_id, payload))

    def send_error(self, msg_id, code, message):
        self.errors.append((msg_id, code, message))


def _snapshot(marker):
    flows = {
        key: {"value": marker, "quality": "valid"}
        for key in (
            "solar_house", "solar_battery", "solar_export", "battery_house",
            "battery_grid", "grid_house", "grid_battery", "unknown_grid_export",
        )
    }
    aggregates = {
        key: {"value": marker, "quality": "valid"}
        for key in ("solar_total", "house_total", "battery_net", "grid_net")
    }
    return {
        "timestamp": "2026-10-07T12:00:00+00:00",
        "timestamp_kind": "calculated_at",
        "freshness": {"age_seconds": 3},
        "inputs": {"solar": {"quality": "valid"}},
        "flows": flows,
        "aggregates": aggregates,
    }


def _send_live_power(module, hass, connection, msg_id, entry_id):
    asyncio.run(
        module.ws_subscribe_live_power(
            hass,
            connection,
            {
                "id": msg_id,
                "type": module.WS_TYPE_SUBSCRIBE_LIVE_POWER,
                "config_entry_id": entry_id,
            },
        )
    )


def test_live_power_subscription_sends_initial_existing_snapshot(monkeypatch):
    module = _load_websocket_module(monkeypatch)
    snapshot = _snapshot(1)
    coordinator = _LivePowerCoordinator(snapshot)
    connection = _Connection()
    hass = types.SimpleNamespace(data={"solar_battery_economy": {"entry-a": coordinator}})

    _send_live_power(module, hass, connection, 4, "entry-a")

    assert connection.results == [(4, None)]
    assert connection.events == [(4, snapshot)]
    assert len(connection.events) == 1  # No event without a coordinator update.
    assert len(snapshot["flows"]) == 8
    assert len(snapshot["aggregates"]) == 4
    assert {"timestamp", "timestamp_kind", "freshness", "inputs"}.issubset(snapshot)
    assert all(flow["quality"] == "valid" for flow in snapshot["flows"].values())


def test_live_power_subscription_uses_entry_and_isolates_multiple_instances(monkeypatch):
    module = _load_websocket_module(monkeypatch)
    first = _LivePowerCoordinator(_snapshot("first"))
    second = _LivePowerCoordinator(_snapshot("second"))
    connection = _Connection()
    hass = types.SimpleNamespace(
        data={"solar_battery_economy": {"entry-a": first, "entry-b": second}}
    )

    _send_live_power(module, hass, connection, 1, "entry-b")
    second.publish(_snapshot("updated"))
    first.publish(_snapshot("unrelated"))

    assert connection.events[0][1] == _snapshot("second")
    assert connection.events[1][1]["flows"]["solar_house"]["value"] == "updated"
    assert len(connection.events) == 2
    assert not first.subscribers


def test_live_power_unknown_entry_returns_not_found_error(monkeypatch):
    module = _load_websocket_module(monkeypatch)
    connection = _Connection()
    hass = types.SimpleNamespace(data={"solar_battery_economy": {}})

    _send_live_power(module, hass, connection, 2, "missing")

    assert connection.errors == [
        (2, "config_entry_not_found", "Solar Battery Economy config entry not found")
    ]
    assert not connection.events


def test_live_power_unsubscribe_disconnect_and_unload_stop_events(monkeypatch):
    module = _load_websocket_module(monkeypatch)
    coordinator = _LivePowerCoordinator(_snapshot(1))
    connection = _Connection()
    hass = types.SimpleNamespace(data={"solar_battery_economy": {"entry-a": coordinator}})
    _send_live_power(module, hass, connection, 3, "entry-a")

    connection.subscriptions[3]()
    coordinator.publish(_snapshot(2))
    assert len(connection.events) == 1
    assert not coordinator.subscribers

    _send_live_power(module, hass, connection, 4, "entry-a")
    coordinator.disconnect_all()
    connection.subscriptions.pop(4, None)
    coordinator.publish(_snapshot(3))
    assert len(connection.events) == 2
    assert 4 not in connection.subscriptions


def test_live_power_subscribers_share_one_coordinator_snapshot(monkeypatch):
    module = _load_websocket_module(monkeypatch)
    coordinator = _LivePowerCoordinator(_snapshot(1))
    first_connection = _Connection()
    second_connection = _Connection()
    hass = types.SimpleNamespace(data={"solar_battery_economy": {"entry-a": coordinator}})

    _send_live_power(module, hass, first_connection, 1, "entry-a")
    _send_live_power(module, hass, second_connection, 2, "entry-a")
    updated = _snapshot(2)
    coordinator.publish(updated)

    assert first_connection.events[-1][1] is updated
    assert second_connection.events[-1][1] is updated
    assert len(coordinator.subscribers) == 2


def test_reusing_subscription_id_does_not_duplicate_callback(monkeypatch):
    module = _load_websocket_module(monkeypatch)
    coordinator = _LivePowerCoordinator(_snapshot(1))
    connection = _Connection()
    hass = types.SimpleNamespace(data={"solar_battery_economy": {"entry-a": coordinator}})

    _send_live_power(module, hass, connection, 5, "entry-a")
    _send_live_power(module, hass, connection, 5, "entry-a")
    coordinator.publish(_snapshot(2))

    assert len(coordinator.subscribers) == 1
    assert len(connection.events) == 3  # Two initial snapshots and one update.


def test_live_power_uses_one_shared_coordinator_listener_and_no_new_loop():
    source = COORDINATOR_PATH.read_text(encoding="utf-8")
    live_methods = source.split("def async_subscribe_live_power(", 1)[1].split(
        "# ---------------------------------------------------------", 1
    )[0]
    assert "self.async_add_listener(" in live_methods
    assert "if self._live_power_update_unsub is None:" in live_methods
    assert "self.data.get(\"live_power\", {})" in live_methods
    assert "async_track_state_change_event" not in live_methods
    assert "async_track_time_interval" not in live_methods
    assert "async_shutdown_live_power()" in (
        MODULE_PATH.parent / "__init__.py"
    ).read_text(encoding="utf-8")


def test_live_power_command_is_additive_to_existing_dashboard_commands():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert 'WS_TYPE_SUBSCRIBE_LIVE_POWER = f"{DOMAIN}/subscribe_live_power"' in source
    assert 'vol.Required("config_entry_id"): cv.string' in source
    assert 'connection.send_event(msg["id"], snapshot)' in source
    assert "async_register_command(hass, ws_subscribe_live_power)" in source
    assert "async_register_command(hass, ws_get_dashboard_data)" in source
    assert "async_register_command(hass, ws_subscribe_dashboard_data)" in source
