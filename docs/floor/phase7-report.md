# Phase 7 report — jobs and operations (MacBook Pro 2014, macOS 11.7, DT3 3.9.17)

Floor checks on 2026-11-06 with the kits "Prüfung 1/2" (test database DT3Agent-T1, test mode on).
Built and merged: PR #78–#96.

## Results

| Package | Check | Result |
|---|---|---|
| J-1 scope listing | `dt3agent list`, scope `DT3Agent-T1 /` | ✅ 6 records in 1.2 s (large database not measured) |
| E-6 power mode | `pmset -g batt`, `kern.memorystatus_vm_pressure_level` on macOS 11 | ✅ on AC: read correctly, not held · battery path: **probably fine**, unit-tested only (the floor Mac does not run without its charger) |
| Q-1 not-found threshold | 3 questions | ❌ at 0.35 (no-match question 0.43 reached the model) → **fixed: 0.47** (#96); real questions 0.50 and 0.64 |
| J-2 scheduler, J-3 nightly | `dt3agent job nightly` | ✅ runs recorded with `ok`; queueing of a changed record not observed (re-checked in the release test) |
| J-4 reports | `job digest`, `job hygiene` with group `/_Berichte/` | ✅ `ok`, two report items in the review list |
| E-7 API key | app saves `test-123`; `security find-generic-password -w`; `ai_key_found` | ✅ key read by `security` and the engine; whether macOS asked for a password: not reported |
| E-8 diagnostics | export button → zip in Downloads | ✅ 0 hits for database, group and document names; counts, error codes, LaunchAgent states, model sizes present |
| App | schedule tab, settings, menu | ✅ |

From the diagnostics: one `dead` job (`ai_unreachable`, morning of 2026-11-06, while the AI server was restarted)
and two `interrupted` jobs (engine restarts during installs) — not caused by Phase 7 code.

## Not built (known limits for v1.0.0)

- E-6 index-server idle stop: both AI servers use about 5 GB on the floor Mac; too much for 8 GB Macs.
- K-5 entities from a model-made list (only sender/receiver/QR creditor today).
- "Invoices due" in the weekly digest (amount and due date not stored together).
- Kind texts of RSS/mail records on DT3 3.9 (J-6) unverified.

## Moved to the Phase 8 release test

- P7-G 48 h soak (nightly run, digest, feeds, entities active; memory and CPU logged).
- K-5 and J-6 on the floor (built after the floor check).
- Q-1 with more questions (margin 0.43 / 0.50 is small).

## Decision

Phase 7 approved by Gianni on 2026-11-06 ("abnahmen ok, weiter die Phase 8. Aber noch nicht veröffentlichen").
