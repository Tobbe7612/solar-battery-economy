from pathlib import Path


COORDINATOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "coordinator.py"
)


def _coordinator_source() -> str:
    return COORDINATOR_PATH.read_text(encoding="utf-8")


def test_coordinator_uses_single_price_source_entity():
    source = _coordinator_source()

    assert 'self.price_source_entity = conf["price_source"]' in source

    # The old two-sensor configuration must no longer exist.
    assert "self.import_price_entity" not in source
    assert "self.export_price_entity" not in source


def test_coordinator_reads_normalized_price_source():
    source = _coordinator_source()

    assert "normalize_price_source(" in source
    assert "price_state = self.hass.states.get(self.price_source_entity)" in source
    assert 'self.data["price"] = price_model' in source


def test_coordinator_uses_normalized_import_and_export_prices():
    source = _coordinator_source()

    assert 'import_price_raw = current_price["import"]' in source
    assert 'export_price_raw = current_price["export"]' in source


def test_coordinator_handles_missing_price_source_without_free_money():
    source = _coordinator_source()

    # Missing price source must result in unavailable prices.
    assert 'price_model = {"current": None, "forecast": []}' in source
    assert "import_price_raw = None" in source
    assert "export_price_raw = None" in source

    # Money accumulation must be skipped when either price is unavailable.
    assert "if import_price_raw is None or export_price_raw is None:" in source
    assert "skip money booking" in source


def test_coordinator_keeps_energy_accumulation_independent_of_price():
    source = _coordinator_source()

    energy_marker = "Energy always accumulates, regardless of price availability"
    price_guard = "if import_price_raw is None or export_price_raw is None:"

    energy_position = source.index(energy_marker)
    price_guard_position = source.index(price_guard)

    # Energy accumulation must occur before the price-availability guard.
    assert energy_position < price_guard_position


def test_coordinator_stores_normalized_price_model():
    source = _coordinator_source()

    price_model_position = source.index("price_model = normalize_price_source(")
    data_price_position = source.index('self.data["price"] = price_model')

    assert price_model_position < data_price_position