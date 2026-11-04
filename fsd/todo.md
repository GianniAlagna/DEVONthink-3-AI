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

## Phase 3 — Block A (epics, sliced at phase start)
- A-1 rules: language, dates/times, amounts, IBAN/QR-IBAN (table-driven tests)
- A-2 naming engine (brief §5.1 test table)
- A-3 review store + decisions
- A-4 pipeline full A1–A9 (OCR hook to Vision stub, tags vocabulary, filing allowlist, summary)
- A-5 duplicates + case folders (A10)

## Phase 4 — Block B
- B-1 vision helper · B-2 QR-bill parser (SIX IG cited) · B-3 UID check digit (official source) · B-4 retention table · B-5 deadlines (reminder path decision) · B-6 urgent letters

## Phase 5 — App
- U-1 menu bar + status · U-2 onboarding · U-3 settings · U-4 review window · U-5 installer · U-6 de-CH/fr-CH/it-CH/en + accessibility pass

## Phase 6–8
- K-1…K-5 knowledge (brief Block C) · J/E epics (Blocks D/E) + 48 h soak · R-1 release (CI signing, DMG, docs, policies)
