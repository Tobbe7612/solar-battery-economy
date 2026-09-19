# AI Handoff â€” Solar Battery Economy

**Project:** Solar Battery Economy
**Current version:** 1.4.0
**Current checkpoint:** 2026-09-13
**Status:** Stable baseline before Energy Dashboard data-gap implementation

## Current goal

Build the data foundation for the new **Energy Dashboard** without moving business logic into Lovelace cards.

```text
Solar Battery Economy
        â”‚
        â”œâ”€â”€ Flow Card
        â”‚     â””â”€â”€ live power flows: "Vad hÃ¤nder just nu?"
        â”‚
        â”œâ”€â”€ Energy Dashboard
        â”‚     â””â”€â”€ energy / economy / price / analytics:
        â”‚         "Vad har hÃ¤nt, vad kostade det och hur gÃ¥r det?"
        â”‚
        â””â”€â”€ Phase Load Card
              â””â”€â”€ phase loading / electrical-system view
```

## Locked rules

1. **All Energy Dashboard costs use total import price.**
2. Spot price is for market-price visualization, not cost calculations.
3. Export is export revenue and remains separate from import cost.
4. The existing Nord Pool template is immutable and must not be changed.
5. Historical dashboard analysis is limited to **maximum 24 hours backwards**.
6. Known future price data is limited to available **today + tomorrow** Nord Pool data.
7. No price extrapolation.
8. SBE owns canonical calculations and normalized data.
9. Lovelace cards present data; they must not recreate SBE business logic.
10. Do not create a large collection of forecast entities for 15-minute price data.
11. Preserve existing verified entity IDs, unique IDs, units, device classes and state classes unless explicitly required.
12. Make small, testable changes and run the full test suite after meaningful changes.

## Verified current baseline

- SBE version: **1.4.0**
- Current DEV package: `solar-battery-economy_latest.zip`
- Test baseline: **102 tests passing**
- Canonical `house_total` energy exists.
- Normalized price data exists.
- Price class exists.
- Price Quality Index exists.
- Configurable cheapest future period exists.
- Existing economy/savings calculations exist.
- Persistent energy/money state exists.

## Current price model

```text
spot   = market price / visual price curve
import = total household purchase price
export = household export revenue price
```

The dashboard must retain this distinction everywhere.

## Current cheapest-period feature

The coordinator exposes `price_intelligence.cheapest_future_period` with duration, selection mode, start/end, average import price and selected intervals.

`consecutive` selects one continuous block. `cheapest_quarters` selects the cheapest individual 15-minute intervals.

Known presentation issue: `cheapest_quarters` can contain gaps, so its envelope `start` â†’ `end` can span a larger period than the selected intervals. Do not silently change the algorithm while implementing unrelated work.

## Current canonical house total

```text
house_total = solar_house + battery_house + grid_house
```

Unit: `kWh`
Device class: `energy`
State class: `total_increasing`

## Current Energy Dashboard data gaps

### GREEN â€” already available

- current spot/import/export price
- price classification
- Price Quality Index
- normalized future forecast
- cheapest future period
- cumulative house total
- existing directional energy flows
- existing economy/savings foundation
- persistence

### YELLOW â€” definition and/or verification required

- price statistics for "today"
- 24h house cost aggregation
- 24h consumer cost aggregation
- exact battery dashboard metrics
- historical Recorder aggregation semantics
- current status interpretation

### RED â€” canonical capability missing

- cheap-use percentage
- expensive-use percentage
- Smart Score
- deterministic insights
- generic consumer analysis
- consumer event model

## Required next work

Do **not** start UI implementation yet.

1. Freeze definition decisions.
2. Finalize the Data Gap Matrix.
3. Decide which missing metrics belong in SBE and which can safely be derived from Recorder presentation data.
4. Write tests for each new canonical calculation.
5. Implement the smallest SBE changes.
6. Run the full regression suite.
7. Then proceed to Energy Dashboard UI/data consumption design.

## Files to inspect before code changes

```text
custom_components/solar_battery_economy/coordinator.py
custom_components/solar_battery_economy/economy_calculations.py
custom_components/solar_battery_economy/flow_calculation.py
custom_components/solar_battery_economy/price_source.py
custom_components/solar_battery_economy/sensor.py
custom_components/solar_battery_economy/sensor_base.py
custom_components/solar_battery_economy/config_flow.py
custom_components/solar_battery_economy/const.py

tests/test_coordinator_price_source.py
tests/test_price_source.py
tests/test_price_classification.py
tests/test_house_total.py
tests/test_energy_accumulation.py
tests/test_economy_calculations.py
tests/test_data_model.py
tests/test_sensor_price_intelligence.py

docs/ARCHITECTURE_NOTES(2).md
docs/ENERGY_DATA_CONTRACT(2).md
docs/ENERGY_DASHBOARD_DATA_SPECIFICATION.md
docs/FAS_3_IMPLEMENTATION_PLAN(3).md
docs/PROJECT_HANDOFF.md
docs/BASELINE_SBE_1.4.0.md
docs/V1.4.0_CODE_AUDIT.md
```

## Known documentation cleanup

`price_source.py` contains an outdated docstring reference to `horizon_hours` in `find_cheapest_future_period()`. The function no longer accepts that parameter. Documentation-only cleanup; do not mix it into unrelated functional changes.

## Do not do

- Do not modify the Nord Pool template.
- Do not replace total import price with spot in any cost metric.
- Do not add 96 forecast entities.
- Do not put business calculations into Lovelace cards.
- Do not implement Smart Score without a frozen definition.
- Do not implement generic consumer metrics without an explicit data contract.
- Do not perform unrelated refactoring.

## Handoff status

**Ready for:** Definition Decisions â†’ Data Gap Matrix finalization â†’ tests â†’ targeted SBE implementation.
