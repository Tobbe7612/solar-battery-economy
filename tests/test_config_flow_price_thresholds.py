from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_DIR = PROJECT_ROOT / "custom_components" / "solar_battery_economy"

CONST_SOURCE = (INTEGRATION_DIR / "const.py").read_text(encoding="utf-8")
CONFIG_FLOW_SOURCE = (INTEGRATION_DIR / "config_flow.py").read_text(
    encoding="utf-8"
)


def test_default_price_thresholds_are_correct():
    """Default price classification thresholds match the agreed values."""
    assert "DEFAULT_VERY_CHEAP_LIMIT: Final = 1.00" in CONST_SOURCE
    assert "DEFAULT_CHEAP_LIMIT: Final = 1.40" in CONST_SOURCE
    assert "DEFAULT_NORMAL_LIMIT: Final = 1.80" in CONST_SOURCE
    assert "DEFAULT_EXPENSIVE_LIMIT: Final = 2.20" in CONST_SOURCE


def test_price_threshold_config_keys_are_correct():
    """Price threshold configuration keys use the canonical names."""
    assert 'CONF_VERY_CHEAP_LIMIT: Final = "very_cheap_limit"' in CONST_SOURCE
    assert 'CONF_CHEAP_LIMIT: Final = "cheap_limit"' in CONST_SOURCE
    assert 'CONF_NORMAL_LIMIT: Final = "normal_limit"' in CONST_SOURCE
    assert 'CONF_EXPENSIVE_LIMIT: Final = "expensive_limit"' in CONST_SOURCE


def test_default_thresholds_are_in_strictly_increasing_order():
    """Default thresholds must form a valid classification range."""
    very_cheap = _extract_float("DEFAULT_VERY_CHEAP_LIMIT")
    cheap = _extract_float("DEFAULT_CHEAP_LIMIT")
    normal = _extract_float("DEFAULT_NORMAL_LIMIT")
    expensive = _extract_float("DEFAULT_EXPENSIVE_LIMIT")

    assert very_cheap < cheap
    assert cheap < normal
    assert normal < expensive


def test_config_flow_contains_all_price_threshold_fields():
    """Config flow exposes all four configurable price thresholds."""
    assert "CONF_VERY_CHEAP_LIMIT" in CONFIG_FLOW_SOURCE
    assert "CONF_CHEAP_LIMIT" in CONFIG_FLOW_SOURCE
    assert "CONF_NORMAL_LIMIT" in CONFIG_FLOW_SOURCE
    assert "CONF_EXPENSIVE_LIMIT" in CONFIG_FLOW_SOURCE


def test_config_flow_uses_correct_default_thresholds():
    """Config flow uses the canonical defaults for all thresholds."""
    assert "DEFAULT_VERY_CHEAP_LIMIT" in CONFIG_FLOW_SOURCE
    assert "DEFAULT_CHEAP_LIMIT" in CONFIG_FLOW_SOURCE
    assert "DEFAULT_NORMAL_LIMIT" in CONFIG_FLOW_SOURCE
    assert "DEFAULT_EXPENSIVE_LIMIT" in CONFIG_FLOW_SOURCE


def _extract_float(const_name: str) -> float:
    """Extract a numeric constant value directly from const.py."""
    prefix = f"{const_name}: Final = "

    for line in CONST_SOURCE.splitlines():
        stripped = line.strip()

        if stripped.startswith(prefix):
            return float(stripped[len(prefix) :])

    raise AssertionError(f"{const_name} was not found in const.py")