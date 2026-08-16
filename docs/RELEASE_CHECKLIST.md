# Release Checklist

## Before coding is frozen

- [ ] Confirm intended version number.
- [ ] Confirm scope of release.
- [ ] Review all changed files.
- [ ] Confirm no unrelated refactors slipped in.
- [ ] Update documentation for behavior changes.

## Version

- [ ] Update `custom_components/solar_battery_economy/manifest.json`.
- [ ] Update `custom_components/solar_battery_economy/const.py` `INTEGRATION_VERSION`.
- [ ] Confirm the two version values match.
- [ ] Update README changelog.
- [ ] Add a GitHub release/tag with the same version.

## Config flow

- [ ] Fresh install.
- [ ] Existing config entry upgrade.
- [ ] Options flow.
- [ ] Advanced Mode off.
- [ ] Advanced Mode on.
- [ ] Reload after options changes.
- [ ] Restart after options changes.
- [ ] Confirm all expected sensors are created.
- [ ] Confirm entity IDs are not unexpectedly recreated.

## Calculations

- [ ] Verify power-flow directions.
- [ ] Verify energy accumulation.
- [ ] Verify money accumulation.
- [ ] Verify total savings.
- [ ] Verify annual savings.
- [ ] Verify ROI.
- [ ] Verify payback time.
- [ ] Verify payback date.
- [ ] Verify solar/battery investment separation.
- [ ] Verify zero export price.
- [ ] Verify grid-charged battery.
- [ ] Verify solar-charged battery.

## Persistence

- [ ] Record energy totals before restart.
- [ ] Record money totals before restart.
- [ ] Restart Home Assistant.
- [ ] Confirm energy totals restored.
- [ ] Confirm money totals restored.
- [ ] Confirm install date remains stable.
- [ ] Confirm annual estimates do not reset unexpectedly.
- [ ] Confirm one-time migrations do not repeat.

## Energy Dashboard / statistics

- [ ] Verify energy sensors retain `kWh`.
- [ ] Verify `device_class=energy`.
- [ ] Verify `state_class=total_increasing`.
- [ ] Verify values do not move backwards.
- [ ] Verify no artificial large consumption spike appears after restart.
- [ ] Check long-term statistics after a representative period.

## Logs

- [ ] No integration setup errors.
- [ ] No listener exceptions.
- [ ] No `Task exception was never retrieved`.
- [ ] No Python syntax/import errors.
- [ ] No unexpected unavailable/unknown sensor states.

## GitHub

- [ ] `git status`
- [ ] `git diff`
- [ ] Commit.
- [ ] Push.
- [ ] Verify repository contents.
- [ ] Create release.
- [ ] Create matching tag.
- [ ] Verify release assets if any.
- [ ] Verify README renders correctly.

## HACS

- [ ] Confirm `hacs.json`.
- [ ] Confirm manifest version.
- [ ] Confirm README.
- [ ] Confirm repository is installable.
- [ ] Confirm HACS sees the new release.
- [ ] If changing HACS metadata, test both fresh install and upgrade.

## Post-release

- [ ] Install/update from HACS.
- [ ] Restart.
- [ ] Check logs.
- [ ] Check key sensors.
- [ ] Check user-facing README.
- [ ] Monitor issue reports before beginning the next large refactor.
