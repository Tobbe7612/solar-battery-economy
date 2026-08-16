# Project Documentation

This directory contains the permanent engineering and AI handoff documentation for **Solar Battery Economy**.

## Start here

For a new developer or AI/chat taking over the project:

1. Read [`PROJECT_HANDOFF.md`](PROJECT_HANDOFF.md)
2. Read [`ARCHITECTURE_NOTES.md`](ARCHITECTURE_NOTES.md)
3. Use [`DEVELOPMENT_WORKFLOW.md`](DEVELOPMENT_WORKFLOW.md) before changing code
4. Use [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) before publishing a release
5. Use [`AI_HANDOFF_TEMPLATE.md`](AI_HANDOFF_TEMPLATE.md) when handing the project to another AI

## Documentation status

This documentation was generated from an audit of the repository supplied with the project handoff ZIP.

**Repository code version:** `1.4.0` (`custom_components/solar_battery_economy/manifest.json` and `const.py`)

The repository's current README contains historical changelog entries through `v1.3.1`, but does not contain a `v1.4.0` changelog entry. Do not infer release history from the manifest alone; verify GitHub tags/releases when exact release chronology matters.

## Evidence labels

- **CONFIRMED** — directly supported by the supplied current code.
- **HISTORICAL** — documented as a previous implementation/decision, not the current implementation.
- **KNOWN ISSUE** — a current code/design issue identified during audit.
- **TODO** — an intentional future task.
- **ASSUMPTION** — not verified against current code and must not be treated as fact.

The documentation deliberately avoids treating earlier ChatGPT proposals as current architecture unless the supplied code confirms them.
