"""Behavioral baseline for the current SBE config and options flows.

Home Assistant is not installed in this repository's test environment, so this
module supplies the small HA flow/selector surface used by config_flow.py and
executes the actual integration module against it.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "solar_battery_economy"


class _AbortFlow(Exception):
    pass


class _Marker:
    def __init__(self, schema, *, has_default=False, default=None):
        self.schema = schema
        self.has_default = has_default
        self.default = default


class _Schema:
    def __init__(self, schema):
        self.schema = schema

    def __call__(self, data):
        result = dict(data)
        for marker in self.schema:
            if marker.schema not in result and marker.has_default:
                default = marker.default
                result[marker.schema] = default() if callable(default) else default
        return result


def _marker(schema, default=...):
    return _Marker(schema, has_default=default is not ..., default=None if default is ... else default)


class _Selector:
    def __init__(self, config):
        self.config = config

    def __call__(self, value):
        return value


class _ConfigEntrySelector(_Selector):
    pass


class _ConfigFlow:
    CONN_CLASS_LOCAL_PUSH = "local_push"

    def __init_subclass__(cls, *, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.domain = domain

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        if self.unique_id in getattr(self.hass.config_entries, "unique_ids", set()):
            raise _AbortFlow("already_configured")

    def async_show_form(self, *, step_id, data_schema, errors=None):
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }

    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}


class _OptionsFlow(_ConfigFlow):
    pass


class _Entries:
    def __init__(self, entries=(), unique_ids=()):
        self.entries = list(entries)
        self.unique_ids = set(unique_ids)

    def async_entries(self, domain):
        return [entry for entry in self.entries if entry.domain == domain]

    def async_get_entry(self, entry_id):
        return next((entry for entry in self.entries if entry.entry_id == entry_id), None)


def _load_config_flow(monkeypatch):
    """Load config_flow.py using a minimal voluptuous/HA compatibility surface."""
    voluptuous = types.ModuleType("voluptuous")
    voluptuous.Schema = _Schema
    voluptuous.Required = lambda key, default=...: _marker(key, default)
    voluptuous.Optional = lambda key, default=...: _marker(key, default)
    voluptuous.In = lambda options: ("in", options)
    ha = types.ModuleType("homeassistant")
    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigFlow = _ConfigFlow
    config_entries.OptionsFlow = _OptionsFlow
    config_entries.CONN_CLASS_LOCAL_PUSH = "local_push"
    helpers = types.ModuleType("homeassistant.helpers")
    config_validation = types.ModuleType("homeassistant.helpers.config_validation")
    config_validation.boolean = lambda value: value
    selector_module = types.ModuleType("homeassistant.helpers.selector")
    selector_module.ConfigEntrySelector = _ConfigEntrySelector
    selector_module.selector = _Selector
    ha.config_entries = config_entries
    helpers.config_validation = config_validation
    helpers.selector = selector_module

    modules = {
        "voluptuous": voluptuous,
        "homeassistant": ha,
        "homeassistant.config_entries": config_entries,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.config_validation": config_validation,
        "homeassistant.helpers.selector": selector_module,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    package_name = "custom_components.solar_battery_economy"
    package = types.ModuleType(package_name)
    package.__path__ = [str(INTEGRATION)]
    monkeypatch.setitem(sys.modules, "custom_components", types.ModuleType("custom_components"))
    monkeypatch.setitem(sys.modules, package_name, package)

    spec = importlib.util.spec_from_file_location(
        f"{package_name}.config_flow", INTEGRATION / "config_flow.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def _entry(entry_id="np_1", areas=("SE3",), *, domain="nordpool"):
    return SimpleNamespace(
        entry_id=entry_id,
        domain=domain,
        data={"areas": list(areas), "currency": "SEK"},
    )


def _hass(entries=(), unique_ids=()):
    return SimpleNamespace(config_entries=_Entries(entries, unique_ids))


def _complete_input(*, entry_id="np_1", area="SE3", **overrides):
    data = {
        "solar_power": "sensor.solar",
        "grid_power": "sensor.grid",
        "battery_power": "sensor.battery",
        "nordpool_config_entry": entry_id,
        "nordpool_area": area,
        "price_period_minutes": "15",
        "price_selection_mode": "consecutive",
        "consumers": [],
        "very_cheap_limit": 1.00,
        "cheap_limit": 1.40,
        "normal_limit": 1.80,
        "expensive_limit": 2.20,
        "investment": 0,
        "solar_investment": 0,
        "battery_investment": 0,
        "advanced_mode": False,
        "co2_factor": 0.4,
        "currency": "SEK",
    }
    data.update(overrides)
    return data


async def _start_before_economy(flow, data):
    await flow.async_step_user()
    await flow.async_step_energy_system(
        {
            "solar_power": data["solar_power"],
            "grid_power": data["grid_power"],
            "battery_power": data["battery_power"],
        }
    )
    await flow.async_step_nordpool_entry(
        {"nordpool_config_entry": data["nordpool_config_entry"]}
    )
    await flow.async_step_nordpool_area({"nordpool_area": data["nordpool_area"]})
    await flow.async_step_prices(
        {
            "price_period_minutes": str(data["price_period_minutes"]),
            "price_selection_mode": data["price_selection_mode"],
            "currency": data["currency"],
        }
    )
    return await flow.async_step_features({"_configure_consumers": False})


async def _complete_wizard(flow, data, *, configure_consumers=None):
    await flow.async_step_user()
    await flow.async_step_energy_system(
        {
            "solar_power": data["solar_power"],
            "grid_power": data["grid_power"],
            "battery_power": data["battery_power"],
        }
    )
    await flow.async_step_nordpool_entry(
        {"nordpool_config_entry": data["nordpool_config_entry"]}
    )
    await flow.async_step_nordpool_area({"nordpool_area": data["nordpool_area"]})
    await flow.async_step_prices(
        {
            "price_period_minutes": str(data["price_period_minutes"]),
            "price_selection_mode": data["price_selection_mode"],
            "currency": data["currency"],
        }
    )
    if configure_consumers is None:
        configure_consumers = bool(data["consumers"])
    next_form = await flow.async_step_features(
        {"_configure_consumers": configure_consumers}
    )
    if configure_consumers:
        next_form = await flow.async_step_consumers(
            {"consumers": data["consumers"]}
        )
    economy_fields = (
        "very_cheap_limit",
        "cheap_limit",
        "normal_limit",
        "expensive_limit",
        "investment",
        "solar_investment",
        "battery_investment",
        "co2_factor",
    )
    next_form = await flow.async_step_economy(
        {key: data[key] for key in economy_fields}
    )
    return await flow.async_step_advanced(
        {"advanced_mode": data["advanced_mode"]}
    )


def _schema_default(schema, key):
    marker = next(marker for marker in schema.schema if getattr(marker, "schema", None) == key)
    return marker.default() if callable(marker.default) else marker.default


def test_first_sbe_entry_is_created_with_fixed_unique_id(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([_entry()])

    result = asyncio.run(_complete_wizard(flow, _complete_input()))

    assert flow.unique_id == "solar_battery_economy"
    assert result["type"] == "create_entry"
    assert result["data"]["price_period_minutes"] == 15


def test_second_sbe_entry_aborts_on_existing_unique_id(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([_entry()], {"solar_battery_economy"})

    with pytest.raises(_AbortFlow, match="already_configured"):
        asyncio.run(_complete_wizard(flow, _complete_input()))

    assert flow.unique_id == "solar_battery_economy"


@pytest.mark.parametrize(
    "overrides",
    [
        {"grid_power": "sensor.solar"},
        {"battery_power": "sensor.solar"},
        {"battery_power": "sensor.grid"},
    ],
)
def test_duplicate_power_entities_are_rejected(monkeypatch, overrides):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([_entry()])

    async def submit_energy():
        await flow.async_step_user()
        return await flow.async_step_energy_system(
            {
                "solar_power": "sensor.solar",
                "grid_power": overrides.get("grid_power", "sensor.grid"),
                "battery_power": overrides.get("battery_power", "sensor.battery"),
            }
        )

    result = asyncio.run(submit_energy())

    assert result["type"] == "form"
    assert result["errors"]["base"] == "duplicate_power_sensors"


def test_distinct_power_entities_are_accepted(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([_entry()])

    async def submit_energy():
        await flow.async_step_user()
        return await flow.async_step_energy_system(
            {
                "solar_power": "sensor.solar",
                "grid_power": "sensor.grid",
                "battery_power": "sensor.battery",
            }
        )

    result = asyncio.run(submit_energy())

    assert result["type"] == "form"
    assert result["step_id"] == "nordpool_entry"


@pytest.mark.parametrize(
    "thresholds,valid",
    [
        ((1.00, 1.40, 1.80, 2.20), True),
        ((1.00, 1.00, 1.80, 2.20), False),
        ((1.00, 1.40, 1.40, 2.20), False),
        ((1.00, 1.40, 1.80, 1.80), False),
        ((2.20, 1.80, 1.40, 1.00), False),
    ],
)
def test_price_threshold_order_is_enforced(monkeypatch, thresholds, valid):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([_entry()])
    values = dict(zip(
        ("very_cheap_limit", "cheap_limit", "normal_limit", "expensive_limit"),
        thresholds,
    ))

    async def submit_economy():
        data = _complete_input(**values)
        await _start_before_economy(flow, data)
        return await flow.async_step_economy(
            {
                "very_cheap_limit": data["very_cheap_limit"],
                "cheap_limit": data["cheap_limit"],
                "normal_limit": data["normal_limit"],
                "expensive_limit": data["expensive_limit"],
                "investment": data["investment"],
                "solar_investment": data["solar_investment"],
                "battery_investment": data["battery_investment"],
                "co2_factor": data["co2_factor"],
            }
        )

    result = asyncio.run(submit_economy())

    assert (result["step_id"] == "advanced") is valid
    if not valid:
        assert result["errors"]["base"] == "invalid_price_thresholds"
        preserved = result["data_schema"]({})
        assert preserved["very_cheap_limit"] == thresholds[0]
        assert preserved["cheap_limit"] == thresholds[1]


def test_schema_defaults_and_allowed_price_values(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    schema = flow_module._build_schema(hass=_hass([_entry()]))
    defaults = schema({})

    assert defaults["price_period_minutes"] == "15"
    assert defaults["price_selection_mode"] == "consecutive"
    assert defaults["consumers"] == []
    assert defaults["investment"] == 0
    assert defaults["solar_investment"] == 0
    assert defaults["battery_investment"] == 0
    assert defaults["advanced_mode"] is False
    assert defaults["co2_factor"] == 0.4
    assert defaults["currency"] == "SEK"
    period_selector = next(
        value for marker, value in schema.schema.items()
        if getattr(marker, "schema", None) == "price_period_minutes"
    )
    assert [
        item["value"] for item in period_selector.config["select"]["options"]
    ] == ["15", "30", "60", "120", "240"]


def test_wizard_price_step_keeps_period_mode_and_currency_defaults(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([_entry()])

    async def get_price_form():
        await flow.async_step_user()
        return await flow.async_step_prices()

    form = asyncio.run(get_price_form())
    defaults = form["data_schema"]({})
    assert form["step_id"] == "prices"
    assert defaults["price_period_minutes"] == "15"
    assert defaults["price_selection_mode"] == "consecutive"
    assert defaults["currency"] == "SEK"
    price_mode_validator = next(
        value for marker, value in form["data_schema"].schema.items()
        if getattr(marker, "schema", None) == "price_selection_mode"
    )
    assert [option["value"] for option in price_mode_validator.config["select"]["options"]] == [
        "consecutive", "cheapest_quarters"
    ]


@pytest.mark.parametrize("mode", ["consecutive", "cheapest_quarters"])
def test_price_selection_modes_are_saved(monkeypatch, mode):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([_entry()])

    result = asyncio.run(_complete_wizard(
        flow, _complete_input(price_selection_mode=mode)
    ))

    assert result["data"]["price_selection_mode"] == mode


def test_saved_price_period_and_economy_currency_values_are_preserved(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    saved = _complete_input(
        price_period_minutes=60,
        investment=12000,
        solar_investment=8000,
        battery_investment=4000,
        currency="EUR",
    )
    schema = flow_module._build_schema(saved, hass=_hass([_entry()]))
    defaults = schema({})

    assert defaults["price_period_minutes"] == "60"
    assert defaults["investment"] == 12000
    assert defaults["solar_investment"] == 8000
    assert defaults["battery_investment"] == 4000
    assert defaults["currency"] == "EUR"


def test_consumers_are_saved_as_a_list_of_entity_ids(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([_entry()])
    consumers = ["sensor.ev_energy", "sensor.heat_pump_energy"]

    result = asyncio.run(_complete_wizard(
        flow, _complete_input(consumers=consumers), configure_consumers=True
    ))
    schema = flow_module._build_schema(hass=_hass([_entry()]))
    consumers_selector = next(
        value for marker, value in schema.schema.items()
        if getattr(marker, "schema", None) == "consumers"
    )

    assert result["data"]["consumers"] == consumers
    assert all(isinstance(entity_id, str) for entity_id in result["data"]["consumers"])
    assert consumers_selector.config["entity"]["device_class"] == "energy"
    assert consumers_selector.config["entity"]["multiple"] is True


def test_enabling_consumers_routes_to_separate_consumers_step(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([_entry()])

    async def enable_consumers():
        data = _complete_input()
        await flow.async_step_user()
        await flow.async_step_energy_system({
            "solar_power": data["solar_power"],
            "grid_power": data["grid_power"],
            "battery_power": data["battery_power"],
        })
        await flow.async_step_nordpool_entry({"nordpool_config_entry": "np_1"})
        await flow.async_step_nordpool_area({"nordpool_area": "SE3"})
        await flow.async_step_prices({
            "price_period_minutes": "15",
            "price_selection_mode": "consecutive",
            "currency": "SEK",
        })
        return await flow.async_step_features({"_configure_consumers": True})

    form = asyncio.run(enable_consumers())
    assert form["step_id"] == "consumers"


def test_empty_consumer_list_is_preserved(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([_entry()])

    result = asyncio.run(_complete_wizard(
        flow, _complete_input(consumers=[]), configure_consumers=True
    ))

    assert result["data"]["consumers"] == []


def test_consumers_disabled_skips_step_and_saves_empty_list(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([_entry()])
    data = _complete_input(consumers=["sensor.ev_energy"])

    result = asyncio.run(_complete_wizard(
        flow, data, configure_consumers=False
    ))

    assert result["data"]["consumers"] == []


def test_setup_starts_with_energy_system_and_preserves_values_on_duplicate_error(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([_entry()])

    form = asyncio.run(flow.async_step_user())
    energy_selector = next(
        value for marker, value in form["data_schema"].schema.items()
        if getattr(marker, "schema", None) == "solar_power"
    )
    assert form["step_id"] == "energy_system"
    assert energy_selector.config == {"entity": {"domain": "sensor"}}

    async def submit_invalid():
        return await flow.async_step_energy_system(
            {
                "solar_power": "sensor.same",
                "grid_power": "sensor.same",
                "battery_power": "sensor.battery",
            }
        )

    invalid = asyncio.run(submit_invalid())
    defaults = invalid["data_schema"]({})
    assert invalid["errors"]["base"] == "duplicate_power_sensors"
    assert defaults["solar_power"] == "sensor.same"
    assert defaults["grid_power"] == "sensor.same"


def test_nordpool_wizard_preselects_one_and_requires_choice_when_multiple(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)

    one_entry_flow = flow_module.SolarBatteryEconomyConfigFlow()
    one_entry_flow.hass = _hass([_entry("only", ("SE3",))])
    asyncio.run(one_entry_flow.async_step_user())
    entry_form = asyncio.run(one_entry_flow.async_step_nordpool_entry())
    assert entry_form["step_id"] == "nordpool_entry"
    assert _schema_default(entry_form["data_schema"], "nordpool_config_entry") == "only"

    multiple_flow = flow_module.SolarBatteryEconomyConfigFlow()
    multiple_flow.hass = _hass([
        _entry("one", ("SE3",)),
        _entry("two", ("FI",)),
    ])
    asyncio.run(multiple_flow.async_step_user())
    multiple_form = asyncio.run(multiple_flow.async_step_nordpool_entry())
    assert _schema_default(multiple_form["data_schema"], "nordpool_config_entry") is None

    area_form = asyncio.run(multiple_flow.async_step_nordpool_entry(
        {"nordpool_config_entry": "two"}
    ))
    assert area_form["step_id"] == "nordpool_area"
    area_selector = next(
        value for marker, value in area_form["data_schema"].schema.items()
        if getattr(marker, "schema", None) == "nordpool_area"
    )
    assert area_selector.config["select"]["options"] == ["FI"]
    assert _schema_default(area_form["data_schema"], "nordpool_area") == "FI"
    assert multiple_flow._flow_data["nordpool_config_entry"] == "two"


def test_nordpool_area_multiple_options_are_scoped_to_selected_entry(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([
        _entry("one", ("SE3", "SE4")),
        _entry("two", ("FI",)),
    ])

    async def get_area_form():
        await flow.async_step_user()
        await flow.async_step_nordpool_entry({"nordpool_config_entry": "one"})
        return await flow.async_step_nordpool_area()

    form = asyncio.run(get_area_form())
    area_selector = next(
        value for marker, value in form["data_schema"].schema.items()
        if getattr(marker, "schema", None) == "nordpool_area"
    )
    assert area_selector.config["select"]["options"] == ["SE3", "SE4"]
    assert _schema_default(form["data_schema"], "nordpool_area") is None


def test_area_selection_and_final_mapping_are_flat_and_complete(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([
        _entry("one", ("SE3", "SE4")),
        _entry("two", ("FI",)),
    ])
    data = _complete_input(entry_id="one", area="SE4", consumers=[])

    result = asyncio.run(_complete_wizard(flow, data, configure_consumers=False))

    assert result["type"] == "create_entry"
    expected = {**data, "price_period_minutes": 15}
    assert result["data"] == expected
    assert result["data"]["nordpool_config_entry"] == "one"
    assert result["data"]["nordpool_area"] == "SE4"
    assert all(not isinstance(value, dict) for value in result["data"].values())
    assert "_configure_consumers" not in result["data"]
    assert set(result["data"]) == {
        "solar_power", "grid_power", "battery_power",
        "nordpool_config_entry", "nordpool_area",
        "price_period_minutes", "price_selection_mode", "currency", "consumers",
        "very_cheap_limit", "cheap_limit", "normal_limit", "expensive_limit",
        "investment", "solar_investment", "battery_investment", "co2_factor",
        "advanced_mode",
    }


def test_prices_economy_and_advanced_defaults_and_values_survive_wizard(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([_entry()])
    data = _complete_input(
        price_period_minutes=120,
        price_selection_mode="cheapest_quarters",
        investment=15000,
        solar_investment=9000,
        battery_investment=6000,
        currency="EUR",
        advanced_mode=True,
        co2_factor=0.7,
    )

    result = asyncio.run(_complete_wizard(flow, data, configure_consumers=False))

    assert result["data"]["price_period_minutes"] == 120
    assert result["data"]["price_selection_mode"] == "cheapest_quarters"
    assert result["data"]["currency"] == "EUR"
    assert result["data"]["investment"] == 15000
    assert result["data"]["solar_investment"] == 9000
    assert result["data"]["battery_investment"] == 6000
    assert result["data"]["co2_factor"] == 0.7
    assert result["data"]["advanced_mode"] is True


def test_no_nordpool_entries_keep_form_and_reject_missing_entry(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass()

    async def submit_without_entry():
        await flow.async_step_user()
        await flow.async_step_energy_system(
            {
                "solar_power": "sensor.solar",
                "grid_power": "sensor.grid",
                "battery_power": "sensor.battery",
            }
        )
        return await flow.async_step_nordpool_entry(
            {"nordpool_config_entry": None}
        )

    result = asyncio.run(submit_without_entry())
    assert result["step_id"] == "nordpool_entry"
    assert result["errors"]["base"] == "invalid_nordpool_entry"


@pytest.mark.parametrize(
    "entries,defaults,expected_entry,expected_area,area_options",
    [
        ([], {}, None, None, []),
        ([_entry("only", ("SE3",))], {}, "only", "SE3", ["SE3"]),
        (
            [_entry("one", ("SE3",)), _entry("two", ("FI",))],
            {},
            None,
            None,
            ["FI", "SE3"],
        ),
        (
            [_entry("one", ("SE3", "SE4"))],
            {},
            "one",
            None,
            ["SE3", "SE4"],
        ),
        (
            [_entry("one", ("SE3",)), _entry("two", ("FI",))],
            {"nordpool_config_entry": "two", "nordpool_area": "FI"},
            "two",
            "FI",
            ["FI", "SE3"],
        ),
        (
            [_entry("one", ("SE3", "SE4")), _entry("two", ("FI",))],
            {"nordpool_config_entry": "one", "nordpool_area": "SE4"},
            "one",
            "SE4",
            ["FI", "SE3", "SE4"],
        ),
    ],
)
def test_nordpool_schema_defaults_and_area_choices(
    monkeypatch, entries, defaults, expected_entry, expected_area, area_options
):
    flow_module = _load_config_flow(monkeypatch)
    schema = flow_module._build_schema(defaults, hass=_hass(entries))
    config = schema.schema
    actual_entry_default = _schema_default(schema, "nordpool_config_entry")
    actual_area_default = _schema_default(schema, "nordpool_area")
    area_selector = next(
        value for marker, value in config.items()
        if getattr(marker, "schema", None) == "nordpool_area"
    )

    assert actual_entry_default == expected_entry
    assert actual_area_default == expected_area
    assert area_selector.config["select"]["options"] == area_options


def test_nordpool_invalid_and_removed_entries_are_rejected(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    hass = _hass([_entry("current", ("SE3",))])

    assert flow_module._validate_nordpool_selection(
        hass, {"nordpool_config_entry": "removed", "nordpool_area": "SE3"}
    ) == "invalid_nordpool_entry"
    assert flow_module._validate_nordpool_selection(
        hass, {"nordpool_config_entry": "current", "nordpool_area": "FI"}
    ) == "invalid_nordpool_area"


def test_zero_nordpool_entries_show_empty_selector_and_cannot_create(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    schema = flow_module._build_schema(hass=_hass())
    area_selector = next(
        value for marker, value in schema.schema.items()
        if getattr(marker, "schema", None) == "nordpool_area"
    )
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass()

    async def submit_missing_entry():
        await flow.async_step_user()
        await flow.async_step_energy_system(
            {
                "solar_power": "sensor.solar",
                "grid_power": "sensor.grid",
                "battery_power": "sensor.battery",
            }
        )
        return await flow.async_step_nordpool_entry(
            {"nordpool_config_entry": None}
        )

    result = asyncio.run(submit_missing_entry())

    assert area_selector.config["select"]["options"] == []
    assert result["type"] == "form"
    assert result["step_id"] == "nordpool_entry"
    assert result["errors"]["base"] == "invalid_nordpool_entry"


def test_options_flow_reads_existing_data_and_saves_complete_mapping(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    existing = _complete_input(
        consumers=["sensor.ev_energy"], investment=1000, currency="EUR"
    )
    entry = SimpleNamespace(options={}, data=existing)
    flow = flow_module.SolarBatteryEconomyOptionsFlow(entry)
    flow.hass = _hass([_entry()])

    async def save_all_categories():
        form = await flow.async_step_init()
        assert form["step_id"] == "energy_system"
        assert form["data_schema"]({})["solar_power"] == "sensor.solar"
        form = await flow.async_step_energy_system({key: existing[key] for key in ("solar_power", "grid_power", "battery_power")})
        assert form["step_id"] == "nordpool_entry"
        assert form["data_schema"]({})["nordpool_config_entry"] == "np_1"
        form = await flow.async_step_nordpool_entry({"nordpool_config_entry": "np_1"})
        assert form["step_id"] == "nordpool_area"
        assert form["data_schema"]({})["nordpool_area"] == "SE3"
        form = await flow.async_step_nordpool_area({"nordpool_area": "SE3"})
        form = await flow.async_step_prices()
        assert form["data_schema"]({})["currency"] == "EUR"
        form = await flow.async_step_prices({key: existing[key] for key in ("price_period_minutes", "price_selection_mode", "currency")})
        assert form["step_id"] == "features"
        form = await flow.async_step_features({"_configure_consumers": True})
        assert form["data_schema"]({})["consumers"] == ["sensor.ev_energy"]
        form = await flow.async_step_consumers({"consumers": existing["consumers"]})
        assert form["step_id"] == "economy"
        assert form["data_schema"]({})["investment"] == 1000
        form = await flow.async_step_economy({key: existing[key] for key in ("very_cheap_limit", "cheap_limit", "normal_limit", "expensive_limit", "investment", "solar_investment", "battery_investment", "co2_factor")})
        assert form["step_id"] == "advanced"
        assert form["data_schema"]({})["advanced_mode"] is False
        return await flow.async_step_advanced({"advanced_mode": False})

    saved = asyncio.run(save_all_categories())

    assert saved["type"] == "create_entry"
    assert saved["data"] == {**existing, "price_period_minutes": 15}
    assert isinstance(saved["data"]["consumers"], list)
    assert entry.data == existing


def test_partial_options_are_merged_for_each_options_category(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    entry = SimpleNamespace(
        options={"price_period_minutes": 60},
        data=_complete_input(),
    )
    flow = flow_module.SolarBatteryEconomyOptionsFlow(entry)
    flow.hass = _hass([_entry()])

    async def forms():
        energy = await flow.async_step_init()
        assert energy["data_schema"]({})["solar_power"] == "sensor.solar"
        entry_form = await flow.async_step_energy_system({"solar_power": "sensor.solar", "grid_power": "sensor.grid", "battery_power": "sensor.battery"})
        assert entry_form["data_schema"]({})["nordpool_config_entry"] == "np_1"
        area_form = await flow.async_step_nordpool_entry({"nordpool_config_entry": "np_1"})
        assert area_form["data_schema"]({})["nordpool_area"] == "SE3"
        price_form = await flow.async_step_nordpool_area({"nordpool_area": "SE3"})
        assert price_form["step_id"] == "prices"
        prices = await flow.async_step_prices()
        assert prices["data_schema"]({})["price_period_minutes"] == "60"
        assert prices["data_schema"]({})["currency"] == "SEK"
        assert (await flow.async_step_features())["step_id"] == "features"
    asyncio.run(forms())


def test_options_category_edit_saves_complete_flat_mapping_without_mutating_data(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    data = _complete_input(consumers=["sensor.ev_energy"], currency="EUR", advanced_mode=False)
    entry = SimpleNamespace(data=data, options={"advanced_mode": True})
    flow = flow_module.SolarBatteryEconomyOptionsFlow(entry)
    flow.hass = _hass([_entry()])

    async def edit_only_advanced():
        await flow.async_step_init()
        await flow.async_step_energy_system({key: data[key] for key in ("solar_power", "grid_power", "battery_power")})
        await flow.async_step_nordpool_entry({"nordpool_config_entry": "np_1"})
        await flow.async_step_nordpool_area({"nordpool_area": "SE3"})
        await flow.async_step_prices({key: data[key] for key in ("price_period_minutes", "price_selection_mode", "currency")})
        await flow.async_step_features({"_configure_consumers": True})
        await flow.async_step_consumers({"consumers": data["consumers"]})
        await flow.async_step_economy({key: data[key] for key in ("very_cheap_limit", "cheap_limit", "normal_limit", "expensive_limit", "investment", "solar_investment", "battery_investment", "co2_factor")})
        return await flow.async_step_advanced({"advanced_mode": False})

    result = asyncio.run(edit_only_advanced())
    assert result["data"] == {**data, "advanced_mode": False, "price_period_minutes": 15}
    assert result["data"]["consumers"] == ["sensor.ev_energy"]
    assert result["data"]["currency"] == "EUR"
    assert entry.data == data
    assert all(not isinstance(value, dict) for value in result["data"].values())


def test_options_area_choices_follow_selected_nordpool_entry(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    data = _complete_input(entry_id="np_one", area="SE4")
    entries = [_entry("np_one", ("SE3", "SE4")), _entry("np_two", ("FI",))]
    flow = flow_module.SolarBatteryEconomyOptionsFlow(SimpleNamespace(data=data, options={}))
    flow.hass = _hass(entries)

    async def choose_other_entry():
        await flow.async_step_init()
        await flow.async_step_energy_system({key: data[key] for key in ("solar_power", "grid_power", "battery_power")})
        area = await flow.async_step_nordpool_entry({"nordpool_config_entry": "np_two"})
        return area

    form = asyncio.run(choose_other_entry())
    area_selector = next(value for marker, value in form["data_schema"].schema.items() if getattr(marker, "schema", None) == "nordpool_area")
    assert area_selector.config["select"]["options"] == ["FI"]
    assert form["data_schema"]({})["nordpool_area"] == "FI"


def test_options_flow_validates_duplicates_and_price_thresholds(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    data = _complete_input()
    flow = flow_module.SolarBatteryEconomyOptionsFlow(SimpleNamespace(data=data, options={}))
    flow.hass = _hass([_entry()])

    async def invalid_energy():
        await flow.async_step_init()
        return await flow.async_step_energy_system({"solar_power": "sensor.same", "grid_power": "sensor.same", "battery_power": "sensor.battery"})

    form = asyncio.run(invalid_energy())
    assert form["errors"]["base"] == "duplicate_power_sensors"

    flow = flow_module.SolarBatteryEconomyOptionsFlow(SimpleNamespace(data=data, options={}))
    flow.hass = _hass([_entry()])

    async def invalid_economy():
        await flow.async_step_init()
        await flow.async_step_energy_system({key: data[key] for key in ("solar_power", "grid_power", "battery_power")})
        await flow.async_step_nordpool_entry({"nordpool_config_entry": "np_1"})
        await flow.async_step_nordpool_area({"nordpool_area": "SE3"})
        await flow.async_step_prices({key: data[key] for key in ("price_period_minutes", "price_selection_mode", "currency")})
        await flow.async_step_features({"_configure_consumers": True})
        await flow.async_step_consumers({"consumers": data["consumers"]})
        return await flow.async_step_economy({"very_cheap_limit": 2, "cheap_limit": 1, "normal_limit": 3, "expensive_limit": 4})

    assert asyncio.run(invalid_economy())["errors"]["base"] == "invalid_price_thresholds"


def test_current_coordinator_and_sensor_config_read_semantics():
    coordinator_source = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
    sensor_source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")

    assert "conf = get_effective_config(entry)" in coordinator_source
    assert 'self.currency = conf.get("currency", "SEK")' in coordinator_source
    assert 'advanced_mode = get_effective_config(entry).get("advanced_mode", False)' in sensor_source
    assert '"consumers": []' not in coordinator_source
    assert 'configured_consumers = conf.get(CONF_CONSUMERS, [])' in coordinator_source


@pytest.mark.parametrize(
    "data,options,expected",
    [
        (
            _complete_input(consumers=["sensor.ev_energy"]),
            {},
            _complete_input(consumers=["sensor.ev_energy"]),
        ),
        (
            _complete_input(consumers=["sensor.ev_energy"]),
            {"advanced_mode": True},
            {**_complete_input(consumers=["sensor.ev_energy"]), "advanced_mode": True},
        ),
        (
            {**_complete_input(), "currency": "SEK"},
            {"currency": "EUR"},
            {**_complete_input(), "currency": "EUR"},
        ),
        (
            {**_complete_input(), "advanced_mode": False, "currency": "SEK"},
            {"advanced_mode": True, "currency": "EUR", "investment": 2500},
            {
                **_complete_input(),
                "advanced_mode": True,
                "currency": "EUR",
                "investment": 2500,
            },
        ),
        ({}, {}, {}),
        ({}, {"advanced_mode": True}, {"advanced_mode": True}),
        ({"currency": "NOK"}, {}, {"currency": "NOK"}),
    ],
)
def test_effective_config_merges_entry_data_and_options(monkeypatch, data, options, expected):
    _load_config_flow(monkeypatch)
    const_module = sys.modules["custom_components.solar_battery_economy.const"]
    entry = SimpleNamespace(data=data, options=options)

    assert const_module.get_effective_config(entry) == expected


def test_effective_config_does_not_mutate_entry_mappings(monkeypatch):
    _load_config_flow(monkeypatch)
    const_module = sys.modules["custom_components.solar_battery_economy.const"]
    data = {"investment": 1000}
    options = {"investment": 2000}
    entry = SimpleNamespace(data=data, options=options)

    effective = const_module.get_effective_config(entry)

    assert effective == {"investment": 2000}
    assert data == {"investment": 1000}
    assert options == {"investment": 2000}


def test_advanced_and_co2_defaults_and_values_are_stored(monkeypatch):
    flow_module = _load_config_flow(monkeypatch)
    schema = flow_module._build_schema(hass=_hass([_entry()]))
    defaults = schema({})
    flow = flow_module.SolarBatteryEconomyConfigFlow()
    flow.hass = _hass([_entry()])

    assert defaults["advanced_mode"] is False
    assert defaults["co2_factor"] == 0.4
    result = asyncio.run(_complete_wizard(
        flow,
        _complete_input(advanced_mode=True, co2_factor=0.75),
        configure_consumers=False,
    ))
    assert result["data"]["advanced_mode"] is True
    assert result["data"]["co2_factor"] == 0.75


def test_economy_is_not_a_runtime_enable_disable_feature():
    sensor_source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    coordinator_source = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")

    assert "economy_enabled" not in sensor_source
    assert "economy_enabled" not in coordinator_source
    assert "sensors.append(PaybackSensor" in sensor_source
    assert "sensors.append(ROISensor" in sensor_source


def test_legacy_entry_data_and_consumer_list_need_no_config_migration():
    init_source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    flow_source = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    coordinator_source = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")

    assert "async_migrate_entry" not in init_source
    assert "VERSION = 1" in flow_source
    assert "get_effective_config(self.entry)" in flow_source
    assert "configured_consumers = conf.get(CONF_CONSUMERS, [])" in coordinator_source
    assert "self.consumer_entities = list(configured_consumers or [])" in coordinator_source
