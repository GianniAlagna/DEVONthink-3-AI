# Todo — Phase 2 (walking skeleton) in detail, later phases as epics

Status: **APPROVED by Gianni 2026-11-03.** Phase 2 complete on the floor 2026-11-04 — **awaiting gate approval** ([report](../docs/floor/phase2-report.md)). Sizes: XS 1 file · S 1–2 · M 3–5 · L 5–8 (split).

## Phase 2 — Walking skeleton (CLI only)

- [x] **T1: DT3 trigger resolved** (risk P1) — done 2026-11-03: external AppleScript works after a DT3 restart (report §4)
  - Acceptance: a documented way in which DT3 3.9.17 hands UUIDs to an external script **or** the decision to use pull + Menu script in v1 · evidence in `docs/spike/phase0-report.md` §4
  - Verify: floor run with rule-editor screenshots; `spike/run.sh s4 check` shows UUIDs
  - Depends on: — · Files: `dt3-scripts/*`, report · Size: S
- [x] **T2: Repo skeleton + CI** — done 2026-11-03 (CI result: see PR)
  - Acceptance: `engine/` package, `pytest` + `ruff` pass in CI on `macos-15-intel` and `macos-15` · stdlib-only test for runtime imports
  - Verify: CI green · Depends on: — · Files: `engine/pyproject.toml`, `engine/tests/test_stdlib_only.py`, `.github/workflows/ci.yml` · Size: S
- [x] **T3: config + store + audit** — done 2026-11-03
  - Acceptance: atomic config write with backup · SQLite WAL with migrations · audit JSONL never contains a sentinel text
  - Verify: `pytest engine/tests/unit -k "config or store or audit"` · Depends on: T2 · Size: M
- [x] **T4: queue + intake (spool + pull)** — done 2026-11-03
  - Acceptance: spool file → one job; duplicate spool for same UUID → one job · partial/failed retry with back-off · pull by `additionDate` via fake adapter
  - Verify: unit + integration tests · Depends on: T3 · Size: M
- [x] **T5: engine-host (Swift) + bridge verbs `info`, `read`, `set_tags`** (risks P2, P3) — done 2026-11-03: floor shows "DT3 Agent Engine" in Automation, `read ok` via OSAKit (`set_tags` floor check in T6)
  - Acceptance: launchd starts the host, host starts Python, restarts it on crash · Automation entry shows "DT3 Agent Engine", not python3.12 · arguments reach DT3 without string building
  - Verify: floor run + screenshot of Automation list · Depends on: T2 · Files: `app/EngineHost/*`, `tools/build-swift.sh` · Size: M
- [x] **T6: dt3-adapter + fake adapter + undo** — merged 2026-11-04 (PR #7); floor: write + undo verified in the gate demo
  - Acceptance: `set_tags` journals old tags first · `undo last` restores exactly · refuses when DT3 is not 3.x
  - Verify: unit tests with fake adapter; floor: tag + undo on the Spike DB · Depends on: T4, T5 · Size: M
- [x] **T7: ai-adapter (llama.cpp) + fake AI server** — done 2026-11-04; floor: real call verified in the gate demo
  - Acceptance: schema request in the verified form · invalid JSON → no write, review item · explicit context size
  - Verify: integration test against fake server; floor: one real call · Depends on: T3 · Size: S
- [x] **T8: pipeline skeleton + dry-run** — done 2026-11-04; floor: `applied` and `no_text` verified
  - Acceptance: UUID → read → fake AI tag → (dry-run: planned only | live: write with undo) · idempotency by contentHash
  - Verify: integration test end-to-end with fakes · Depends on: T6, T7 · Size: M
- [x] **T9: CLI + rpc minimal + LaunchAgent install (Phase 2 gate)** — floor demo passed 2026-11-04 (`docs/floor/phase2-report.md`)
  - Acceptance: `dt3agent status|process|undo|pause|resume` · socket `0600` · install/uninstall commands
  - Verify: floor demo: new document → tag written → undo · Depends on: T8 · Size: M

## Phase 3 — Block A (inbox pipeline) in detail

Gate: Phase 2 **approved by Gianni 2026-11-04** ([floor report](../docs/floor/phase2-report.md)). Phase 3 sliced 2026-11-04.
Rule for every rule module: pure Python, table-driven tests, no AI, no I/O (SPEC §4.10).

- [x] **P3-1: rules — language** (A2) — done 2026-11-04 · Acceptance: de/fr/it/en + score by stop words; mixed or short text → `None` with low score · Verify: table test with the 4 synthetic invoices + edge cases · Size: S
- [x] **P3-2: rules — dates and times** (A4) — done 2026-11-04 · Acceptance: `17.04.2026`, `17. April 2026`, `3 mars 2026`, `9 febbraio 2026`, `January 20, 2026`, times `14:30` → ISO + position; invalid dates rejected · Verify: table test per language · Size: S
- [x] **P3-3: rules — amounts** — done 2026-11-04 · Acceptance: `CHF 1'957.04`, `1 957,04 CHF`, `Fr. 249.98` → Rappen int + currency + label (total/net/VAT) from "Total/Totale/Montant…" lines · Verify: table test · Size: S
- [x] **P3-4: rules — IBAN, QR-IBAN, QR reference, SCOR** — done 2026-11-04 · Acceptance: mod 97 (ISO 13616), QR-IID 30000–31999, QR ref mod 10 recursive, SCOR ISO 11649 — each cited in code · Verify: table test incl. the Phase 0 QR-bill fixtures · Size: S
- [x] **P3-5: rules — keywords** — done 2026-11-04 (A3 hints, urgent hints) · Acceptance: user-editable lists in config, doc-type + urgent hints with matched word positions · Verify: table test · Size: S
- [x] **P3-6: naming engine** — done 2026-11-05 (A6, brief §5.1) · Acceptance: the brief §5.1 rules exactly (template, `YYYYMMDDHHMMSS`, separators, forbidden chars, NFC, no `ß`, per-field max, ≤ 200, `unknown`, `_2`/`_3`) · Verify: brief §5.1 test table · Size: M
- [x] **P3-7: review store + decisions** — done 2026-11-05 · Acceptance: items per field (before/after, confidence, source); accept / edit / reject via CLI; decisions audited · Verify: unit + CLI tests · Size: M
- [x] **P3-8: Vision OCR hook** — done 2026-11-05 (floor check in P3-11) (A1) · Acceptance: `wordCount == 0` → Vision helper (ADR-0006) → text for analysis only, original untouched · Verify: fake helper in tests; floor: the scanned PDF from the Phase 2 run · Size: M
- [x] **P3-9: pipeline full A1–A9** — done 2026-11-05 (a-d; floor in P3-11) — split at start into (a) field merge rule > QR > AI with confidence and thresholds, (b) write verbs `set_name`, `set_comment`, `set_metadata`, `move` with undo, (c) filing allowlist + `_AI-Review`, (d) summary · Size: L (split)
- [x] **P3-10: duplicates + case folders** — done 2026-11-05 (floor in P3-11) (A10, brief §5.2) · Acceptance: exact + near duplicates → review items only; actions only after the user's choice · Size: M
- [x] **P3-11: Phase 3 floor gate** — floor runs done 2026-11-05 (`docs/floor/phase3-report.md`); approved by Gianni 2026-11-05 · Acceptance: real inbox sample (test DB) → names, tags, filing, review; Smart Rule "On Import" verified (carried from Phase 2) · Size: S

## Phase 4 — Block B
- B-0 (from Phase 3 floor): review items whose DT3 record no longer exists → mark `record_missing`, do not offer accept; guide hint "select a document first" for osascript checks
- B-1 vision helper · B-2 QR-bill parser (SIX IG cited) · B-3 UID check digit (official source) · B-4 retention table · B-5 deadlines (reminder path decision) · B-6 urgent letters

## Phase 5 — App
- U-1 menu bar + status · U-2 onboarding · U-3 settings · U-4 review window · U-5 installer · U-6 de-CH/fr-CH/it-CH/en + accessibility pass

## Phase 6–8
- K-1…K-5 knowledge (brief Block C) · J/E epics (Blocks D/E) + 48 h soak · R-1 release (CI signing, DMG, docs, policies)
