from pathlib import Path


def _sensor_source() -> str:
    """Return the source code for sensor.py."""
    path = (
        Path(__file__).resolve().parents[1]
        / "custom_components"
        / "solar_battery_economy"
        / "sensor.py"
    )
    return path.read_text(encoding="utf-8")


def test_cheapest_future_period_sensor_exists():
    source = _sensor_source()

    assert "class CheapestFuturePeriodSensor(EconomySensor):" in source


def test_cheapest_future_period_sensor_is_created():
    source = _sensor_source()

    assert (
        "sensors.append(CheapestFuturePeriodSensor(coordinator, hass, entry))"
        in source
    )


def test_cheapest_future_period_sensor_has_correct_identity():
    source = _sensor_source()

    assert '"13 Cheapest Future Period"' in source
    assert '"cheapest_future_period"' in source
    assert 'sensor_type="price_intelligence"' in source


def test_cheapest_future_period_sensor_is_diagnostic():
    source = _sensor_source()

    assert '_attr_entity_category = EntityCategory.DIAGNOSTIC' in source


def test_cheapest_future_period_sensor_has_expected_icon():
    source = _sensor_source()

    assert '_attr_icon = "mdi:clock-outline"' in source


def test_cheapest_future_period_sensor_reads_price_intelligence():
    source = _sensor_source()

    assert (
        'intelligence = self.coordinator.data.get("price_intelligence", {})'
        in source
    )
    assert (
        'period = intelligence.get("cheapest_future_period")'
        in source
    )


def test_cheapest_future_period_sensor_handles_missing_period():
    source = _sensor_source()

    assert "if not period:" in source
    assert "self._value = None" in source
    assert "self._attr_extra_state_attributes = {}" in source


def test_cheapest_future_period_sensor_formats_local_time_range():
    source = _sensor_source()

    assert "start_local = dt_util.as_local(start)" in source
    assert "end_local = dt_util.as_local(end)" in source
    assert "strftime('%H:%M')" in source
    assert 'f"–{end_local.strftime(\'%H:%M\')}"' in source


def test_cheapest_future_period_sensor_exposes_expected_attributes():
    source = _sensor_source()

    expected_attributes = [
        '"duration_minutes"',
        '"selection_mode"',
        '"start"',
        '"end"',
        '"average_import_price"',
        '"intervals"',
    ]

    for attribute in expected_attributes:
        assert attribute in source


def test_cheapest_future_period_sensor_exposes_iso_timestamps():
    source = _sensor_source()

    assert "start.isoformat()" in source
    assert "end.isoformat()" in source