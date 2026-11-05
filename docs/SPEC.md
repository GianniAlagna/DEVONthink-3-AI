# Spec: DT3 Agent (working name)

Status: **APPROVED by Gianni 2026-11-03** (Phase 1 gate passed). Changes to this spec go through a PR before the code that depends on them.
Sources: `docs/BRIEF.md` (incl. owner decisions), `docs/spike/phase0-report.md`, `docs/adr/0001…0010` (accepted).
Legend: **verified** = measured on the floor machine in Phase 0 · `UNVERIFIED` = to be proven in the named task.

---

## 1. Objective

| Item | Content |
|---|---|
| What | Open-source macOS menu-bar app that processes DEVONthink 3 documents with **local, private AI**: names, tags, files, summarises, finds duplicates, reads Swiss QR-bills, flags deadlines and urgent letters, answers questions with sources |
| For whom | Individuals on DT3 3.9.x; Swiss SMEs and fiduciaries via a modular.codes support plan |
| Why | DT3 has no built-in AI; DT4 does, but many users stay on DT3. Cloud AI is not acceptable for private documents (revDSG) |
| Success | A new invoice in an enabled DT3 group is named, tagged and filed correctly within 60 s on the floor machine, fully offline, with undo; anything uncertain lands in the Review Queue instead of being applied |

## 2. Stack (fixed by ADRs)

| Layer | Choice | ADR |
|---|---|---|
| Engine | Python **3.12.16**, standard library only at runtime, bundled (python-build-standalone 20261026) | 0001 |
| AI runtime | `llama-server` built from the latest llama.cpp tag, target macOS 11.0 | 0002 |
| Default model | Qwen3-1.7B Q4_K_M (Apache-2.0), thinking off, temperature 0, JSON schema | 0003 |
| DT3 access | Verified DT3 3.9.17 command set only, via the Swift bridge | 0004, 0005 |
| Apple events | Signed Swift process ("DT3 Agent Engine") is the LaunchAgent program and sends all Apple events | 0005 |
| OCR + QR | Swift Vision helper (revision 2 OCR, barcode detection) | 0006 |
| Process + IPC | LaunchAgent (KeepAlive) · Unix socket `0600` · JSON-RPC 2.0 | 0007 |
| Toolchain | Command Line Tools for Xcode 13.2 (Swift 5.5.2); `swiftc` + `lipo` | 0008 |
| Extraction | Rules first; AI only for type, sender/receiver, subject, summary | 0009 |
| Signing | Project self-signed certificate, no notarization | 0010 |
| Bundle ID | `codes.modular.dt3agent` (+ `.engine`, `.bridge`, `.vision`) | D1 |

## 3. Capability map (modules, dependency order)

Ids are stable. Dependencies point one way only.

| # | Module id | Responsibility | Depends on | Phase |
|---|---|---|---|---|
| 1 | `core-config` | `config.json` schema, defaults, atomic write, backup before migration, import/export | — | 2 |
| 2 | `core-store` | SQLite (WAL) databases `queue.db`, `undo.db`, `review.db`, `index.db`; versioned migrations | core-config | 2 |
| 3 | `core-audit` | JSONL audit log (no document content), daily rotation, diagnostics export | core-config | 2 |
| 4 | `engine-host` | Signed Swift LaunchAgent program: starts/restarts the Python engine, owns Apple events (bridge), relays OCR/QR calls to the Vision helper | — | 2 |
| 5 | `dt3-adapter` | Python API over `engine-host` bridge verbs; allowlisted actions only; DT3 version check | engine-host, core-audit | 2 |
| 6 | `intake` | DT3 Smart Rule / Menu scripts drop UUIDs into a spool folder; engine ingests the spool; fallback pull by `additionDate` | core-store | 2 |
| 7 | `queue` | Jobs (one at a time), retry with backoff, partial = retry, idempotency by `contentHash` + pipeline version | core-store | 2 |
| 8 | `undo` | Journal before every write; undo last batch / per record | core-store, dt3-adapter | 2 |
| 9 | `ai-adapter` | Backends llama.cpp / Ollama / OpenAI-compatible LAN; schema output; explicit context; chunking; health; model download with consent + SHA-256 + license | core-config | 2 (fake) · 3 (real) |
| 10 | `rules` | Language, dates/times, amounts, IBAN/QR-IBAN, QR reference (mod 10 recursive), SCOR (ISO 11649), UID/MWST check digit, keywords (type, urgent), stated deadlines | — | 3–4 |
| 11 | `naming` | Template engine (brief §5.1) | — | 3 |
| 12 | `review` | Review items (low confidence, duplicates, cases, deadlines), decisions, "always do this" | core-store | 3 |
| 13 | `pipeline` | Per record: text → rules → AI → validate → decide (apply / review / dry-run) → write with undo | queue, dt3-adapter, rules, naming, ai-adapter, undo, review, vision | 2 (skeleton) · 3 |
| 14 | `duplicates` | Exact (DT3 `duplicates()`), near-duplicate (shingling), A10 actions, case folders | dt3-adapter, review | 3 |
| 15 | `vision` | Swift CLI: PDF → OCR text; PDF → QR payload (byte-exact) | — | 4 |
| 16 | `swiss` | QR-bill parser (SIX IG, version cited), retention table, deadline proposals, urgent detection | rules, vision, review | 4 |
| 17 | `rpc` | JSON-RPC server on the socket; schema per method; events (status, counts) | queue, review, undo, core-config | 2 (minimal) · 5 |
| 18 | `app` | Menu bar, onboarding, settings, review window, chat window, 4 languages, accessibility | rpc | 5 |
| 19 | `installer` | Consent, LaunchAgent install/uninstall, DT3 scripts install, model download | app, engine-host | 5 |
| 20 | `knowledge` | Embeddings index, chat with sources (read-only tools), related docs, entities, translation | ai-adapter, dt3-adapter, core-store | 6 |
| 21 | `jobs` | Scheduler: nightly incremental, weekly digest, hygiene, tag hygiene, RSS/mail summaries | pipeline, knowledge | 7 |
| 22 | `ops` | Health, power mode (battery, memory pressure), remote AI (Keychain key), diagnostics | engine-host, ai-adapter | 7 |
| 23 | `release` | CI, signing (ADR-0010), DMG, docs (de/fr/it/en), PRIVACY/SUPPORT/SECURITY | all | 8 |

```
core-config ─┬─ core-store ─┬─ queue ─┐
             │              ├─ undo ──┤
             │              ├─ review ┼─ pipeline ── duplicates ── jobs
             ├─ core-audit ─┘         │      ▲
engine-host ── dt3-adapter ───────────┘      │
rules · naming · vision ─────────────────────┘ (pure / helper)
ai-adapter ── pipeline, knowledge
rpc ── app ── installer
```

## 4. Module specs (contracts)

### 4.1 `core-config`
- File `~/Library/Application Support/DT3 Agent/config.json`, schema-versioned. Unknown keys rejected on import.
- Write: temp file + `rename`; previous version kept as `config.json.bak`. Shrink guard: an import that removes enabled scopes asks for confirmation.
- Defaults: dry-run **on**, no scope enabled, AI backend unset, update check **off**, logs without content.

### 4.2 `core-store`
- One SQLite file per concern, `journal_mode=WAL`, `foreign_keys=ON`. Migrations numbered; backup copy before each migration.
- Times stored as UTC ISO-8601; shown in the user's zone.

### 4.3 `core-audit`
- One JSON line per action: `ts, actor (rule|ai|user), action, uuid, fields_changed, batch_id, result`. Never document text.
- Diagnostics export: config (secrets removed), versions, counts, last 500 audit lines with UUIDs hashed.

### 4.4 `engine-host` (Swift)
- Is the LaunchAgent `ProgramArguments[0]` (ADR-0005). Starts `python3 -I -m dt3agent.engine`, restarts it on crash (back-off), stops it on `SIGTERM`.
- Bridge: the engine sends `{"verb": …, "args": {…}}` lines over a private pipe; the host runs **pre-written** DT3 scripts with those arguments passed as Apple-event parameters (OSAKit handler call), never by string building. **Verified (T5, 2026-11-03, floor):** OSAKit handler call with parameters works on macOS 11 (`read` of a real UUID → `read ok`); Automation entry shows "DT3 Agent Engine". OSAKit is the default mode; `/usr/bin/osascript` is a fallback (`info` verified).
- Allowed verbs: `info`, `read`, `read_text` (plain text, capped at 200 000 characters with the full length reported; verified on the floor 2026-11-04), `set_name`, `set_tags`, `set_comment`, `set_metadata`, `move`, `replicate`, `duplicate`, `create_markdown`, `import`, `list_added_since`, `selected` (verified on the floor 2026-11-04). **No delete verb exists.**

### 4.5 `dt3-adapter` (Python)
- Typed functions mirroring the verbs; every write goes through `undo.record()` first.
- Refuses to run if DT3 `version()` does not start with `3.` (polite message for DT4).
- Batch reads: one bridge call per record returns name, tags, comment, kind, wordCount, contentHash, dates, location, custom metadata, `numberOfDuplicates`.

### 4.6 `intake`
- DT3 scripts write `{uuid}.json` (UUID only + timestamp) atomically into `~/Library/Application Support/DT3 Agent/spool/` and return at once.
- Engine ingests the spool (poll every 2 s while active), deletes the spool file after the job is committed.
- Fallback (verified API): pull records with `additionDate` > last pull from enabled groups, every N minutes (configurable, default 5).
- Verified (T1): an external **AppleScript** Smart Rule script (`dt3-scripts/SmartRule-Enqueue.applescript`, rule action "Apply Script › External") receives all matching records — if it was installed while DT3 was not running.
- The engine skips spool files younger than 2 s (the script writes in place).

### 4.7 `queue`
- States: `queued → running → done | review | failed | partial`. `partial` and `failed` retry with back-off (max 5).
- Idempotency key: `contentHash + pipeline_version`; unchanged → `skipped`.
- One job at a time (brief §2.4).

### 4.8 `undo`
- Before any write: snapshot `name, tags, comment, location(s), custom metadata` → `undo.db` with `batch_id`.
- Undo restores the snapshot; refuses if the record changed since (shows a diff, user decides).

### 4.9 `ai-adapter`
- Interface: `extract(text, schema, lang_hint) → (obj, raw, timings)`; `embed(texts)`; `chat(messages, tools=read-only)`.
- llama.cpp: `response_format.json_schema.schema` (ADR-0002), `chat_template_kwargs.enable_thinking=false`, `-c` set explicitly.
- Long text: chunk by tokens with overlap; never truncate silently (record `truncated=false/true`).
- Direct connection only: no `*_proxy` variables, no macOS system proxy (document text must not pass a third party).
- Text that cannot fit the context is refused (`ai_too_long`), never cut; failures are short codes (`ai_invalid_json`, `ai_schema_mismatch`, `ai_http_<n>`, `ai_unreachable`) and lead to a review item, never a write.
- Output is untrusted: JSON parse → schema → allowlists (tags vocabulary, group allowlist) → only then use.
- Model manager: download only after consent; show size + license; verify SHA-256; keep model unloaded after 5 min idle.

### 4.10 `rules` (pure Python, table-driven tests)

| Rule | Output | Source of truth |
|---|---|---|
| Language | de/fr/it/en + score | stop-word scoring |
| Date/time | ISO date, time or `None`, position | regex per language |
| Amount | value (Rappen int), currency, label (total/net/VAT) | "Total/Totale/Montant…" lines; QR-bill wins |
| IBAN / QR-IBAN | normalized, valid (mod 97), is_qr (IID 30000–31999) | ISO 13616; SIX IG |
| QR reference | valid (mod 10 recursive) | SIX IG |
| SCOR | valid (ISO 11649) | ISO 11649 |
| UID / MWST | `CHE-123.456.789` (+ MWST/TVA/IVA), valid check digit | eCH-0097 v5.2.0 §2.4: weights 5,4,3,2,7,6,5,4, mod 11, "10" never issued (verified T-B3) |
| Keywords | doc-type hints, urgent hints (Betreibung, Zahlungsbefehl, Gericht, Steueramt…) | user-editable lists |
| Deadline | stated date + phrase | "innert 30 Tagen", "dans les dix jours"… → **hint only** |

### 4.11 `naming`
Brief §5.1 exactly: default `{datetime}_{sender}_{receiver}_{subject}`; `YYYYMMDDHHMMSS`; `_` between fields, `-` inside; strip `/ : \ * ? " < > |`; NFC; no `ß` for de-CH; per-field max; total ≤ 200; unknown → `unknown`; collision `_2`, `_3`; date source stored.

### 4.12 `review`
- Item: `uuid, kind (field|duplicate|case|deadline|urgent), proposal (before/after), confidence, source, created`.
- Decisions: accept · edit · reject · always-do-this (creates a user rule, scoped).

### 4.13 `pipeline` (per record)
1. Read record (one bridge call). Skip if out of scope or idempotency key unchanged.
2. Text: DT3 plain text; if `wordCount == 0` → Vision OCR (analysis only).
3. Rules (§4.10), QR-bill if present.
4. AI for missing fields (type, sender/receiver, subject, summary, tags from vocabulary).
5. Validate + merge: rule > QR > AI > placeholder, except payment fields where QR > rule (§4.16); each field `{value, source, confidence}`.
6. Decide per field: ≥ threshold → apply; else → review. Dry-run → everything to review as "planned".
7. Write via adapter with undo; store hash + pipeline version (Phase 2: engine DB table `processed`; custom metadata from Phase 3).
- Budget (floor, 1-page document): **≤ 60 s** end-to-end (AI ~20 s, OCR ≤ 6 s, DT3 ≤ 2 s).

### 4.14 `duplicates`
- Exact: DT3 `duplicates()` (verified). Near: 5-word shingles, Jaccard ≥ 0.8 (configurable).
- Only creates review items; A10 actions executed after the user's choice. Case folders: user-created; engine suggests matches by sender/entities/references.

### 4.15 `vision` (Swift CLI)
- `vision ocr <pdf> --langs de-DE,fr-FR,… --pages …` → JSON lines `{page, text, ms}`.
- `vision qr <pdf>` → JSON `{page, payload_b64}`. Called only by `engine-host`.

### 4.16 `swiss`
- QR-bill parser per the current SIX "Swiss Implementation Guidelines QR-bill" (fetch + cite version in code, T-B2). Decoded values beat AI values.
  Done in `engine/dt3agent/qrbill.py`: SIX IG **v2.4 of 24.02.2026** (SIC release 13.11.2026; v2.3 valid until Nov 2027). Lenient only for older valid bills (address type K, EUR + QRR); checksums never lenient. Payment fields (amount, currency, IBAN, reference) from the QR code beat text rules ("QR-bill wins", §4.10); creditor name beats the AI sender. Note: the SCOR in SIX Annex A Table 20 (`RF72…JSH0438`, unchanged since v2.2) fails ISO 11649; it is refused.
- Retention table (editable; default example accounting records 10 years, OR Art. 958f; UI says "Not legal advice").
- Deadline/urgent → review items + notification; never create reminders without confirmation.

### 4.17 `rpc`
- Socket `~/Library/Application Support/DT3 Agent/engine.sock` (`0600`, dir `0700`), path ≤ 103 bytes. One JSON line per message, 64 KB max: `{"method", "params"}` → `{"ok": true, "result"}` or `{"ok": false, "error": "<code>"}`. Codes are the same short codes as the queue (`unknown_method`, `bad_params`, `bad_request`, `engine_error`, …); never content. (Changed in T9 from JSON-RPC 2.0: both ends are ours, and string codes match queue and audit.)
- Methods (phase 2 minimal): `status`, `process(uuid)`, `process_selected` (records selected in DT3, max 100), `review` (open items: reason codes and planned tags, never raw model output), `undo` (last batch), `pause`, `resume`, `live(on)` (switches dry-run, saved to config). There is no delete method.
- Single-threaded engine loop: rpc requests and pipeline jobs take turns, because the DT3 bridge is one pipe.

### 4.18 `app`, 4.19 `installer`
- AppKit `NSStatusItem` + `NSPopover`/windows hosting SwiftUI (macOS 11 API). Menu per brief §6.1, onboarding §6.2, settings §6.3, review §6.4.
- Languages de-CH, fr-CH, it-CH, en; VoiceOver labels, full keyboard, AA contrast, Dark Mode.
- Installer: shows what will be installed (LaunchAgent, DT3 scripts, model) and asks first; uninstall removes all of it.

### 4.20–4.23 `knowledge`, `jobs`, `ops`, `release`
Specified in detail at the start of their phases (6–8) from brief §5 C/D/E and §8; contracts above (rpc, ai-adapter, dt3-adapter) already cover their needs.

## 5. Commands (engine; Swift added in Phase 2)

```bash
python3 -m pytest engine/tests -q
```
```bash
python3 -m ruff check engine
```
```bash
bash tools/build-swift.sh     # engine-host, vision, app: swiftc per arch + lipo, target 11.0
```

Dev tools (pytest, ruff) are dev-only, pinned in `engine/requirements-dev.txt`; the runtime imports only the standard library (a test enforces this).

## 6. Structure

```
app/            Swift: app, engine-host (bridge), vision
engine/dt3agent/ Python package: config, store, audit, adapter, intake, queue, undo, ai, rules, naming, review, pipeline, rpc
engine/tests/   unit + integration (fake DT3 adapter, fake AI server)
dt3-scripts/    Smart Rule + Menu scripts (spool writers)
fixtures/       synthetic documents only
docs/           SPEC, ADRs, spike report, user guide (de/fr/it/en)
fsd/            plan, todo, test plan, bugs
tools/          build scripts
```

## 7. Code style

```python
def iban_is_valid(iban: str) -> bool:
    """ISO 13616 mod-97 check. Input may contain spaces."""
    s = iban.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", s):
        return False
    digits = "".join(str(int(c, 36)) for c in s[4:] + s[:4])
    return int(digits) % 97 == 1
```
- Type hints, small pure functions, no globals; snake_case (Python), Swift API guidelines (Swift).
- Comments only for the *why*; `UNVERIFIED:` marker where a fact is not yet proven.

## 8. Testing

| Level | What | Where |
|---|---|---|
| Unit (~80 %) | rules, naming, schema validation, queue states, undo snapshots | `engine/tests/unit` |
| Integration | pipeline with **fake DT3 adapter** + **fake AI server** (deterministic) | `engine/tests/integration` |
| Swift | view models, vision helper on fixture PDFs | `app/Tests` |
| Floor | checklist on the MacBook 2014 (DT3 + llama.cpp) before each phase gate | `fsd/test-plan.md` |
| Performance | per-document time on the floor; regressions block release | recorded per release |

Red → green → refactor for every non-trivial function. Bugs get a failing test first.

## 9. Boundaries

| Always | Ask first | Never |
|---|---|---|
| stdlib-only engine runtime · argv/stdin for scripts · undo before write · dry-run default · schema-validate AI output · no content in logs | new dependency (even dev) · schema/migration change · CI changes · anything that sends data off the Mac | delete in DT3 · string-built scripts or shell · secrets in repo/logs · telemetry · bundle model weights · use "DEVONthink" as product name |

## 10. Success criteria (testable)

1. Fresh install on the floor machine, offline after model download: an invoice PDF added to an enabled group is renamed per template, tagged from the vocabulary, filed to an allowlisted group in **≤ 60 s**; undo restores it exactly.
2. With dry-run on (default), **no** DT3 record changes; all proposals appear in the Review Queue.
3. Synthetic QR-bill fixtures: amount, currency, IBAN, reference match the payload **100 %**; invalid checksums rejected.
4. Duplicate fixtures: exact duplicates proposed 100 %, never acted on without a decision.
5. Engine runtime imports only the standard library (test).
6. No document text in logs (test with a sentinel string).
7. App: VoiceOver reads every control; full keyboard flow through onboarding; de-CH texts contain no "ß".
8. Works on macOS 11 Intel (floor) and one Apple Silicon Mac before release.

## 11. Open questions

| # | Question | My guess |
|---|---|---|
| O1 | Smart Rule trigger (Phase 0 open item) | Resolve in T1 with rule-editor screenshots; fallback pull is acceptable for v1 |
| O2 | Product certificate: who creates it, where is the key backed up? | Gianni creates it on a trusted Mac (not the floor), exports `.p12` to password manager + CI secret (Phase 8; a test cert is enough until then) |
| O3 | Default UI language | de-CH, switchable |
| O4 | Final product name | Decided in Phase 8 with trademark screen |
| O5 | Pull interval default | 5 min while DT3 runs |
