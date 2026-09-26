# Energy Dashboard Data Gap Matrix

**Project:** Solar Battery Economy  
**Baseline:** SBE 1.4.0  
**Checkpoint:** 2026-09-20
**Definition status:** V1 dashboard semantics frozen

## Status legend

- **GREEN** — canonical capability already exists.
- **YELLOW** — data exists, but exact dashboard semantics/aggregation are not frozen or verified.
- **RED** — canonical capability is missing.
- **WHITE** — presentation-only responsibility.

## Matrix

| Requirement | Current source | Status | Current finding | Next action |
|---|---|---:|---|---|
| Current import price | normalized price model | GREEN | Current `import` exists | Present everywhere as dashboard price |
| Current total import price | normalized price model | GREEN | Current `import` exists | Use for **all costs** |
| Current export price | normalized price model | GREEN | Current `export` exists | Keep as revenue |
| Price class | SBE price intelligence | GREEN | `current_price_class` exists | Present only |
| PQI | SBE price intelligence | GREEN | `price_quality_index` exists | Present only |
| Cheapest future period | SBE price intelligence | GREEN | Structured result exists | Present only |
| Future 15-min prices | normalized forecast | GREEN | Structured intervals exist | No entity explosion |
| Lowest/highest/average today | price intervals | GREEN | Deterministic current-day total-import-price statistics are defined and tested | Present only |
| 24h house consumption | SBE + Recorder | GREEN | Rolling 24h uses canonical `house_total` and Recorder/statistics | Preserve/test |
| 24h house cost | Recorder + normalized import price | GREEN | Rolling 24h house-total energy × total import price is implemented and tested | Present only |
| Cheap-use % | Recorder + normalized import price | GREEN | Shared previous-24h median reference and energy-weighted calculation are implemented and tested | Present only |
| Expensive-use % | Recorder + normalized import price | GREEN | Shared previous-24h median reference and energy-weighted calculation are implemented and tested | Present only |
| Smart Score | SBE | GREEN | Deterministic 0–100 score is implemented and tested with the frozen V1 weights | Present only |
| Highest-cost period | Recorder + normalized import price | GREEN | 15-min maximum valid house period cost with deterministic tie handling is implemented and tested | Present only |
| Lowest-cost period | Recorder + normalized import price | GREEN | 15-min minimum valid cost with energy > 0 and earliest-tie handling is implemented and tested | Present only |
| Consumer energy history | configured HA entities + Recorder | GREEN | Generic configured consumer history is available; source entity remains authoritative | Preserve/test |
| Consumer cost | consumer history + normalized import price | GREEN | Energy × total import price is implemented and covered by tests | Present only |
| Consumer average price | consumer history + normalized import price | YELLOW | Energy-weighted total import price; zero energy excluded | Preserve/test |
| Consumer cheap-use % | consumer history + normalized import price | YELLOW | Shared median reference; energy-weighted | Preserve/test |
| Consumer expensive-use % | consumer history + normalized import price | YELLOW | Shared median reference; energy-weighted | Preserve/test |
| Consumer event intervals | Recorder/history | GREEN | Generic events are extracted from actual historical energy intervals without invented timing | Present only |
| Battery contribution | SBE + Recorder | GREEN | Rolling 24h battery-house energy / house-total energy is implemented and tested | Present only |
| Battery charge/discharge history | SBE + Recorder | YELLOW | Directional energy exists; presentation aggregation still to verify | Implement/verify |
| Actual grid cost | SBE savings/economy | GREEN | `actual_grid_cost` exists | Preserve import-price basis |
| Export income | SBE savings/economy | GREEN | `export_income` exists | Keep separate from cost |
| Total savings | SBE savings/economy | GREEN | `savings.total` exists | Verify dashboard wording |
| Grid independence | SBE sensor | GREEN | Existing sensor | Present only |
| Solar self-consumption | SBE sensor | GREEN | Existing sensor | Present only |
| CO2 saved | SBE sensor | GREEN | Existing sensor | Present only |
| Historical timeline | HA Recorder | GREEN | Recorder owns historical storage; dashboard consumes prepared history | Preserve boundary |
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

> **Total import price is the Energy Dashboard price basis everywhere.**

## Remaining implementation gaps

### RED — canonical capability still missing

None of the frozen V1 analytical requirements remain RED.

### YELLOW — definition or presentation verification remains

1. Current status wording remains a presentation-level interpretation to be finalized by the dashboard UI.
2. Battery charge/discharge presentation aggregation remains a dashboard presentation concern.

### Resolved definitions

Cheap/expensive usage, consumer average price, consumer share, Consumer Price
Alignment, today's total-import-price statistics and Smart Score semantics are now defined.

## Architectural boundary

Canonical business logic belongs in SBE. Historical retrieval, chart slicing, date-window selection and visual formatting can remain in the Energy Dashboard layer when they do not create a competing business definition.

## Guardrails

- Total import price is the sole basis for Energy Dashboard prices and costs.
- Raw spot remains available in the normalized source model but is not used as the dashboard price basis.
- Export remains revenue.
- Nord Pool template remains unchanged.
- No business logic in Lovelace cards.
- No forecast entity explosion.
- Existing verified entity contracts remain protected.
