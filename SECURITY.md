# Security policy

DT3 Agent processes private documents locally. Security reports are taken seriously.

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's private reporting: **Security → Report a vulnerability** on this repository.
Include: affected version/commit, macOS and DEVONthink versions, steps to reproduce, impact.

## Scope

- The engine, the Swift app/helpers, the DEVONthink scripts and the build/release pipeline in this repository.
- Out of scope: DEVONthink itself, third-party AI servers, models.

## Design principles

No delete actions · no telemetry · arguments never string-built · AI output validated before use · Unix socket `0600` · secrets only in the macOS Keychain. See [`docs/SPEC.md`](docs/SPEC.md) §9.
