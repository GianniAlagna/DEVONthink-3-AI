# Privacy

DT3 Agent is built to keep your documents on your Mac. This page lists everything it stores and every network
connection it makes. It applies to DT3 Agent 1.0.0.

## What stays on your Mac

| What | Where | Content |
|---|---|---|
| Settings | `~/Library/Application Support/DT3 Agent/config.json` | your choices (groups, vocabulary, schedules); your name if you enter it |
| Queue, review list, undo journal | `engine.db`, `undo.db` in the same folder | record IDs, proposals, old and new values for undo |
| Search index | `index.db` in the same folder | text pieces and numeric vectors of the records you process |
| Audit log | `audit/` in the same folder | one line per action: time, actor, action, record ID, field names, result — **never document text** |
| Models | `models/` in the same folder | the AI model files you agreed to download |
| API key (optional) | macOS login Keychain, service `codes.modular.dt3agent.ai` | only if you enter one; never in any file |

The engine logs no document content. "Log document content" in Settings → Privacy is off by default.

## Network connections

| When | To | What is sent |
|---|---|---|
| Installer, only if you tick the download box | `huggingface.co` | a download request for the model file (pinned version, checked by SHA-256) |
| Every AI request | the AI server in Settings → AI (default: `127.0.0.1` on your Mac) | the text of the document or question being processed |
| Only if you enter an API key and switch it on | the same AI server | the key, and only over https or within your own network |
| Menu → Support (you click it) | your web browser opens a GitHub page | nothing from DT3 Agent |

There is **no telemetry, no analytics, no crash reporting and no update check**. Nothing else connects anywhere.

If you point the AI address to another computer, the document text goes to that computer. The app shows a warning
for addresses outside your own network.

## Diagnostics

"Export diagnostics …" writes a zip to your Downloads folder. It holds versions, counts, short error codes and
settings with every personal text replaced by `<set>` — no document text, names, group paths or record IDs. It
leaves your Mac only if you send it to someone.

## Removing everything

Menu → Installation … → **Remove** stops and removes the engine and AI servers. Tick the boxes to also delete the
models and the folder with settings, review list and logs. Your DEVONthink databases are never changed by removal.

## Contact

Privacy questions: open an issue, or for anything sensitive use **Security → Report a vulnerability** on GitHub.

*DT3 Agent is not affiliated with DEVONtechnologies.*
