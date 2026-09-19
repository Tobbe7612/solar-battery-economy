# Energy Dashboard Data Specification

**Project:** Solar Battery Economy ecosystem\
**Document status:** FAS 3.1 --- WORKING SPECIFICATION\
**Version:** 1.0\
**Purpose:** Define exactly what the new Energy Dashboard needs before
UI implementation begins.

------------------------------------------------------------------------

# 1. Product Goal

The Energy Dashboard answers:

> **What happened, what did it cost, and how is it going?**

It is complementary to:

-   Solar Battery Economy Flow Card --- live power flows;
-   Phase Load Card --- phase loading.

The dashboard is a presentation client of SBE + Home Assistant Recorder.

------------------------------------------------------------------------

# 2. Non-Negotiable Data Rules

## 2.1 Historical horizon

The dashboard uses:

``` text
maximum 24 hours backwards
```

No dashboard feature may require more than 24 hours of historical data
for the primary dashboard analysis.

## 2.2 Future price horizon

Future price data is limited to:

``` text
today + tomorrow
```

More precisely:

``` text
from the current moment
to the end of the available upstream Nord Pool price data
```

If tomorrow's prices are unavailable, they are not displayed as known
future prices.

## 2.3 Cost semantics

**Every cost shown by the Energy Dashboard uses total import price.**

Never use spot price for cost.

``` text
spot
→ market-price visualization

import
→ actual household purchase cost

export
→ export revenue
```

## 2.4 Upstream price source

The existing Nord Pool template is unchanged.

The dashboard consumes the normalized SBE price model.

------------------------------------------------------------------------

# 3. Status Legend

``` text
GREEN  = already available and verified
YELLOW = partially available / needs verification
RED    = missing canonical capability
WHITE  = presentation only
```

------------------------------------------------------------------------

# 4. Dashboard Component Matrix

## 4.1 Live Price Header

  Component                  Required data                Status Owner
  -------------------------- -------------------------- -------- -------
  Current spot price         current `spot`                GREEN SBE
  Price class                `current_price_class`         GREEN SBE
  Price Quality Index        `price_quality_index`         GREEN SBE
  Current status text        class/PQI interpretation     YELLOW SBE
  Current visual gauge       price data                    WHITE Card
  Stars/quality indicator    PQI presentation              WHITE Card
  Cheapest upcoming period   `cheapest_future_period`      GREEN SBE

### Definition issue

The mockup's prominent current price is a spot-price presentation.

The dashboard must label or otherwise clearly communicate that it is
spot price.

Economic cost displays remain based on import price.

------------------------------------------------------------------------

# 5. Price Statistics

Mockup elements:

``` text
Lowest Today
Highest Today
Average Price
```

### Required

``` text
minimum spot price
maximum spot price
average spot price
```

### Status

YELLOW.

The raw intervals exist, but the exact statistical population must be
frozen.

Questions to resolve:

-   Does "today" mean midnight → current moment?
-   Does it include remaining known intervals today?
-   Does the average include future today intervals?
-   Are low/high times based on a single 15-minute interval or an
    aggregated continuous period?
-   Are values displayed in öre/kWh with a fixed rounding rule?

Recommended default for the mockup:

``` text
current calendar day
known intervals only
spot price
```

This recommendation requires approval before implementation.

------------------------------------------------------------------------

# 6. Smart Score

Mockup:

``` text
Smart Score
91 / 100
Excellent
```

### Status

RED.

Smart Score must be defined separately from PQI.

Required before implementation:

``` text
inputs
weights
normalization
score range
classification
edge cases
tests
```

Possible conceptual inputs may include:

-   cheap-use percentage;
-   expensive-use percentage;
-   consumer price alignment;
-   energy-use efficiency indicators;
-   battery contribution.

These are candidates only until the algorithm is approved.

------------------------------------------------------------------------

# 7. Main Timeline

## 7.1 Time structure

``` text
<---------------- 24h history ---------------->
                                                  NOW
                                                    |
                                                    +---- available today ----+
                                                    |                         |
                                                    +--------- tomorrow ------+
```

The exact future endpoint is dynamic.

It is never assumed to be a fixed 48-hour future window.

## 7.2 Historical layers

Required:

-   spot price history;
-   actual house consumption;
-   optional consumer energy history;
-   relevant event markers where data exists.

Source:

``` text
Home Assistant Recorder/statistics/history
```

## 7.3 Future layers

Required:

-   15-minute spot price intervals;
-   price class;
-   PQI/price quality;
-   known future intervals only.

Source:

``` text
SBE normalized Price Model
```

Historical and future data must be visually distinguishable.

------------------------------------------------------------------------

# 8. House Consumption

Required canonical value:

``` text
house_total =
    solar_house
  + battery_house
  + grid_house
```

Unit:

``` text
kWh
```

Semantics:

``` text
device_class: energy
state_class: total_increasing
```

### Dashboard use

-   24h consumption;
-   timeline consumption;
-   cheap/expensive usage analysis;
-   cost correlation.

### Status

GREEN for canonical cumulative value.

YELLOW for derived 24h presentation aggregation, which must use
Recorder/history/statistics.

------------------------------------------------------------------------

# 9. 24h Cost

Mockup/dashboard requirement:

``` text
Cost — last 24h
```

### Definition

``` text
actual imported electricity cost
```

using:

``` text
total import price
```

Never spot price.

### Status

YELLOW.

The exact aggregation path and canonical SBE representation must be
verified before implementation.

------------------------------------------------------------------------

# 10. Cheap Usage %

Example insight:

``` text
You used 72% of your electricity
during cheaper-than-average prices.
```

### Required inputs

-   house consumption;
-   price intervals;
-   total import price or the defined price basis;
-   defined threshold/statistical population.

### Status

RED.

Definition must be frozen.

A likely definition:

``` text
cheap consumption
=
consumption occurring during intervals classified
as cheaper than the defined daily reference
```

This is only a candidate until approved.

------------------------------------------------------------------------

# 11. Consumer Analysis

Consumers are generic.

Examples:

``` text
Bil
Spa
Värmepump
Appliance
```

Required conceptual data:

``` text
energy
cost
average_price
cheap_usage_percent
expensive_usage_percent
```

### Cost rule

Consumer cost uses:

``` text
total import price
```

### Historical source

The configured consumer energy entity is authoritative.

### Status

YELLOW/RED depending on metric.

------------------------------------------------------------------------

# 12. Consumer Timeline Events

Mockup may show event blocks for:

-   car charging;
-   battery activity;
-   spa;
-   heat pump.

### Requirement

Events must be derived from actual available entity history/data.

The dashboard must not invent event timing.

### Status

RED for generic consumer event modeling.

A first implementation may derive simple event intervals from historical
energy/power availability if the data supports it.

The exact event model must be defined before UI implementation.

------------------------------------------------------------------------

# 13. Battery Analysis

Potential dashboard metrics:

-   battery energy contribution;
-   battery charge/discharge;
-   battery-related cost/savings;
-   battery share of house consumption.

Existing SBE battery analytics remain authoritative.

### Status

GREEN/YELLOW depending on the exact mockup metric.

No competing battery calculation is allowed in the card.

------------------------------------------------------------------------

# 14. Upcoming Cheapest Period

Existing SBE price intelligence provides:

``` text
cheapest_future_period
```

The period is constrained by available future data.

### Status

GREEN.

The dashboard presents the result.

The card does not recalculate it.

------------------------------------------------------------------------

# 15. Insights

Initial deterministic insight categories:

``` text
cheap_consumption
expensive_consumption
highest_cost_period
lowest_cost_period
consumer_cost
consumer_share
consumer_price_alignment
```

### Status

RED.

Each insight must have:

-   deterministic inputs;
-   explicit calculation;
-   stable output structure;
-   tests.

The dashboard only presents the resulting insight.

------------------------------------------------------------------------

# 16. Data Ownership Matrix

  Data                         Source                         Card calculates?
  ---------------------------- --------------------------- -------------------
  Current spot                 SBE price model                              No
  Current import               SBE price model                              No
  Price class                  SBE                                          No
  PQI                          SBE                                          No
  Cheapest period              SBE                                          No
  House total                  SBE                                          No
  Historical house energy      Recorder                      No business logic
  Consumer energy history      Recorder                      No business logic
  Import cost                  SBE/canonical calculation                    No
  Consumer cost                SBE/canonical calculation                    No
  Smart Score                  SBE                                          No
  Insights                     SBE                                          No
  Gauge rendering              Dashboard                                   Yes
  Timeline rendering           Dashboard                                   Yes
  Layout/responsive behavior   Dashboard                                   Yes

------------------------------------------------------------------------

# 17. Required SBE Gaps

Before dashboard design, the following gaps must be resolved or
explicitly waived:

## RED

1.  Smart Score definition.
2.  Cheap-use percentage.
3.  Expensive-use percentage.
4.  Highest-cost consumption period.
5.  Deterministic insights.
6.  Generic consumer analysis where not already available.
7.  Consumer event model.

## YELLOW

1.  Lowest/highest/average price statistics.
2.  24h house cost aggregation.
3.  24h consumer cost aggregation.
4.  Exact battery dashboard metrics.
5.  Current status interpretation.
6.  Historical Recorder aggregation semantics.

## GREEN

1.  Normalized price source.
2.  Spot/import/export separation.
3.  Price classes.
4.  PQI.
5.  Cheapest future period.
6.  House Total canonical energy.
7.  Existing SBE directional flows.
8.  Existing economy/savings foundation.

------------------------------------------------------------------------

# 18. Definition Decisions Before Coding

The following decisions must be explicitly frozen:

### Price statistics

-   population;
-   spot vs import;
-   today boundary;
-   average formula;
-   low/high period selection.

### House cost

-   exact imported-energy calculation;
-   handling of unavailable price;
-   rounding.

### Consumer cost

-   same total-import-price rule;
-   exact historical aggregation.

### Cheap/expensive usage

-   reference population;
-   threshold/classification;
-   treatment of equal-to-reference values.

### Smart Score

-   formula;
-   components;
-   weights;
-   score classes.

### Insights

-   exact insight types;
-   trigger conditions;
-   output structure;
-   ranking.

------------------------------------------------------------------------

# 19. V1 Boundaries

Not part of this specification:

-   automatic battery control;
-   automatic EV charging;
-   autonomous optimization;
-   AI control;
-   price forecast beyond tomorrow;
-   dashboard history beyond 24h;
-   second persistent history database;
-   hardcoded consumer categories;
-   merging card repositories.

------------------------------------------------------------------------

# 20. Definition of Ready for Dashboard Design

The Energy Dashboard is ready for UI design only when:

-   all RED data gaps required for V1 are resolved;
-   all YELLOW definition decisions are frozen;
-   cost semantics are verified as total import price;
-   24h historical boundary is enforced;
-   future price boundary is enforced;
-   Smart Score is defined;
-   insight outputs are defined;
-   consumer data contract is stable;
-   SBE tests pass;
-   no card business logic is required to compensate for missing
    canonical data.

------------------------------------------------------------------------

# 21. Current Status

``` text
Mockup                     APPROVED
Architecture               APPROVED
Cost semantics             LOCKED
History horizon            LOCKED — max 24h
Future price horizon       LOCKED — today + tomorrow
Nord Pool template         LOCKED / UNCHANGED

Next:
Definition Decisions
→ Data Gap Matrix finalization
→ SBE implementation scope
→ tests
→ SBE implementation
→ dashboard UI design
```
