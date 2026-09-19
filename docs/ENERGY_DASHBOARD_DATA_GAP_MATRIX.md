# Energy Dashboard Data Gap Matrix

**Project:** Solar Battery Economy  
**Baseline:** SBE 1.4.0  
**Checkpoint:** 2026-09-13

## Status legend

- **GREEN** — canonical capability already exists.
- **YELLOW** — data exists, but exact dashboard semantics/aggregation are not frozen or verified.
- **RED** — canonical capability is missing.
- **WHITE** — presentation-only responsibility.

## Matrix

| Requirement | Current source | Status | Current finding | Next action |
|---|---|---:|---|---|
| Current spot price | normalized price model | GREEN | Current `spot` exists | Present as market price |
| Current total import price | normalized price model | GREEN | Current `import` exists | Use for **all costs** |
| Current export price | normalized price model | GREEN | Current `export` exists | Keep as revenue |
| Price class | SBE price intelligence | GREEN | `current_price_class` exists | Present only |
| PQI | SBE price intelligence | GREEN | `price_quality_index` exists | Present only |
| Cheapest future period | SBE price intelligence | GREEN | Structured result exists | Present only |
| Future 15-min prices | normalized forecast | GREEN | Structured intervals exist | No entity explosion |
| Lowest/highest/average today | price intervals | YELLOW | Raw intervals exist | Freeze population + rounding |
| 24h house consumption | SBE + Recorder | YELLOW | Cumulative `house_total` exists | Use Recorder for 24h delta/series |
| 24h house cost | SBE economy | YELLOW | Cumulative import-related money exists | Freeze exact 24h aggregation |
| Cheap-use % | Recorder + price intervals | RED | No canonical metric | Define + test |
| Expensive-use % | Recorder + price intervals | RED | No canonical metric | Define + test |
| Smart Score | SBE | RED | No canonical metric | Define inputs/weights/normalization |
| Highest-cost period | Recorder + price | RED | No canonical metric | Define deterministic algorithm |
| Lowest-cost period | Recorder + price | RED | Not defined as dashboard metric | Define separately from price low |
| Consumer energy history | configured HA entities + Recorder | YELLOW | Consumer configuration exists in card ecosystem | Define generic historical contract |
| Consumer cost | consumer history + import price | RED | No generic canonical layer | Define + test using total import price |
| Consumer average price | consumer history + import price | RED | No canonical metric | Weighted average definition |
| Consumer cheap-use % | consumer history + price | RED | No canonical metric | Define + test |
| Consumer expensive-use % | consumer history + price | RED | No canonical metric | Define + test |
| Consumer event intervals | Recorder/history | RED | No generic event model | Define before UI |
| Battery contribution | SBE energy/economy | GREEN/YELLOW | Existing battery energy/savings foundation | Verify exact dashboard metric |
| Battery charge/discharge history | SBE + Recorder | YELLOW | Directional energy exists | Define 24h presentation aggregation |
| Actual grid cost | SBE savings/economy | GREEN | `actual_grid_cost` exists | Preserve import-price basis |
| Export income | SBE savings/economy | GREEN | `export_income` exists | Keep separate from cost |
| Total savings | SBE savings/economy | GREEN | `savings.total` exists | Verify dashboard wording |
| Grid independence | SBE sensor | GREEN | Existing sensor | Present only |
| Solar self-consumption | SBE sensor | GREEN | Existing sensor | Present only |
| CO2 saved | SBE sensor | GREEN | Existing sensor | Present only |
| Historical timeline | HA Recorder | YELLOW | Recorder is source | Dashboard renders; no business logic |
| Future timeline | SBE price model | GREEN | Known intervals exist | Render only known data |

## Important code finding

The current coordinator already creates the canonical cumulative house total:

```text
energy.house_total =
    energy.solar_house
  + energy.battery_house
  + energy.grid_house
```

Therefore **House Total does not need to be reimplemented** for the Energy Dashboard.

## Important economy finding

Current money accumulation uses the normalized import price for import-priced flows and the normalized export price for export-priced flows.

Import-priced examples:

```text
solar_house
battery_house
grid_house
grid_battery
```

Export-priced examples:

```text
solar_export
battery_grid
house_grid
```

This is compatible with the locked dashboard rule:

> **Every dashboard cost uses total import price, never spot.**

## RED items

1. Smart Score.
2. Cheap-use percentage.
3. Expensive-use percentage.
4. Deterministic cost-period insights.
5. Generic consumer analysis.
6. Generic consumer cost.
7. Generic consumer event model.

## YELLOW items

1. Today price-statistics population.
2. 24h cost aggregation.
3. 24h consumer cost aggregation.
4. Battery dashboard metric definitions.
5. Recorder aggregation semantics.
6. Current status wording.

## Architectural boundary

Canonical business logic belongs in SBE. Historical retrieval, chart slicing, date-window selection and visual formatting can remain in the Energy Dashboard layer when they do not create a competing business definition.

## Guardrails

- Total import price is the sole basis for Energy Dashboard costs.
- Spot remains a market-price visualization value.
- Export remains revenue.
- Nord Pool template remains unchanged.
- No business logic in Lovelace cards.
- No forecast entity explosion.
- Existing verified entity contracts remain protected.
