# BASELINE — SOLAR BATTERY ECONOMY 1.4.0

**Project:** Solar Battery Economy  
**Baseline:** 1.4.0  
**Status:** FROZEN  
**Purpose:** Establish the verified starting point before architectural extensions for the Energy Intelligence ecosystem.

---

## 1. Baseline Purpose

This document records the state of Solar Battery Economy before implementation
of the new Energy Data Contract.

It is the reference point against which all future changes must be evaluated.

The baseline is intentionally conservative:

- existing functionality is preserved;
- no production behavior is changed by this baseline exercise;
- known limitations are recorded rather than silently corrected;
- later changes must be attributable to an approved implementation phase.

---

## 2. Baseline Source

The baseline is the supplied Solar Battery Economy 1.4.0 project archive.

The baseline project contains the existing Home Assistant custom integration and
its current documentation.

This baseline corresponds to the implementation reviewed during FAS 1–3.1.

---

## 3. Existing Architecture

The integration uses a coordinator-centered architecture:

```text
Home Assistant entity states
          |
          v
     Coordinator
          |
     +----+-------------------+
     |                        |
     v                        v
Flow calculations       Economy calculations
     |                        |
     +------------+-----------+
                  |
                  v
        Persistent accumulation
                  |
                  v
               Sensors
```

The architecture is retained for the Energy Intelligence expansion.

The project must not be rewritten wholesale.

---

## 4. Existing Functional Areas

The baseline includes:

- Config Flow;
- event-driven coordinator updates;
- solar power input;
- grid power input;
- battery power input;
- import price input;
- export price input;
- directional power-flow calculations;
- accumulated energy-flow calculations;
- money accumulation;
- savings calculations;
- battery-origin attribution;
- persistent storage;
- battery/economy analytics;
- current import/export price entities;
- Advanced Mode;
- diagnostic price-data tracking.

---

## 5. Existing Energy Flow Model

The baseline contains eight directional flow concepts:

```text
Solar   → House
Solar   → Battery
Solar   → Grid

Battery → House
Battery → Grid

Grid    → House
Grid    → Battery

House   → Grid
```

These existing flows are protected by the backward-compatibility requirements
in `docs/ENERGY_DATA_CONTRACT.md`.

No new data model may redefine their meaning without an explicit architectural
decision.

---

## 6. Existing Persistence

SBE uses Home Assistant persistent storage for accumulated energy and economy
values.

Persistence is considered critical functionality.

Future changes must preserve:

- accumulated energy;
- accumulated money;
- install-date information;
- restore behavior after Home Assistant restart.

A restart must not cause artificial energy or economy spikes.

---

## 7. Baseline Verification

### 7.1 Python syntax

The current Python implementation passes syntax/bytecode compilation checks.

Status:

```text
PASS
```

### 7.2 Core calculation smoke tests

The following core calculation areas were exercised at smoke-test level:

```text
calculate_flows()
calculate_savings()
battery_solar_share()
```

Status:

```text
PASS
```

The smoke tests confirm expected basic behavior for representative inputs.

They are not a replacement for a complete automated regression suite.

---

## 8. Automated Test Coverage

The supplied baseline did not contain a complete pytest/unittest regression
suite covering the integration.

Status:

```text
NOT PRESENT
```

This is an identified development gap.

A small regression test foundation is therefore required before substantial
modification of the coordinator, persistence or sensor layers.

---

## 9. Full Home Assistant Runtime Verification

A complete Home Assistant runtime/integration test could not be performed in
the development analysis environment.

Therefore the following are explicitly **not claimed as fully verified** by
the baseline exercise:

- full Config Flow execution;
- entity registration inside a live Home Assistant instance;
- Recorder interaction;
- restore behavior inside live Home Assistant;
- complete options-flow behavior;
- live state-change lifecycle;
- frontend entity rendering.

These require verification in an actual Home Assistant environment.

---

## 10. Known Correctness Area — Price Availability

The current implementation contains a distinction between:

- helper functions that convert invalid/unavailable numeric states;
- coordinator logic that attempts to distinguish unavailable price data.

This area requires explicit regression tests before the new price intelligence
layer is introduced.

The goal is to ensure that an unavailable price never results in an incorrect
money transaction.

This is a correctness item, not an optional cleanup.

---

## 11. Backward Compatibility Requirements

The following are protected:

```text
Existing entity unique IDs
Existing entity semantics
Existing units
Existing energy state classes
Existing accumulated values
Existing persistent data
Existing configuration behavior
```

Changes should be additive whenever reasonably possible.

Any required breaking change must be identified and approved before
implementation.

---

## 12. Baseline Gaps Identified

The baseline does not yet provide the complete Energy Data Contract.

Known gaps include:

```text
House Total Energy
Price Forecast normalization
Price classification
Price Quality Index
Generic Consumer model
Consumer analysis
Canonical House Cost
Formal regression suite
```

These are implementation targets, not baseline defects.

---

## 13. What Must NOT Change During Baseline

The baseline exercise must not:

- rename existing entities;
- remove existing entities;
- reset accumulated values;
- change existing flow semantics;
- replace the coordinator architecture;
- introduce the Energy Intelligence Card;
- alter Flow Card behavior;
- alter Phase Load Card behavior.

---

## 14. Baseline Test Matrix

Before each major implementation milestone, the following baseline behaviors
must be considered:

| Area | Expected |
|---|---|
| Solar flow | Existing calculation preserved |
| Battery flow | Existing calculation preserved |
| Grid flow | Existing calculation preserved |
| Energy accumulation | Continues correctly |
| Money accumulation | Continues correctly |
| Savings | Continues correctly |
| Battery attribution | Continues correctly |
| Persistence | Survives restart |
| Import price | Existing behavior preserved |
| Export price | Existing behavior preserved |
| Config Flow | Existing configuration remains usable |
| Advanced Mode | Existing behavior preserved |

---

## 15. Baseline Definition of Done

The baseline is considered established when:

- the supplied 1.4.0 code has been reviewed;
- Python syntax is valid;
- core calculations pass smoke tests;
- existing architecture is documented;
- persistence is identified as protected;
- known limitations are recorded;
- missing automated tests are explicitly identified;
- no production code has been modified as part of baseline establishment.

---

## 16. Baseline Status

```text
FAS 3.1 — Baseline
------------------

Code review:                 COMPLETE
Syntax verification:        PASS
Core smoke tests:            PASS
Automated regression suite:  MISSING / NEXT STEP
Live HA runtime test:        NOT AVAILABLE IN BASELINE ENVIRONMENT

BASELINE STATUS: FROZEN
```

---

## 17. Relationship to Other Project Documents

```text
docs/
├── ENERGY_DATA_CONTRACT.md
├── FAS_3_IMPLEMENTATION_PLAN.md
└── BASELINE_SBE_1.4.0.md
```

### `ENERGY_DATA_CONTRACT.md`

Defines what SBE must provide.

### `FAS_3_IMPLEMENTATION_PLAN.md`

Defines how the approved expansion should be implemented.

### `BASELINE_SBE_1.4.0.md`

Defines where the implementation started.

Together they form the current architectural control set.

---

## 18. Next Phase

The next approved phase is:

```text
FAS 3.2 — Regression Test Foundation
```

The objective is to create automated tests around the existing core behavior
before modifying production code.

No Energy Intelligence functionality should be implemented as part of the
regression-test foundation itself.

---

**BASELINE STATUS: FROZEN**
