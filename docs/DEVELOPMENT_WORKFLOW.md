# Development Workflow

## 1. Establish the current baseline

Before changing anything:

- identify the current Git branch/tag
- read the complete relevant files
- check `manifest.json` version
- check `const.py` integration version
- inspect current README/changelog
- inspect current HA logs
- note current entity IDs

Never start from an old ChatGPT-generated version of a file.

## 2. Identify the smallest change

Write down:

- affected file
- affected function/class
- input/output contract
- dependent sensors
- persistence implications
- entity/statistics implications

If the change affects a shared class such as `EconomySensor` or the coordinator, inspect every consumer first.

## 3. Preserve public entity contracts

Treat these as public API:

- entity IDs
- unique IDs
- names
- units
- device class
- state class
- sensor meaning

Avoid changing them unless the change is intentional and migration-safe.

## 4. Financial changes require hand calculations

For every financial formula change, test at least:

- no solar
- solar self-consumption
- solar export
- grid import
- grid charging
- battery discharge
- solar-charged battery discharge
- grid-charged battery discharge
- battery export
- zero export price

Compare the expected result with the sensor value.

## 5. Persistence changes require restart testing

For changes involving energy, money, install date or RestoreEntity:

1. record current values
2. restart/reload
3. verify values are restored
4. verify accumulation continues
5. inspect HA statistics
6. inspect Energy Dashboard if relevant

## 6. Do not use chance-coding

If the current code is unavailable:

> Stop and request the file.

Do not invent:

- function signatures
- Home Assistant APIs
- entity IDs
- config keys
- storage schemas.

## 7. Validate config flow changes

After config changes:

- fresh installation
- existing installation/options
- Advanced Mode on/off
- reload
- restart
- verify all expected entities
- verify unchanged entities retain their IDs

Pay particular attention to the current options-flow reload ordering.

## 8. Build/test

At minimum:

- Python syntax/import check
- Home Assistant integration setup
- no errors in logs
- sensor state validation

Prefer automated tests for calculation-heavy code.

## 9. Git workflow

Before commit:

```text
git status
git diff
```

Review every changed file.

Use focused commits.

Example:

```text
Fix persistent annualization reference
```

rather than vague messages such as:

```text
Update stuff
```

## 10. Release discipline

Do not release immediately after a large refactor.

Run:

- fresh-install test
- upgrade test
- restart test
- reload test
- sensor creation test
- financial sanity test
- Energy Dashboard/statistics test

Then update version and release notes.

## 11. AI handoff discipline

At the end of a significant change, update:

- PROJECT_HANDOFF.md
- ARCHITECTURE_NOTES.md
- known issues
- release history

The next AI should be able to determine the current state without relying on old chat history.
