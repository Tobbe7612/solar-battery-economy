import ast
from pathlib import Path


COORDINATOR_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solar_battery_economy"
    / "coordinator.py"
)


def _dashboard_method_source(name="async_build_dashboard_payload") -> str:
    source = COORDINATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    coordinator = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "SolarBatteryEconomyCoordinator"
    )
    method = next(
        node
        for node in coordinator.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == name
    )
    return ast.get_source_segment(source, method) or ""


def test_dashboard_timeseries_window_is_extended_from_stockholm_calendar():
    source = _dashboard_method_source()

    assert "analysis_start, analysis_end = clamp_history_window(" in source
    assert "dashboard_calendar_boundaries(now=analysis_end)" in source
    assert "series_start = normalize_datetime(calendar.yesterday_start)" in source
    assert '"today_start": calendar.today_start.isoformat()' in source
    assert '"start": series_start.isoformat()' in source
    assert 'forecast = price_model.get("forecast", [])' in source
    assert "window_end = max([series_end, *forecast_ends])" in source
    assert '"yesterday_start": calendar.yesterday_start.isoformat()' in source


def test_request_response_contract_delegates_to_dashboard_builder():
    source = _dashboard_method_source("async_get_dashboard_data")
    assert "return await self.async_build_dashboard_payload(start=start, end=end)" in source


def test_dashboard_price_payload_is_built_from_fresh_runtime_model_and_not_coordinator_data():
    source = _dashboard_method_source()

    assert "price_model = await async_get_nordpool_price_model(" in source
    assert "cache=self._nordpool_price_cache" in source
    assert '"price": price_model' in source
    assert '"price": self.data.get("price"' not in source
    assert '"price_intelligence": self.data.get("price_intelligence"' not in source
    assert '"today_import_price_statistics": calculate_today_import_price_statistics(' in source
    assert '"cheapest_future_period": find_cheapest_future_period(' in source
    assert "forecast,\n                now=analysis_end" in source


def test_dashboard_builder_does_not_trigger_entity_updates_or_use_template_price_sensor():
    source = _dashboard_method_source()

    assert "async_set_updated_data" not in source
    assert "async_write_ha_state" not in source
    assert "_handle_event_update" not in source
    assert "sensor.nord_pool_se3_aktuellt_pris" not in source


def test_dashboard_extended_recorder_request_does_not_remove_analysis_clamp():
    source = _dashboard_method_source()

    assert "start=series_start" in source
    assert "end=series_end" in source
    assert "timeseries_energy_ids = [" in source
    assert "for entity_id in [house_total_entity, *consumer_entities]" in source
    assert "enforce_max_history=False" in source
    assert "analysis_statistics = await async_get_statistics(" in source
    assert "start=analysis_start" in source
    assert "end=analysis_end" in source
    assert "select_price_intervals_window(" in source


def test_analysis_and_consumer_metrics_use_only_24h_samples():
    source = _dashboard_method_source()

    assert "analysis_house_total_samples =" in source
    assert "house = build_house_analysis(\n            analysis_house_total_samples" in source
    assert "samples=analysis_samples" in source
    assert 'consumer_data["history"] = samples' in source
    assert '"house_history": build_energy_samples_from_statistics(' in source


def test_dashboard_data_fetch_does_not_trigger_entity_updates():
    source = _dashboard_method_source()

    assert "async_set_updated_data" not in source
    assert "async_write_ha_state" not in source
    assert "_handle_event_update" not in source
