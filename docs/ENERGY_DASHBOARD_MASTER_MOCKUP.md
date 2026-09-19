# Energy Dashboard — Master Mockup

**Status:** FROZEN MASTER  
**Checkpoint:** 2026-09-13  
**Purpose:** Visual and information-architecture reference for the new Energy Dashboard.

This document freezes the latest approved mockup as the master target. It does not freeze implementation details that have not yet been decided.

## 1. Core concept

The Energy Dashboard answers:

> **Vad har hänt, vad kostade det och hur går det?**

It is deliberately separated from the Solar Battery Economy Flow Card, whose primary responsibility is live power-flow visualization.

## 2. Main changes from the previous target

### A. Clearer page hierarchy

The dashboard is organized into a compact sequence:

1. Current price / status
2. Today's price statistics
3. Combined 24h historical + 24h future timeline
4. Upcoming 15-minute prices
5. Key 24h KPIs
6. Consumption by unit
7. Insights

This makes the dashboard readable from top to bottom without requiring every piece of information to have equal visual weight.

### B. Smart Score was renamed/reframed as Price Index (PQI)

The top-right metric now uses:

**Prisindex (PQI)**

rather than presenting Smart Score as if it were already a fully defined optimization score.

This is more faithful to the currently implemented SBE capability. Smart Score remains a future analytical concept and is not treated as implemented merely because the mockup contains a score.

### C. Cost semantics are explicit

The dashboard now labels the main cost metric:

**Importkostnad (total importpris)**

This reinforces the locked project rule:

- all dashboard costs use total import price
- spot is used for market-price visualization
- export remains separate revenue

This is one of the most important changes because it prevents visual ambiguity between spot price and actual household purchase cost.

### D. Timeline is explicitly historical + forecast

The main graph is now titled:

**Spotpris & husförbrukning — senaste 24h och nästa 24h**

The visual distinction is:

- solid price line = historical spot price
- dashed price line = known future spot-price forecast
- bars = house consumption
- `NU` = current-time boundary

The future side represents known Nord Pool data, not extrapolation.

### E. Future price section is simplified

The future-price strip is explicitly:

**Kommande priser (15 minuter)**

Rather than creating many entities, it represents the structured forecast visually.

A single navigation affordance can expose the complete forecast when needed.

### F. KPI row is more focused

The primary summary row contains:

- Importkostnad senaste 24h
- Förbrukning senaste 24h
- Andel under medianpris
- Nästa billiga period

This keeps the most actionable information together.

### G. Consumer analysis is separated from general KPIs

The dashboard now gives consumption-by-unit its own section:

**Förbrukning per enhet — senaste 24h**

The table/bar presentation shows:

- unit
- energy
- share
- average import price

This makes the consumer comparison useful without forcing every consumer into the main KPI area.

### H. Insights become a dedicated analytical layer

A separate:

**Insikter — senaste 24h**

section summarizes meaningful observations such as:

- share of consumption below median
- expensive periods
- device activity during cheap periods

The dashboard therefore separates raw measurements from interpretation.

### I. Mobile layout is a condensed version, not a different product

The mobile mockup keeps the same information architecture but changes presentation:

- stacked cards
- condensed timeline
- compact KPI cards
- expandable/scrollable sections
- bottom navigation

The mobile view should consume the same canonical SBE data as desktop.

## 3. What is deliberately NOT frozen

The mockup does **not** freeze:

- exact Smart Score formula
- exact consumer-event algorithm
- exact cheap/expensive percentage calculation
- exact historical Recorder query implementation
- exact cheapest-period presentation for non-contiguous selections
- exact chart library or rendering implementation
- exact responsive breakpoints
- exact iconography or typography
- any new SBE sensor unless explicitly approved by the data contract

Those remain implementation/definition decisions.

## 4. Architectural ownership

### Solar Battery Economy

Owns:

- canonical calculations
- normalized price model
- energy/economy data
- price intelligence
- persistent state
- stable shared semantics

### Energy Dashboard

Owns:

- presentation
- history-window selection
- chart rendering
- dashboard aggregation that is explicitly presentation-level
- user-facing insights presentation

It must consume canonical SBE semantics and must not duplicate SBE business logic.

### Flow Card

Owns:

- live directional power flows
- live flow animation
- immediate system status relevant to power flow

### Phase Load Card

Owns:

- phase loading
- phase current/power visualization
- electrical-system phase view

## 5. Frozen visual intent

The master should preserve the following design characteristics:

- dark premium energy-dashboard aesthetic
- strong but restrained neon/semantic accents
- rounded panels with clear grouping
- high information density without visual clutter
- clear hierarchy between live state, history, forecast, KPIs and insights
- desktop and mobile use the same underlying data model
- charts remain the primary analytical visualization
- color communicates semantic state rather than decoration alone

## 6. Master rule

Future implementation decisions should be evaluated against this master.

Small implementation improvements are allowed when they:

1. improve clarity,
2. reduce complexity,
3. preserve the information architecture,
4. preserve the locked price semantics,
5. do not expand SBE scope unnecessarily.

A change that materially alters the information architecture or user intent should be treated as a new mockup revision rather than silently modifying this master.
