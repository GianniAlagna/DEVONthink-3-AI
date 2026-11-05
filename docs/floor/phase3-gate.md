# Phase 3 gate — floor test (MacBook Pro 2014, macOS 11.7, DT3 3.9.17)

Goal: the full inbox pipeline on the **test database**: names, metadata, summary, filing, review decisions, OCR,
duplicates, case folder, urgent letter, Smart Rule on import. Time: about 30 minutes. Nothing is ever deleted.

## Prepare (once)

| # | Do | Expected |
|---|---|---|
| 1 | `cd ~/dt3agent-dev-kit && bash tools/dev-agent.sh llama` | `llama-server running on http://127.0.0.1:8080` |
| 2 | In the **test database** create 4 groups: `Finanzen/Rechnungen`, `_AI-Review`, `_Duplicates`, `Recht/Fall-Muster` | groups visible |
| 3 | `bash tools/dev-agent.sh testconfig "Erika Beispiel"` | `Test settings saved` |
| 4 | Quit DT3, `bash tools/dev-agent.sh smartrule`, start DT3 (skip if done in Phase 2) | `Installed: …` |
| 5 | `bash tools/dev-agent.sh install osakit` — click **OK** if macOS asks | `Started (osakit, service)` |
| 6 | `tools/dt3agent status` | `"ai_ok": true`, `"dry_run": true` |

## Test

| # | Do | Expected |
|---|---|---|
| 7 | **Dry run:** drag `samples/Rechnung-Muster-Treuhand.txt` into the test DB, select it, `tools/dt3agent process`, wait 60 s, `tools/dt3agent review` | items `field` with `"planned": true` for **name**, **comment**, **metadata**, **location**; nothing changed in DT3 |
| 8 | **Live:** `tools/dt3agent live on`, select the same document, `tools/dt3agent process`, wait 60 s, `tools/dt3agent review` | metadata written (Info pane: custom metadata `dt3agentdate 2026-04-17`, `dt3agenttotal CHF 1957.04`); document moved to `_AI-Review`; `name` and `comment` wait as items |
| 9 | Accept the name: `tools/dt3agent decide <id of the name item> accept` | document renamed `20260417000000_Muster-Treuhand-AG_Erika-Beispiel_…` |
| 10 | `tools/dt3agent undo` | old name back |
| 11 | **OCR:** select the scanned PDF from Phase 2 (`PRT10.scan…`) or `samples/ocr-de.pdf`, `tools/dt3agent process`, wait 90 s, `tools/dt3agent review` | no `no_text` any more; items for the scan. If macOS asks for access to a folder: **OK** |
| 12 | **Duplicate:** drag `samples/Rechnung-Muster-Treuhand.txt` in a second time, select the new copy, `tools/dt3agent process`, wait 60 s, `tools/dt3agent review` | item `duplicate` (`duplicate_exact` or `_near`) |
| 13 | `tools/dt3agent decide <id> accept` | the new copy gets tag `duplicate` and moves to `_Duplicates` (you delete it yourself if you want) |
| 14 | **Case folder:** item `case` "Fall Muster" for the invoice → `tools/dt3agent decide <id> accept` | the invoice also appears in `Recht/Fall-Muster` (replicant) |
| 15 | **Urgent:** drag `samples/Zahlungsbefehl-Muster.txt` in, select, `tools/dt3agent process`, wait 60 s, `tools/dt3agent review` | item `urgent` with `Zahlungsbefehl` |
| 16 | **Smart Rule on import:** drag `samples/Rechnung-Muster-Treuhand.txt` in once more (do not select, do not process) — wait 60 s, `bash tools/dev-agent.sh status` | a new `job …` line appears without `process` = "On Import" works |
| 17 | `bash tools/dev-agent.sh status` and `tools/dt3agent review` — send both outputs + screenshots of steps 8, 9, 14 | — |
| 18 | Cleanup: `tools/dt3agent live off`, `bash tools/dev-agent.sh uninstall` | agents removed |

If a step fails, stop and send the full output of that step.
