# Phase 0 spike report — INTERIM (run 2, 2026-10-31)

Floor machine: MacBook Pro 15" Mid 2014 · macOS 11.7.11 (20G1443) · i7-4770HQ (4C/8T, AVX2/FMA/F16C) · 16 GB · DT3 3.9.17.
Legend: **verified** = measured on the floor machine in this run.

## Status per step

| Step | Status | Key evidence |
|---|---|---|
| S0 Inventory | ✅ verified | see header; Command Line Tools 12.5.1 (Swift 5.4.2, clang 12.0.5); default SDK MacOSX12.1 |
| S1 Python runtime | ✅ verified | CPython 3.12.16, `minos 10.15`, SQLite 3.53.1 with WAL + JSON + FTS5, relocatable, start 0.02 s |
| S2 llama.cpp | ✅ verified | **latest tag b12015** builds in 353 s with AppleClang 12.0.5, `minos 11.0`, only system libraries linked |
| S3 Models | ⏳ not run | — |
| S4 DT3 scripting | 🟡 mostly verified | see below; reminders, import, OCR need run 3 |
| S7 LaunchAgent + socket | ✅ verified | bootstrap OK, KeepAlive restart after kill in < 15 s, socket `0600`, invalid JSON-RPC rejected, path 69 of 103 bytes |
| S5 Automation (TCC) | 🟡 partly | background engine → `osascript` → DT3 worked (rc=0, 4 s after reset). Missing: which app the dialog named (screenshot), persistence after restart |
| S6 Vision | ❌ blocked | Swift 5.4.2 compiler cannot read the Swift 5.5 SDK interface → kit v3 picks a matching SDK |
| S8 Menu-bar app | ❌ blocked | same cause as S6 |

## DT3 3.9.17 scripting (S4) — verified

| Capability | Result | Consequence for the engine |
|---|---|---|
| Target DT3 by bundle ID `com.devon-technologies.think3` | ✅ `version()` = 3.9.17 | Address DT3 by bundle ID, check `3.` prefix |
| Create Markdown | ✅ with `content`; ❌ `plainText` gives an **empty** record | Always use `content` |
| Rename / tags / comment, read old values first | ✅ | Undo journal possible |
| Custom metadata | ✅ `addCustomMetaData` / `getCustomMetaData`; stored keys get prefix `md`; dates kept as dates | Use for hash + pipeline version |
| `contentHash` property | ✅ 40-hex value | Idempotency without own hashing of the file |
| Replicate | ✅ same UUID, `numberOfReplicants` = 1 | Multi-context option works |
| Duplicate (copy) | ✅ new UUID | Works; DT3's own duplicate detection not yet shown (test used empty records) → run 3 |
| Move | ✅ | — |
| Item link | ✅ `x-devonthink-item://<UUID>`; link note with Markdown link created | Link-note option works |
| AppleEvent round trip | ✅ median **223 ms** (min 216, max 570) | Batch reads; never one call per field |
| Smart Rule / Menu script folders | ✅ both exist under `~/Library/Application Scripts/com.devon-technologies.think3/` | Install path confirmed |
| Reminder | ❌ `make` → "property, not an element" | run 3 tests two other forms |
| Import file | ❌ `importPath` not understood | run 3 uses `import` |
| OCR | ❌ "Parameter is missing" | run 3 tests two forms + `convertImage` |
| `sdef` tool | ❌ needs full Xcode | run 3 reads the dictionary file from the app bundle |

## Decisions this run supports (draft ADR input)

1. **Python runtime:** python-build-standalone CPython 3.12.16 works on the floor → bundle it (ADR-0001).
2. **llama.cpp:** build from source, latest tag, `CMAKE_OSX_DEPLOYMENT_TARGET=11.0`, Accelerate/Metal/BLAS/OpenMP off → no need to pin an old release (ADR-0002).
3. **Process model:** a launchd agent can drive DT3 through `osascript` → engine-side DT3 adapter is viable (ADR-0005, pending S5 evidence).

## Open before the final report

- S3 (models), S6, S8 after the toolchain fix
- S4 run 3 + `s4 check` (Smart Rule / Menu probes)
- S5 screenshot + `s5 again` before and after a restart
- Toolchain: install Command Line Tools for Xcode 13.2 (Swift 5.5.2) — the brief targets Swift 5.5
