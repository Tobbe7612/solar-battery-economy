# ENERGY DATA CONTRACT

**Project:** Solar Battery Economy ecosystem\
**Document status:** FROZEN --- FAS 2B, updated for FAS 3.1\
**Version:** 1.1\
**Purpose:** Source of Truth for data exposed by Solar Battery Economy
to the ecosystem's Lovelace cards.

------------------------------------------------------------------------

## 1. Purpose

This document defines the data contract between the Solar Battery
Economy (SBE) integration and its related Lovelace cards.

The contract defines:

-   what data SBE guarantees to expose;
-   the semantic meaning of each value;
-   which data is represented as Home Assistant entities;
-   which data is structured/forecast data;
-   how historical data is obtained;
-   consumer configuration;
-   price intelligence;
-   Energy Dashboard requirements;
-   backward-compatibility requirements;
-   the boundaries of V1.

This document is an architectural contract, not an implementation guide.

No card may invent a competing definition for a value already defined
here.

------------------------------------------------------------------------

## 2. Ecosystem Architecture

``` text
                          HOME ASSISTANT
                               |
              +----------------+----------------+
              |                |                |
           Nord Pool       Solar / Grid     Battery / Loads
              |                |                |
              +----------------+----------------+
                               |
                               v
                  +--------------------------+
                  |   SOLAR BATTERY ECONOMY  |
                  |                          |
                  |  Data ingestion          |
                  |  Flow calculation        |
                  |  Energy accumulation     |
                  |  Economy calculation     |
                  |  Price intelligence      |
                  |  Consumer metadata       |
                  |  Persistence             |
                  +------------+-------------+
                               |
                        ENERGY DATA CONTRACT
                               |
          +--------------------+--------------------+
          |                    |                    |
          v                    v                    v
      Flow Card        Energy Dashboard       Phase Load Card
```

SBE is the central energy/economy data engine.

The Energy Dashboard depends on SBE.

The Energy Dashboard is a separate presentation layer/repository.

Phase Load Card remains a separate presentation layer and is not forced
into the SBE data model unless a later architectural decision explicitly
requires it.

------------------------------------------------------------------------

## 3. Core Principles

### 3.1 SBE is the data/intelligence layer

Cards should primarily consume data rather than duplicate business
logic.

### 3.2 Cards are presentation/analysis clients

Cards must not independently redefine:

-   energy flow semantics;
-   SBE cost semantics;
-   SBE savings semantics;
-   price classification rules;
-   canonical analytical definitions.

### 3.3 Home Assistant Recorder is the historical layer

SBE should expose correct HA entities and state metadata.

SBE must not create a parallel historical database for normal card
history.

### 3.4 Structured data for high-cardinality forecast data

The 15-minute price forecast must not create one entity per interval.

### 3.5 Backward compatibility is a hard requirement

Existing SBE entities should remain stable whenever reasonably possible.

Existing entity unique IDs, units, semantics and historical continuity
must not be changed unnecessarily.

### 3.6 Nord Pool integration is the price source

SBE selects the configured Nord Pool integration and market area, then reads
current, forecast, and historical intervals directly. Import and export
prices are calculated by SBE using the established formulas.

------------------------------------------------------------------------

## 4. Existing SBE Data --- Preserve

The following existing flow model remains the foundation.

### Power flows

-   Solar → House
-   Solar → Battery
-   Solar → Grid
-   Battery → House
-   Battery → Grid
-   Grid → House
-   Grid → Battery
-   House → Grid

### Energy flows

The corresponding accumulated energy values remain available as kWh with
appropriate Home Assistant energy semantics.

### Economy

Existing SBE economy/savings entities remain part of the public contract
and must not be silently repurposed.

### Battery analytics

Existing battery-related calculations and sensors remain authoritative
unless a future version explicitly changes their contract.

------------------------------------------------------------------------

## 5. House Energy Contract

### 5.1 House Total Energy

A canonical house-consumption energy value is exposed.

Definition:

``` text
House Total Energy =
    Solar → House
  + Battery → House
  + Grid → House
```

This is the total electrical energy consumed by the house/load system,
regardless of energy source.

Required Home Assistant semantics:

``` text
unit_of_measurement: kWh
device_class: energy
state_class: total_increasing
```

The value must survive Home Assistant restarts according to the same
persistence principles used by existing SBE accumulated-energy sensors.

------------------------------------------------------------------------

## 6. Power Contract

Existing SBE power-flow sensors remain authoritative for real-time flow
visualization.

The Flow Card may use these values directly.

No second competing power-flow calculation should be introduced unless
required by a later approved architecture change.

------------------------------------------------------------------------

## 7. Price Data Contract

SBE reads current, forecast, and historical market intervals directly from
the configured Nord Pool integration and market area. No separate price
sensor is required.

Conceptual interval structure:

``` text
{
  start: datetime,
  end: datetime,
  spot: SEK/kWh,
  import: SEK/kWh,
  export: SEK/kWh
}
```

SBE normalizes spot intervals into its price model and applies the existing
import/export formulas. Historical price intervals come from the Nord Pool
history action; Recorder remains the source for measured energy statistics.

------------------------------------------------------------------------

## 8. Price Semantics

### 8.1 Spot price

Spot price is the raw market price retained in the normalized source model.

The Energy Dashboard does not use raw spot as its displayed price basis.
It uses total import price everywhere for its electricity-price presentation
and household cost calculations.

### 8.2 Import price

Import price is the actual household purchase price.

It includes the configured SBE price components:

-   Nord Pool spot price;
-   supplier markup;
-   energy tax;
-   VAT;
-   variable grid transfer fee.

**All household electricity cost calculations in the Energy Dashboard
MUST use total import price, never spot price.**

This applies to:

-   house cost;
-   consumer cost;
-   cost per period;
-   cost comparisons;
-   cost-based insights;
-   average purchase price;
-   any future cost metric.

Spot price must never be substituted for import price in a cost
calculation.

### 8.3 Export price

Export price represents the value/revenue associated with electricity
exported to the grid.

Export revenue remains a separate economic concept and must not be mixed
into household import cost.

### 8.4 Savings

Savings remain a separate economic concept and must not be silently
treated as either import cost or export income.

------------------------------------------------------------------------

## 9. Price Forecast Contract

Forecast resolution is fixed at:

``` text
15 minutes
```

### 9.1 Forecast horizon

The Energy Dashboard future price horizon is explicitly limited to the
data supplied by the configured Nord Pool integration:

``` text
today + tomorrow
```

No price data may be invented, extrapolated or projected beyond the
available Nord Pool intervals.

If tomorrow's prices are not available, the dashboard must not present
them as known future prices.

The dashboard must respect `tomorrow_available`.

### 9.2 Forecast interval

``` text
PriceInterval {
    start
    end
    spot
    import
    export
    price_class
    price_quality
}
```

No one-entity-per-interval forecast implementation is allowed.

Forecast data remains structured data.

------------------------------------------------------------------------

## 10. Current Price

SBE shall retain existing current import/export price entities where
they already exist.

New functionality must not require breaking or renaming existing
entities.

Price semantics are explicit:

``` text
spot
  = market-price visualization

import
  = household purchase cost

export
  = export revenue
```

------------------------------------------------------------------------

## 11. Price Classification

SBE provides normalized relative price classification.

Conceptual classes:

``` text
VERY_CHEAP
CHEAP
NORMAL
EXPENSIVE
VERY_EXPENSIVE
```

Classification is relative to the available price distribution, not a
fixed SEK/kWh threshold.

The algorithm must be deterministic, specified, tested and documented
before being treated as a stable contract.

------------------------------------------------------------------------

## 12. Price Quality Index

SBE exposes:

``` text
Price Quality Index: 0–100
```

Semantic direction:

``` text
100 = exceptionally favorable / cheap
0   = exceptionally unfavorable / expensive
```

The primary PQI is based on import price.

For future prices, the comparison population is the available price
intervals for today and tomorrow.

PQI is a price-quality metric. It is not the same thing as the Energy
Dashboard Smart Score.

------------------------------------------------------------------------

## 13. Cheapest Future Period

SBE shall be able to identify the cheapest available future price
period.

The result must be derived only from normalized future price data
available from the Nord Pool runtime.

The calculation must never require price data beyond today + tomorrow.

Advanced autonomous optimization/control remains outside this contract.

------------------------------------------------------------------------

## 14. Economy Contract

Existing SBE economy entities remain authoritative.

Where required for the Energy Dashboard, SBE shall provide clearly
defined house-cost values.

### 14.1 Cost rule

The canonical dashboard cost definition is:

``` text
Cost = actual electricity purchase cost
     = imported energy × applicable total import price
```

The following must remain separate:

``` text
actual grid purchase cost
solar avoided cost/value
battery avoided cost/value
export income
savings
opportunity cost
```

Cards must not silently mix these concepts.

------------------------------------------------------------------------

## 15. Generic Consumer Contract

A Consumer is a configurable load that the user wants to analyze against
electricity price.

A Consumer is not a hardcoded device category.

Examples:

-   car;
-   pool;
-   spa;
-   heat pump;
-   washing machine;
-   server;
-   any other measurable load.

### Required

``` text
name
energy_entity
```

### Optional

``` text
power_entity
icon
color
```

The energy entity is the authoritative source for historical energy
analysis.

The optional power entity may be used for real-time display.

SBE should not create or integrate consumer energy from power merely
because a power entity exists.

------------------------------------------------------------------------

## 16. Consumer Configuration

Consumers shall be configurable through Home Assistant Config Flow /
Options Flow.

Consumers belong to the relevant SBE config entry.

The data model must support an arbitrary number of consumers.

The card may impose a practical display limit independently.

There shall be no hardcoded concepts such as EV, SPA or HEATPUMP in the
consumer data model.

Consumer groups are outside V1.

------------------------------------------------------------------------

## 17. Consumer Analysis

For a configured consumer, the system should support:

``` text
Energy
Cost
Average Price
```

Where the data permits:

``` text
Cheap Usage %
Expensive Usage %
```

**Consumer Cost MUST use total import price, never spot price.**

The consumer's original energy entity remains the authoritative source
for its energy history.

------------------------------------------------------------------------

## 18. Historical Data Contract

Historical visualization uses Home Assistant Recorder/statistics/history
mechanisms.

SBE provides correctly classified sensors and persistent cumulative
values.

The Energy Dashboard retrieves historical data through Home Assistant.

The card must not maintain a second persistent history database.

### Dashboard history window

``` text
maximum 24 hours backwards
```

The Energy Dashboard must not request or depend on more than 24 hours of
historical data for its primary timeline/analysis window.

------------------------------------------------------------------------

## 19. Energy Dashboard Future Window

The Energy Dashboard's future price visualization may use:

``` text
current moment
→ remaining available intervals today
→ tomorrow's available intervals
```

Maximum future horizon:

``` text
end of tomorrow's available Nord Pool data
```

There is no 3-day, 7-day or extrapolated price forecast in V1.

------------------------------------------------------------------------

## 20. Energy Dashboard Functional Contract

The approved mockup is the visual/functional target.

It defines:

-   information hierarchy;
-   intended density;
-   visual language;
-   functional intent.

It is not a pixel-perfect implementation requirement.

### Main concepts

#### Live Price

Show:

-   current total import price as the Energy Dashboard price basis;
-   price class;
-   Price Quality Index;
-   current status;
-   relevant near-term price information;
-   cheapest upcoming period.

#### Price Statistics

Support:

-   lowest available price for the defined current-day population;
-   highest available price for the defined current-day population;
-   average available price for the defined current-day population.

The exact statistical population and interval-selection semantics must
be finalized before implementation.

#### Timeline

Primary timeline:

``` text
maximum 24h history
+
current moment
+
available future price data through today + tomorrow
```

Historical data:

-   actual price;
-   actual house consumption;
-   configured consumer usage where available.

Future data:

-   known 15-minute price intervals only.

Historical and future data must be visually distinguishable.

#### Energy and Economy

The dashboard may show:

-   house consumption;
-   import cost;
-   consumer energy;
-   consumer cost;
-   energy shares;
-   battery contribution;
-   other canonical SBE metrics.

All cost values use total import price.

#### Insights

The dashboard may present deterministic analytical insights derived from
canonical data.

Examples include:

-   share of consumption during cheaper-price periods;
-   expensive consumption periods;
-   highest-cost periods;
-   consumer price alignment.

Insight definitions must be specified before implementation.

------------------------------------------------------------------------

## 21. Smart Score

The Energy Dashboard Smart Score is a deterministic 0--100 household
energy/economic behavior metric over the rolling 24-hour analysis window.
It is distinct from Price Quality Index (PQI).

``` text
score =
    0.40 * cheap_usage_percent
  + 0.40 * (100 - expensive_usage_percent)
  + 0.20 * battery_contribution_percent
```

V1 weights:

-   40% cheap usage;
-   40% inverse expensive usage;
-   20% battery contribution.

Consumer Price Alignment is not included in V1.

Score classes:

``` text
90–100  Excellent
75–89   Good
60–74   Fair
40–59   Poor
0–39    Very Poor
```

Edge cases:

-   no house energy → unavailable;
-   no battery data → unavailable;
-   no valid price data → unavailable;
-   valid battery data with zero contribution → 0% contribution;
-   missing price data is never treated as zero.

The implementation must be deterministic, tested and versioned as part of
the stable contract. No card may invent or recalculate Smart Score.

------------------------------------------------------------------------

## 22. Dashboard Analytical Contract

The following analytical definitions are stable V1 contract semantics.

### 22.1 Cheap/expensive usage

Reference: median total import price over the previous 24 hours.

``` text
price < median  → cheap
price = median  → neutral
price > median  → expensive
```

Percentages are energy-weighted over energy with valid price data.

### 22.2 Cost periods

Cost period resolution is 15 minutes.

``` text
period_cost = house_energy_kwh × total_import_price
```

Highest cost selects the maximum valid period. Lowest cost selects the
minimum valid period with energy > 0. Ties select the earliest interval.

### 22.3 Battery contribution

``` text
battery_house_energy / house_total_energy × 100
```

The metric is undefined when house energy is zero.

### 22.4 Consumer Price Alignment

``` text
house_average_import_price - consumer_average_import_price
```

Positive means the consumer's average import price was lower than the house
average. This is a SEK/kWh delta, not a score.

### 22.5 Consumer events

Events are derived only from actual Recorder/history data. Cumulative energy
alone cannot establish exact event timing.

## 23. Card Responsibilities

### Solar Battery Economy

Responsible for:

-   data ingestion;
-   canonical energy flow calculations;
-   accumulation;
-   economy calculations;
-   persistence;
-   price normalization;
-   price intelligence;
-   consumer configuration/metadata;
-   canonical analytical definitions.

### Solar Battery Economy Flow Card

Responsible for:

-   real-time visualization;
-   energy flow rendering;
-   presentation and interaction.

Its primary role is:

> What is happening with power right now?

### Energy Dashboard

Responsible for:

-   energy summary;
-   economy summary;
-   price visualization;
-   historical price + consumption visualization;
-   future price visualization;
-   consumer analysis;
-   presentation of price intelligence;
-   deterministic insight presentation.

Its primary role is:

> What happened, what did it cost, and how is it going?

### Phase Load Card

Remains focused on phase loading and electrical installation
visualization.

------------------------------------------------------------------------

## 23. Dashboard Design Rules

The Energy Dashboard should make the following immediately apparent:

1.  Is electricity cheap or expensive now?
2.  What happened to consumption when prices changed?
3.  When is the next favorable period?
4.  How much did selected loads consume?
5.  What did that consumption cost?
6.  How well did selected loads align with electricity prices?
7.  What meaningful insight can be derived from the last 24 hours?

The dashboard should favor visual comprehension over displaying large
numbers of individual metrics simultaneously.

------------------------------------------------------------------------

## 24. Backward Compatibility

The following are protected:

-   existing entity unique IDs;
-   existing entity meanings;
-   existing units;
-   existing energy semantics;
-   existing accumulated values;
-   existing persistent state behavior.

Changes must be additive wherever reasonably possible.

If an existing sensor must change for correctness, the migration impact
must be identified before implementation.

No existing entity should be removed or repurposed silently.

------------------------------------------------------------------------

## 25. V1 Explicit Boundaries

The following are outside V1 unless the scope is formally changed:

-   automatic EV charging control;
-   automatic battery control;
-   automatic appliance control;
-   autonomous energy optimization;
-   AI-based control;
-   consumer groups;
-   multi-hour autonomous optimal charging control;
-   a second persistent history database;
-   hardcoded appliance categories;
-   replacing the existing SBE architecture wholesale;
-   merging the separate Lovelace repositories;
-   price forecasts beyond today + tomorrow;
-   historical dashboard analysis beyond 24 hours.

------------------------------------------------------------------------

## 26. FAS 3.1 Prerequisites

Before implementation:

1.  Exact entity names for new SBE entities.
2.  Exact device classes and state classes.
3.  Exact house-cost definition.
4.  Exact price-class boundaries.
5.  Exact PQI mathematical algorithm.
6.  Exact structured forecast exposure mechanism.
7.  Exact Config Flow representation for Consumers.
8.  Migration/backward-compatibility behavior.
9.  Restore-state behavior for new cumulative entities.
10. Unit and rounding conventions.
11. Exact Smart Score definition.
12. Exact price-statistics population.
13. Exact 24h historical aggregation semantics.
14. Exact consumer cost semantics.
15. Exact deterministic insight definitions.

------------------------------------------------------------------------

## 27. Source of Truth Rule

If a future implementation decision conflicts with this document, the
document wins unless the user explicitly approves a change.

Any approved change to the contract must update this document before or
together with the corresponding implementation.

------------------------------------------------------------------------

## 28. Implementation Status

``` text
FAS 0 — Project Definition          COMPLETE / FROZEN
FAS 1 — Data Gap Analysis           COMPLETE / APPROVED
FAS 2A — Architecture Decisions     COMPLETE / FROZEN
FAS 2B — Energy Data Contract       UPDATED / FROZEN
FAS 3 — SBE Implementation          ANALYTICAL V1 IMPLEMENTED / TESTED
FAS 3.1 — Dashboard Data Spec       IMPLEMENTATION-ALIGNED / FROZEN
```

**Next approved step:** use the implementation-aligned contract as the data boundary for the Energy Dashboard UI. Remaining presentation decisions must not introduce competing business logic.
