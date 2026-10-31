# ADR-0001: Bundled Python runtime

Status: **Proposed** (Phase 0, 2026-10-31) — accepted when Gianni approves the spike report.

## Context
The engine must run offline on macOS 11 Intel without compiled dependencies (brief §2.3, §3.1).

## Decision
Bundle **python-build-standalone CPython 3.12.16** (release 20261026), one `install_only` build per architecture, inside the app bundle. Pin version and SHA-256 per release; verify the checksum against the release's `SHA256SUMS` at build time.

## Evidence (floor machine, see `docs/spike/phase0-report.md`)
S1: `minos 10.15`; SQLite 3.53.1 with WAL, JSON and FTS5; relocatable (moved folder still runs); start 0.02 s. S7: runs as LaunchAgent.

## Consequences
- No system Python, no Homebrew needed.
- ~100 MB per architecture in the bundle.
- The interpreter must never be the process that sends Apple events (see ADR-0005).
