"""Static checks for Home Assistant Config/Options Flow translations."""

from __future__ import annotations

import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "solar_battery_economy"
TRANSLATIONS = INTEGRATION / "translations" / "sv.json"


def _flow_step_ids(class_name: str) -> set[str]:
    tree = ast.parse((INTEGRATION / "config_flow.py").read_text(encoding="utf-8"))
    flow_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    step_ids = set()
    for node in ast.walk(flow_class):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "async_show_form":
            continue
        step = next((kw.value for kw in node.keywords if kw.arg == "step_id"), None)
        if isinstance(step, ast.Constant) and isinstance(step.value, str):
            step_ids.add(step.value)
    return step_ids


def test_swedish_translation_file_is_valid_and_covers_flow_steps():
    translations = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))

    assert _flow_step_ids("SolarBatteryEconomyConfigFlow") <= set(
        translations["config"]["step"]
    )
    assert _flow_step_ids("SolarBatteryEconomyOptionsFlow") <= set(
        translations["options"]["step"]
    )

    expected_titles = {
        "energy_system": "Energisystem",
        "nordpool_entry": "Nord Pool-entry",
        "nordpool_area": "Nord Pool-område",
        "prices": "Priser",
        "features": "Funktioner",
        "consumers": "Förbrukare",
        "economy": "Ekonomi",
        "advanced": "Avancerat",
    }
    for flow in ("config", "options"):
        for step_id, title in expected_titles.items():
            assert translations[flow]["step"][step_id]["title"] == title


def test_swedish_translation_file_covers_flow_fields_and_errors():
    translations = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    required_fields = {
        "solar_power",
        "grid_power",
        "battery_power",
        "nordpool_config_entry",
        "nordpool_area",
        "price_period_minutes",
        "price_selection_mode",
        "currency",
        "consumers",
        "advanced_mode",
        "co2_factor",
        "investment",
        "solar_investment",
        "battery_investment",
    }
    for flow in ("config", "options"):
        fields = {
            key
            for step in translations[flow]["step"].values()
            for key in step.get("data", {})
        }
        assert required_fields <= fields
        assert {
            "duplicate_power_sensors",
            "invalid_price_thresholds",
            "invalid_nordpool_entry",
            "invalid_nordpool_area",
        } <= set(translations[flow]["error"])

