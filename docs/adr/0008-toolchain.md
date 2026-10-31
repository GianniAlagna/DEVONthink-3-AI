# ADR-0008: Floor toolchain

Status: **Proposed** (Phase 0, 2026-10-31) — accepted when Gianni approves the spike report.

## Context
Brief §2.2: Xcode 13.2.x max, Swift 5.5.

## Decision
**Command Line Tools for Xcode 13.2** (Swift 5.5.2, clang 13.0.0, SDK 12.1) are enough to build the engine dependencies, Vision helper and app with `swiftc` + `lipo`. Full Xcode is optional on the floor.

## Evidence (floor machine, see `docs/spike/phase0-report.md`)
S0/S6/S8: universal builds `minos 11.0`. CLT 12.5.1 (Swift 5.4.2) failed against the 12.1 SDK.

## Consequences
- Document CLT 13.2 as the floor requirement for contributors.
- `sdef` needs full Xcode (not needed).
