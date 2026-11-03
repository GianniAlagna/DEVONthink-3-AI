# Phase 0 spike report — FINAL (2026-10-31)

Floor machine: MacBook Pro 15" Mid 2014 · macOS 11.7.11 (20G1443) · i7-4770HQ (4C/8T, AVX2/FMA/F16C) · 16 GB · DT3 3.9.17.
Toolchain: Command Line Tools for Xcode 13.2 (Swift 5.5.2, clang 13.0.0, SDK 12.1). Six runs (kit v1–v6).
Legend: **verified** = measured on the floor machine.

**Gate passed:** Gianni approved Phase 0 on 2026-10-31; ADRs accepted. Next: Phase 1 (spec + plan).

## 1. Result in one table

| Step | Status | Key evidence |
|---|---|---|
| S0 Inventory | ✅ | header above |
| S1 Python runtime | ✅ | CPython 3.12.16, `minos 10.15`, SQLite WAL/JSON/FTS5, relocatable, start 0.02 s → ADR-0001 |
| S2 llama.cpp | ✅ | latest tag b12015 builds in 353 s, `minos 11.0` → ADR-0002 |
| S3 Models | ✅ | Qwen3-1.7B: 20/20 schema-valid, ~20 s/doc, 1.9 GB → ADR-0003, ADR-0009 |
| S4 DT3 scripting | ✅ (1 open item) | all A10 options, import, duplicate detection; no JXA reminders, no DT3 OCR → ADR-0004 |
| S5 Automation (TCC) | ✅ | grant persists across restarts; shown as "python3.12" → ADR-0005 |
| S6 Vision | ✅ | OCR de/fr/it/en 0.966–1.000; QR-bill byte-exact → ADR-0006 |
| S7 LaunchAgent + socket | ✅ | KeepAlive, `0600`, schema-checked JSON-RPC → ADR-0007 |
| S8 Menu-bar app + signing | ✅ | universal app opens; **self-signed certificate keeps the DT3 permission across updates** → ADR-0008, ADR-0010 |
| Smart Rule entry point | ❌ open | see §4 |

## 2. Key numbers

| Measure | Value |
|---|---|
| AI per 1-page document (Qwen3-1.7B, 4 threads) | median **19.9 s** (16.5–21.6) |
| AI schema compliance | **20 / 20** (after request fix) |
| AI field accuracy (synthetic invoices de/fr/it/en) | 78.6 % — errors deterministic (language, net vs total, one date) |
| Model peak memory footprint | 1.92 GB (Qwen3-1.7B) · 2.41 GB (Granite 3B) |
| OCR per page (Vision) | 1.7–5.9 s |
| QR-bill decode | 0.3–0.8 s, byte-exact |
| DT3 Apple event round trip | median 220 ms |
| llama.cpp build on floor | 353 s |

## 3. Findings that change the brief

| # | Finding | Change |
|---|---|---|
| F1 | DT3 OCR command unusable from scripts | Vision OCR for every text-less document (A1); DT3 OCR not used |
| F2 | DT3 `reminder` via JXA crashes `osascript` | B5 reminders via macOS Reminders/Calendar (or AppleScript) — spike in Phase 4 |
| F3 | Automation grant attaches to the interpreter ("python3.12") | Swift "DT3 Agent Bridge" sends Apple events (ADR-0005) |
| F4 | Ad-hoc signing → new permission prompt after every update | Project **self-signed certificate** for all binaries (ADR-0010) |
| F5 | AI wrong on language/amount/date in a fixed way | Rules-first for those fields (ADR-0009) — confirms brief §3.2 |
| F6 | llama.cpp README's `response_format` form is ignored by the server | Use `response_format.json_schema.schema` (ADR-0002) |
| F7 | `plainText` creates empty records | Always `content` (ADR-0004) |

## 4. Open item: Smart Rule entry point

| Run | What happened |
|---|---|
| 4 | JXA `performsmartrule` ran once and returned at once, with **0 records** |
| 5, 6 | Applied to documents: **no file** from the JXA nor the AppleScript probe; DT3 Log empty |
| Menu script | ✅ works (`run()` + `selectedRecords()`, UUID written) |

**Assessment:** DT3 does not run the external scripts for the configured rule (conditions, scope or script binding), not a crash in the script. **Risk for Phase 2** (walking skeleton starts with "Smart Rule → queue").
**Mitigation:** Phase 2 task 1 = Smart Rule on the floor with screenshots of the rule editor; fallback paths that are already verified: Menu script, and engine-side pull of new records by `additionDate` (AppleEvents verified).

## 5. Not covered (by design or deferred)

- Apple Silicon run (Q6 machine) — before release, per brief §8.2.
- Real 8 GB machine — before release (R1).
- Embeddings / chat (Block C) — Phase 6.
- Granite 3B with schema — optional; default decided on Qwen3-1.7B.

## 6. Cleanup on the floor machine (when done)

```bash
cd ~/dt3agent-spike-kit && bash spike/run.sh s7 uninstall
```
```bash
rm -rf ~/dt3agent-spike ~/dt3agent-spike-kit
```
Then in DT3: delete the Spike database and the two test Smart Rules; in Finder: the three `DT3Agent Spike Enqueue*.scpt` files in `~/Library/Application Scripts/com.devon-technologies.think3/`. Keep the **"DT3 Agent Spike Signing"** certificate only if you want to reuse it for tests; the product certificate is created separately (ADR-0010).

## 7. ADR index (all Accepted)

| ADR | Decision |
|---|---|
| [0001](../adr/0001-python-runtime.md) | Bundle CPython 3.12.16 (python-build-standalone) |
| [0002](../adr/0002-llama-cpp-build.md) | Build latest llama.cpp from source, target 11.0 |
| [0003](../adr/0003-default-model.md) | Qwen3-1.7B Q4_K_M default |
| [0004](../adr/0004-dt3-api-surface.md) | Verified DT3 3.9 command set |
| [0005](../adr/0005-process-model-apple-events.md) | Swift bridge sends Apple events |
| [0006](../adr/0006-vision-helper.md) | Vision for OCR + QR-bill |
| [0007](../adr/0007-launchd-socket.md) | LaunchAgent + `0600` Unix socket |
| [0008](../adr/0008-toolchain.md) | Command Line Tools for Xcode 13.2 |
| [0009](../adr/0009-rules-first.md) | Rules first for language, amounts, dates |
| [0010](../adr/0010-signing-without-developer-id.md) | Self-signed project certificate, no notarization |
