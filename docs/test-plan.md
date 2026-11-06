# Release test plan and pre-launch checklist (R-4, SPEC §4.23)

Run before every release. A release needs every **must** line ✅ on machine A and B. Write results into
`docs/floor/release-<version>-report.md`. Nothing is published until the owner says go.

## Machines

| | Machine | Required |
|---|---|---|
| A | Floor Mac: MacBook Pro 2014, macOS 11.7, Intel, 16 GB, DEVONthink 3.9.17 | must |
| B | One Apple Silicon Mac, macOS 12 or later (owner decision Q6) | must |
| C | One 8 GB Mac (owner decision Q2) | if available; else the 8 GB limit stays in the guide |

Use a **test database** only (DT3Agent-T1 and the samples from the kit). Test mode stays on except where a line says
otherwise.

## Baselines (from the phase reports)

| Measure | Baseline (machine A) | Blocks the release if |
|---|---|---|
| Time per 1-page document (AI + rules + index) | 1–2 min (Phase 4–6) | > 3 min |
| Memory: answer server / index server | 3.6 GB / 1.4 GB (Phase 6) | > 4.5 GB / > 2 GB |
| Index: 7 records incl. OCR | 3 min 25 s (Phase 6) | > 6 min |

## 1. Install from the DMG (A, B)

| # | Step | Expected | Must |
|---|---|---|---|
| 1.1 | Remove any older install (menu → Installation … → Remove, both boxes), delete the old app | `launchctl list \| grep dt3agent` empty | ✓ |
| 1.2 | Open the DMG, drag the app to Applications, first launch as in `README-first-launch.txt` | app opens after one Gatekeeper confirmation | ✓ |
| 1.3 | Quit DT3; Installation … → both model boxes → Install | all rows green; `Smart Rule script installed.` (compiled on this Mac); `Done.` | ✓ |
| 1.4 | `launchctl list \| grep dt3agent` | engine, llama, embed, app | ✓ |
| 1.5 | Open DT3; first action → macOS asks for "DT3 Agent Engine" → OK | permission granted once | ✓ |

## 2. Setup and inbox (A, B)

| # | Step | Expected | Must |
|---|---|---|---|
| 2.1 | Setup … all steps; AI test | `The AI answers.`; name preview updates | ✓ |
| 2.2 | Smart Rule On Import → Apply Script › External › DT3 Agent Enqueue; import the kit samples | items appear in the Review Queue (test mode) | ✓ |
| 2.3 | Accept, edit, reject one item each; Undo last batch | DT3 shows the change; undo restores it | ✓ |
| 2.4 | QR-bill sample | amount, IBAN, reference proposed; deadline item → accept → calendar event + reminder | ✓ |
| 2.5 | Urgent sample (Betreibung) | urgent item; accept moves it to the urgent group | ✓ |
| 2.6 | Test mode off; process one sample | confident fields applied directly; audit line written | ✓ |

## 3. Knowledge (A, B)

| # | Step | Expected | Must |
|---|---|---|---|
| 3.1 | Ask 5 questions with a matching document, 5 without (list in the kit) | 5× answer with the right source; 5× "not found"; record each `best` value | ✓ |
| 3.2 | Injection samples (Phase 6 D) | no "HACKED", nothing changed in DT3, filtered note shown | ✓ |
| 3.3 | Summaries DE/FR/IT/EN | right language, no orders obeyed | ✓ |

## 4. Schedules and operations (A)

| # | Step | Expected | Must |
|---|---|---|---|
| 4.1 | Settings → Schedule: scope, digest, hygiene, feeds with `/_Berichte/`; Advanced: entities with `/Kontakte/` | `Saved.` | ✓ |
| 4.2 | `tools/dt3agent job nightly`, change a tag in DT3, `job nightly` again | the changed record is queued | ✓ |
| 4.3 | `job digest`, `job hygiene`, `job feeds` (an RSS feed in the test database) | report items; accept writes a note; record the DT3 `kind` of the RSS record | ✓ |
| 4.4 | Two documents from the same sender processed | entity note proposal | |
| 4.5 | Export diagnostics … | zip in Downloads, no database/group/document names | ✓ |
| 4.6 | API key save/remove (AI tab) | `security … -w` shows it; macOS asks no password (record if it does) | |
| 4.7 | Menu-bar states: stop the AI server (`launchctl bootout gui/$(id -u)/codes.modular.dt3agent.llama`) | red ⚠︎ "AI not reachable"; Installation … → Install restores it | ✓ |

## 5. Accessibility and languages (A) — carried over from Phase 5

| # | Step | Expected | Must |
|---|---|---|---|
| 5.1 | VoiceOver (Cmd+F5): menu-bar icon, setup system check, Review Queue buttons, Settings | every control has a spoken name; states are spoken, not only colours | ✓ |
| 5.2 | Keyboard navigation (Tab, Space, Cmd+S) in Settings and Review Queue | no trap; all controls reachable | ✓ |
| 5.3 | App language fr-CH, it-CH, en (`defaults write codes.modular.dt3agent.app AppleLanguages …`) | no cut-off or English left-overs | ✓ |

## 6. 48 h soak (A) — P7-G

Settings as in 4.1, test mode on, charger connected, DT3 open, Mac not sleeping (System Preferences → Energy Saver).
Add 3–5 documents per day. At start, after 24 h and after 48 h:

```bash
date; tools/dt3agent status | grep -E '"queue"|"queue_backlog"|"last_job"' -A4; ps -axo rss,etime,command | grep -E '[l]lama-server|[D]T3AgentEngine|[d]t3agent' | awk '{printf "%d MB %s %s\n", $1/1024, $2, $3}'
```

| Must | Expected |
|---|---|
| ✓ | no process restarted (elapsed time keeps growing), memory within the baselines |
| ✓ | nightly run, digest and hygiene ran on schedule (`status` → `jobs`) |
| ✓ | `queue_backlog` stays empty or below 120 minutes; no new `dead` jobs |

## 7. Removal (A, B)

| # | Step | Expected | Must |
|---|---|---|---|
| 7.1 | Installation … → Remove, both boxes | no `dt3agent` in `launchctl list`; models and data folder gone | ✓ |
| 7.2 | DT3 databases | unchanged | ✓ |

## Pre-launch checklist (owner says go only when all are ✅)

- [ ] Release test report written, all **must** lines ✅ on A and B
- [ ] CI green on `main`
- [ ] Version PR merged (1.0.0 in engine and both Info.plists; CHANGELOG dated)
- [ ] `SUPPORT.md` placeholders filled by modular.codes (or the section removed)
- [ ] Signing certificate created by the owner, `.p12` and password backed up offline, three secrets set (`docs/release.md`)
- [ ] README status and links checked; "not affiliated with DEVONtechnologies" present
- [ ] Owner pushed tag `v1.0.0`; draft release built; both DMG checksums verified; one DMG installed on a clean Mac
- [ ] Owner pressed **Publish release**
