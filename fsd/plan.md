# Plan — DT3 Agent

Status: **DRAFT — waiting for Gianni's approval (Phase 1 gate).** Spec: `docs/SPEC.md`. Tasks: `fsd/todo.md`.

## 1. Approach

- Vertical slices: every task leaves a working, tested path through the stack.
- Riskiest first: trigger (Smart Rule), Apple events from the signed host, then the pipeline.
- Checkpoint after every 2–3 tasks: tests green, floor demo, Gianni sees the result.
- Phases and gates as in the brief §9; tasks are detailed for the **next** phase only and sliced again at the start of each later phase.

## 2. Dependency order (from the capability map)

```
Phase 2  core-config → core-store → core-audit → queue → intake
         engine-host (bridge) → dt3-adapter → undo → ai-adapter (fake) → pipeline skeleton → rpc (minimal)
Phase 3  rules (language, dates, amounts, IBAN) → naming → review → pipeline full (A1–A9) → duplicates (A10)
Phase 4  vision → swiss (QR-bill, UID, retention, deadlines, urgent)
Phase 5  app shell → onboarding → settings → review window → installer → 4 languages
Phase 6  knowledge (index, chat, related, entities, translation)
Phase 7  jobs + ops (scheduler, digest, hygiene, power, remote AI, diagnostics) → 48 h soak
Phase 8  release (CI, signing, DMG, docs, PRIVACY/SUPPORT/SECURITY)
```

## 3. Risks

| # | Risk | Impact | Mitigation | Task |
|---|---|---|---|---|
| P1 | Smart Rule does not call external scripts | No automatic trigger | Resolve on the floor with rule screenshots; fallback: pull by `additionDate` + Menu script (both verified) | T1 |
| P2 | Apple-event grant lands on python3.12 again (responsible process) | Untrusted permission name, resets | `engine-host` (Swift) is the LaunchAgent program and sends events itself | T5 |
| P3 | OSAKit handler call with parameters on macOS 11 behaves differently | Bridge needs string building (forbidden) | Fallback: `osascript` child of the signed host with argv (verified pattern) | T5 |
| P4 | 1.7B model quality on real Swiss documents < synthetic | More review items | Rules first; thresholds; optional 3B / LAN server | Phase 3 |
| P5 | 8 GB floor not measured (16 GB machine) | Memory promise untested | Peak footprint 1.9 GB measured; real 8 GB test before release | Phase 8 |
| P6 | Contributors without macOS 11 | Floor regressions | CI on macOS 15 Intel + floor checklist per phase gate | ongoing |

## 4. Checkpoints

| After | Demo on the floor machine |
|---|---|
| T1–T3 | Spool file from DT3 → job in `queue.db`; config/audit written atomically |
| T4–T6 | Engine host started by launchd; Automation entry named "DT3 Agent Engine"; a tag written and undone via CLI |
| T7–T9 | **Walking skeleton (Phase 2 gate):** Smart Rule (or pull) → queue → fake AI → tag written → undo works, dry-run default |

## 5. Decisions taken in this plan

- Intake via **spool folder** (DT3 scripts write one small JSON file and return) — no socket code inside DT3 scripts.
- Fake AI server and fake DT3 adapter are first-class test tools, built in Phase 2.
- Swift builds with `swiftc` scripts (no Xcode project) until the app phase needs one.
