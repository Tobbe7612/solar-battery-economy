# Architecture Notes

## 1. Current Repository

The current Solar Battery Economy repository baseline is version
`1.4.0`.

``` text
custom_components/solar_battery_economy/
├── __init__.py
├── config_flow.py
├── const.py
├── coordinator.py
├── economy_calculations.py
├── flow_calculation.py
├── manifest.json
├── sensor.py
├── sensor_base.py
├── sensor_helpers.py
├── strings.json
└── brand/
```

------------------------------------------------------------------------

## 2. Target Ecosystem Architecture

``` text
                    SOLAR BATTERY ECONOMY
                            │
                 canonical data + intelligence
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
   ENERGY DASHBOARD      FLOW CARD       PHASE LOAD CARD
   "What happened?"     "What is         "How are the
   "What did it cost?"   happening now?"  phases loaded?"
   "How is it going?"
```

SBE is the central data and intelligence layer.

The three Lovelace cards are complementary presentation layers.

They are not intended to become one all-in-one card.

------------------------------------------------------------------------

## 3. Runtime Architecture

``` text
Configured HA sensors
    │
    ├── solar power
    ├── grid power
    ├── battery power
    └── configured price source
            │
            ▼
SolarBatteryEconomyCoordinator
            │
            ├── normalized input values
            ├── canonical power flows
            ├── energy accumulation
            ├── money accumulation
            ├── savings
            ├── normalized price model
            ├── price intelligence
            └── consumer data/analysis
                    │
                    ▼
              coordinator.data
                    │
                    ▼
                 sensor.py
                    │
                    ├── HA entities
                    │
                    └── structured data
```

------------------------------------------------------------------------

## 4. Ownership Boundaries

### Solar Battery Economy owns

-   input normalization;
-   flow calculations;
-   energy accumulation;
-   financial calculations;
-   persistence;
-   price normalization;
-   price intelligence;
-   canonical analytical definitions;
-   consumer configuration and metadata;
-   Home Assistant entity semantics.

### Home Assistant Recorder owns

-   historical storage;
-   statistics/history used by presentation clients.

SBE must not create a second persistent history database for normal
dashboard use.

### Energy Dashboard owns

-   presentation of energy;
-   presentation of economy;
-   price visualization;
-   historical timeline;
-   consumer analysis presentation;
-   deterministic insight presentation;
-   responsive UI.

The dashboard must not redefine SBE calculations.

### Flow Card owns

-   live power-flow visualization;
-   flow animation;
-   current flow presentation;
-   live interaction.

The Flow Card is not the place for historical economy or intelligence
business logic.

### Phase Load Card owns

-   phase loading visualization;
-   phase current/power presentation;
-   electrical installation view.

------------------------------------------------------------------------

## 5. Data Flow

``` text
Nord Pool template
        │
        ▼
   SBE Price Adapter
        │
        ▼
 Normalized Price Model
        │
        ├── spot
        ├── import
        ├── export
        ├── price_class
        ├── price_quality
        └── forecast intervals
```

The user's existing Nord Pool template remains an upstream source.

It must not be modified as part of this architecture work.

------------------------------------------------------------------------

## 6. Price Semantics

The three price concepts must remain separate.

``` text
SPOT
└── raw market price
    └── market-price visualization

IMPORT
└── actual household purchase price
    └── ALL dashboard cost calculations

EXPORT
└── export value/revenue
    └── export-income calculations
```

### Absolute rule

**Every Energy Dashboard cost is based on total import price, never spot
price.**

This applies to house cost, consumer cost, period cost, cost comparisons
and cost-based insights.

------------------------------------------------------------------------

## 7. Time Horizon

The dashboard has a strict time contract.

### Historical

``` text
maximum 24 hours backwards
```

### Future price

``` text
current moment
→ remaining available data today
→ tomorrow's available data
```

Maximum future horizon is the end of tomorrow's available Nord Pool
data.

No data is extrapolated beyond the upstream source.

No 3-day or 7-day price forecast is introduced.

------------------------------------------------------------------------

## 8. House Total

Canonical house consumption:

``` text
house_total =
    solar_house
  + battery_house
  + grid_house
```

Required semantics:

``` text
kWh
device_class = energy
state_class = total_increasing
```

Existing directional energy entities remain untouched.

------------------------------------------------------------------------

## 9. Persistence

The coordinator owns persistent accumulated values.

Existing persistence must remain compatible.

New cumulative values must:

-   survive restart;
-   not reset to zero;
-   not create artificial energy spikes;
-   preserve historical continuity.

Every persistence-sensitive change requires unit tests and runtime
verification.

------------------------------------------------------------------------

## 10. Generic Consumers

A consumer is a configurable measurable load.

``` text
Consumer
├── name               required
├── energy_entity      required
├── power_entity       optional
├── icon               optional
└── color              optional
```

Consumers are not hardcoded device types.

Examples:

-   car;
-   spa;
-   heat pump;
-   appliance;
-   washing machine;
-   server.

The original energy entity remains authoritative for historical energy.

The optional power entity is for live display.

The card may limit how many consumers it displays without changing the
SBE data model.

------------------------------------------------------------------------

## 11. Price Intelligence

SBE provides canonical price intelligence.

Current concepts:

``` text
current_price_class
price_quality_index
cheapest_future_period
```

Conceptual price classes:

``` text
VERY_CHEAP
CHEAP
NORMAL
EXPENSIVE
VERY_EXPENSIVE
```

PQI:

``` text
0–100
higher = better/cheaper
```

PQI is not Smart Score.

------------------------------------------------------------------------

## 12. Smart Score

Smart Score is a dashboard-level intelligence concept intended to
summarize broader energy/economic behavior.

It must not be implemented as a duplicate of PQI.

Before implementation, the Smart Score must have:

-   an explicit definition;
-   deterministic inputs;
-   mathematical calculation;
-   tests;
-   documented interpretation.

The dashboard may not invent its own Smart Score formula.

------------------------------------------------------------------------

## 13. Dashboard Information Architecture

The mockup is the visual and functional target.

The dashboard should broadly contain:

``` text
LIVE PRICE
├── current price
├── price class
├── PQI
├── status
└── near-term information

PRICE STATISTICS
├── lowest
├── highest
└── average

TIMELINE
├── max 24h history
├── actual consumption
├── actual consumer usage
├── current moment
└── future price through today + tomorrow

ENERGY & ECONOMY
├── consumption
├── import cost
├── consumer energy
├── consumer cost
├── battery contribution
└── other canonical metrics

INSIGHTS
├── cheap-use analysis
├── expensive-use analysis
├── costliest periods
└── consumer price alignment
```

The exact visual arrangement is a UI decision made after the data
contract is complete.

------------------------------------------------------------------------

## 14. Architecture Rules

1.  No business logic duplication in cards.
2.  No second history database.
3.  No sensor explosion for 15-minute forecast data.
4.  Existing public entities remain stable.
5.  New capabilities should be additive.
6.  Cost calculations always use total import price.
7.  Spot remains available for market-price visualization.
8.  Forecast horizon never exceeds today + tomorrow.
9.  Dashboard history never exceeds 24 hours.
10. Nord Pool template remains unchanged.
11. Flow Card remains focused on live flows.
12. Phase Load Card remains focused on phase loading.
13. New code must be covered by appropriate tests.
14. Documentation must be updated together with contract-changing code.

------------------------------------------------------------------------

## 15. Development Boundary

Before modifying SBE, every proposed feature must be classified:

``` text
CANONICAL SBE DATA
        │
        ├── existing → reuse
        │
        ├── missing → add minimal canonical capability
        │
        └── unclear → define/test first

RECORDER
        │
        └── historical retrieval

CARD
        │
        └── presentation only
```

No feature should be added to SBE merely because it makes card
implementation easier.

------------------------------------------------------------------------

## 16. Current Status

``` text
Architecture baseline       COMPLETE
Energy Data Contract        UPDATED / FROZEN
Dashboard target            APPROVED
Time horizon                LOCKED
Cost semantics              LOCKED
Nord Pool template          LOCKED / UNCHANGED

Next:
FAS 3.1 Data Specification
FAS 3.1 Data Gap Matrix
FAS 3.1 Definition Decisions
```
