# Solar Battery Economy

A professional Home Assistant custom integration that calculates the real financial and performance impact of your solar panel and home battery system.

---

## Features

### Energy System
- Real-time power flow distribution
- Accumulated energy flows (kWh)
- Solar → House
- Solar → Battery
- Solar → Grid
- Battery → House
- Grid → House
- Grid → Battery

---

### Financial System
- Baseline Cost (without system)
- Actual Grid Cost
- Export Income
- Total Savings
- Return On Investment (%)
- Estimated Annual Savings
- Payback Time (years)
- Estimated Payback Date

---

### Performance Metrics
- Grid Independence (%)
- Battery Utilization (%) *(Advanced Mode)*

---

### Environmental
- CO₂ Saved (total)

---

## Advanced Mode

Optional toggle in integration settings.

When enabled:
- Shows detailed money flow breakdown
- Shows savings breakdown per flow
- Shows battery utilization %

---

## How It Works

The integration:

1. Listens to power sensors (solar, grid, battery)
2. Calculates real-time energy flows
3. Accumulates energy (kWh)
4. Calculates monetary impact using import/export price sensors
5. Computes savings, ROI and payback projections

No polling.
Event-driven.
Low overhead.

---

## Configuration

You must provide:

- Solar production power sensor
- Grid power sensor
- Battery power sensor
- Import price sensor
- Export price sensor
- Optional investment cost

---

## Requirements

Home Assistant 2026.2.3 or newer.

---

## Installation

### HACS (Recommended)
1. Add this repository as a custom repository in HACS.
2. Search for "Solar Battery Economy".
3. Install and restart Home Assistant.

### Manual Installation
Copy the `solar_battery_economy` folder into:
/config/custom_components/
Restart Home Assistant.

---

## Devices Created

### Energy System Device
Contains:
- Power sensors
- Energy sensors

### Financial Device
Contains:
- Savings
- ROI
- Payback
- Annual projections
- Environmental metrics

---

## Philosophy

This integration focuses on:

- Real savings vs. hypothetical cost
- Clear financial understanding
- Long-term performance tracking
- Clean device separation
- Minimal UI clutter

---

## Future Improvements

- Estimated annual CO₂ projection
- Advanced analytics
- Optional comparison charts

---

## License

MIT License
