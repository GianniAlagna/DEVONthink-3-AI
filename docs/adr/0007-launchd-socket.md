# ADR-0007: Engine process and socket

Status: **Accepted** (2026-10-31, Phase 0 approved by Gianni).

## Context
The engine must run when the app is closed and talk to the app safely.

## Decision
LaunchAgent in `gui/<uid>` with `RunAtLoad` and `KeepAlive`, installed via `launchctl bootstrap` after user consent. Unix socket in `~/Library/Application Support/DT3 Agent/`, directory `0700`, socket created `0600` (umask before bind). Every JSON-RPC message validated; anything else answered with `-32600`.

## Evidence (floor machine, see `docs/spike/phase0-report.md`)
S7: restart after kill within 15 s; socket `0600`; invalid and garbage messages rejected; path 69 of 103 bytes (34 spare).

## Consequences
- No `SMAppService` (macOS 13) needed.
- Uninstall = `launchctl bootout` + remove plist.
