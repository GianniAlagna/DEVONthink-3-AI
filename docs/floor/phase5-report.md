# Phase 5 report — menu-bar app (MacBook Pro 2014, macOS 11.7, DT3 3.9.17)

Floor test on 2026-11-05 with `docs/floor/phase5-gate.md` and the retest kit. System language en-CH; the app was
also run in de-CH, fr-CH and it-CH (`AppleLanguages`). DT3 runs in English.

## Results

| Part | Item | Result |
|---|---|---|
| A | `dev-agent.sh bundle`: app with Python and llama-server (93 MB) | ✅ after bug 1 |
| B | Installer: engine, llama-server, Smart Rule script, folders | ✅ after bug 3 |
| B | Model download after consent, SHA-256 checked | ✅ "AI model downloaded and checked" |
| B | Script not copied while DT3 is open, clear message | ✅ |
| B | `launchctl list`: app, engine, llama | ✅ |
| C | Setup, 7 steps; system check all green | ✅ after bug 4 |
| C | AI test: "Die KI antwortet." | ✅ |
| C | Unknown template field `{foo}`: warning, Continue disabled | ✅ |
| C | Settings saved (name, template, AI address, test mode) | ✅ config.json |
| D | Smart Rule action in DT3: Apply Script › External › DT3 Agent Enqueue | ✅ (bug 5: hint text) |
| E | Review Queue: 11 items, record name, before/proposal, confidence, Show in DT3 | ✅ |
| E | Edit + Return, Edit + Escape, Reject | ✅ |
| F | Settings: tab Swiss, change group, Cmd+S "Gesichert.", value persists | ✅ |
| G | French and Italian (installer window) | ✅ |
| H | VoiceOver and keyboard | **deferred to the Phase 8 release test** (Gianni, 2026-11-05) |
| I | Remove: agents gone, settings kept, model deleted when ticked | ✅ |

## Bugs found and fixed

| # | Bug | Fix |
|---|---|---|
| 1 | Swift 5.5 on the floor Mac: a view builder takes at most 10 children (installer did not build) | PR #56 |
| 2 | `bundle && open` while the app ran: `kLSNoExecutableErr` | PR #57 (quit the app first) |
| 3 | Re-install: `launchctl bootout` returns early, the following bootstrap failed silently; "AI server started" was shown anyway | PR #58 (wait, retry, check /health) |
| 4 | Setup kept "saving failed: engine not running" from before the install; no naming example | PR #59 |
| 5 | Smart Rule hint said "Execute Script"; DT3 shows "Apply Script › External" | PR #60 |
| 6 | Names: en dash gave `-–-`; long subject cut inside a word | PR #61 |

## Follow-ups

- Settings window: tab labels are cut ("Allgem…", "Duplika…", "Datens…") at 640 px; widen the window.
- Review Queue: a duplicate shows a raw `x-devonthink-item://` link instead of the other record's name (Phase 6).
- German DT3 menu labels for the Smart Rule stay UNVERIFIED (floor DT3 runs in English).
- CI builds with a newer Swift than the floor Mac; floor builds remain the check for old-Swift limits.
- VoiceOver and keyboard check in the Phase 8 release test.

## Decision

Phase 5 approved by Gianni on 2026-11-05 ("Phase 5 approved, go for phase 6"). VoiceOver and keyboard check deferred to the Phase 8 release test.
