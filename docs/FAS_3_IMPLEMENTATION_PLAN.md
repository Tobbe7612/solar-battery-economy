# FAS 3 — SBE Implementation & Migration Plan

**Project:** Solar Battery Economy  
**Status:** PLANNING — no implementation changes made  
**Source of Truth:** `docs/ENERGY_DATA_CONTRACT.md`  
**Current code baseline:** SBE 1.4.0  
**Planning revision:** Dashboard-driven implementation plan

---

## 1. Purpose

This document defines the implementation plan for extending Solar Battery Economy into the central data/intelligence engine for:

- Solar Battery Economy Flow Card
- Energy Intelligence Card
- future/common data needs of Phase Load Card

The primary objective of FAS 3 is **not to redesign the cards**. The first objective is to identify and implement the canonical data that the new dashboard requires and that SBE does not currently provide.

The plan is deliberately incremental.

The existing SBE architecture is preserved wherever practical. The objective is to add the minimum required capabilities without breaking existing users, entities, accumulated values or historical continuity.

No code change should be made outside the approved scope in this document without explicitly updating the project plan.

---

# 2. Current Baseline

The supplied SBE 1.4.0 implementation contains:

- Config Flow
- Coordinator
- event-driven updates
- eight directional power flows
- eight accumulated energy flows
- persistent Store for accumulated energy/money
- economy/savings calculations
- battery-origin money attribution
- current import/export price sensors
- battery/economy analytics
- Advanced Mode
- diagnostic price-data counter

Current implementation files:

```text
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
└── strings.json
```

---

# 3. Implementation Principles

## 3.1 Dashboard-first

FAS 3 is driven by the actual data requirements of the new dashboard.

Before implementing a capability, we ask:

1. Does the dashboard require this data?
2. Does SBE already provide it?
3. Can an existing SBE entity satisfy the requirement?
4. If not, what is the smallest canonical addition required?

This prevents implementing attractive but unnecessary functionality before the dashboard can use the data.

## 3.2 Additive first

Prefer adding new entities/data structures over modifying existing public entities.

## 3.3 Preserve existing entity identity

Do not change existing unique IDs, names, units or semantics unless a documented migration is unavoidable.

## 3.4 Do not rebuild SBE

The existing coordinator/flow/economy architecture is retained.

## 3.5 Separate data ownership

```text
SBE
  = canonical calculations + normalized data

HA Recorder
  = historical storage

Lovelace cards
  = visualization + presentation
```

## 3.6 No card-specific business logic in the cards

The cards should consume canonical SBE data.

## 3.7 Avoid sensor explosion

High-cardinality data such as 15-minute forecast intervals must be represented as structured data, not one entity per interval.

## 3.8 Test every persistence-sensitive change

Existing energy/money persistence is a critical part of the integration.

## 3.9 Configuration belongs with SBE

Where the dashboard currently requires the user to manually provide a data source that logically belongs to the SBE data model, that configuration should progressively move into the SBE Config Flow / Options Flow.

The goal is that cards consume SBE's canonical configuration rather than maintaining duplicate device configuration.

---

# 4. Dashboard Data Gap Analysis — FAS 3 Driver

The new dashboard is the primary consumer of the expanded SBE data model.

The following categories have been identified as the relevant gaps or consolidation opportunities.

## 4.1 Already available in SBE

The following core energy-flow information already exists and should be reused:

- Solar → House
- Solar → Battery
- Solar → Grid
- Battery → House
- Battery → Grid
- Grid → House
- Grid → Battery
- House → Grid

The existing eight directional power flows and accumulated energy flows remain part of the public compatibility surface.

The dashboard must not recreate these calculations independently.

## 4.2 Data that should become canonical in SBE

The dashboard requires or benefits from canonical versions of:

### House

- total house energy
- house power, where derivable from existing canonical flows
- house cost/economic interpretation

### Price

- current normalized price
- import price
- export price
- structured future price data
- price classification
- Price Quality Index
- cheapest future period

### Consumers

For configured consumers:

- name
- energy entity
- optional power entity
- optional icon
- optional presentation metadata
- energy
- cost
- average price
- supported cheap/expensive usage metrics
- SOC where a suitable source exists

### Consumer configuration

The dashboard currently has consumers such as the car configured separately.

The target architecture is that relevant consumer configuration is owned by SBE and exposed to cards through the SBE data model.

This includes the car and other configurable consumers, but does **not** mean that SBE should contain hardcoded EV, spa, heat-pump or other device-specific logic.

## 4.3 SOC

State of Charge must be treated as a first-class optional consumer attribute where an appropriate source exists.

Example:

```text
Consumer
├── name
├── energy_entity
├── power_entity
├── soc_entity       optional
├── icon              optional
└── presentation     optional
```

SOC is primarily presentation/current-state information. It must not be confused with the authoritative historical energy entity.

SBE should not invent SOC from power or energy unless a separate, explicitly defined calculation is later approved.

## 4.4 Data that remains presentation-owned

The following remain card responsibilities:

- visual layout
- animations
- SVG rendering
- node appearance
- flow animation
- responsive layout
- dashboard-specific visual grouping
- visual status indicators derived from canonical SBE data

SBE supplies the data; the card decides how to display it.

---

# 5. Phase 3.1 — Establish Test/Baseline Foundation

## Objective

Protect SBE 1.4.0 before making implementation changes.

The development branch must contain a known-good baseline.

Required baseline:

```text
SBE 1.4.0
        |
        v
regression tests
        |
        v
new FAS 3 development
```

Before production behavior is changed:

- establish the existing test structure;
- capture the current public sensor semantics;
- verify existing flow calculations;
- verify persistence behavior;
- verify current price behavior;
- verify current configuration keys.

No feature implementation should be mixed into this step.

---

# 6. Phase 3.2 — Internal Data Model Preparation

## Objective

Introduce a clean internal data model without changing public behavior.

Coordinator data will evolve from:

```python
{
    "power": {},
    "energy": {},
    "money": {},
    "savings": {},
}
```

toward a structured model that can also contain:

```text
price
price_intelligence
consumers
house
```

The exact Python representation will be selected during implementation based on Home Assistant compatibility and testability.

### Important

Existing keys under:

```text
power
energy
money
savings
```

must remain compatible with current sensors.

---

# 7. Phase 3.3 — Canonical House Energy

## Objective

Expose total house consumption as a first-class SBE energy entity.

Definition:

```text
house_total =
    solar_house
  + battery_house
  + grid_house
```

### New entity

Conceptual name:

```text
Energy House Total
```

Required semantics:

```text
unit: kWh
device_class: energy
state_class: total_increasing
```

It must use the same persistent accumulation model as the existing energy sensors.

### No change

The existing eight energy-flow entities remain untouched.

---

# 8. Phase 3.4 — Price Source Adapter

## Objective

Allow SBE to consume the user's existing structured Nord Pool template sensor.

The current upstream source provides current data plus structured future intervals containing fields such as:

```text
start
end
spot
import
export
```

Architecture:

```text
User's structured Nord Pool template sensor
                    |
                    v
              SBE Price Adapter
                    |
                    v
             normalized Price Model
                    |
                    v
             dashboard consumers
```

### Important

The cards must not depend on the user's specific template sensor name.

The source entity must be configurable.

### Compatibility

The existing current import/export price configuration remains valid.

We should extend configuration rather than silently replace the current price inputs.

---

# 9. Phase 3.5 — Price Intelligence

## Objective

Add canonical price interpretation required by the dashboard.

Required concepts:

```text
current_price_class
price_quality_index
cheapest_future_period
```

Classes:

```text
VERY_CHEAP
CHEAP
NORMAL
EXPENSIVE
VERY_EXPENSIVE
```

PQI:

```text
0–100
```

where higher means better/cheaper.

## Algorithm

The exact percentile/boundary algorithm must not be invented during coding.

It must be:

1. specified;
2. unit-tested;
3. documented;
4. then considered part of the stable contract.

## Forecast

The normalized forecast contains:

```text
start
end
spot
import
export
price_class
price_quality
```

No 96 forecast entities.

---

# 10. Phase 3.6 — Generic Consumer Configuration

## Objective

Move relevant dashboard consumer configuration into SBE.

Conceptual model:

```text
Consumer
├── name
├── energy_entity       required
├── power_entity        optional
├── soc_entity          optional
├── icon                optional
└── presentation        optional
```

Use Config Flow / Options Flow.

Consumers belong to the relevant SBE config entry.

Example:

```text
name: Bil
energy_entity: sensor.ev_energy
power_entity: sensor.ev_power
soc_entity: sensor.ev_soc
icon: mdi:car
```

### Rules

- Energy entity is authoritative for historical analysis.
- Power entity is optional and intended for live display.
- SOC is optional and represents current battery state where available.
- SBE does not create energy by integrating consumer power in V1.
- Consumer groups are out of scope.
- No hardcoded EV/spa/heat-pump logic.

## Migration principle

Existing card configuration must continue to work during the transition.

The migration path should be:

```text
existing Flow Card consumer config
              |
              v
SBE Consumer configuration
              |
              v
Flow Card reads SBE configuration
```

Only after the SBE representation is verified should redundant card configuration be removed.

---

# 11. Phase 3.7 — Consumer Analysis

For each configured consumer, provide a canonical basis for:

```text
energy
cost
average_price
```

Where supported by the available data:

```text
cheap_usage_percent
expensive_usage_percent
```

The first implementation should prioritize correctness and a clear data contract over sophisticated optimization.

SOC remains separate from historical energy/cost analysis unless a future feature explicitly defines a calculation involving SOC.

---

# 12. Phase 3.8 — House Economy Definition

Before exposing a new House Cost entity, finalize the exact semantic definition.

Do not simply add together unrelated SBE money values.

The implementation must distinguish:

```text
actual grid purchase cost
solar avoided cost/value
battery avoided cost/value
export income
savings
```

A formal test matrix is required before this becomes a public sensor.

The dashboard should consume one clearly defined canonical house-cost value rather than independently reconstructing it from several money sensors.

---

# 13. Existing Known Issue — Must Be Addressed Deliberately

The current helper `_float_state()` converts:

```text
unknown
unavailable
invalid
```

to:

```text
0.0
```

while coordinator money-booking logic checks for `None`.

Therefore the intended "do not book money when price is unavailable" behavior is not fully aligned with the helper contract.

This is a correctness issue and must be resolved before the new price-dependent logic is considered stable.

It must be fixed deliberately, not as incidental cleanup.

---

# 14. Persistence and Migration Plan

Every new cumulative sensor must survive restart.

Tests must cover:

```text
before restart
      |
      v
restart HA
      |
      v
after restart
```

Expected:

- energy totals unchanged except for legitimate post-restart accumulation;
- money totals unchanged except for legitimate post-restart accumulation;
- install date preserved;
- no artificial energy spike;
- no reset to zero.

Existing Store schema must remain compatible.

If the Store schema needs to change, implement an explicit migration rather than silently replacing stored data.

---

# 15. Config Flow Migration

Current Config Flow has five required input entities.

We must preserve the current setup experience as much as practical.

New configuration sections are expected to include:

```text
Price intelligence source
Consumers
```

Consumer configuration should support, where applicable:

```text
energy_entity
power_entity
soc_entity
icon
```

The exact UI is to be designed after inspecting the current Home Assistant Config Flow APIs and supported selectors for the target Home Assistant version.

### Important

Do not remove or rename existing configuration keys.

---

# 16. Sensor Implementation Strategy

Existing `EnergySensor`, `MoneySensor`, `FlowPowerSensor` and economy sensor classes should be reused where semantics match.

Avoid creating many one-off classes if a generic, well-defined base class can represent the new sensor type safely.

New sensor classes are justified where the Home Assistant semantics differ materially.

Structured forecast and consumer configuration should remain structured data wherever possible rather than generating unnecessary entities.

---

# 17. Dashboard Integration Boundary

The dashboard integration happens **after the required SBE data exists and has been verified**.

The sequence is:

```text
SBE data gap
    |
    v
canonical SBE implementation
    |
    v
unit/integration/persistence tests
    |
    v
Flow Card consumes SBE data
    |
    v
remove redundant card configuration only when safe
```

The Flow Card is therefore a consumer of SBE, not a second calculation engine.

The same principle applies to the future Energy Intelligence Card.

---

# 18. Documentation Updates During Implementation

When FAS 3 implementation starts, documentation must be updated together with code.

Expected documents:

```text
docs/
├── ENERGY_DATA_CONTRACT.md
├── ARCHITECTURE_NOTES.md
├── V1.4.0_CODE_AUDIT.md
├── DEVELOPMENT_WORKFLOW.md
└── ...
```

New documents should only be created when they contain stable, useful information.

The root README should be updated only when user-facing behavior changes.

---

# 19. Testing Plan

Before declaring the SBE implementation complete:

## Unit tests

- existing flow calculations
- house total calculation
- price normalization
- price classification
- PQI
- cheapest period
- consumer calculations
- SOC configuration/handling
- house-cost calculation

## Integration/config tests

- fresh install
- existing configuration
- options flow
- consumer addition
- consumer removal/update
- invalid entity
- unavailable entity
- unavailable SOC entity
- price source unavailable

## Persistence tests

- energy restore
- money restore
- install date restore
- new house total restore
- migration from existing Store

## Runtime tests

- normal power updates
- price changes
- 15-minute price changes
- unavailable price
- unavailable consumer
- unavailable SOC
- Home Assistant restart

## Dashboard contract tests

Verify that the canonical SBE data required by the new dashboard is available without the card having to reproduce business logic.

---

# 20. Implementation Order

The revised coding order is intentionally dashboard-driven:

```text
1. Establish tests / baseline
        |
        v
2. Internal data model
        |
        v
3. Canonical House Total Energy
        |
        v
4. Price source adapter
        |
        v
5. Price intelligence
        |
        v
6. Generic Consumer configuration
        |
        v
7. Consumer analysis + SOC
        |
        v
8. Canonical House Cost
        |
        v
9. Verify SBE dashboard data contract
        |
        v
10. Integrate Flow Card with SBE-owned configuration/data
        |
        v
11. Persistence / migration verification
        |
        v
12. Full regression test
        |
        v
13. Documentation / release preparation
```

### Critical sequencing rule

We do **not** begin by rewriting the Flow Card.

We first make SBE capable of supplying the data the new dashboard actually needs.

No dashboard visual rewrite occurs as part of the SBE implementation steps.

---

# 21. Explicitly NOT Part of FAS 3

Do not implement:

- Energy Intelligence Card UI
- Flow Card visual rewrite
- Phase Load Card rewrite
- automatic charging
- automatic battery control
- AI optimization
- optimal multi-hour charging windows
- consumer groups
- second history database
- repository merging

The Flow Card **data-source/configuration migration** is part of FAS 3 because it is directly connected to the goal of making SBE the canonical data/configuration engine.

The Flow Card's visual redesign remains a later phase.

---

# 22. Definition of Done for SBE

FAS 3 is complete only when:

- existing SBE functionality still works;
- existing entities remain compatible;
- accumulated values survive restart;
- House Total Energy is correct;
- structured price data is normalized;
- price intelligence is deterministic and tested;
- Consumers can be configured generically;
- SOC can be supplied where a suitable entity exists;
- consumer analysis is correct;
- relevant Flow Card consumer configuration can be owned by SBE;
- the Flow Card can consume canonical SBE data without duplicating business logic;
- historical data remains owned by HA Recorder;
- no unnecessary sensor explosion exists;
- documentation reflects the implementation;
- regression tests pass;
- no unrelated refactor has slipped into the release.

---

# 23. Phase Status

```text
FAS 0 — Project Definition       COMPLETE / FROZEN
FAS 1 — Data Gap Analysis        COMPLETE / APPROVED
FAS 2A — Architecture Decisions  COMPLETE / FROZEN
FAS 2B — Energy Data Contract    COMPLETE / FROZEN

FAS 3 — Implementation Planning  UPDATED / APPROVED

Next:
FAS 3.1 — Establish test/baseline and prepare implementation
```

**No production code has been changed as part of this plan.**
