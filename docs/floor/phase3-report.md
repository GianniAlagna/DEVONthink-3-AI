# Phase 3 floor report (MacBook Pro 2014, macOS 11.7.11, DT3 3.9.17)

Runs on 2026-11-05: run 1 (kit c929fe03), run 2 (kit 75eeb6f5), retest 2 (kit f47962e5), retest 3 (kit 727d0fb4), retest 4 (kit dc4b0d35). Test database only. Nothing deleted.

| Point | Result | Evidence |
|---|---|---|
| Name proposal (A6) | verified | `decide 3 accept` → `applied: true` (real invoice) |
| Comment / summary (A8) | verified | `decide 4 accept` → `applied: true` |
| Re-check older pipeline | verified | run 2: all jobs `applied`, none `skipped` |
| Exact duplicate (A10) | verified | 3 pairs `duplicate_exact`, score 1.0 |
| Urgent letter | verified | `urgent_letter`: Betreibungsamt, Zahlungsbefehl, Betreibung |
| Case match | verified | `case_match` → `/Recht/Fall-Muster/` |
| Unknown date → low confidence | verified | Veranlagungsverfügung: name with confidence 0.0, review only |
| Duplicate accept (A10) | verified | retest 3: `decide 25 accept` → `applied: true` |
| Case replicate on accept | verified | diagnose kit 0b9895a8: `decide 51 accept` → `applied: true` (group named `Recht/Fall-Muster`) |
| Near duplicate (A10) | verified | `duplicate_near` item for the Zahlungsbefehl copy |
| Dry-run | verified | retest 2: `engine job planned`, 8 planned items, nothing written |
| Metadata values (A4/A5) | verified | planned: date 2026-04-17, total CHF 1957.04, IBAN, lang de (conf 0.95) |
| Metadata, filing written | verified | retest 4: `decide 30` (dt3agentdate) and `decide 34` (move to `/_AI-Review/`) → `applied: true` |
| OCR of a scan | verified | `ocr-de.pdf` (image only): name and comment built from the recognised text (Steueramt, Veranlagungsverfügung, 30 Tage) |
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

4. Retest 3, verified cause: the test database had **one** top-level group named `Recht/Fall-Muster`
   (a slash in the name), not `Fall-Muster` inside `Recht`. Same for `Finanzen/Rechnungen`. The setup
   message ("Create these groups: /Recht/Fall-Muster") was ambiguous. Fix: the message now says
   "Recht > Fall-Muster" and "never a / in a group name". Not a code bug.

5. Retest 4 + group listing (2026-11-05): the groups were still single top-level groups named
   `Recht/Fall-Muster` and `Finanzen/Rechnungen`. Fix: the host's read-only path walk also accepts a group whose
   own name holds the rest of the path. Checked with a node test of the host walk function.

6. Diagnosis (2026-11-05): records of earlier review items no longer exist in DT3 (`getRecordWithUuid` → null,
   with and without `in:`); removed outside the engine (the engine has no delete verb). Follow-up P4: review items
   whose record is gone must be marked, not offered for decision.

Open: Smart Rule "On Import" only.
