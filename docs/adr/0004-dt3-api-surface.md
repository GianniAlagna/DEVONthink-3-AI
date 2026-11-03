# ADR-0004: DT3 3.9 scripting surface

Status: **Accepted** (2026-10-31, Phase 0 approved by Gianni).

## Context
The DT3 adapter must use only commands verified on DT3 3.9.17.

## Decision
Address DT3 by bundle ID `com.devon-technologies.think3`, refuse if `version()` does not start with `3.`. Create records with `createRecordWith({…, content})` (never `plainText`). Use `import(path, {to})`, `addCustomMetaData`/`getCustomMetaData` (stored keys get prefix `md`), `contentHash`, `numberOfDuplicates`/`duplicates()`, `replicate`, `duplicate`, `move`, `referenceURL`. Text-layer check: `wordCount == 0` ⇒ OCR via Vision. **Do not** use DT3 `ocr`/`convertImage` ("Parameter is missing" in all forms) or the `reminder` property via JXA (crashes osascript).

## Evidence (floor machine, see `docs/spike/phase0-report.md`)
S4 runs 2–5 (all listed commands verified; reminder segfault; OCR errors). Round trip median 220 ms.

## Consequences
- Batch reads per record; one `osascript` call per record, not per field.
- B5 reminders: macOS Reminders/Calendar via EventKit in the app, or AppleScript — separate spike in Phase 4.
- Smart Rule entry point not yet verified (see report, open item).
