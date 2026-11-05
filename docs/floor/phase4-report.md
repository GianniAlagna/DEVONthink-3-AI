# Phase 4 floor report (MacBook Pro 2014, macOS 11.7.11, DT3 3.9.17)

Runs on 2026-11-05 with kits 2353e4c9, 68be46e7, b5bd86d2 and f4bc787d. Test database only. Nothing deleted.

| Point | Result | Evidence |
|---|---|---|
| B-0 missing record | verified | items 12, 24: `record_missing: true`, `actions: ["reject"]`; `decide 12 accept` → `record_missing` |
| B-1/B-2 QR-bill (synthetic PDF) | verified | record 2BA1C95E custom metadata: `dt3agentiban` CH4431999123000889012, `dt3agenttotal` CHF 1957.04, `dt3agentreference` 210000000003139471430009017 (applied directly, confidence 0.95) |
| B-3 UID | tests only | no sample on the floor carries a UID; check digit (eCH-0097 §2.4) covered by `test_rules_uid.py` |
| B-4 retention | verified | `dt3agentretention` 2036-12-31 and `dt3agentretentionbasis` "OR Art. 958f · Hinweis, Keine Rechtsberatung" in review |
| B-5 deadline detection | verified | `stated_deadline` 2026-12-17, phrase "zahlbar bis", title "Frist: Muster Verwaltung AG, CHF 312.40" |
| B-5 no overwrite | verified | record with a hand-set reminder: `decide 195 accept` → `reminder_exists`, nothing changed |
| B-5 reminder + .ics | verified | `decide 272`, `308`, `347 accept` → `applied: true` (host returns only after reminder and .ics import) |
| B-6 Betreibung | verified | hint "Rechtsvorschlag … SchKG Art. 74 Abs. 1 – bitte prüfen"; accept → record in `_Urgent` (items 176, 335, 395, 515) |
| B-6 tax office | verified | record 158E9F3A: `words: ["Steueramt"]`, `hints: []`; `decide 530 accept` → `applied: true` |
| Queue recovery | verified | stuck `running` job ended as `interrupted`, queue `done` 26 |

## Bugs found and fixed

1. A job stuck in `running` blocked the queue; `install && live on` raced the engine start (PR #39).
2. Accepting an urgent item added the trigger words as tags; it now moves the record to `_Urgent`.
3. Deadline accept returned a bare `apply_failed`; the host's code is now passed through (PR #40).
4. `make new reminder … at r` failed (-10008) and reading `reminder of r` without one raised -2763.
   Fixed with the form from DT3's own "Remind Me Tomorrow" script: `tell r to make new reminder …`, read in `try` (PR #41).
5. Tax office letter not flagged. Two causes: the saved test config kept the Phase 3 urgent words (PR #42), and
   the running engine kept its old settings in memory, so `live on` wrote them back over `testconfig` (PR #43).
   `testconfig` now refreshes the words and restarts the engine.

## Follow-ups

- Phase 5: the settings UI changes the config while the engine runs; the engine must reload it instead of
  saving a stale copy (cause of bug 5).
- Calendar screenshot (.ics opened in macOS Calendar) not taken; the import itself is verified.

Result: all Phase 4 points verified on the floor except B-3 (unit tests only, no floor sample).
