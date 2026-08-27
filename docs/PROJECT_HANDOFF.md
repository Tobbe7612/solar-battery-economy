# Solar Battery Economy — Project Handoff

## 1. Project identity

**Name:** Solar Battery Economy  
**Domain:** `solar_battery_economy`  
**Type:** Home Assistant custom integration  
**Current code version:** `1.4.0`  
**Integration type:** `hub`  
**IoT class:** `local_push`  
**Minimum Home Assistant version declared by the repository:** `2023.8.0`

The integration analyzes real-time solar, battery and grid power and turns those measurements into directional energy flows, accumulated energy, money flows, savings and financial performance metrics.

---

## 2. What the integration does

### CONFIRMED

The integration accepts five required sensor inputs:

- Solar production power
- Grid power
- Battery power
- Electricity import price
- Electricity export price

It derives eight directional power flows:

```text
Solar → House
Solar → Battery
Solar → Grid
Battery → House
Battery → Grid
Grid → House
Grid → Battery
House → Grid
```

Those flows are integrated over elapsed time into accumulated kWh values.

Money values are accumulated from the flow energy and the configured import/export prices.

Financial sensors then expose:

- total savings
- estimated annual savings
- ROI
- payback time
- estimated payback date
- effective electricity price
- solar savings
- battery savings
- solar annual savings
- battery annual savings
- solar ROI
- battery ROI
- solar payback
- battery payback
- grid independence
- solar self-consumption
- battery utilization
- CO₂ saved
- period savings
- price-data issue count

Advanced mode additionally exposes detailed money-flow and battery-analysis sensors.

---

## 3. Current architecture

### CONFIRMED

The current repository is compact:

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
├── strings.json
└── brand/
```

### Data path

```text
Home Assistant input sensors
        │
        ▼
SolarBatteryEconomyCoordinator
        │
        ├── sensor_helpers._float_state()
        │
        ▼
flow_calculation.calculate_flows()
        │
        ├── directional power flows
        │
        ▼
energy accumulation
        │
        ▼
money accumulation
        │
        ▼
economy_calculations.calculate_savings()
        │
        ▼
coordinator.data
        │
        ▼
sensor.py
```

The coordinator is event-driven. It listens for state changes on the five configured input entities and schedules `_handle_event_update()`.

---

## 4. Input conventions

### CONFIRMED

`flow_calculation.py` explicitly defines:

```text
solar > 0   = producing
battery > 0 = discharging
battery < 0 = charging
grid < 0    = importing
grid > 0    = exporting
```

All directional flow outputs are non-negative W values.

### Power balance

The house load is estimated as:

```text
solar
+ battery discharge
+ grid import
- battery charge
- grid export
```

Negative calculated house load is clamped to zero.

### Important

These sign conventions are part of the integration's input contract. Do not change them without a migration/documentation plan.

---

## 5. Persistence and restart behavior

### CONFIRMED

The coordinator uses Home Assistant `Store` with:

```text
solar_battery_economy_<entry_id>
```

The stored data contains:

- accumulated energy
- accumulated money
- `install_date`
- `battery_split_migrated`

`__init__.py` calls `await coordinator.async_restore()` before forwarding platform setup.

Therefore the accumulated energy/money model is designed to survive Home Assistant restarts.

### CONFIRMED — current annualization

The coordinator stores a persistent `install_date`.

`annual_estimate(total)` calculates:

```text
days_running =
    now - persisted install_date

effective_days = max(days_running, 3)

daily_average = total / effective_days

annual_estimate = daily_average × 365
```

This is now a coordinator-level calculation used by:

- `AnnualSavingsSensor`
- `PaybackSensor`
- `PaybackDateSensor`
- `SolarAnnualSavingsSensor`
- `BatteryAnnualSavingsSensor`
- `SolarPaybackSensor`
- `BatteryPaybackSensor`

This is materially different from the earlier per-sensor `_start_date` implementation.

### IMPORTANT MIGRATION DETAIL

If existing stored data does not contain `install_date`, the current code sets it to the current UTC time. Therefore an upgrade from an older installation does **not** automatically recover the original installation date from the historical sensor runtime.

This is explicitly documented in the repository README's historical `v1.3.1` changelog.

Do not claim that the persisted date is always the true physical installation date.

---

## 6. RestoreEntity versus Store

### CONFIRMED

Two mechanisms are present and should not be conflated.

### Integration Store

Used by the coordinator for persistent business totals:

- energy
- money
- install date
- migration flag

### Home Assistant RestoreEntity

Used by several sensor classes to restore the last entity state.

Current RestoreEntity users include:

- `EnergySensor`
- `MoneySensor`
- `PeriodEconomySensor`
- `PaybackSensor`

The coordinator remains the source of truth for the accumulated energy/money data.

---

## 7. Energy sensor semantics

### CONFIRMED

Energy flow sensors:

```text
unit = kWh
device_class = energy
state_class = total_increasing
```

They represent accumulated directional energy.

The eight energy keys are:

```text
solar_house
solar_battery
solar_export
battery_house
battery_grid
grid_house
grid_battery
house_grid
```

### Energy Dashboard warning

These sensors are especially sensitive to Home Assistant's statistics semantics.

Do not casually change:

- entity ID
- unique ID
- device class
- state class
- unit
- monotonic behavior

for existing energy sensors.

A reset or backwards jump in an accumulated energy sensor can create incorrect Energy Dashboard/statistics results.

This was a major lesson from earlier project work.

---

## 8. Money model

### CONFIRMED

The coordinator accumulates money per directional flow.

Import-priced flows:

```text
Solar → House
Battery → House
Grid → House
Grid → Battery
```

Export-priced flows:

```text
Solar → Grid
Battery → Grid
House → Grid
```

Money is accumulated only when the coordinator's price values are accepted by the current implementation.

### Important current-code observation

`_float_state()` converts missing, `unknown`, `unavailable`, invalid, NaN and infinite values to `0.0`.

The coordinator nevertheless contains a branch checking:

```python
if import_price_raw is None or export_price_raw is None:
```

Given the current `_float_state()` implementation, that branch is not reachable for ordinary unavailable/invalid source states because `_float_state()` returns `0.0`, not `None`.

**KNOWN ISSUE:** The price-unavailable protection and `_float_state()` semantics are inconsistent. This should be verified and redesigned deliberately before changing it.

Do not silently fix this as part of unrelated work.

---

## 9. Savings calculation

### CONFIRMED

`economy_calculations.calculate_savings()` currently derives:

```text
actual_grid_cost = grid_house + grid_battery

avoided_cost = solar_house + battery_house

export_income = solar_export + battery_export

total =
    avoided_cost
    + export_income
    - grid_battery
```

The returned savings dictionary contains:

- `baseline_cost`
- `actual_grid_cost`
- `export_income`
- `solar_house`
- `battery_house`
- `total`

### Important nuance

`battery_house` is valued as avoided import cost, while `grid_battery` is separately subtracted in total savings. This is how the current implementation accounts for grid-charged battery energy.

Do not rewrite this formula without testing representative scenarios:

1. solar → house
2. solar → battery → house
3. grid → battery → house
4. solar → grid
5. battery → grid
6. grid import with no battery
7. zero export price

---

## 10. Solar/battery financial split

### CONFIRMED

The current coordinator tracks separate investment configuration:

```text
investment
solar_investment
battery_investment
```

Solar financial metrics use `solar_investment`.

Battery financial metrics use `battery_investment`.

This separation was explicitly verified during project development by changing battery investment to a deliberately extreme value and observing that battery payback changed independently.

### Current attribution model

The coordinator uses:

```text
battery_solar_share(energy)
```

from `economy_calculations.py`.

The share is:

```text
solar battery charge energy
--------------------------------
solar battery charge energy
+ grid battery charge energy
```

This cumulative ratio is then used to split battery discharge money into:

```text
battery_*_from_solar
battery_*_from_grid
```

### IMPORTANT LIMITATION

This is an allocation model based on cumulative charge-energy proportions. It is not a physical battery state-of-charge provenance tracker.

Therefore the solar/grid origin of a specific battery discharge is estimated, not directly measured.

Mark this as a **KNOWN LIMITATION**, not a bug, unless a future design replaces it.

---

## 11. Sensor architecture

### CONFIRMED

`EconomySensor` in `sensor_base.py` is the common base class.

It provides:

- coordinator integration
- stable unique IDs
- entity names
- device grouping
- device information
- `native_value`

Two device groups are created:

```text
Solar Battery Economy - Energy System
Solar Battery Economy - Financial
```

Power and energy sensors go into the Energy System group. Other sensor types go into the Financial group.

### Entity ID rule

The integration's unique IDs are built from:

```text
DOMAIN + entry_id + sensor_type + key
```

Do not change this scheme casually. Entity IDs generated by Home Assistant can become user-facing dependencies.

---

## 12. Current sensor families

### CONFIRMED

### Power sensors

Eight:

```text
Power Solar-House
Power Solar-Battery
Power Solar-Export
Power Battery-House
Power Battery-Grid
Power Grid-House
Power Grid-Battery
Power House-Grid
```

Unit: W  
State class: measurement  
Instantaneous.

### Energy sensors

Eight matching flow sensors.

Unit: kWh  
Device class: energy  
State class: total_increasing  
Accumulated.

### Money sensors

Advanced mode:

```text
Money Solar-House
Money Solar-Export
Money Battery-House
Money Battery-Grid
Money Grid-House
Money Grid-Battery
Money House-Grid
Money Battery-House (from Solar)
Money Battery-House (from Grid)
Money Battery-Export (from Solar)
Money Battery-Export (from Grid)
```

Unit: configured currency  
Device class: monetary  
State class: total.

### Main savings sensors

```text
01 Total Savings
02 Estimated Annual Savings
03 Savings Today
04 Savings This Month
05 Savings This Year
06 Effective Electricity Price
07 Import Electricity Price
08 Export Electricity Price
10 Payback Time
11 Estimated Payback Date
12 Return On Investment
```

### Solar/battery analytics

```text
20 Solar Savings
21 Battery Savings
40 Solar Annual Savings
41 Battery Annual Savings
42 Solar ROI
43 Battery ROI
44 Solar Payback Time
45 Battery Payback Time
```

### Performance

```text
30 Grid Independence
31 Battery Utilization
32 Solar Self-Consumption Rate
33 CO2 Saved
```

### Advanced battery diagnostics

```text
22 Battery Self-Consumption Gain
23 Battery Arbitrage Profit
```

### Diagnostic

```text
90 Price Data Issues
```

---

## 13. Advanced mode

### CONFIRMED

Advanced mode controls creation of:

- detailed money sensors
- battery utilization
- battery arbitrage profit
- battery self-consumption gain

Main financial sensors are still created without Advanced Mode.

### KNOWN ISSUE / NEEDS VERIFICATION

`SolarBatteryEconomyOptionsFlow.async_step_init()` calls:

```python
await self.hass.config_entries.async_reload(self.entry.entry_id)
```

before returning the new options data.

The reload therefore occurs before the options flow has returned the new values to Home Assistant.

This is a suspicious ordering and should be tested against current Home Assistant behavior, particularly because the project historically experienced Advanced Mode changes that required an additional reload.

Do not change this blindly; verify with a real config-entry options test.

---

## 14. Config flow

### CONFIRMED

The config flow:

- prevents duplicate configuration
- requires three distinct power sensors
- requires import and export price sensors
- accepts optional total, solar and battery investment values
- accepts CO₂ factor
- accepts currency
- accepts Advanced Mode

The current configuration schema supports:

```text
SEK
EUR
USD
NOK
DKK
GBP
```

The integration does not perform currency conversion. The price sensors must use the selected currency.

### Battery-less systems

**ASSUMPTION / NEEDS VERIFICATION**

The current config flow requires a battery power sensor:

```python
vol.Required(CONF_BATTERY_POWER)
```

There is no explicit "no battery" mode in the current code.

Therefore the documentation must not claim native battery-less configuration until this is intentionally designed and tested.

---

## 15. Home Assistant-specific rules

### CONFIRMED project rules

1. Read the actual current file before changing it.
2. Never invent file contents or APIs.
3. Identify dependencies before changing a shared class/function.
4. Prefer one focused change at a time.
5. Test after every meaningful change.
6. Check Home Assistant logs after reload/restart.
7. Check entity state, attributes, units and state classes.
8. Specifically test Energy Dashboard/statistics behavior after energy-sensor changes.
9. Never change existing entity IDs unnecessarily.
10. Preserve persistent totals and migration behavior.
11. Do not refactor stable architecture solely for aesthetic reasons.
12. Treat financial formulas as production logic and test them with hand-calculated scenarios.
13. Separate historical implementation from current implementation in documentation.
14. If a required file is missing, request it rather than guessing.

---

## 16. Relationship to solar-battery-economy-flow-card

### CONFIRMED at architectural level

The intended relationship is:

```text
Physical/Home Assistant input entities
            ↓
Solar Battery Economy
            ↓
energy + financial entities
            ↓
solar-battery-economy-flow-card
```

Solar Battery Economy should own calculations and data semantics.

The Lovelace card should primarily visualize those entities.

### NEEDS VERIFICATION

The exact entity list consumed by the current flow-card repository is not contained in this integration repository.

Before documenting a hard dependency list, audit the current flow-card code as well.

Do not guess the card's current entity contract from historical conversations.

---

## 17. Historical decisions

### HISTORICAL — per-sensor runtime

Earlier versions used local `_start_date` values in annual/payback sensors. This caused annualized estimates to restart or diverge after reload/restart.

This implementation was later replaced.

### CONFIRMED CURRENT

The coordinator now owns a persisted `install_date` and a single `annual_estimate()` function.

### HISTORICAL — shared in-memory runtime

A central in-memory:

```python
runtime_start = dt_util.now()
```

was considered and rejected because it would reset on restart/reload unless persisted.

Do not reintroduce that design.

---

## 18. Data integrity rules

Never casually modify:

```text
Energy sensor state_class
Energy sensor device_class
Energy sensor unit
Energy sensor unique_id
Entity ID naming
Coordinator storage schema
Stored energy totals
Stored money totals
```

Any migration affecting stored data must include:

- old-schema handling
- migration flag/version
- restart test
- upgrade test
- rollback consideration

The current battery-origin split already demonstrates the intended pattern: a persisted migration flag is used to ensure a one-time backfill.

---

## 19. Current risks and TODOs

### KNOWN ISSUE

Price availability handling is internally inconsistent because `_float_state()` returns `0.0` for unavailable input while coordinator logic checks for `None`.

### NEEDS VERIFICATION

Options-flow reload ordering.

### NEEDS VERIFICATION

Exact current contract between this integration and the latest flow-card repository.

### NEEDS VERIFICATION

Battery-less system behavior.

### TODO

Add a documented release/version history for the current `1.4.0` repository state.

### TODO

Add automated tests for:

- flow calculation
- money calculation
- savings calculation
- solar/battery attribution
- annualization
- restart restoration
- zero export price
- unavailable price sensors

---

## 20. Golden principle

The project is now a user-facing data backend. Its entities and financial calculations are an API.

**Do not optimize for code elegance at the expense of data continuity.**

When in doubt:

```text
verify → make smallest safe change → test → inspect HA state/logs → release
```
