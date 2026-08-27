# ENERGY DATA CONTRACT

**Project:** Solar Battery Economy ecosystem  
**Document status:** FROZEN — FAS 2B  
**Version:** 1.0  
**Purpose:** Source of Truth for data exposed by Solar Battery Economy to the ecosystem's Lovelace cards.

---

## 1. Purpose

This document defines the data contract between the Solar Battery Economy (SBE)
integration and its related Lovelace cards.

The contract defines:

- what data SBE guarantees to expose;
- the semantic meaning of each value;
- which data is represented as Home Assistant entities;
- which data is structured/forecast data;
- how historical data is obtained;
- consumer configuration;
- price intelligence;
- backward-compatibility requirements;
- the boundaries of V1.

This document is an architectural contract, not an implementation guide.

No card may invent a competing definition for a value already defined here.

---

## 2. Ecosystem Architecture

```text
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
              +---------------+----------------+
              |               |                |
              v               v                v
          Flow Card    Energy Intelligence   Phase Load
                            Card               Card
```

SBE is the central energy/economy data engine.

The Energy Intelligence Card depends on SBE.

The Energy Intelligence Card is initially a separate GitHub repository.

Phase Load Card remains a separate presentation layer and is not forced into
the SBE data model unless a later architectural decision explicitly requires it.

---

## 3. Core Principles

### 3.1 SBE is the data/intelligence layer

Cards should primarily consume data rather than duplicate business logic.

### 3.2 Cards are presentation/analysis clients

Cards must not independently redefine:

- energy flow semantics;
- SBE cost semantics;
- SBE savings semantics;
- price classification rules.

### 3.3 Home Assistant Recorder is the historical layer

SBE should expose correct HA entities and state metadata.

SBE must not create a parallel historical database for normal card history.

### 3.4 Structured data for high-cardinality forecast data

The 15-minute price forecast must not create one entity per interval.

### 3.5 Backward compatibility is a hard requirement

Existing SBE entities should remain stable whenever reasonably possible.

Existing entity unique IDs, units, semantics and historical continuity must not
be changed unnecessarily.

---

## 4. Existing SBE Data — Preserve

The following existing flow model remains the foundation:

### Power flows

- Solar → House
- Solar → Battery
- Solar → Grid
- Battery → House
- Battery → Grid
- Grid → House
- Grid → Battery
- House → Grid

### Energy flows

The corresponding accumulated energy values remain available as kWh,
with appropriate Home Assistant energy semantics.

### Economy

Existing SBE economy/savings entities remain part of the public contract and
must not be silently repurposed.

### Battery analytics

Existing battery-related calculations and sensors remain authoritative unless
a future version explicitly changes their contract.

---

## 5. House Energy Contract

### 5.1 House Total Energy

A new canonical house-consumption energy value shall be exposed.

Definition:

```text
House Total Energy =
    Solar → House
  + Battery → House
  + Grid → House
```

This is the total electrical energy consumed by the house/load system,
regardless of energy source.

Required Home Assistant semantics:

```text
unit_of_measurement: kWh
device_class: energy
state_class: total_increasing
```

The value must survive Home Assistant restarts according to the same persistence
principles used by the existing SBE accumulated-energy sensors.

This is a key data source for the Energy Intelligence Card.

---

## 6. Power Contract

Existing SBE power-flow sensors remain authoritative for real-time flow
visualization.

The Flow Card may use these values directly.

No second competing power-flow calculation should be introduced unless required
by a later approved architecture change.

---

## 7. Price Data Contract

The upstream price source is currently the user's Nord Pool based template
sensor.

The current template provides:

- current price;
- spot price;
- import price;
- export price;
- 15-minute intervals;
- today's intervals;
- tomorrow's intervals.

Its interval structure is conceptually:

```text
{
  start: datetime,
  end: datetime,
  spot: SEK/kWh,
  import: SEK/kWh,
  export: SEK/kWh
}
```

The current template sensor is an upstream data source and is not itself the
public API of the Energy Intelligence Card.

SBE shall normalize this information into the project's price model.

The exact entity name of the user's existing template sensor must remain a
configuration detail rather than being hardcoded into the card.

---

## 8. Price Semantics

### 8.1 Import price

The primary consumer-facing price is the actual import price.

It represents the price paid when purchasing electricity.

The user's current calculation includes the configured components such as:

- Nord Pool spot price;
- supplier markup;
- energy tax;
- VAT;
- variable grid transfer fee.

The exact fee components and values must be documented in the project's
configuration/documentation rather than silently embedded in card code.

### 8.2 Spot price

Spot price remains available as separate raw price data.

### 8.3 Export price

Export price remains available for future battery/export analysis.

Export price is not the primary price shown in the V1 Energy Intelligence
Card.

---

## 9. Price Forecast Contract

Forecast resolution is fixed at:

```text
15 minutes
```

Target horizon:

```text
24 hours forward
```

The forecast consists of intervals:

```text
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

No 96 individual forecast entities shall be created.

Forecast data is structured data.

If tomorrow's prices are not available, those intervals must be represented as
unknown/unavailable/neutral.

The system must never substitute a guessed or stale price and present it as a
known future price.

---

## 10. Current Price

SBE shall retain the existing current import/export price entities where they
already exist.

New functionality must not require breaking or renaming existing entities.

The current import price is the default reference for:

- price classification;
- Price Quality Index;
- Energy Intelligence Card primary price display.

---

## 11. Price Classification

SBE shall provide normalized relative price classification.

The conceptual classes are:

```text
VERY_CHEAP
CHEAP
NORMAL
EXPENSIVE
VERY_EXPENSIVE
```

Classification is relative to the available price distribution, not a fixed
SEK/kWh threshold.

The exact algorithm and percentile boundaries are an implementation detail to
be validated during FAS 3 and documented with tests.

The algorithm must be deterministic.

---

## 12. Price Quality Index

SBE shall expose a normalized:

```text
Price Quality Index: 0–100
```

Semantic direction:

```text
100 = exceptionally favorable / cheap
0   = exceptionally unfavorable / expensive
```

The primary PQI is based on import price.

For future prices, the comparison population is the available price intervals
for today and tomorrow.

For historical/current-day interpretation, the relevant available daily price
distribution is used.

The exact mathematical transformation is deliberately left to FAS 3 so it can
be tested and documented before becoming implementation-locked.

---

## 13. Cheapest Period

The Energy Intelligence Card V1 shall be able to identify the cheapest
available future price period.

This is a V1 requirement.

The result must be derived from the normalized future price data.

The implementation must not assume a fixed price threshold.

Advanced optimization such as:

> "Find the cheapest continuous 3-hour window"

is outside V1 and belongs in the future backlog.

---

## 14. Economy Contract

Existing SBE economy entities remain authoritative.

Where required for the Energy Intelligence Card, SBE shall provide a clearly
defined house-cost value.

The semantic distinction between:

- actual grid purchase cost;
- value of self-produced solar energy;
- opportunity cost;
- export income;
- savings;

must remain explicit.

Cards must not silently mix these concepts.

A house-cost definition must therefore be finalized and tested in FAS 3 before
implementation is released.

---

## 15. Generic Consumer Contract

A Consumer is a configurable load that the user wants to analyze against
electricity price.

A Consumer is not a hardcoded device category.

Examples:

- car;
- pool;
- spa;
- heat pump;
- washing machine;
- server;
- any other measurable load.

### Required

```text
name
energy_entity
```

### Optional

```text
power_entity
icon
color
```

The energy entity is the authoritative source for historical energy analysis.

The optional power entity may be used for real-time display.

SBE should not integrate or calculate energy for a consumer from power merely
because a power entity exists in V1.

---

## 16. Consumer Configuration

Consumers shall be configured through Home Assistant Config Flow.

Consumers belong to the relevant SBE config entry.

The data model must support an arbitrary number of consumers.

The card may impose a practical display limit independently.

There shall be no hardcoded concepts such as:

```text
EV
SPA
HEATPUMP
```

in the consumer data model.

Consumer groups are outside V1.

---

## 17. Consumer Analysis

For a configured consumer, the system should support:

```text
Energy
Cost
Average Price
```

and, where the data permits:

```text
Cheap Usage %
Expensive Usage %
```

The Energy Intelligence Card may visualize these values.

The consumer's original energy entity remains the authoritative source for its
energy history.

---

## 18. Historical Data Contract

Historical visualization uses Home Assistant's Recorder/statistics/history
mechanisms.

SBE provides correctly classified sensors and persistent cumulative values.

The Energy Intelligence Card retrieves historical data through Home Assistant.

The card must not maintain a second persistent history database.

Target primary history window:

```text
24 hours backwards
```

Target future window:

```text
24 hours forwards
```

---

## 19. Card Responsibilities

### Solar Battery Economy

Responsible for:

- data ingestion;
- canonical energy flow calculations;
- accumulation;
- economy calculations;
- persistence;
- price normalization;
- price intelligence;
- consumer configuration/metadata;
- canonical definitions.

### Solar Battery Economy Flow Card

Responsible for:

- real-time visualization;
- energy flow rendering;
- presentation and interaction.

It should consume SBE's canonical data wherever practical.

### Energy Intelligence Card

Responsible for:

- price visualization;
- historical price + consumption visualization;
- future price visualization;
- consumer analysis;
- presentation of price intelligence;
- live and historical views.

### Phase Load Card

Remains focused on phase loading and electrical installation visualization.

It may later consume common SBE data where this provides clear value, but this
is not a requirement of the initial SBE data contract.

---

## 20. Energy Intelligence Card V1 — Functional Contract

The frozen visual target is based on the approved desktop "D Deep Dive"
concept and mobile "B Timeline Fusion" concept.

The mockup defines:

- visual language;
- information hierarchy;
- intended information density;
- functional intent.

It is not a pixel-perfect implementation requirement.

### Main concepts

#### Live

Show:

- current import price;
- price class;
- Price Quality Index;
- current status;
- relevant near-term price information;
- cheapest upcoming period.

#### History

Primary visualization:

```text
24h history
price + actual consumption
```

The historical visualization is the main visual element.

Consumers may be selected to compare their energy use with the price curve.

#### Future

Primary future visualization:

```text
24h forward
15-minute price intervals
```

The future section should visually connect with the historical timeline while
remaining clearly distinguishable from actual historical data.

Unknown future intervals must remain visually neutral.

---

## 21. Design/Information Rules

The Energy Intelligence Card should make the following immediately apparent:

1. Is electricity cheap or expensive now?
2. What happened to consumption when prices changed?
3. When is the next favorable period?
4. How much did selected loads consume?
5. How did those loads align with electricity prices?

The card should favor visual comprehension over displaying large numbers of
individual metrics simultaneously.

---

## 22. Backward Compatibility

The following are protected:

- existing entity unique IDs;
- existing entity meanings;
- existing units;
- existing energy semantics;
- existing accumulated values;
- existing persistent state behavior.

Changes must be additive wherever reasonably possible.

If an existing sensor must change for correctness, the migration impact must be
identified before implementation.

No existing entity should be removed or repurposed silently.

---

## 23. V1 Explicit Boundaries

The following are explicitly OUTSIDE the V1 implementation unless the scope is
formally changed:

- automatic EV charging control;
- automatic battery control;
- automatic appliance control;
- autonomous energy optimization;
- AI-based control;
- consumer groups;
- multi-hour optimal charging-window optimization;
- a second persistent history database;
- hardcoded appliance categories;
- replacing the existing SBE architecture wholesale;
- merging the separate Lovelace repositories.

These may be maintained as future backlog ideas.

---

## 24. FAS 3 Prerequisites

Before implementation, the following must be specified and tested:

1. Exact entity names for new SBE entities.
2. Exact device classes and state classes.
3. Exact house-cost definition.
4. Exact Price Quality Index mathematical algorithm.
5. Exact price-class boundaries.
6. Exact structured forecast exposure mechanism.
7. Exact Config Flow representation for Consumers.
8. Migration/backward-compatibility behavior.
9. Restore-state behavior for new cumulative entities.
10. Unit and rounding conventions.

---

## 25. Source of Truth Rule

If a future implementation decision conflicts with this document, the document
wins unless the user explicitly approves a change.

Any approved change to the contract must update this document before or together
with the corresponding implementation.

---

## 26. Current Status

```text
FAS 0 — Project Definition       COMPLETE / FROZEN
FAS 1 — Data Gap Analysis        COMPLETE / APPROVED
FAS 2A — Architecture Decisions  COMPLETE / FROZEN
FAS 2B — Energy Data Contract    COMPLETE / FROZEN

FAS 3 — SBE Implementation       NOT STARTED
```

**Next approved step:** FAS 3 — implementation planning and migration design.
