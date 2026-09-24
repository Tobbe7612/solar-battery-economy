# FAS 3 --- SBE Implementation & Migration Plan

**Project:** Solar Battery Economy\
**Status:** IMPLEMENTATION CHECKPOINT --- V1 analytical data foundation implemented and tested
document\
**Source of Truth:** `docs/ENERGY_DATA_CONTRACT.md`\
**Current code baseline:** SBE 1.4.0

------------------------------------------------------------------------

## 1. Purpose

This document defines the implementation plan for extending Solar
Battery Economy into the central data/intelligence engine for:

-   Solar Battery Economy Flow Card;
-   Energy Dashboard;
-   future/common data needs of Phase Load Card.

The plan is deliberately incremental.

The existing SBE architecture is preserved wherever practical.

The objective is to add the minimum required capabilities without
breaking existing users, entities, accumulated values or historical
continuity.

No code change should be made outside the approved scope without
explicitly updating the project plan.

------------------------------------------------------------------------

## 2. Target Product Architecture

``` text
SBE
│
├── canonical energy data
├── canonical economy data
├── normalized price data
├── price intelligence
├── consumer analysis
└── deterministic insights
        │
        ├───────────────┬───────────────┐
        ▼               ▼               ▼
 Energy Dashboard    Flow Card     Phase Load Card
```

The Energy Dashboard is now the primary driver for the new data
requirements.

The Flow Card is not to be expanded merely to support dashboard
functionality.

------------------------------------------------------------------------

## 3. Current Baseline

The current SBE implementation contains:

-   Config Flow;
-   Coordinator;
-   event-driven updates;
-   directional power flows;
-   accumulated energy;
-   persistent Store;
-   economy/savings calculations;
-   battery-origin money attribution;
-   current import/export price sensors;
-   price normalization/intelligence;
-   price quality index;
-   cheapest future period;
-   diagnostic price-data handling.

Existing verified behavior must be preserved.

------------------------------------------------------------------------

## 4. Implementation Principles

### 4.1 Additive first

Prefer adding new entities/data structures over modifying existing
public entities.

### 4.2 Preserve existing identity

Do not change existing unique IDs, names, units or semantics unless a
documented migration is unavoidable.

### 4.3 Do not rebuild SBE

The existing coordinator/flow/economy architecture remains the
foundation.

### 4.4 Separate data ownership

``` text
SBE
  = canonical calculations + normalized data + intelligence

HA Recorder
  = historical storage

Lovelace cards
  = visualization + presentation
```

### 4.5 No card-specific business logic

Cards consume canonical SBE data.

### 4.6 No sensor explosion

15-minute forecast data remains structured data.

### 4.7 Test persistence-sensitive changes

Energy/money persistence is critical.

------------------------------------------------------------------------

# FAS 3.1 --- Energy Dashboard Data Specification

## Objective

Before new implementation, map the approved dashboard mockup to exact
data requirements.

No dashboard UI implementation occurs during this phase.

------------------------------------------------------------------------

## 5. Dashboard Data Gap Matrix

Every mockup component must be classified as:

``` text
GREEN  = existing and verified
YELLOW = partially available / needs verification or aggregation
RED    = missing canonical capability
WHITE  = presentation only
```

For every metric record:

``` text
Dashboard component
→ metric definition
→ data source
→ existing entity/structured data
→ Recorder dependency
→ SBE gap
→ implementation requirement
```

------------------------------------------------------------------------

## 6. Definition Decisions — FROZEN

The required V1 dashboard semantics have now been explicitly defined.

1.  Current prominent price = spot; dashboard costs = total import price.
2.  Today's low/high/average = spot, current calendar day `00:00` → now,
    elapsed intervals only.
3.  House and consumer cost = energy × total import price over rolling 24h.
4.  Cheap/expensive reference = median total import price over previous 24h;
    equality is neutral.
5.  Cost-period resolution = normalized 15 minutes; highest/lowest are
    actual house period cost, not price; earliest interval wins ties.
6.  Consumer average price and house average import price are energy-weighted.
7.  Consumer share = consumer 24h energy / house 24h energy.
8.  Battery contribution = battery-house energy / house-total energy over
    the same 24h window.
9.  Consumer Price Alignment = house average import price minus consumer
    average import price; it is not part of Smart Score V1.
10. Smart Score = 40% cheap usage + 40% inverse expensive usage + 20%
    battery contribution, on a 0–100 scale.
11. Smart Score classes: 90–100 Excellent, 75–89 Good, 60–74 Fair,
    40–59 Poor, 0–39 Very Poor.
12. Missing price data is never treated as zero, interpolated or guessed.
13. Dashboard history is max 24h; future data is limited to available today
    + tomorrow prices.
14. Consumer events must come from actual Recorder/history resolution; timing
    is never invented.
15. Business calculations are not presentation-rounded; display formatting
    belongs to the dashboard.


------------------------------------------------------------------------

## 7. Locked Time Rules

### History

``` text
maximum 24 hours backwards
```

### Future

``` text
only available central Nord Pool data
today + tomorrow
```

### Prohibited

-   history beyond 24h for the dashboard's primary analysis;
-   forecast beyond tomorrow;
-   extrapolated prices;
-   guessed future values;
-   stale future prices presented as current known data.

------------------------------------------------------------------------

## 8. Locked Cost Rule

All dashboard cost calculations use:

``` text
total import price
```

Never:

``` text
spot price
```

This applies to:

-   house cost;
-   consumer cost;
-   cost per time period;
-   average purchase cost;
-   cost-based insights;
-   price/consumption cost correlations.

Spot price remains available for market-price visualization.

------------------------------------------------------------------------

# FAS 3.2 --- Internal Data Model

## Objective

Ensure coordinator data can cleanly represent:

``` text
power
energy
money
savings
price
price_intelligence
consumers
insights
```

Existing keys under:

``` text
power
energy
money
savings
```

must remain compatible with existing sensors.

The exact Python representation must prioritize Home Assistant
compatibility and testability.

------------------------------------------------------------------------

# FAS 3.3 --- Canonical House Energy

## Objective

Expose/verify canonical house consumption:

``` text
house_total =
    solar_house
  + battery_house
  + grid_house
```

Required semantics:

``` text
kWh
device_class: energy
state_class: total_increasing
```

Existing directional energy entities remain untouched.

If House Total is already correctly implemented, do not reimplement it
unnecessarily; verify and document it instead.

------------------------------------------------------------------------

# FAS 3.4 --- Price Source Adapter

## Objective

Consume the user's existing structured Nord Pool template source.

Input:

``` text
current price
all_prices[]
tomorrow_available
```

Intervals:

``` text
start
end
spot
import
export
```

Output:

``` text
normalized Price Model
```

The upstream Nord Pool template must not be modified.

------------------------------------------------------------------------

# FAS 3.5 --- Price Intelligence

Required canonical concepts:

``` text
current_price_class
price_quality_index
cheapest_future_period
```

Forecast:

``` text
15-minute intervals
today + tomorrow only
```

No one-entity-per-interval implementation.

No price forecast beyond the upstream data horizon.

------------------------------------------------------------------------

# FAS 3.6 --- Generic Consumers

## Objective

Provide configurable consumers:

``` text
Consumer
├── name
├── energy_entity
├── power_entity (optional)
├── icon (optional)
└── color (optional)
```

Use Config Flow / Options Flow.

Do not hardcode device categories.

Do not create consumer energy by integrating power in V1.

------------------------------------------------------------------------

# FAS 3.7 --- Consumer Analysis

For each consumer, support where data permits:

``` text
energy
cost
average_price
cheap_usage_percent
expensive_usage_percent
```

Consumer cost uses total import price.

The source energy entity remains authoritative for historical energy.

------------------------------------------------------------------------

# FAS 3.8 --- House Economy

Before exposing a new canonical House Cost entity, finalize its exact
semantics.

Do not simply add unrelated SBE money values.

Maintain separation between:

``` text
actual grid purchase cost
solar avoided value
battery avoided value
export income
savings
opportunity cost
```

All actual household purchase cost uses total import price.

A formal test matrix is required.

------------------------------------------------------------------------

# FAS 3.9 --- Smart Score

Smart Score is now defined and approved for V1. It is distinct from PQI.

``` text
score =
    0.40 * cheap_usage_percent
  + 0.40 * (100 - expensive_usage_percent)
  + 0.20 * battery_contribution_percent
```

Range: `0..100`.

Classes:

``` text
90–100  Excellent
75–89   Good
60–74   Fair
40–59   Poor
0–39    Very Poor
```

Consumer Price Alignment is excluded from Smart Score V1.

Edge cases:

- no house energy → unavailable;
- no battery data → unavailable;
- no valid price data → unavailable;
- valid battery data with zero contribution → 0% contribution;
- missing price data is never converted to zero.

The implementation must be deterministic and unit-tested.

# FAS 3.10 --- Deterministic Insights

Initial V1 insight types are frozen as:

``` text
cheap_consumption
expensive_consumption
highest_cost_period
lowest_cost_period
consumer_cost
consumer_share
consumer_price_alignment
```

Insights are deterministic facts derived from canonical metrics. They do not
contain autonomous recommendations or inferred user intent.

Cost-period insights use 15-minute normalized price intervals, actual house
energy and total import price. Consumer share is an energy share, not a cost
share. Consumer Price Alignment is a transparent SEK/kWh delta and not a
score.

The dashboard presents the resulting structured insight data and does not
recalculate business metrics.

# 10. Existing Known Issue

The current helper `_float_state()` converts:

``` text
unknown
unavailable
invalid
```

to:

``` text
0.0
```

while money-booking logic checks for `None`.

This can create a mismatch in the intended "do not book money when price
is unavailable" behavior.

This correctness issue must be resolved deliberately before new
price-dependent functionality is considered stable.

It must not be fixed as unrelated cleanup.

------------------------------------------------------------------------

# 11. Persistence and Migration

Every new cumulative sensor must survive restart.

Tests must cover:

``` text
before restart
      |
      v
restart HA
      |
      v
after restart
```

Expected:

-   energy totals unchanged except legitimate post-restart accumulation;
-   money totals unchanged except legitimate post-restart accumulation;
-   install date preserved;
-   no artificial energy spike;
-   no reset to zero.

Existing Store schema must remain compatible.

Any schema change requires explicit migration.

------------------------------------------------------------------------

# 12. Config Flow Migration

Current configuration must remain valid.

New configuration should be additive.

Potential additions:

``` text
Price intelligence source
Consumers
```

Do not remove or rename existing configuration keys.

------------------------------------------------------------------------

# 13. Sensor Strategy

Reuse existing sensor classes where semantics match.

Avoid many one-off classes.

New classes are justified where Home Assistant semantics differ
materially.

Do not change entity identity merely for implementation convenience.

------------------------------------------------------------------------

# 14. Testing Plan

## Unit tests

-   flow calculations;
-   house total calculation;
-   price normalization;
-   price classification;
-   PQI;
-   cheapest period;
-   consumer calculations;
-   consumer cost;
-   house-cost calculation;
-   price statistics;
-   Smart Score;
-   deterministic insights.

## Integration/config tests

-   fresh install;
-   existing configuration;
-   options flow;
-   consumer addition;
-   consumer removal/update;
-   invalid entity;
-   unavailable entity;
-   unavailable price source;
-   unavailable tomorrow data.

## Persistence tests

-   energy restore;
-   money restore;
-   install date restore;
-   house total restore;
-   migration from existing Store.

## Runtime tests

-   normal power updates;
-   price changes;
-   15-minute price changes;
-   unavailable price;
-   unavailable consumer;
-   unavailable tomorrow prices;
-   Home Assistant restart;
-   price horizon boundary.

------------------------------------------------------------------------

# 15. Implementation Order

``` text
1. Finalize Data Specification
        |
2. Finalize Data Gap Matrix
        |
3. Finalize Definition Decisions
        |
4. Establish tests/baseline
        |
5. Internal data model
        |
6. Verify/complete House Total
        |
7. Price source adapter verification
        |
8. Price intelligence verification
        |
9. Consumer configuration
        |
10. Consumer analysis
        |
11. House cost
        |
12. Smart Score
        |
13. Deterministic insights
        |
14. Persistence/migration verification
        |
15. Full regression test
        |
16. Documentation update
        |
17. Energy Dashboard design
```

**No Energy Dashboard UI implementation occurs before the required
SBE/data contract work is complete.**

------------------------------------------------------------------------

# 16. Explicitly NOT Part of FAS 3

Do not implement:

-   Energy Dashboard UI;
-   Flow Card visual rewrite;
-   Phase Load Card rewrite;
-   automatic charging;
-   automatic battery control;
-   AI optimization/control;
-   consumer groups;
-   autonomous optimal multi-hour charging;
-   second history database;
-   repository merging;
-   forecast beyond today + tomorrow;
-   dashboard history beyond 24h.

------------------------------------------------------------------------

# 17. Definition of Done for SBE

FAS 3 is complete only when:

-   existing SBE functionality still works;
-   existing entities remain compatible;
-   accumulated values survive restart;
-   House Total is correct;
-   structured price data is normalized;
-   price intelligence is deterministic and tested;
-   Consumers can be configured generically;
-   consumer analysis is correct;
-   all dashboard cost calculations use total import price;
-   Smart Score is deterministic and tested;
-   deterministic insights are tested;
-   historical data remains owned by HA Recorder;
-   dashboard history is limited to 24h;
-   future price data is limited to today + tomorrow;
-   no unnecessary sensor explosion exists;
-   documentation reflects the implementation;
-   regression tests pass;
-   no unrelated refactor has slipped into the release.

------------------------------------------------------------------------

## 18. Phase Status

``` text
FAS 0 — Project Definition          COMPLETE / FROZEN
FAS 1 — Data Gap Analysis           COMPLETE / APPROVED
FAS 2A — Architecture Decisions     COMPLETE / FROZEN
FAS 2B — Energy Data Contract       UPDATED / FROZEN

FAS 3.1 — Dashboard Specification   DEFINITION FROZEN
FAS 3   — Implementation            IN PROGRESS
```

**Next approved step:** reconcile documentation with the implementation-aligned V1 contract, then proceed to Energy Dashboard UI/data-client work. No canonical V1 analytical gap remains RED.
