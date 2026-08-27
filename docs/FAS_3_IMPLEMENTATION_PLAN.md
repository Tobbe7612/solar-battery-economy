# FAS 3 — SBE Implementation & Migration Plan

**Project:** Solar Battery Economy  
**Status:** PLANNING — no implementation changes made  
**Source of Truth:** `docs/ENERGY_DATA_CONTRACT.md`  
**Current code baseline:** SBE 1.4.0

---

## 1. Purpose

This document defines the implementation plan for extending Solar Battery Economy
into the central data/intelligence engine for:

- Solar Battery Economy Flow Card
- Energy Intelligence Card
- future/common data needs of Phase Load Card

The plan is deliberately incremental.

The existing SBE architecture is preserved wherever practical. The objective is
to add the minimum required capabilities without breaking existing users,
entities, accumulated values or historical continuity.

No code change should be made outside the approved scope in this document
without explicitly updating the project plan.

---

## 2. Current Baseline

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
└── sensor_helpers.py
```

---

## 3. Implementation Principles

### 3.1 Additive first

Prefer adding new entities/data structures over modifying existing public
entities.

### 3.2 Preserve existing entity identity

Do not change existing unique IDs, names, units or semantics unless a
documented migration is unavoidable.

### 3.3 Do not rebuild SBE

The existing coordinator/flow/economy architecture is retained.

### 3.4 Separate data ownership

```text
SBE
  = canonical calculations + normalized data

HA Recorder
  = historical storage

Lovelace cards
  = visualization + presentation
```

### 3.5 No card-specific business logic in the cards

The cards should consume canonical SBE data.

### 3.6 Do not create a sensor explosion

High-cardinality data such as 15-minute forecast intervals must be represented
as structured data, not one entity per interval.

### 3.7 Test every persistence-sensitive change

Existing energy/money persistence is a critical part of the integration.

---

# 4. Phase 3.1 — Data Model Preparation

## Objective

Introduce a clean internal data model without changing public behavior.

### Planned changes

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
```

The exact Python representation will be selected during implementation based on
Home Assistant compatibility and testability.

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

# 5. Phase 3.2 — Canonical House Energy

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

It must use the same persistent accumulation model as the existing energy
sensors.

### No change

The existing eight energy-flow entities remain untouched.

---

# 6. Phase 3.3 — Price Source Adapter

## Objective

Allow SBE to consume the user's existing structured Nord Pool template sensor.

The current upstream sensor supplies:

```text
current price
all_prices[]
```

where intervals contain:

```text
start
end
spot
import
export
```

### Architecture

```text
User's Nord Pool template sensor
              |
              v
        SBE Price Adapter
              |
              v
     normalized Price Model
```

### Important

The card must not depend on the user's specific template sensor name.

The source entity must be configurable.

### Compatibility

The existing current import/export price configuration remains valid.

We should extend configuration rather than silently replace the current price
inputs.

---

# 7. Phase 3.4 — Price Intelligence

## Objective

Add canonical price interpretation.

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

where higher = better/cheaper.

### Algorithm

The exact percentile/boundary algorithm is NOT to be invented during coding.

It must be:

1. specified;
2. unit-tested;
3. documented;
4. then considered part of the stable contract.

### Forecast

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

# 8. Phase 3.5 — Generic Consumers

## Objective

Introduce configurable consumers without hardcoding device types.

Conceptual model:

```text
Consumer
├── name
├── energy_entity      required
├── power_entity       optional
├── icon               optional
└── color              optional
```

### Configuration

Use Config Flow / Options Flow.

Consumers belong to the relevant SBE config entry.

### Example

```text
name: Bil
energy_entity: sensor.ev_energy
power_entity: sensor.ev_power
icon: mdi:car
color: optional
```

### Rules

- Energy entity is authoritative for historical analysis.
- Power entity is optional and intended for live display.
- SBE does not create energy by integrating consumer power in V1.
- Consumer groups are out of scope.
- No hardcoded EV/spa/heat-pump logic.

---

# 9. Phase 3.6 — Consumer Analysis

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

The first implementation should prioritize correctness and a clear data
contract over sophisticated optimization.

---

# 10. Phase 3.7 — House Economy Definition

Before exposing a new House Cost entity, finalize the exact semantic definition.

Do NOT simply add together unrelated SBE money values.

The implementation must distinguish:

```text
actual grid purchase cost
solar avoided cost/value
battery avoided cost/value
export income
savings
```

A formal test matrix is required before this becomes a public sensor.

---

# 11. Existing Known Issue — Must Be Addressed Deliberately

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

Therefore the intended "do not book money when price is unavailable" behavior is
not fully aligned with the helper contract.

This is a correctness issue and must be resolved before the new price-dependent
logic is considered stable.

It must be fixed deliberately, not as incidental cleanup.

---

# 12. Persistence and Migration Plan

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

If the Store schema needs to change, implement an explicit migration rather than
silently replacing stored data.

---

# 13. Config Flow Migration

Current Config Flow has five required input entities.

We must preserve the current setup experience as much as practical.

New configuration should be additive.

Potential new sections:

```text
Price intelligence source
Consumers
```

The exact UI is to be designed after inspecting current HA Config Flow APIs and
supported selectors for the target Home Assistant version.

### Important

Do not remove or rename existing configuration keys.

---

# 14. Sensor Implementation Strategy

Existing `EnergySensor`, `MoneySensor`, `FlowPowerSensor` and economy sensor
classes should be reused where semantics match.

Avoid creating many one-off classes if a generic, well-defined base class can
represent the new sensor type safely.

New sensor classes are justified where the HA semantics differ materially.

---

# 15. Documentation Updates During Implementation

When FAS 3 implementation starts, documentation must be updated together with
code.

Expected documents:

```text
docs/
├── ENERGY_DATA_CONTRACT.md
├── ARCHITECTURE_NOTES.md
├── V1.4.0_CODE_AUDIT.md
├── DEVELOPMENT_WORKFLOW.md
└── ...
```

New documents should only be created when they contain stable, useful
information.

The root README should be updated only when user-facing behavior changes.

---

# 16. Testing Plan

Before declaring the SBE implementation complete:

## Unit tests

- flow calculations
- house total calculation
- price normalization
- price classification
- PQI
- cheapest period
- consumer calculations
- house-cost calculation

## Integration/config tests

- fresh install
- existing configuration
- options flow
- consumer addition
- consumer removal/update
- invalid entity
- unavailable entity
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
- Home Assistant restart

---

# 17. Implementation Order

The actual coding order is:

```text
1. Establish tests/baseline
        |
2. Internal data model
        |
3. House Total Energy
        |
4. Price source adapter
        |
5. Price intelligence
        |
6. Consumer configuration
        |
7. Consumer analysis
        |
8. House cost
        |
9. Persistence/migration verification
        |
10. Full regression test
        |
11. Documentation update
```

No card implementation occurs during these steps.

---

# 18. Explicitly NOT part of FAS 3

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

Those belong to later phases/backlog.

---

# 19. Definition of Done for SBE

FAS 3 is complete only when:

- existing SBE functionality still works;
- existing entities remain compatible;
- accumulated values survive restart;
- House Total Energy is correct;
- structured price data is normalized;
- price intelligence is deterministic and tested;
- Consumers can be configured generically;
- consumer analysis is correct;
- historical data remains owned by HA Recorder;
- no unnecessary sensor explosion exists;
- documentation reflects the implementation;
- regression tests pass;
- no unrelated refactor has slipped into the release.

---

# 20. Phase Status

```text
FAS 0 — Project Definition       COMPLETE / FROZEN
FAS 1 — Data Gap Analysis        COMPLETE / APPROVED
FAS 2A — Architecture Decisions  COMPLETE / FROZEN
FAS 2B — Energy Data Contract    COMPLETE / FROZEN

FAS 3 — Implementation Planning  COMPLETE

Next:
FAS 3.1 — Establish test/baseline and prepare implementation
```

**No production code has been changed as part of this plan.**
