# AI Handoff Template — Home Assistant Project

Copy this template into a project's documentation and fill it with verified information.

## Project

**Name:**  
**Repository:**  
**Current version:**  
**Home Assistant minimum version:**  
**Current branch/tag:**  

## Purpose

What problem does the project solve?

## Current architecture

```text
Input
  ↓
Core/data layer
  ↓
Calculation/business layer
  ↓
Entities/UI/API
```

Describe each layer using actual files and functions.

## Current file structure

```text
custom_components/<domain>/
├── ...
```

## CONFIRMED behavior

List only behavior directly verified against current code.

## HISTORICAL behavior

List previous implementations that are no longer current.

## KNOWN ISSUES

For each issue:

- symptom
- affected file/function
- current impact
- workaround
- status

## TODO

List intentional future work.

## ASSUMPTIONS

List anything that has not been verified.

## Public contracts

Document:

- entity IDs
- unique IDs
- units
- device classes
- state classes
- service names
- config keys
- storage keys
- API contracts

## Persistence

Document:

- what is persisted
- where it is persisted
- restore behavior
- migrations
- restart behavior

## External dependencies

List:

- Home Assistant APIs
- HACS
- other integrations
- companion Lovelace cards
- external services

## Development rules

1. Read actual code first.
2. Do not guess missing code.
3. Identify dependencies before changing shared code.
4. Make the smallest safe change.
5. Test after meaningful changes.
6. Protect entity/statistics contracts.
7. Test restart and reload behavior.
8. Test upgrade behavior.
9. Update documentation after significant architectural changes.

## Release process

- [ ] version
- [ ] tests
- [ ] restart/reload
- [ ] persistence
- [ ] regression
- [ ] Git
- [ ] release/tag
- [ ] package/HACS distribution
- [ ] post-release verification

## Current handoff task

**What should the next AI/developer do?**

## Files the next AI must inspect

List exact files required before making changes.
