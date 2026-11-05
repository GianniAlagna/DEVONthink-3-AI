# Phase 3 floor report (MacBook Pro 2014, macOS 11.7.11, DT3 3.9.17)

Runs on 2026-11-05: run 1 (kit c929fe03), run 2 (kit 75eeb6f5), retest 2 (kit f47962e5). Test database only. Nothing deleted.

| Point | Result | Evidence |
|---|---|---|
| Name proposal (A6) | verified | `decide 3 accept` → `applied: true` (real invoice) |
| Comment / summary (A8) | verified | `decide 4 accept` → `applied: true` |
| Re-check older pipeline | verified | run 2: all jobs `applied`, none `skipped` |
| Exact duplicate (A10) | verified | 3 pairs `duplicate_exact`, score 1.0 |
| Urgent letter | verified | `urgent_letter`: Betreibungsamt, Zahlungsbefehl, Betreibung |
| Case match | verified | `case_match` → `/Recht/Fall-Muster/` |
| Unknown date → low confidence | verified | Veranlagungsverfügung: name with confidence 0.0, review only |
| Case replicate on accept | **failed** | `decide 9/5 accept` → `group_not_found` |
| Dry-run | verified | retest 2: `engine job planned`, 8 planned items, nothing written |
| Metadata values (A4/A5) | verified | planned: date 2026-04-17, total CHF 1957.04, IBAN, lang de (conf 0.95) |
| Metadata, filing written | open | screenshot missing |
| OCR of a scan | open | not run |
| Smart Rule "On Import" | open | all 4 jobs came from `process` |

## Bugs found and fixed

1. A failed decision removed the item from the review list (items 5 and 9 vanished after `group_not_found`).
   Fix: the decision is reopened when the write fails. Test: `test_failed_decision_keeps_the_item_open`.
2. `group_not_found` for `/Recht/Fall-Muster/`. Cause **UNVERIFIED**: either the group did not exist, or
   `getRecordAt` does not accept the trailing `/`. Fix: the host tries the path as given, then without the
   trailing `/`. Retest step C checks both forms on the floor.

3. Retest 2: `getRecordAt` returned nothing for both path forms (`null`, `null`). Either the group does not
   exist, or `getRecordAt` does not work like this in JXA (**UNVERIFIED**). Fix: if `getRecordAt` finds nothing,
   the host walks the path name by name from the database root (read-only). Retest 3 step B lists the groups.

Next: `docs/floor/phase3-retest.md` (retest 3, open points only).
