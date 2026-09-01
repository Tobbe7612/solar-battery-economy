import importlib.util
from pathlib import Path

import pytest


# Load price_source.py directly so these pure-domain tests do not require
# the Home Assistant package to be installed in the local test environment.
PRICE_SOURCE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "price_source.py"
)

_spec = importlib.util.spec_from_file_location(
    "solar_battery_economy_price_source",
    PRICE_SOURCE_PATH,
)
price_source = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(price_source)


CHEAP = price_source.CHEAP
DEFAULT_CHEAP_LIMIT = price_source.DEFAULT_CHEAP_LIMIT
DEFAULT_EXPENSIVE_LIMIT = price_source.DEFAULT_EXPENSIVE_LIMIT
DEFAULT_NORMAL_LIMIT = price_source.DEFAULT_NORMAL_LIMIT
DEFAULT_VERY_CHEAP_LIMIT = price_source.DEFAULT_VERY_CHEAP_LIMIT
EXPENSIVE = price_source.EXPENSIVE
NORMAL = price_source.NORMAL
VERY_CHEAP = price_source.VERY_CHEAP
VERY_EXPENSIVE = price_source.VERY_EXPENSIVE
classify_price = price_source.classify_price


def test_default_thresholds_are_correct():
    assert DEFAULT_VERY_CHEAP_LIMIT == 1.00
    assert DEFAULT_CHEAP_LIMIT == 1.40
    assert DEFAULT_NORMAL_LIMIT == 1.80
    assert DEFAULT_EXPENSIVE_LIMIT == 2.20


def test_price_below_one_is_very_cheap():
    assert classify_price(0.99) == VERY_CHEAP


def test_price_at_one_is_cheap():
    assert classify_price(1.00) == CHEAP


def test_price_between_one_and_one_four_is_cheap():
    assert classify_price(1.39) == CHEAP


def test_price_at_one_four_is_normal():
    assert classify_price(1.40) == NORMAL


def test_price_between_one_four_and_one_eighty_is_normal():
    assert classify_price(1.79) == NORMAL


def test_price_at_one_eighty_is_expensive():
    assert classify_price(1.80) == EXPENSIVE


def test_price_at_two_twenty_is_expensive():
    assert classify_price(2.20) == EXPENSIVE


def test_price_above_two_twenty_is_very_expensive():
    assert classify_price(2.21) == VERY_EXPENSIVE


def test_custom_thresholds_are_supported():
    assert (
        classify_price(
            1.25,
            very_cheap_limit=0.80,
            cheap_limit=1.20,
            normal_limit=1.60,
            expensive_limit=2.00,
        )
        == NORMAL
    )


@pytest.mark.parametrize(
    ("kwargs", "expected_message"),
    [
        (
            {
                "very_cheap_limit": 1.40,
                "cheap_limit": 1.40,
            },
            "very_cheap_limit must be below cheap_limit",
        ),
        (
            {
                "cheap_limit": 1.80,
                "normal_limit": 1.80,
            },
            "cheap_limit must be below normal_limit",
        ),
        (
            {
                "normal_limit": 2.20,
                "expensive_limit": 2.20,
            },
            "normal_limit must be below expensive_limit",
        ),
    ],
)
def test_invalid_threshold_order_is_rejected(kwargs, expected_message):
    with pytest.raises(ValueError, match=expected_message):
        classify_price(1.50, **kwargs)