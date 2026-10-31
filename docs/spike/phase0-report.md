# Phase 0 spike report — run 5 (2026-10-31), near-final

Floor machine: MacBook Pro 15" Mid 2014 · macOS 11.7.11 (20G1443) · i7-4770HQ (4C/8T, AVX2/FMA/F16C) · 16 GB · DT3 3.9.17.
Toolchain: Command Line Tools for Xcode 13.2 (Swift 5.5.2, clang 13.0.0, SDK 12.1).
Legend: **verified** = measured on the floor machine.

## Status per step

| Step | Status | Key evidence |
|---|---|---|
| S0 Inventory | ✅ verified | header above |
| S1 Python runtime | ✅ verified | CPython 3.12.16, `minos 10.15`, SQLite 3.53.1 (WAL, JSON, FTS5), relocatable, start 0.02 s |
| S2 llama.cpp | ✅ verified | latest tag b12015 builds in 353 s, `minos 11.0`, system libraries only |
| S3 Models | ✅ verified | Qwen3-1.7B: **20/20 schema-valid**, ~20 s / document, 1.9 GB |
| S4 DT3 scripting | ✅ verified (2 gaps) | all A10 options, import, duplicate detection; reminders crash JXA; DT3 OCR command unusable → Vision |
| S5 Automation (TCC) | ✅ verified | grant on `python3.12` survives agent restarts **and a Mac restart** |
| S6 Vision | ✅ verified | OCR de/fr/it/en 0.966–1.000, QR-bill byte-exact |
| S7 LaunchAgent + socket | ✅ verified | KeepAlive restart < 15 s, socket `0600`, invalid JSON-RPC rejected |
| S8 Menu-bar app | ✅ opens, real Apple event works; 🟡 update behaviour to confirm | run 5: `count of databases` → **macOS asked for permission**, popover "DT3 open databases: 3"; build 2 has a new cdhash (`1d67e02f…` → `536f77d0…`) and **macOS asked again** (confirmed by Gianni) → ad-hoc signing loses the permission on every update; self-signed certificate test pending |

## S3 — models (floor, 4 threads, ctx 8192, temperature 0)

| Model (Q4_K_M, Apache-2.0) | Schema-valid | s / document | Field accuracy | Peak memory footprint |
|---|---|---|---|---|
| **Qwen3-1.7B** (run 4, schema fixed) | **20 / 20** | **19.9** (16.5–21.6) | 78.6 % | **1.92 GB** |
| Granite-4.0-micro 3B (run 3, no schema) | — | 45.5 | not measured | 2.41 GB |

Bench: Qwen3-1.7B pp512 42–55 t/s, tg128 12–13 t/s. Memory pressure (`memory_pressure -l warn`): no slowdown (18.1 s median).

Field errors (identical in every run — deterministic at temperature 0):

| Field | Result | Consequence (design rule 3.2-1 "rules first") |
|---|---|---|
| language | always `de` | **language detection by rules** (stop-word scoring, pure Python), never AI |
| amount | EN: net 925.07 instead of total 1'000.00 | amounts from **rules** (total line, QR-bill) — AI value only as fallback + Review Queue |
| document date | FR: 03-01 instead of 03-03 | dates from **rules** first |
| doc type | DE: `receipt` instead of `invoice` | AI classification stays below threshold → Review Queue; keyword rules as tie-breaker |
| sender, due date, currency | correct | AI usable for sender/receiver/subject/summary |

## S4 — DT3 3.9.17 scripting

| Capability | Result | Consequence |
|---|---|---|
| Address DT3 by bundle ID, `version()` = 3.9.17 | ✅ | refuse if not `3.` |
| Create Markdown / text | ✅ `content`; ❌ `plainText` → empty record | always `content` |
| Rename / tags / comment, read old values | ✅ | undo journal |
| Custom metadata | ✅ (stored keys prefixed `md`, dates stay dates) | hash + pipeline version |
| `contentHash` | ✅ 40-hex; identical content → identical hash | idempotency |
| **Duplicate detection** | ✅ identical text → `numberOfDuplicates` = 1, `duplicates()` lists the other UUID | use DT3's own exact-duplicate info (A10) |
| Replicate · duplicate · move · item link · link note | ✅ | all A10 options feasible |
| **Import file** | ✅ `import(path, {to: group})` | — |
| Text layer check (A1) | ✅ vector PDF → kind `PDF+Text`, 90 words; scanned PDF → kind `PDF document`, 0 words | A1 rule: `wordCount == 0` ⇒ needs OCR |
| DT3 OCR (`ocr`, `convertImage`) | ❌ "Parameter is missing" in all forms; dictionary file not found to check names | **use Vision OCR for analysis** (S6 proves quality); original untouched |
| Reminder | ❌ setting `reminder` **crashes osascript** (segfault); `make` → "index too large" | B5: reminders via macOS Reminders/Calendar (EventKit, user picks) or AppleScript — spike in Phase 4 |
| AppleEvent round trip | median **220 ms** | batch reads per record |
| Menu script | ✅ `run()` + `selectedRecords()` → UUID written, returned at once | — |
| Smart Rule script | ❌ run 4: called with **0 records**; run 5: applied to documents, **no trace at all** | kit v6: JXA probe that logs even on error + AppleScript variant |

## S5 — Automation permission (TCC)

- System Preferences → Automation shows **`python3.12` → DEVONthink 3.app** (and Terminal).
- Grant kept across agent restarts and **after a full Mac restart** (run 4: probe rc 0, no prompt).
- **Draft ADR-0005:** the engine must not appear as "python3.12". A small Swift helper inside the app bundle ("DT3 Agent Bridge") sends the Apple events; the engine calls it with argv. Confirm signing behaviour with S8 v5.

## S6 — Vision on macOS 11

| Check | Result |
|---|---|
| OCR languages (revision 2, accurate) | en-US, fr-FR, it-IT, de-DE, es-ES, pt-BR, zh-Hans, zh-Hant |
| OCR de / fr / it / en | char similarity **0.997 / 0.966 / 1.000 / 1.000**, 1.7–5.9 s per page |
| Swiss QR-bill (QRR + SCOR) | **byte-exact**, 0.3–0.8 s |
| Build | universal x86_64 + arm64, `minos 11.0` |

## S8 — menu-bar app

- Universal build, ad-hoc signature, Launch Services re-register → **opens on macOS 11**, SwiftUI popover works (screenshot: "DEVONthink 3.9.17").
- Ad-hoc designated requirement = **cdhash** → every build is a new identity (predicts: permission asked again after each update).
- Open: does an ad-hoc rebuild lose the permission? Does a self-signed certificate keep it? → kit v5.

## Draft decisions (ADR input)

| ADR | Draft decision | Evidence |
|---|---|---|
| 0001 Python runtime | Bundle python-build-standalone CPython 3.12.16 | S1 |
| 0002 llama.cpp | Build latest tag from source, target 11.0, Metal/Accelerate/BLAS/OpenMP off | S2 |
| 0003 Default model | **Qwen3-1.7B Q4_K_M** default on the floor (20/20 valid, ~20 s, 1.9 GB); larger model only as option | S3 |
| 0004 DT3 API surface | `content` not `plainText`; bundle-ID addressing; `import`; DT3 duplicate info; no DT3 OCR; no JXA reminders | S4 |
| 0005 Process model | Swift bridge helper sends Apple events (not python3.12) | S5 (+ S8 v5) |
| 0006 Vision helper | Vision OCR revision 2 + barcode detection for all text and QR-bill work | S6 |
| 0007 launchd + socket | LaunchAgent with KeepAlive; socket in Application Support, `0600` | S7 |
| 0008 Toolchain | Command Line Tools for Xcode 13.2 (Swift 5.5.2); full Xcode not required | S0, S6, S8 |
| 0009 Rules first | Language, amounts, dates, IBAN, references by rules; AI for type/sender/subject/summary only | S3 field errors |

## Open before the final report (kit v5, ~10 min)

1. S8 build 1 + 2 with a real Apple event (`count of databases`) — permission kept or asked again?
2. Smart Rule on 2–3 **documents** — how many records arrive?
