# Phase 0 spike kit — how to run it

Throwaway test scripts for the **floor machine** (MacBook Pro 2014, macOS 11).
They only measure. Product code comes after Phase 1.

---

## 1. Before you start (10 min, once)

| # | Do this | Check |
|---|---|---|
| 1 | Download **`dt3agent-spike-kit.zip`** from the Claude chat | Lands in `Downloads` |
| 2 | Open **Terminal** (Applications → Utilities → Terminal) | — |
| 3 | Unpack into your **home folder** (copy this line): `ditto -x -k ~/Downloads/dt3agent-spike-kit.zip ~` | If macOS asks "Terminal would like to access Downloads" → **OK** |
| 4 | Go into the kit: `cd ~/dt3agent-spike-kit` | `ls` shows `spike` and `fixtures` |
| 5 | Optional — check the download is intact: `shasum -a 256 ~/Downloads/dt3agent-spike-kit.zip` | Must equal the SHA-256 in the chat |
| 6 | In DT3: create database **`DT3Agent-Spike`** (name must contain `Spike`) | Optional 2nd one: `DT3Agent-Spike-2` |
| 7 | Plug in the power cable, close other apps | Measurements are cleaner |

### Command Line Tools (needed for S2, S6, S8)

Run 2 showed: compiler **Swift 5.4.2** (Command Line Tools 12.5.1) next to an SDK made for **Swift 5.5** → Swift builds fail.
The kit now picks a matching SDK by itself. The clean fix (and the version the project targets) is **Command Line Tools for Xcode 13.2**:

| # | Do this | Check |
|---|---|---|
| a | Sign in at developer.apple.com/download/all (free Apple ID, no paid program) | — |
| b | Search **Command Line Tools for Xcode 13.2**, download the `.dmg`, open it, run the installer | Installs over the old version |
| c | Test: `xcrun swiftc --version` | Shows **Swift version 5.5.2** |

Full Xcode is **not** needed for the spike.

**Keep the kit in `~/dt3agent-spike-kit`** (not in Downloads, Desktop or Documents). macOS protects those folders, and the background test service (S7/S5) could not read the scripts there.

Free disk space needed: about **8 GB** (models ~3.4 GB, builds, Python).
Downloads and builds go into `~/dt3agent-spike/`. Delete that folder at the end.

---

## 2. Run the steps (in this order)

Always start in the kit folder: `cd ~/dt3agent-spike-kit`. Each line is one command. Wait until it says `Done.`

**Do not skip a step.** S1 installs the Python every later step needs. If a step prints `STOP` or `FAILED`, send me that log before going on.

| Step | Command | Time | You do |
|---|---|---|---|
| S0 | `bash spike/run.sh s0` | 1 min | nothing |
| S1 | `bash spike/run.sh s1` | 5 min | nothing |
| S2 | `bash spike/run.sh s2` | 20–90 min | nothing (tries older llama.cpp versions by itself if needed) |
| S3 | `bash spike/run.sh s3` | 1–3 h | nothing — Mac gets hot and loud, that is normal |
| S4 | `bash spike/run.sh s4 "DT3Agent-Spike"` | 5 min | allow "Terminal wants to control DEVONthink 3" → **OK**; then 3 short clicks (below) |
| S7 | `bash spike/run.sh s7` | 1 min | nothing |
| S5 | `bash spike/run.sh s5` | 3 min | type `y`; watch for a permission dialog → note the name, click **OK**, screenshot |
| S6 | `bash spike/run.sh s6` | 3 min | nothing |
| S8 | `bash spike/run.sh s8 1` then `bash spike/run.sh s8 2` | 5 min | click the menu-bar icon → "Ask DEVONthink 3…" after each build; screenshot |
| End | `bash spike/run.sh s7 uninstall` | 1 min | stops the test background service |

### S4 — three short clicks in DT3 (after the command)
1. **Tools → New Smart Rule** · Search in: `DT3Agent-Spike` · Kind is Any Document · Trigger: **On Demand** · Action: **Execute Script → External → "DT3Agent Spike Enqueue"** · Save.
2. Select 2–3 records → right-click → **Apply Rules** → your rule.
3. Select 2 records → Scripts menu (scroll icon) → **DT3Agent Spike Enqueue**.
4. Run `bash spike/run.sh s4 check`

### S5 — later, two more short runs
- `bash spike/run.sh s5 again` (same day — does the permission stay?)
- after a Mac restart: `bash spike/run.sh s5 again`

### S8 — optional, self-signed certificate (5 min)
Tests if a self-signed certificate keeps the permission across updates (relevant because there is no Apple Developer ID).
1. **Keychain Access → Certificate Assistant → Create a Certificate…** · Name: `DT3 Agent Spike Signing` · Identity Type: Self-Signed Root · Certificate Type: **Code Signing** · Create.
2. `bash spike/run.sh s8 1 "DT3 Agent Spike Signing"` → click icon → ask DT3
3. `bash spike/run.sh s8 2 "DT3 Agent Spike Signing"` → click icon → ask DT3
4. Afterwards you may delete the certificate in Keychain Access.

---

## 3. Send me the results (answer to Q5)

| Option | How | When |
|---|---|---|
| **A — recommended** | `bash spike/run.sh collect` → creates `dt3agent-spike-results-<date>.zip` on your Desktop → **attach it in this Claude chat** + attach your screenshots | Normal case |
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
cd ~/dt3agent-spike-kit && bash spike/run.sh s7 uninstall
```
```bash
rm -rf ~/dt3agent-spike ~/dt3agent-spike-kit
```
Then delete in DT3: the Spike database(s) and the Smart Rule; in Finder: the two `DT3Agent Spike Enqueue.scpt` files in `~/Library/Application Scripts/com.devon-technologies.think3/`.
