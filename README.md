# Solar Battery Economy
<p align="center">
  <img src="https://raw.githubusercontent.com/Tobbe7612/solar-battery-economy/main/images/architecture.png" width="900">
</p>
<p align="center">
  <img src="https://raw.githubusercontent.com/Tobbe7612/solar-battery-economy/main/images/icon.png" width="160">
</p>

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![License](https://img.shields.io/github/license/Tobbe7612/solar-battery-economy)](LICENSE)
[![GitHub release](https://img.shields.io/github/v/release/Tobbe7612/solar-battery-economy)](https://github.com/Tobbe7612/solar-battery-economy/releases)

**Solar Battery Economy** is a Home Assistant custom integration that analyzes the real economic performance of a **solar + battery energy system**.


It calculates energy flows, financial savings, ROI, and performance indicators based on real-time power measurements and electricity prices.

The integration converts power flows into accumulated **kWh**, **SEK**, and **system performance metrics** to show the true value of your solar and battery system.

---

# Features

### Energy Flow Analysis

The integration calculates the following power flows:

* Solar → House
* Solar → Battery
* Solar → Export
* Battery → House
* Battery → Grid
* Grid → House
* Grid → Battery
* House → Grid

These flows are integrated into accumulated **energy values (kWh)**.

---

### Financial Analysis

The integration calculates:

* Total savings
* Estimated annual savings
* Return on investment (ROI)
* Payback time
* Estimated payback date
* Effective electricity price

It also breaks down savings by source:

* Solar savings
* Battery savings
* Export income
* Battery arbitrage profit
* Battery self-consumption value

---

### System Performance Metrics

Performance indicators include:

* Grid Independence (%)
* Solar Self-Consumption Rate (%)
* Battery Utilization (%)
* CO₂ saved

---

### Time-Based Savings

Savings are tracked over time:

* Savings Today
* Savings This Month
* Savings This Year

---

### Advanced Mode

Advanced Mode enables diagnostic sensors for deeper analysis:

* Detailed money flows
* Savings breakdown sensors
* Battery arbitrage
* Internal energy flows

This keeps the default UI clean while still allowing advanced analysis.

---

# Required Input Sensors

The integration requires **five input sensors**.

| Input         | Description                    |
| ------------- | ------------------------------ |
| Solar Power   | Current solar production       |
| Grid Power    | Net grid import/export         |
| Battery Power | Battery charge/discharge power |
| Import Price  | Electricity purchase price     |
| Export Price  | Electricity export price       |

---

# Power Sensor Requirements

All power sensors must report **instantaneous power in Watts (W)**.

### Solar Power

Must be **positive when producing power**.

Example:

```
Solar producing 3500 W → sensor = 3500
```

---

### Grid Power (Important)

The grid sensor must follow this convention:

```
Negative  = importing electricity
Positive  = exporting electricity
```

Example:

```
Importing 1200 W from grid → -1200
Exporting 800 W to grid → 800
```

⚠️ Note:
Some systems use the opposite convention:
```
Positive = import
Negative = export

If your sensor follows this, you must invert it in Home Assistant.

Example template:

```yaml
template:
  - sensor:
      - name: "Grid Power Corrected"
        unit_of_measurement: "W"
        state: "{{ states('sensor.your_grid_sensor') | float * -1 }}"
---
### Battery Power

Battery power must follow this convention:

```
Positive  = battery discharging
Negative  = battery charging
```

Example:

```
Battery powering house → 1500
Battery charging → -900
```

---

### Electricity Price Sensors

Both price sensors must report **price per kWh**.

Example:

```
Import price → 2.35 SEK/kWh
Export price → 0.85 SEK/kWh
```

---

# Financial Model

Savings are calculated as:

```
Savings =
Baseline cost (without solar/battery)
− Actual grid cost
+ Export income
```

All calculations are based on **real-time power integration**, avoiding historical recalculation errors.

---

# Effective Electricity Price

The integration calculates the **real average electricity price you paid** after solar and battery savings:

```
Effective Price =
Total Grid Cost / Grid Energy Used
```

This shows the real cost of electricity after self-consumption and battery usage.

---

# Installation

### HACS (Recommended)

1. Open **HACS**
2. Go to **Integrations**
3. Add custom repository:

```
https://github.com/Tobbe7612/solar-battery-economy
```

4. Install **Solar Battery Economy**
5. Restart Home Assistant

---

### Manual Installation

1. Copy the folder

```
custom_components/solar_battery_economy
```

into your Home Assistant

```
/config/custom_components/
```

2. Restart Home Assistant
3. Add the integration via **Settings → Devices & Services**

---

# Configuration

After installation, add the integration and select the required sensors:

* Solar power sensor
* Grid power sensor
* Battery power sensor
* Import electricity price
* Export electricity price
* System investment cost

Advanced Mode can be enabled in the integration options.

## 💱 Currency Support

The integration supports multiple currencies.

You can select your currency during setup:

- SEK (Swedish Krona)
- EUR (€ Euro)
- USD ($ US Dollar)
- NOK (Norwegian Krone)
- DKK (Danish Krone)
- GBP (£ British Pound)

⚠️ Important:
The selected currency must match your electricity price sensors.
```markdown
⚠️ The integration does not convert currencies. It only changes the displayed unit.

Example:
- If using EUR → price sensors must be €/kWh
- If using SEK → price sensors must be SEK/kWh

The integration calculates:
Energy (kWh) × Price (currency/kWh) = Money (currency)

---

# Device Structure

The integration creates two devices:

### Energy System

Contains energy flow sensors:

* Power flows
* Energy flows
* Grid independence
* Solar self-consumption
* Battery utilization
* CO₂ saved

---

### Financial System

Contains financial analytics:

* Total savings
* Annual savings
* Payback
* ROI
* Solar vs battery savings
* Effective electricity price

---

# Example Metrics

Typical values for a solar + battery system:

| Metric                 | Example    |
| ---------------------- | ---------- |
| Grid Independence      | 65 %       |
| Solar Self-Consumption | 82 %       |
| Battery Utilization    | 75 %       |
| Annual Savings         | 27,000 SEK |
| Payback Time           | 5.4 years  |

---

# Requirements

Home Assistant version:

```
2023.8+
```

---

# License

MIT License

---

# Author

Created by **Tobbe7612**

GitHub:
https://github.com/Tobbe7612/solar-battery-economy








