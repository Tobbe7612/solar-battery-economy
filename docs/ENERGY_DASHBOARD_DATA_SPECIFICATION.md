# Energy Dashboard Data Specification

**Project:** Solar Battery Economy ecosystem\
**Document status:** FAS 3.1 --- IMPLEMENTATION-ALIGNED V1 SPECIFICATION\
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

**The Energy Dashboard uses total import price as its primary displayed electricity price.**

All household cost calculations also use total import price.

``` text
import
→ primary dashboard electricity price
→ actual household purchase cost

export
→ export revenue

spot
→ retained raw market-price source data; not used as the dashboard price basis
```

## 2.4 Upstream price data

SBE selects a configured Nord Pool integration and market area. Its runtime
fetches current, forecast, and historical market intervals directly.

The dashboard consumes the normalized SBE price model. Historical dashboard
windows are limited to 24 hours; unavailable historical intervals remain
missing rather than being filled from another sensor.

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
  Current import price      current `import`             GREEN SBE
  Price class                `current_price_class`         GREEN SBE
  Price Quality Index        `price_quality_index`         GREEN SBE
  Current status text        class/PQI interpretation     YELLOW SBE
  Current visual gauge       price data                    WHITE Card
  Stars/quality indicator    PQI presentation              WHITE Card
  Cheapest upcoming period   `cheapest_future_period`      GREEN SBE

### Definition

The dashboard's prominent current price is **total import price**.

The displayed price therefore represents the household purchase price, not
raw Nord Pool spot price.

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
minimum total import price
maximum total import price
average total import price
```

### Status

DEFINITION FROZEN.

The population is the current calendar day from `00:00` through the
current moment. Only intervals that have actually elapsed are included.
Future intervals for the remainder of today are excluded.

The statistic basis is **total import price**.

-   lowest = minimum total-import value in the population;
-   highest = maximum total-import value in the population;
-   average = arithmetic mean of the included total-import values;
-   low/high period resolution = normalized 15-minute interval.

Business calculations retain full precision. Presentation rounding belongs
to the dashboard and must not alter the underlying calculation.

------------------------------------------------------------------------

# 6. Smart Score

Mockup:

``` text
Smart Score
91 / 100
Excellent
```

### Status

DEFINITION FROZEN — implementation remains to be added and tested.

Smart Score is distinct from PQI. It evaluates household energy/economic
usage behavior over the dashboard's rolling 24-hour analysis window.

### V1 inputs and weights

``` text
40%  cheap usage
40%  inverse expensive usage
20%  battery contribution
```

Formula:

``` text
score =
    0.40 * cheap_usage_percent
  + 0.40 * (100 - expensive_usage_percent)
  + 0.20 * battery_contribution_percent
```

The result is constrained to the range `0..100`.

Consumer Price Alignment is explicitly **not** part of Smart Score V1.

### V1 score classes

``` text
90–100  Excellent
75–89   Good
60–74   Fair
40–59   Poor
0–39    Very Poor
```

### Edge cases

-   no house energy → Smart Score unavailable;
-   no battery data → Smart Score unavailable;
-   no valid price data → Smart Score unavailable;
-   valid battery data with zero battery contribution → 0% contribution;
-   missing price data is never treated as zero.

The calculation must be deterministic, unit-tested and implemented in SBE.
No card may invent or recalculate the Smart Score.

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

-   total import-price history;
-   actual house consumption;
-   optional consumer energy history;
-   relevant event markers where data exists.

Source:

``` text
Home Assistant Recorder/statistics/history
```

## 7.3 Future layers

Required:

-   15-minute total import-price intervals;
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
  Current import price        SBE price model                              No
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
2.  Import/export separation; raw spot remains available in the normalized source model.
3.  Price classes.
4.  PQI.
5.  Cheapest future period.
6.  House Total canonical energy.
7.  Existing SBE directional flows.
8.  Existing economy/savings foundation.

------------------------------------------------------------------------

# 18. Definition Decisions — Frozen

The following decisions are now frozen for FAS 3 V1.

## 18.1 Cost and price basis

-   **Total import price is the Energy Dashboard price basis everywhere.**
-   Raw spot remains part of the normalized source model but is not used as the dashboard price basis or for dashboard statistics.
-   Export price represents export revenue and is kept separate from cost.
-   Nord Pool integration settings are managed in Home Assistant.

## 18.2 Historical and future windows

-   Primary dashboard history is a rolling `now - 24h` → `now` window.
-   Future price data is limited to currently available data for today and
    tomorrow.
-   No interpolation, extrapolation, guessed values or stale future values
    are permitted.

## 18.3 House and consumer cost

For each valid normalized price interval:

``` text
cost = energy_kwh × total_import_price
```

House and consumer calculations use the same price rule. Consumer energy
comes from the configured HA energy entity and remains authoritative.
Different Recorder/statistics sampling resolutions must be handled without
assuming that every source produces exactly 15-minute samples.

## 18.4 Weighted average import price

``` text
average_import_price =
    sum(energy_kwh × import_price) / sum(energy_kwh)
```

Zero-energy intervals do not contribute to the denominator. Energy paired
with missing price data is excluded from price-dependent averages.

## 18.5 Cheap and expensive usage

The shared reference is the **median total import price over the previous
24 hours**.

``` text
price < median  → cheap
price = median  → neutral
price > median  → expensive
```

Percentages are energy-weighted. The denominator contains only energy with
valid price data. Cheap and expensive percentages therefore do not have to
sum to 100% because median-equal intervals are neutral.

The same definition applies to house and configured consumers.

## 18.6 Cost periods

Cost-period resolution is 15 minutes and is aligned to normalized price
intervals.

``` text
period_cost = house_energy_kwh × total_import_price
```

-   highest-cost period = maximum valid period cost;
-   lowest-cost period = minimum valid period cost among periods with
    energy > 0;
-   zero-energy periods are excluded from the lowest-cost selection;
-   ties are resolved by selecting the earliest interval.

These are cost metrics, not highest/lowest price metrics.

## 18.7 Battery contribution

For the same rolling 24-hour dashboard window:

``` text
battery_contribution_percent =
    battery_house_energy / house_total_energy × 100
```

If house consumption is zero, the metric is unavailable. The metric is an
energy contribution, not battery savings, avoided value, charge energy or
discharge energy.

## 18.8 Consumer Price Alignment

``` text
alignment_delta =
    house_average_import_price - consumer_average_import_price
```

Unit: SEK/kWh.

-   positive = consumer used electricity at a lower average import price
    than the house average;
-   zero = equal;
-   negative = consumer used electricity at a higher average import price.

This is a transparent delta, not a score, and is excluded from Smart Score
V1.

## 18.9 Missing historical price data

Missing or invalid price data is never converted to zero and never
interpolated or guessed. Price-dependent calculations exclude the affected
energy from their valid denominator. The implementation must expose enough
coverage information internally to distinguish complete from incomplete
price-dependent analysis.

## 18.10 Deterministic insight model

Initial V1 insight types are:

``` text
cheap_consumption
expensive_consumption
highest_cost_period
lowest_cost_period
consumer_cost
consumer_share
consumer_price_alignment
```

Insights are deterministic facts derived from canonical metrics. They must
not contain autonomous recommendations or inferred intent.

The cost-period insights use the exact period definitions above. Consumer
share is:

``` text
consumer_energy_24h / house_energy_24h × 100
```

It is an energy share, not a cost share.

## 18.11 Consumer events

Consumer events must be derived from actual Recorder/history data. A generic
event may contain `consumer_id`, `start`, `end`, `energy` and optional
`average_power`/`max_power`.

Cumulative energy alone does not establish exact event timing. Event timing
may only be exposed when the source resolution supports it.

## 18.12 Rounding

Business calculations are performed without presentation rounding. Display
rounding is a dashboard responsibility. Serialized analytical values may use
the implementation's documented numeric precision, but rounding must not
change classification, weighting, selection or score calculations.

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
Smart Score                IMPLEMENTED / TESTED / FROZEN
Consumer analysis          DEFINED / FROZEN
Cost-period semantics      DEFINED / FROZEN
Insight categories         DEFINED / FROZEN
Nord Pool integration      CONFIGURED IN HOME ASSISTANT

Next:
Implementation-aligned documentation and dashboard UI design
→ implementation scope review
→ tests for frozen definitions
→ SBE implementation
→ persistence/regression verification
→ documentation verification
→ dashboard UI design
```
