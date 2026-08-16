# Architecture Notes

## Current repository

The supplied repository is version `1.4.0`.

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

## Runtime architecture

```text
Configured HA sensors
    │
    ├── solar power
    ├── grid power
    ├── battery power
    ├── import price
    └── export price
            │
            ▼
SolarBatteryEconomyCoordinator
            │
            ├── _float_state()
            │
            ▼
calculate_flows()
            │
            ├── power flows
            │
            ├── energy accumulation
            │
            └── money accumulation
                    │
                    ▼
             calculate_savings()
                    │
                    ▼
             coordinator.data
                    │
                    ▼
                sensor.py
```

## Coordinator

`coordinator.py` is the central runtime/data layer.

It owns:

- configured entity IDs
- total investment
- solar investment
- battery investment
- CO₂ factor
- currency
- persistent Store
- install date
- current `power`
- accumulated `energy`
- accumulated `money`
- calculated `savings`

It listens to state changes from the five configured inputs.

## Flow layer

`flow_calculation.py` contains no Home Assistant entity code. It transforms three power inputs into eight directional flow values.

This separation is intentional and should be preserved.

## Financial layer

`economy_calculations.py` currently contains:

- `calculate_savings()`
- `battery_solar_share()`

The coordinator handles time integration and money accumulation. The economy module handles savings derivation and battery-origin share.

## Sensor layer

`sensor.py` contains both:

1. entity creation
2. sensor implementations

This is currently a large file (~1000 lines).

A future refactor may split sensor classes into modules, but such a refactor should not change unique IDs or entity semantics.

## Base entity

`sensor_base.py` defines `EconomySensor`.

It is responsible for common HA entity behavior and two device groups.

## Persistence

Coordinator storage:

```text
energy
money
install_date
battery_split_migrated
```

RestoreEntity is used by selected sensors for state restoration.

## Battery origin attribution

Battery discharge value is split by cumulative charge-energy origin:

```text
solar_share =
    solar_battery_energy /
    (solar_battery_energy + grid_battery_energy)
```

That share is applied to battery-house and battery-grid money values.

This is an allocation model, not an exact physical battery provenance model.

## Entity data semantics

### Power

`W`, `measurement`.

### Energy

`kWh`, `energy`, `total_increasing`.

### Money

Configured currency, `monetary`, `total`.

### Annualized metrics

Configured currency, `measurement`.

### Payback

Years or date.

## Configuration

The config flow uses entity selectors for the five required input sensors and number selectors for investments/CO₂ factor.

There is no explicit no-battery configuration in the current code.

## Important architecture boundary

Solar Battery Economy owns:

- flow calculations
- accumulation
- financial calculations
- persistence
- HA entity semantics

The flow card should consume the resulting entities rather than recreate the financial model.
