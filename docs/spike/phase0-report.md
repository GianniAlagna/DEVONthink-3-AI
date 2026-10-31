# Phase 0 spike report — INTERIM (run 3, 2026-10-31)

Floor machine: MacBook Pro 15" Mid 2014 · macOS 11.7.11 (20G1443) · i7-4770HQ (4C/8T, AVX2/FMA/F16C) · 16 GB · DT3 3.9.17.
Toolchain since run 3: **Command Line Tools for Xcode 13.2** (Swift 5.5.2, clang 13.0.0, SDK 12.1).
Legend: **verified** = measured on the floor machine.

## Status per step

| Step | Status | Key evidence |
|---|---|---|
| S0 Inventory | ✅ verified | header above |
| S1 Python runtime | ✅ verified | CPython 3.12.16, `minos 10.15`, SQLite 3.53.1 with WAL + JSON + FTS5, relocatable, start 0.02 s |
| S2 llama.cpp | ✅ verified | latest tag **b12015** builds in 353 s, `minos 11.0`, only system libraries linked |
| S3 Models | 🟡 speed verified, quality not yet | schema was not applied (kit bug, fixed in v4) → 0/40 valid; values themselves mostly correct |
| S4 DT3 scripting | 🟡 core verified | extras crashed `osascript` (segfault) → isolated in v4 |
| S7 LaunchAgent + socket | ✅ verified | KeepAlive restart < 15 s, socket `0600`, invalid JSON-RPC rejected, path 69 / 103 bytes |
| S5 Automation (TCC) | ✅ verified (reboot test open) | grant listed as **"python3.12 → DEVONthink 3.app"**; kept across agent restarts |
| S6 Vision | ✅ verified | OCR de/fr/it/en + QR-bill byte-exact; universal binary |
| S8 Menu-bar app | 🟡 builds, did not open | universal build + ad-hoc signature OK; `open` → -10827 (stale Launch Services record) → fixed in v4 |

## S3 — models (floor machine, 4 threads, ctx 8192)

| Model (Q4_K_M, Apache-2.0) | Prompt t/s | Gen t/s | s / document* | Peak memory footprint |
|---|---|---|---|---|
| Qwen3-1.7B | 55 (bench) · 50 (real) | 12.3 · 10.4 | **29** (25–43) | **1.93 GB** |
| Granite-4.0-micro 3B | 27 · 29 | 6.9 · 5.5 | **46** (32–71) | **2.41 GB** |

\* ~210–250 prompt tokens + ~215–245 generated tokens per request. Memory pressure (`memory_pressure -l warn`): no measurable slowdown.

- **Root cause of 0 % valid:** the request used `response_format: {"type":"json_schema","schema":…}` (as in the llama.cpp README). In b12015 the server reads the schema only from `response_format.json_schema.schema` (`tools/server/server-common.cpp:1392-1394`), so it silently fell back to "any JSON object". Kit v4 uses the OpenAI form. **Fix verified in the cloud** with llama-server b12015 + Qwen3-0.6B: 4/4 responses schema-valid (before: 0/40).
- **Even unconstrained**, both models extracted sender, date, invoice number, total, due date and IBAN correctly from the German invoice (Qwen wrote the due date as "17. Mai 2026", not ISO).
- **Inference:** a 1-page document costs ~30 s (1.7B) / ~45 s (3B) on the floor; longer documents scale mostly with output length, which the schema will cut. Background processing is viable; interactive chat on the floor will feel slow → LAN server recommendation stands.

## S4 — DT3 3.9.17 scripting

| Capability | Result | Consequence |
|---|---|---|
| Address DT3 by bundle ID `com.devon-technologies.think3` | ✅ | check `version()` starts with `3.` |
| Create Markdown / text | ✅ with `content`; ❌ `plainText` → **empty record** | always `content` |
| Rename / tags / comment, read old values first | ✅ | undo journal possible |
| Custom metadata | ✅ keys stored with prefix `md`; dates stay dates | hash + pipeline version |
| `contentHash` | ✅ 40-hex | idempotency |
| Replicate · duplicate · move · item link · link note | ✅ all | all A10 options feasible |
| AppleEvent round trip | median **220 ms** | batch reads |
| Smart Rule / Menu folders | ✅ exist | install path confirmed |
| Smart Rule / Menu probe triggered | ⏳ not done (manual clicks pending) | — |
| Reminder, import, OCR, duplicate detection | ⏳ crashed `osascript` (rc 139) in one combined run | v4 runs each in its own process |
| `.sdef` dictionary | ⏳ not found within 2 levels; `sdef` tool needs Xcode | v4 reads `OSAScriptingDefinition` from Info.plist |

## S5 — Automation permission (TCC)

- Screenshot (System Preferences → Automation): **`python3.12` → DEVONthink 3.app** and Terminal → DEVONthink 3.app.
- The grant is attached to the **interpreter binary**, not to `osascript` or a product name. It persisted across two agent restarts (`s5 again`: rc 0, no prompt).
- **Product risk:** users would see "python3.12" asking to control DT3 (looks untrustworthy), and any Python update or re-sign may reset the grant.
- **Draft decision (ADR-0005):** the engine does not send AppleEvents itself. A small Swift helper inside the app bundle (working name "DT3 Agent Bridge") runs the JXA calls; the engine calls it with argv. The permission then shows a product name and the helper's identity changes only when we change it. Confirm with S8 (does the grant survive a rebuild?).

## S6 — Vision on macOS 11

| Check | Result |
|---|---|
| OCR languages (revision 2, accurate) | en-US, fr-FR, it-IT, de-DE, es-ES, pt-BR, zh-Hans, zh-Hant |
| OCR de / fr / it / en (char similarity) | **0.997 / 0.966 / 1.000 / 1.000** · 1.7–5.9 s per page |
| Swiss QR-bill (QRR + SCOR) | **byte-exact** payload, 0.3–0.8 s |
| Build | universal x86_64 + arm64, `minos 11.0` |

Note: French run logs "Resource initialization failed … RequiredAssets_fr.bundle … variants.dat" (missing language-model asset on this macOS install); accuracy still 0.966.

## S8 — menu-bar app

- Universal build and ad-hoc signature OK. Ad-hoc **designated requirement = cdhash** (changes with every build) → predicts a lost permission after every update; to be confirmed when the app opens (v4).
- Gatekeeper: `rejected` (expected without notarization).

## Decisions this run supports (draft ADR input)

| ADR | Draft decision | Evidence |
|---|---|---|
| 0001 Python runtime | Bundle python-build-standalone CPython 3.12.16 | S1 |
| 0002 llama.cpp | Build latest tag from source, target 11.0, Metal/Accelerate/BLAS/OpenMP off | S2 |
| 0003 Default model | Qwen3-1.7B Q4_K_M as floor default (speed, 1.9 GB); Granite-4.0-micro as "quality" option — **pending S3 with schema** | S3 |
| 0004 DT3 API surface | `content` not `plainText`; bundle-ID addressing; batch AppleEvents | S4 |
| 0005 Process model | Swift bridge helper sends AppleEvents (not python3.12) | S5 |
| 0006 Vision helper | Vision OCR revision 2 + barcode detection meet de/fr/it/en + QR-bill | S6 |
| 0007 launchd + socket | LaunchAgent with KeepAlive; socket in Application Support, `0600` | S7 |
| 0008 Toolchain | Command Line Tools for Xcode 13.2 suffice for the spike; Swift 5.5.2 | S0, S6, S8 |

## Open before the final report

1. S3 again with the corrected schema request (quality + speed)
2. S4 extras (reminder, import, OCR, duplicate detection) + Smart Rule / Menu probe clicks + `s4 check`
3. S8 build 1 and 2 opening, permission kept or lost after rebuild
4. S5 after a Mac restart
