import importlib.util
from datetime import datetime, timezone
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "dashboard_data.py"
)

# Load dashboard_data with its package dependencies available through a tiny
# synthetic package so the test remains independent of Home Assistant runtime.
import sys
import types

package = types.ModuleType("custom_components.solar_battery_economy")
package.__path__ = [str(MODULE_PATH.parent)]
sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
sys.modules[package.__name__] = package

spec = importlib.util.spec_from_file_location(
    "custom_components.solar_battery_economy.dashboard_data", MODULE_PATH
)
if spec is None or spec.loader is None:
    raise ImportError("Could not load dashboard_data module")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_extract_spot_price_history_accepts_iso_attribute_timestamps():
    recorded = datetime(2026, 9, 19, 10, 2, tzinfo=timezone.utc)
    history = [
        {
            "timestamp": recorded,
            "state": "0.83",
            "attributes": {
                "all_prices": [
                    {
                        "start": "2026-09-19T10:00:00+00:00",
                        "end": "2026-09-19T10:15:00+00:00",
                        "spot": 0.54,
                    }
                ]
            },
        }
    ]

    result = module.extract_spot_price_history(history)

    assert len(result) == 1
    assert result[0]["spot"] == 0.54
    assert result[0]["start"] == datetime(2026, 9, 19, 10, tzinfo=timezone.utc)


def test_extract_spot_price_history_keeps_latest_snapshot_per_interval():
    first = datetime(2026, 9, 19, 10, 1, tzinfo=timezone.utc)
    second = datetime(2026, 9, 19, 10, 14, tzinfo=timezone.utc)
    interval = {
        "start": "2026-09-19T10:00:00+00:00",
        "end": "2026-09-19T10:15:00+00:00",
        "spot": 0.54,
    }
    later_interval = {**interval, "spot": 0.55}

    result = module.extract_spot_price_history(
        [
            {"timestamp": first, "attributes": {"all_prices": [interval]}},
            {"timestamp": second, "attributes": {"all_prices": [later_interval]}},
        ]
    )

    assert len(result) == 1
    assert result[0]["spot"] == 0.55


def test_build_energy_samples_from_statistics_ignores_invalid_change():
    start = datetime(2026, 9, 19, 10, tzinfo=timezone.utc)
    end = datetime(2026, 9, 19, 10, 5, tzinfo=timezone.utc)

    result = module.build_energy_samples_from_statistics(
        [
            {"start": start, "end": end, "change": 0.25},
            {"start": start, "end": end, "change": -1},
            {"start": start, "end": end, "change": "bad"},
        ]
    )

    assert result == [
        {"start": start, "end": end, "energy_kwh": 0.25},
    ]
