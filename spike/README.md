# Phase 0 spike kit — how to run it

Throwaway test scripts for the **floor machine** (MacBook Pro 2014, macOS 11).
They only measure. Product code comes after Phase 1.

---

## 1. Before you start (10 min, once)

| # | Do this | Check |
|---|---|---|
| 1 | Open **Terminal** | — |
| 2 | Get the repo: `git clone https://github.com/GianniAlagna/DEVONthink-3-AI.git ~/DEVONthink-3-AI` | If git asks for login: on GitHub click **Code → Download ZIP**, unzip to `~/DEVONthink-3-AI` |
| 3 | `cd ~/DEVONthink-3-AI && git checkout claude/gallant-albattani-tbsfnl` | Skip if you used the ZIP of this branch |
| 4 | In DT3: create database **`DT3Agent-Spike`** (name must contain `Spike`) | Optional 2nd one: `DT3Agent-Spike-2` |
| 5 | Plug in the power cable, close other apps | Measurements are cleaner |

Free disk space needed: about **8 GB** (models ~3.4 GB, builds, Python).
Everything is downloaded into `~/dt3agent-spike/`. Delete that folder at the end.

---

## 2. Run the steps (in this order)

Each line is one command. Wait until it says `Done.`

| Step | Command | Time | You do |
|---|---|---|---|
| S0 | `./spike/run.sh s0` | 1 min | nothing |
| S1 | `./spike/run.sh s1` | 5 min | nothing |
| S2 | `./spike/run.sh s2` | 20–90 min | nothing (tries older llama.cpp versions by itself if needed) |
| S3 | `./spike/run.sh s3` | 1–3 h | nothing — Mac gets hot and loud, that is normal |
| S4 | `./spike/run.sh s4 "DT3Agent-Spike"` | 5 min | allow "Terminal wants to control DEVONthink 3" → **OK**; then 3 short clicks (below) |
| S7 | `./spike/run.sh s7` | 1 min | nothing |
| S5 | `./spike/run.sh s5` | 3 min | type `y`; watch for a permission dialog → note the name, click **OK**, screenshot |
| S6 | `./spike/run.sh s6` | 3 min | nothing |
| S8 | `./spike/run.sh s8 1` then `./spike/run.sh s8 2` | 5 min | click the menu-bar icon → "Ask DEVONthink 3…" after each build; screenshot |
| End | `./spike/run.sh s7 uninstall` | 1 min | stops the test background service |

### S4 — three short clicks in DT3 (after the command)
1. **Tools → New Smart Rule** · Search in: `DT3Agent-Spike` · Kind is Any Document · Trigger: **On Demand** · Action: **Execute Script → External → "DT3Agent Spike Enqueue"** · Save.
2. Select 2–3 records → right-click → **Apply Rules** → your rule.
3. Select 2 records → Scripts menu (scroll icon) → **DT3Agent Spike Enqueue**.
4. Run `./spike/run.sh s4 check`

### S5 — later, two more short runs
- `./spike/run.sh s5 again` (same day — does the permission stay?)
- after a Mac restart: `./spike/run.sh s5 again`

### S8 — optional, self-signed certificate (5 min)
Tests if a self-signed certificate keeps the permission across updates (relevant because there is no Apple Developer ID).
1. **Keychain Access → Certificate Assistant → Create a Certificate…** · Name: `DT3 Agent Spike Signing` · Identity Type: Self-Signed Root · Certificate Type: **Code Signing** · Create.
2. `./spike/run.sh s8 1 "DT3 Agent Spike Signing"` → click icon → ask DT3
3. `./spike/run.sh s8 2 "DT3 Agent Spike Signing"` → click icon → ask DT3
4. Afterwards you may delete the certificate in Keychain Access.

---

## 3. Send me the results (answer to Q5)

| Option | How | When |
|---|---|---|
| **A — recommended** | `./spike/run.sh collect` → creates `dt3agent-spike-results-<date>.zip` on your Desktop → **attach it in this Claude chat** + attach your screenshots | Normal case |
| B | Open a log in `spike/out/`, copy the text, paste it in the chat | One step only, or if upload fails |

Privacy: `collect` replaces your home path and user name with `~` / `<user>`.
Logs contain: macOS/CPU/RAM facts, versions, timings, DT3 database **names** and the synthetic test records — no document content from your real databases.
Look inside the zip before you send it.

You can send results **step by step** (e.g. after S0–S2) — I then fix scripts early if something fails.

---

## 4. Safety

| Rule | How the kit keeps it |
|---|---|
| No real data touched | DT3 writes only into databases whose name contains `Spike`, inside `/_spike/<time>` |
| Nothing deleted in DT3 | No delete command anywhere |
| Downloads verified | SHA-256 checked before use (Python, CMake, models); mismatch = file removed, step stops |
| No system changes | Everything in `~/dt3agent-spike/`, one LaunchAgent (removed with `s7 uninstall`), 2 small DT3 scripts |
| Permission reset (S5) | Asks `y/N` first — resets Automation permissions for **all** apps (approved by you) |

## 5. Cleanup at the end
```bash
./spike/run.sh s7 uninstall
```
```bash
rm -rf ~/dt3agent-spike
```
Then delete in DT3: the Spike database(s) and the Smart Rule; in Finder: the two `DT3Agent Spike Enqueue.scpt` files in `~/Library/Application Scripts/com.devon-technologies.think3/`.
