from pathlib import Path


SOURCE = Path(
    "custom_components/solar_battery_economy/config_flow.py"
).read_text(encoding="utf-8")


def test_consumer_config_key_exists():
    assert 'CONF_CONSUMERS' in SOURCE


def test_consumers_use_energy_entity_selector():
    assert '"device_class": "energy"' in SOURCE
    assert '"multiple": True' in SOURCE
