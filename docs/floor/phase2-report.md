# Phase 2 gate — floor report (2026-11-04)

Floor machine: MacBook Pro 15" Mid 2014 · macOS 11.7.11 · 16 GB · DEVONthink 3.9.17 · Qwen3-1.7B Q4_K_M on llama.cpp b12015 (built on the floor).
Guide: [`phase2-gate.md`](phase2-gate.md). Legend: **verified** = seen on the floor machine.

**Gate result:** the walking skeleton works end to end on the floor: DT3 selection → engine (via "DT3 Agent Engine") → plain text → local AI → tag written with undo journal → undo restored it.

## 1. Results

| Check | Evidence (floor log / CLI output) | Status |
|---|---|---|
| Engine host owns the Automation grant (T5) | Automation list: "DT3 Agent Engine → DEVONthink 3.app" | verified |
| Bridge `info`, `read` with parameters (T5) | `dt3 version=3.9.17`, `read ok fields=[…]` | verified |
| Service + private socket + CLI (T9) | `tools/dt3agent status` → `dt3_version 3.9.17`, `ai_ok true` | verified |
| `selected` verb (DT3 selection) | `process` → `"queued": 1` for the selected record | verified |
| `read_text` (DT3 `plainText`) | text record (1766 words) → `job applied`; scanned PDF and image → `no_text` | verified |
| Real AI call, schema + vocabulary enum (T7) | `job applied` (only possible with a schema-valid answer and an allowed tag) | verified |
| Live write with undo journal (T6, T8) | `job applied`, then `undo` → `"restored": 1, "conflicts": []` | verified |
| No text → no write, review item (T8) | 2 records: `review` items `error / no_text`, tags unchanged | verified |
| Malformed record ID refused | `process "pbpaste"` → `bad_uuid` | verified |
| Dry-run is the default; `live on/off` saved | `"dry_run": true` after every install; `live off` at the end | verified |
| LaunchAgents start/stop cleanly | `SIGTERM, stopping engine` on uninstall; restart back-off seen in T5 | verified |

## 2. Not covered on the floor (carried forward)

| Item | Why | Where next |
|---|---|---|
| Smart Rule "On Import" → spool | no spool file seen; rule setup not confirmed | Phase 3 (A-4); on-demand trigger is verified (T1) |
| Dry-run `planned` item on the floor | all floor dry-run jobs had no text; covered by unit + e2e tests | Phase 3 review store (A-3) |
| Which tag the model chose | no screenshot; undo proves a tag was written and removed | Phase 3 tag quality (rules first, ADR-0009) |
| OCR for scans/images | by design: `no_text` until Vision is wired | Phase 3 (A-4, ADR-0006) |

## 3. Findings fixed during the gate

| Finding | Fix |
|---|---|
| Model download stopped at 82.6 % (`curl 56`, Mac fell asleep) | resume + retry + `caffeinate` (PR #11) |
| Clipboard held `pbpaste` instead of the item link (twice) | `dt3agent process` uses the DT3 selection (PR #12) |
| Review reason only visible with `sqlite3` | `dt3agent review` (PR #12) |
| Without a vocabulary the model returned field values as tags | tag vocabulary as schema `enum` (PR #10) |
