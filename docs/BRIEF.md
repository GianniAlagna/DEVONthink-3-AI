# Project brief — DT3 Agent (working name)

Source of truth from the owner (Gianni), received 2026-10-30. Sections 0–11 are kept verbatim.
**Owner decisions** that change or clarify the brief are listed first; they win over the text below.

---

## Owner decisions (2026-10-30)

| # | Topic | Decision | Effect on the brief |
|---|---|---|---|
| Q1 | DT3 version on floor machine | **3.9.17** | Supported range is checked from 3.9.17 in Phase 0 |
| Q2 | RAM of floor machine | **16 GB** | The floor machine cannot prove the 8 GB promise directly → budget by measured peak memory + memory-pressure test; one real 8 GB Mac before release |
| Q3 | Default model license | **Apache-2.0 / MIT only** | Llama, Gemma and other custom-license models are never defaults |
| Q4 | Who runs the spike | **Gianni**, on a dedicated test database | Spike kit in `spike/`, results sent back to Claude |
| Q5 | How results come back | Zip from `./spike/run.sh collect`, attached in the chat (see `spike/README.md`) | — |
| Q6 | Apple Silicon test Mac | **Yes** | Used before each release |
| Q7 | Apple Developer Program | **No, and not planned** | **Changes 7, 8.3, 8.4:** no Developer ID signing, no notarization. Distribution = ad-hoc or self-signed app + build-from-source. Consequences measured in Phase 0 (S8) and decided in an ADR |
| Q8 | `tccutil reset AppleEvents` on floor machine | **Yes** | Used in S5 |
| Q9 | Bundle ID prefix | **One ID for all users: `codes.modular.dt3agent`** (decided 2026-10-30, following the recommendation) | Same app for individuals and businesses; support plan is a service. Spike uses `codes.modular.dt3agent.spike.*` so test permissions never mix with the product |
| Q10 | Keep the brief in the repo | **Yes** | This file |
| Plan | Phase 0 spike plan incl. Step 5 (TCC test) | **Approved** | Spike kit built |

---

## 0. Your role and working rules

You are the lead engineer of an **open-source macOS app** that brings private, offline, agentic AI to **DEVONthink 3 (DT3)** users.

- If the `fullstackdev` skill is available, load it and work at level **full**. Otherwise follow the rules in this file.
- **Do not write product code before the spec and the plan are approved** (Gates in section 9).
- Smallest complete change. No features, options or abstractions that are not in this file.
- Every non-trivial logic gets a test first (red → green → refactor).
- Framework/API code comes from **official docs for the exact version** (Apple developer docs, Python docs, llama.cpp, Ollama, DT3 scripting dictionary). If you cannot verify something, mark it `UNVERIFIED` in code and in your reply.
- Keep fact and inference apart in every reply: "verified" vs "assumed".
- Replies to the owner: short, structured, clear headings, consistent terms (the owner has dyslexia: small chunks, tables, no walls of text).
- The owner (Gianni) owns all accounts, keys, certificates and money. Never sign up, buy, or paste secrets. Write `.env.example` / config templates instead.

---

## 1. Product goal

| Item | Decision |
|---|---|
| Users | **Individuals** running DT3 3.9.x in production (DT4 not required) |
| Business users | Swiss SMEs and fiduciaries get a **support plan by modular.codes** (see 8.4) |
| Promise | 100 % local, private, no cloud, no telemetry, no token limits |
| Interface | **Professional menu-bar app** + full setup in an intuitive, simple UI |
| Scope | **All** automation blocks A–E (section 5) |
| Hardware floor | **macOS 11 Big Sur, Intel, 8 GB RAM** — must work there |
| Upward | Every macOS version above 11, Intel and Apple Silicon |
| License | Apache-2.0 |
| Working name | `DT3 Agent` (final name later; never use "DEVONthink" as the product name — only descriptive "for DEVONthink 3"; add a "not affiliated with DEVONtechnologies" note) |

---

## 2. Hard constraints (the floor)

The development machine is a **MacBook Pro 15" Mid 2014, macOS 11.7.x (Big Sur), Intel Haswell, no OpenCore Legacy Patcher**. It is the reference "floor" machine. Do not suggest patching it.

1. **Floor-only APIs:** use only what exists on macOS 11 and DT3 3.9.x. Anything newer is optional and gated by a runtime version check.
2. **Toolchain on the floor:** Xcode 13.2.x max, Swift 5.5. No `MenuBarExtra` (macOS 13), no `SMAppService` (macOS 13).
3. **Engine without compiled dependencies:** Python **standard library only** at runtime (`sqlite3`, `json`, `urllib`, `subprocess`, `hashlib`, `re`, `unicodedata`). Dev/test dependencies are allowed.
4. **8 GB RAM support:** default model ≤ 3B parameters, quantized; one job at a time; unload the model when idle; pause on memory pressure and on battery (configurable).
5. **Offline after setup:** the only network calls ever allowed are explicitly user-triggered (model download, optional update check — off by default). No telemetry.
6. **DT3 never waits for the AI.** DT3 scripts only enqueue and return immediately (long JXA work inside Smart Rules freezes DT3 and causes AppleEvent timeouts).
7. **Never delete anything** in DT3. No delete tool exists in the engine.

---

## 3. Target architecture

```
┌──────────────── DT3 3.9.x ────────────────┐
│ Smart Rule script  performsmartrule(recs) │──┐ enqueue UUIDs only
│ Menu script        run()                  │──┤ (returns at once)
└───────────────────────────────────────────┘  │
                                               ▼
┌──────────── DT3 Agent.app (Swift) ────────────────────────┐
│ NSStatusItem menu · SwiftUI windows (macOS 11 API level)  │
│ Onboarding wizard · Settings · Review Queue · Chat · Logs │
│ Vision helper: QR-bill decode + OCR (Vision framework)    │
└───────────────▲───────────────────────────────────────────┘
                │ JSON-RPC over Unix socket (0600, per user)
┌───────────────┴──── Engine (Python 3.12, stdlib) ─────────┐
│ launchd LaunchAgent · SQLite queue (WAL) · pipeline       │
│ rules-first extractors · AI adapter · DT3 adapter         │
│ undo journal · audit log (JSONL) · scheduler · index      │
└───────────────┬──────────────────────────┬────────────────┘
                │ osascript (args via argv) │ HTTP localhost / LAN
                ▼                           ▼
          DT3 (read/write)        AI backend: llama.cpp server
                                  | Ollama | remote server in LAN
```

### 3.1 Components

| Component | Tech | Notes |
|---|---|---|
| Menu-bar app | Swift 5.5, AppKit `NSStatusItem` + `NSPopover`/windows hosting SwiftUI (macOS 11 level), deployment target 11.0, **universal** (x86_64 + arm64) | Professional look, native, VoiceOver, keyboard, Dark Mode |
| Engine | Python 3.12, stdlib only, pinned | Runs as LaunchAgent (`launchctl bootstrap gui/<uid>`), works when the app is closed |
| Python runtime | Bundled relocatable runtime (e.g. python-build-standalone) per architecture inside the app → **offline install** | `UNVERIFIED`: confirm the build runs on macOS 11 Intel in Phase 0 |
| DT3 scripts | JXA files, installed by the app into `~/Library/Application Scripts/com.devon-technologies.think3/Smart Rules/` and `…/Menu/` after user consent | Verify paths on the floor machine |
| DT3 adapter | Engine calls `osascript -l JavaScript <file> <args…>`; data passed via argv/stdin, **never** string-interpolated | Detect DT3 by version (`version()` starts with `3.`); refuse politely if DT4 answers to `DNtp` |
| Vision helper | Swift CLI inside the app bundle: PDF page → image (PDFKit) → `VNDetectBarcodesRequest` (QR) and `VNRecognizeTextRequest` (OCR fallback for DT3 Standard, which has no OCR) | Verify OCR language support (de/fr/it/en) on macOS 11 |
| AI adapter | One interface, three backends: **llama.cpp `llama-server`** (bundled binary per arch, pinned release), **Ollama** (if installed, macOS 12+), **remote server** (LAN URL) | Structured output: JSON schema / grammar. Set context size explicitly; chunk long docs; never truncate silently |
| Storage | `~/Library/Application Support/DT3 Agent/` → `queue.db`, `index.db`, `undo.db`, `audit/*.jsonl`, `config.json` | Atomic writes (temp + rename), backups before migration |

### 3.2 Design rules

1. **Rules first, AI second.** Everything with a fixed format is extracted deterministically (dates, IBAN/QR-IBAN, Swiss QR-bill, UID/MWST number, amounts, references). The AI only does classification, summary, tags, sender/receiver/subject when rules fail.
2. **AI output is untrusted data.** Parse → validate against JSON schema → check against allowlists → only then act. Document text may contain prompt injections.
3. **Confidence everywhere.** Every extracted field stores `value`, `source` (`rule` | `ai` | `user`), `confidence`. Below threshold → Review Queue, never auto-apply.
4. **Undo for everything.** Before any write: save old name, tags, groups, metadata in the undo journal. "Undo last batch" and "Undo for this record".
5. **Idempotent.** Content hash + pipeline version in custom metadata. Unchanged record → skip.
6. **Dry-run is the default** on first install, until the user switches it off.
7. **Opt-in scope.** Nothing is processed unless the database/group is enabled.

---

## 4. Supported matrix (publish in README)

| Environment | Status |
|---|---|
| macOS 11 Intel, 8 GB | Supported (llama.cpp, ≤ 3B model, slow but works) |
| macOS 11–26 Intel | Supported; recommend remote AI server in LAN for speed |
| macOS 12+ Apple Silicon | Supported, best experience (Ollama or llama.cpp) |
| DT3 3.9.x | Supported (determine the exact range in Phase 0) |
| DT4 | Not supported (DT4 has built-in AI) |

---

## 5. Features — all blocks

### Block A — Inbox processing

| # | Feature | Requirements |
|---|---|---|
| A1 | Text layer check | No text → DT3 OCR if available (Pro), else Vision OCR fallback (text used for analysis, original untouched) |
| A2 | Language detection | de / fr / it / en |
| A3 | Document type | Invoice, contract, letter, receipt, statement, official letter, reminder, offer, other — list configurable |
| A4 | Document date | Extract date **and time if stated**; distinguish from import date; store source |
| A5 | Sender / receiver | Receiver defaults to the user's own name/company from settings for inbound mail |
| A6 | **Standard name** | See 5.1 |
| A7 | Tags | Only from a user-editable **controlled vocabulary**; new tags only as suggestions |
| A8 | Auto-filing | Target groups only from an allowlist; below confidence threshold → `_AI-Review` group |
| A9 | Summary | 3 lines → DT3 comment or custom metadata (configurable) |
| A10 | **Duplicates** | See 5.2 — never automatic, always a human decision |

#### 5.1 Naming (A6)

- **Default template:** `{datetime}_{sender}_{receiver}_{subject}`
- `{datetime}` = `YYYYMMDDHHMMSS` → chronological sorting in any DMS.
- Template is fully editable in Settings with a live preview. Tokens: `{datetime}`, `{date}`, `{sender}`, `{receiver}`, `{subject}`, `{type}`, `{lang}`, `{amount}`, `{reference}`.
- Date source priority: document date (extracted) → DT3 creation date. If no time is stated: `000000` (configurable). Store which source was used.
- Field separator `_` only between fields. Inside a field: words joined with `-`. Strip `/ : \ * ? " < > |`, normalize Unicode to NFC, keep umlauts/accents (de-CH: no `ß`).
- Per-field max length (configurable), total name ≤ 200 characters.
- Unknown field → configurable placeholder (default `unknown`). **Never invent a sender or subject.**
- Collision → suffix `_2`, `_3`.
- Original name saved for undo.
- Tests: table-driven (missing fields, long names, special characters, fr/it accents, same-second collision).

#### 5.2 Duplicates and multi-context documents (A10)

Detection: exact (content hash; use DT3's own duplicate information if available — verify in the dictionary) + near-duplicate (text shingling, pure Python). Result goes **only** to the Review Queue. The user chooses:

| Option | What happens | When |
|---|---|---|
| Not a duplicate | Mark as reviewed, never ask again for this pair | False positive |
| Mark as duplicate | Tag `duplicate`, move the newer copy to `_Duplicates` group; **user deletes manually** | Real duplicate |
| **Replicate** (recommended for multi-context) | Same record appears in a second group (DT3 replicant), no copy, edits stay in sync | Same database, e.g. supplier letter also under a legal case |
| Duplicate as copy | Independent copy + backlink metadata to the original | Different database, or a frozen copy for a legal file is wanted |
| Link note | Small Markdown note in the target group with an item link (`x-devonthink-item://UUID`) pointing to the original | Different database, no copy wanted |

**Case folders** (e.g. legal dispute with a supplier):
- The user creates a case in the app ("Dispute Supplier X", target group, related sender/entities).
- The engine **suggests** existing and new documents that match the case (sender, entities, references).
- The user confirms per document: replicate / copy / link note. Nothing happens without confirmation.

Verify the exact DT3 3.9 commands for replicate, duplicate and item links in the scripting dictionary before use.

### Block B — Swiss specifics

| # | Feature | Requirements |
|---|---|---|
| B1 | Invoice fields | Amount CHF/EUR, due date, IBAN/QR-IBAN, reference, creditor |
| B2 | **Swiss QR-bill decode** | Vision helper reads the QR code; parse per the current **SIX Swiss Payment Standards — Implementation Guidelines QR-bill** (fetch the official spec, cite the version). Validate IBAN (mod 97), QR-IBAN range, QR reference (mod 10 recursive), creditor reference ISO 11649. Decoded values beat AI values |
| B3 | UID / MWST number | Pattern `CHE-123.456.789` (+ `MWST`/`TVA`/`IVA`), validate the check digit (verify the algorithm from an official source) |
| B4 | Retention class | User-editable table (default example: accounting records 10 years, OR Art. 958f). UI text: "Not legal advice" |
| B5 | Deadlines | Extract **stated** deadlines from letters → propose a reminder (DT3 reminder, macOS Reminders or Calendar — user picks); never create without confirmation |
| B6 | Urgent letters | Detect debt collection (Betreibung / Zahlungsbefehl), court, tax office, authorities → group `_Urgent` + notification. Known legal deadlines only as a **hint** with "verify" (no automatic legal calculation) |

### Block C — Knowledge work

| # | Feature | Requirements |
|---|---|---|
| C1 | Semantic index | Embeddings from the active AI backend, stored in SQLite; incremental; per database |
| C2 | Chat with documents | Chat window in the app; answers **always** with sources as `x-devonthink-item://` links; read-only tools only (search, read); any write action = proposal the user confirms |
| C3 | Related documents | Suggest links between related records |
| C4 | Entity index | People, companies, projects → Markdown notes (opt-in) |
| C5 | Translation | Summaries de ↔ fr ↔ it ↔ en |

### Block D — Scheduled jobs

| # | Feature | Requirements |
|---|---|---|
| D1 | Nightly incremental run | Changed records only (hash) |
| D2 | Weekly digest | Markdown note: new documents, open deadlines, invoices due |
| D3 | Hygiene report | Untagged / unfiled records |
| D4 | Tag hygiene | Suggest merging synonyms — never change on its own |
| D5 | RSS / mail summaries | For items imported by DT3 |

### Block E — Operations

| # | Feature | Requirements |
|---|---|---|
| E1 | Health check | Engine, AI backend, model, DT3 running, queue backlog → status icon color in the menu bar |
| E2 | Dry-run | Default on first install; shows planned changes in the Review Queue |
| E3 | Undo | Last batch / per record |
| E4 | Opt-in scope | Per database and group |
| E5 | Configuration | Everything in the UI; `config.json` as the single source; import/export of settings |
| E6 | Power mode | Pause on battery and on memory pressure (configurable) |
| E7 | Remote AI | LAN server URL for llama.cpp/Ollama/OpenAI-compatible; warn if not `localhost`/private range; optional API key in the **Keychain** |
| E8 | Logs | Audit log JSONL without document content by default; "export diagnostics" without personal data |

---

## 6. The app UI (professional and simple)

**Principles:** native macOS look, plain language, one decision per screen, sensible defaults, everything changeable, nothing hidden. Languages: **de-CH, fr-CH, it-CH, en** (de-CH: "ss", never "ß"; numbers `1'234.50`, dates `31.12.2026`). Accessible: VoiceOver labels, full keyboard use, contrast AA, Dark Mode.

### 6.1 Menu-bar menu
Status (icon color + text) · Process selected records · Queue (count) · **Review Queue (count)** · Pause/Resume · Chat · Undo last batch · Settings · Help & Support · Quit

### 6.2 Onboarding wizard (first start)
1. Welcome + privacy promise
2. System check: macOS, CPU, RAM, DT3 version, permissions (Automation for DT3) — with clear "how to fix" steps
3. AI backend: use existing Ollama / install bundled llama.cpp + recommended model (show size, license, download only after consent) / remote LAN server
4. Model choice by RAM (8 GB → ≤ 3B default); quick speed test with a sample document
5. Your identity (name/company → default receiver), languages
6. Databases and groups to enable (opt-in)
7. Naming template with live preview
8. Install DT3 scripts + example Smart Rule instructions (screenshots)
9. Dry-run on 5 sample documents → user sees results → switch dry-run off or keep

### 6.3 Settings (tabs)
General · AI backend & model · Databases & scope · Naming · Tags (vocabulary) · Filing rules & groups · Swiss (QR-bill, UID, retention table, urgent rules) · Duplicates & case folders · Schedules · Power & performance · Privacy & logs · Advanced (thresholds, context size, prompts — with "reset to default")

### 6.4 Review Queue window
List of pending decisions (low confidence, duplicates, case suggestions, deadlines). Each item: document preview, proposed changes as before/after, confidence, source (rule/AI), buttons: Accept · Edit · Reject · Always do this.

---

## 7. Security and privacy (non-negotiable)

- Threat model first (STRIDE per boundary): DT3 ↔ engine, engine ↔ AI backend, app ↔ engine socket, document content (prompt injection), remote LAN server.
- Allowed engine actions: set name, set tags, set comment/custom metadata, move to allowlisted group, replicate, duplicate, create note, create reminder (after confirmation). **No delete.**
- `osascript` arguments via argv only; no shell string building; no `eval`.
- Unix socket in Application Support with mode `0600`; validate every JSON-RPC message against a schema.
- Secrets (remote API key) only in the macOS Keychain.
- No document content in logs by default. revDSG/GDPR: all processing local; document this in `PRIVACY.md`.
- Code signing + notarization in CI on Apple Silicon runners; certificates only as CI secrets — **never on the floor machine** (macOS 11 gets no security updates). *(See owner decision Q7.)*
- Dependency audit in CI; pin every version; one lockfile per install boundary.

---

## 8. Repository, tests, CI, distribution

### 8.1 Structure
```
/app            Swift app (Xcode project, target macOS 11, universal)
/app/VisionHelper  Swift CLI (QR + OCR)
/engine         Python package (stdlib runtime), pyproject, tests
/dt3-scripts    JXA scripts (Smart Rule + Menu)
/fixtures       synthetic documents only (no real personal data), incl. generated Swiss QR-bills
/docs           SPEC.md, ADRs, user guide (de/fr/it/en), screenshots
/fsd            planning files (plan, todo, test plan, bugs)
CLAUDE.md  README.md  PRIVACY.md  SUPPORT.md  SECURITY.md  LICENSE  CHANGELOG.md
```

### 8.2 Tests
- Engine: unit tests for every extractor, validator and the naming function (table-driven); integration tests with a **fake DT3 adapter** and a **fake AI server** (deterministic responses).
- Swift: unit tests for view models and the Vision helper (fixture PDFs with QR-bills).
- Manual/real: `docs/test-plan.md` with a checklist run on the floor machine (DT3 + llama.cpp) and on one Apple Silicon Mac before each release.
- Performance budget on the floor machine: measure and record per-document time; regressions block the release.

### 8.3 CI (GitHub Actions)
- Runners: `macos-15-intel` (Intel; GitHub retires Intel macOS runners after Fall 2027 — note in docs) and `macos-15` (Apple Silicon).
- Jobs: lint, engine tests, Swift build + tests (deployment target 11.0), dependency audit, signed + notarized release build on tags. *(See owner decision Q7.)*
- There is no macOS 11 runner: the floor machine is the floor test.

### 8.4 Distribution and support
- Signed and notarized `.dmg` (universal). Optional Homebrew cask later. *(See owner decision Q7.)*
- Model weights are **never** bundled; downloaded only after consent, with the model license shown.
- `SUPPORT.md` and the in-app "Help & Support":
  - **Individuals:** community support via GitHub Issues and Discussions; docs in 4 languages.
  - **Swiss SMEs and fiduciaries:** professional support plan by **modular.codes** (https://modular.codes) as service provider — e.g. installation, multi-database setup, custom rules and vocabularies, training, SLA. **Do not invent prices, SLAs or contact details**: leave clearly marked placeholders for Gianni to fill.

---

## 9. Phases and gates (follow in order)

| Phase | Output | Gate |
|---|---|---|
| **0 — Floor spike** (on the MacBook Pro 2014) | Verified facts: bundled Python runtime runs on macOS 11 Intel · llama.cpp builds with Xcode 13 (else pin an older release) · speed of a 1.5B and a 3B model · DT3 3.9 dictionary: create record (markdown/content vs plain text), custom metadata, replicate, duplicate, reminders, item links · Vision QR + OCR languages on macOS 11 · launchd LaunchAgent install. Write one ADR per decision in `/docs/adr/` | Gianni reviews the spike report |
| **1 — Spec + plan** | `docs/SPEC.md` (capability map + module specs in dependency order), `fsd/plan.md`, `fsd/todo.md` with vertical slices, sizes, acceptance criteria | **Gianni approves — no code before this** |
| **2 — Walking skeleton** | Smart Rule → queue → engine → fake AI → tag written → undo works (CLI only) | Tests green, demo on the floor machine |
| **3 — Block A** | Full pipeline, naming, review queue (engine side), duplicates | Tests + manual checklist |
| **4 — Block B** | Vision helper, QR-bill, UID, deadlines, urgent | Tests with synthetic QR-bills |
| **5 — App** | Menu bar, onboarding, settings, review queue UI, 4 languages | Accessibility check, screenshots |
| **6 — Block C** | Index, chat with sources, related docs, entities, translation | Prompt-injection tests |
| **7 — Blocks D + E** | Scheduler, digests, health, power mode, remote AI, diagnostics | 48 h soak test on the floor machine |
| **8 — Release** | Signing, notarization, DMG, docs, PRIVACY/SUPPORT/SECURITY, changelog | Pre-launch checklist + Gianni says go |

After each phase: short report (what was done, what was verified, what was assumed, open risks, next step). Commit with Conventional Commits; one concern per PR.

---

## 10. Known pitfalls (check, do not repeat)

1. Long work inside a DT3 Smart Rule freezes DT3 → enqueue only.
2. Smart Rule JXA entry point is `performsmartrule(records)`; menu scripts use `run()`.
3. Never pass document text on the command line (length limit, quoting, injection).
4. OpenAI-compatible endpoints may ignore context size → set it explicitly per backend; chunk.
5. Small models without native tool calling → use structured output (JSON schema/grammar), not free tool calls, for the pipeline.
6. Ollama uses the GPU (Metal) on Apple Silicon, not the Neural Engine; Intel Macs run CPU only.
7. `Application("DNtp")` can reach DT4 too → check the version.
8. `displayNotification(text, {withTitle, subtitle})` — text first.
9. macOS 11 lacks `MenuBarExtra` and `SMAppService`.
10. Homebrew and newer Ollama versions may not support macOS 11 → never required on the floor.

---

## 11. First action now

1. Confirm you read the whole file.
2. List your **assumptions** and **open questions** (max. 10, each with your best guess).
3. Write the **Phase 0 spike plan** (steps, commands, expected evidence) and wait for Gianni's yes.
