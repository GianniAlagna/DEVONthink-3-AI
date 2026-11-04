# Phase 2 gate — floor demo (MacBook Pro 2014, macOS 11.7, DT3 3.9.17)

Goal: **new document → AI tag → undo**, through the real path: Smart Rule → spool → engine (via "DT3 Agent Engine") → llama-server → DT3.
Time: about 30 minutes, most of it the one-time build and download in step 2.
Use the **test database** only.

| # | Do | Expected |
|---|---|---|
| 1 | `cd ~/dt3agent-dev-kit && bash tools/dev-agent.sh python` | `Python 3.12.16 ready` (skip if done before) |
| 2 | `bash tools/dev-agent.sh llama` | about 6 min build + 1.9 GB download, then `llama-server running on http://127.0.0.1:8080`. If the download stops, run the same command again: it continues where it stopped |
| 3 | Quit DT3 (Cmd+Q), then `bash tools/dev-agent.sh smartrule`, then start DT3 | `Installed: Smart Rules/DT3 Agent Enqueue.scpt` |
| 4 | In DT3: **Tools › New Smart Rule** — Search in: test database · Kind: **is any document** · Perform: **On Import** · Action: **Apply Script › External › DT3 Agent Enqueue** · Name: `DT3 Agent` | rule saved |
| 5 | `bash tools/dev-agent.sh install osakit` | `Started (osakit, service)`; click OK if macOS asks |
| 6 | `tools/dt3agent status` | `"dt3_version": "3.9.17"`, `"ai_ok": true`, `"dry_run": true` |
| 7 | **Dry run:** drag `samples/Rechnung-Muster-Treuhand.txt` into the test database. Wait 60 s. `tools/dt3agent review` | one item `"kind": "planned"` with `tags_add`; **no new tag** in DT3 |
| 8 | **Live:** `tools/dt3agent live on`. Click the Rechnung in DT3 (select it), then `tools/dt3agent process`. Wait 60 s | `"queued": 1`; a tag from the list (e.g. **Rechnung**) appears on the document |
| 9 | **Undo:** `tools/dt3agent undo` | `"restored": 1`, the tag is gone in DT3 |
| 10 | `bash tools/dev-agent.sh status` — send the output + 1 screenshot of the document after step 8 | log lines `job planned`, `job applied` |
| 11 | Cleanup: `tools/dt3agent live off` then `bash tools/dev-agent.sh uninstall` | both LaunchAgents removed |

If step 7 shows nothing: the "On Import" trigger is **UNVERIFIED** (T1 proved the on-demand trigger). Select the document and run `tools/dt3agent process` instead (dry-run still on). Step 8 does not depend on the Smart Rule.
A document without text (image, scan) ends as review item `no_text`: correct, OCR comes in Phase 3.

What this proves: T5 host + Automation, T6 write + undo, T7 real AI call, T8 dry-run → live, T9 CLI + socket + LaunchAgents.
