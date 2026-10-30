# Phase 0 — Floor spike plan

Status: **APPROVED by Gianni 2026-10-30.** Spike kit ready in `spike/` (how to run: `spike/README.md`). Nothing has run on the floor machine yet.

## Verified while building the kit (2026-10-30, from official sources — not yet on the floor)

| Fact | Source | Consequence |
|---|---|---|
| Official llama.cpp macOS x64 release binaries target **macOS 13.3** | llama.cpp `b12015` `.github/workflows/release.yml` (`CMAKE_OSX_DEPLOYMENT_TARGET=13.3`) | Prebuilt route dropped; S2 builds from source with target 11.0 |
| `GGML_ACCELERATE` uses `ACCELERATE_NEW_LAPACK` (macOS 13.3 SDK headers) | llama.cpp `b12015` `ggml/src/ggml-cpu/CMakeLists.txt` | Build with `-DGGML_ACCELERATE=OFF -DGGML_BLAS=OFF` on Xcode 13.2 |
| llama.cpp needs CMake ≥ 3.14 and C++17 | llama.cpp `b12015` `CMakeLists.txt` | CMake 3.31.12 universal tarball from cmake.org (SHA-256 pinned) |
| llama-server supports `response_format: {"type":"json_schema","schema":…}`, `chat_template_kwargs`, `--reasoning-budget`, `-c`, `-t`, `-np`, `--no-webui` | llama.cpp `b12015` `tools/server/README.md` | Used in S3 |
| python-build-standalone Intel macOS builds target **macOS 10.15** | `astral-sh/python-build-standalone` tag `20261026`, `cpython-unix/targets.yml` | Floor-compatible on paper; S1 confirms with `otool` |
| Pinned CPython **3.12.16** (+20261026) | same tag, `pythonbuild/downloads.json` | — |
| Models: `Qwen3-1.7B` Q4_K_M (1.28 GB) and `granite-4.0-micro` 3B Q4_K_M (2.10 GB), both **Apache-2.0**; Granite lists German, French, Italian, English | Hugging Face API + model card | SmolLM3-3B rejected: no German in its language list |
| Synthetic QR-bills decode byte-exact with an independent decoder (OpenCV) | `spike/tools/make_fixtures.py`, run in the cloud | Fixtures valid for S6; QR payload uses CRLF (kept byte-exact via `.gitattributes`) |

Goal: turn every `UNVERIFIED` item in the brief into a fact measured on the **floor machine**
(MacBook Pro 15" Mid 2014, macOS 11.7.x, Intel Haswell, Xcode 13.2.x), before any spec or product code.

Legend: **verified** = measured on the floor machine · **assumed** = from docs or memory, not yet measured.

---

## Ground rules for the spike

| Rule | Why |
|---|---|
| Use a **throwaway DT3 database** `DT3Agent-Spike` with synthetic documents only | Never touch production data; no delete needed |
| Spike code lives in `spike/` and is **thrown away** after Phase 0 | It is not product code; only the ADRs and the report survive |
| Every step writes its output to `spike/out/<step>.log` | Evidence for the report; nothing is "ok" without a log line |
| No Homebrew, no OCLP, no system changes outside `~/` | Floor must stay a realistic user machine |
| The DT3 `sdef` dictionary stays **local** (not committed) | DEVONtechnologies' content; we commit only our notes about it |
| Downloads (Python, llama.cpp, models, cmake) only from the official source, with SHA-256 recorded | Supply chain; reproducible pins |

---

## Steps

### S0 — Inventory (5 min)

```bash
sw_vers; uname -m
sysctl -n machdep.cpu.brand_string hw.memsize hw.physicalcpu hw.logicalcpu
sysctl -n machdep.cpu.leaf7_features | tr ' ' '\n' | grep -E 'AVX2|BMI2'
sysctl -n machdep.cpu.features | tr ' ' '\n' | grep -E 'FMA|F16C|AVX1.0'
xcodebuild -version; swift --version
mdls -name kMDItemVersion -name kMDItemCFBundleIdentifier "/Applications/DEVONthink 3.app"
df -h ~
```

Evidence: exact macOS build, CPU flags (AVX2/FMA/F16C decide the llama.cpp CPU path), **real RAM**
(a 15" Mid 2014 shipped with 16 GB — see risk R1), Xcode/Swift version, DT3 version + bundle id.

### S1 — Bundled Python runtime (30 min)

Candidate: `python-build-standalone` (astral-sh), CPython 3.12.x, `x86_64-apple-darwin-install_only` and `aarch64-apple-darwin-install_only`.

```bash
mkdir -p ~/spike/py && cd ~/spike/py
# download the pinned tarball from the official GitHub release page, then:
shasum -a 256 cpython-3.12.*-x86_64-apple-darwin-install_only*.tar.gz
tar xzf cpython-3.12.*-x86_64-apple-darwin-install_only*.tar.gz
otool -l python/bin/python3.12 | grep -A4 LC_BUILD_VERSION      # minos must be <= 11.0
python/bin/python3 -c "import sys,sqlite3,ssl,json,hashlib,unicodedata;print(sys.version);print(sqlite3.sqlite_version);print(ssl.OPENSSL_VERSION)"
python/bin/python3 -c "import sqlite3;c=sqlite3.connect('/tmp/w.db');print(c.execute('pragma journal_mode=wal').fetchone())"
```

Pass: runs on macOS 11 Intel, `minos` ≤ 11.0, SQLite supports WAL + JSON functions, relocatable (works after moving the folder).
Fallback: older 3.12 patch release, or 3.11 (ADR documents the trade-off).

### S2 — llama.cpp on the floor (1–2 h)

Build from source only (official prebuilt binaries need macOS 13.3 — verified, see top).
CMake 3.31.12 from cmake.org (no Homebrew) + Xcode 13.2 clang. `spike/s2-llama.sh` tries tags newest first:
`b12015 b11000 b10000 b9000 b6000`, and stops at the first that builds.

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0 -DBUILD_SHARED_LIBS=OFF \
  -DGGML_NATIVE=ON -DGGML_METAL=OFF -DGGML_ACCELERATE=OFF -DGGML_BLAS=OFF -DGGML_OPENMP=OFF \
  -DLLAMA_OPENSSL=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF
cmake --build build -j 4 --target llama-server llama-bench
```

Pass: a working `llama-server` on macOS 11 Intel; the ADR records the tag and any build error of newer tags.
Note for later (assumed): the shipped binary will be built in CI with `CMAKE_OSX_DEPLOYMENT_TARGET=11.0`; the spike proves it runs.

### S3 — Model speed and memory (2–3 h incl. downloads)

Two models, GGUF `Q4_K_M`, one ~1.5–2B and one ~3B. Candidates to confirm (size, **license**, de/fr/it quality) — see open question Q3.

```bash
cd ~/spike/llama.cpp
./build/bin/llama-bench -m ~/spike/models/<model>.gguf -p 512 -n 128 -t 4
/usr/bin/time -l ./build/bin/llama-server -m ~/spike/models/<model>.gguf -c 4096 -t 4 --port 8089 &
# then: POST a synthetic 1-page Swiss invoice text with a JSON schema (fixtures/spike/invoice-de.txt)
curl -s http://127.0.0.1:8089/completion -H 'Content-Type: application/json' -d @spike/req-invoice-de.json
```

Measure per model:

| Metric | How |
|---|---|
| Prompt processing t/s, generation t/s | `llama-bench` |
| Seconds per document (classify + fields + 3-line summary) | wall time of the real request, median of 5 |
| Peak RSS | `/usr/bin/time -l` "maximum resident set size" |
| Schema compliance | 20 runs, count valid JSON that matches the schema |
| Behaviour under memory pressure | repeat once while `memory_pressure -l warn` runs |
| Language quality | same invoice in de/fr/it/en, manual check of fields |

Pass: at least one model ≤ 3B gives valid schema output ≥ 19/20 with acceptable seconds/doc (target set by Gianni after seeing numbers).
Also verify (assumed): the request field for JSON schema / grammar and the context-size flag in the pinned tag.

### S4 — DT3 3.9 scripting surface (2 h)

```bash
mkdir -p ~/spike/dt3 && sdef "/Applications/DEVONthink 3.app" > ~/spike/dt3/dt3.sdef   # local only
grep -nE 'replicate|duplicate|create record|custom meta|reference URL|reminder|content hash|duplicates|ocr|annotation' ~/spike/dt3/dt3.sdef
```

Then one JXA probe per capability, run against `DT3Agent-Spike`, with **arguments via argv only**:

| # | Capability | What we record |
|---|---|---|
| 1 | Target DT3, not DT4 | `Application("/Applications/DEVONthink 3.app")` by path vs `Application("DNtp")`; `version()` starts with `3.`; bundle ids of DT3/DT4 |
| 2 | Read record by UUID | `getRecordWithUuid`, plain text, name, tags, dates, type, size |
| 3 | Create Markdown record | `createRecordWith` with type markdown + content vs plain text |
| 4 | Custom metadata | add/read a text and a date field; key naming rules |
| 5 | Rename, set tags, set comment | old values readable first (undo journal) |
| 6 | Move / replicate / duplicate | exact commands; replicate across groups in the same DB; duplicate across DBs |
| 7 | Item link | `referenceURL` / `x-devonthink-item://UUID` format |
| 8 | Duplicates info | does a record expose its duplicates / a content hash? |
| 9 | Reminders | DT3 reminder object: create/read; alarm types |
| 10 | OCR | which command exists, and on which edition (Pro vs Standard) |
| 11 | Latency | median ms of one `osascript` round trip (cold and warm) |
| 12 | Smart Rule entry | `performsmartrule(records)` that only appends UUIDs to a file and returns; confirm install path `~/Library/Application Scripts/com.devon-technologies.think3/Smart Rules/` and Menu path |

Pass: each row has a working snippet or a documented "not available in 3.9.x".

### S5 — Automation permission (TCC) from a background engine (1 h) — highest risk

Question: when a **LaunchAgent** runs bundled Python, which calls `osascript`, which process does macOS 11 ask
for "Automation → DEVONthink 3", does the prompt even appear, and does the grant persist?

```bash
tccutil reset AppleEvents          # clean start (affects all apps' Automation grants — run only with Gianni's OK)
# run S7 LaunchAgent with a job that calls the S4 read probe
log show --last 5m --predicate 'subsystem == "com.apple.TCC"' | tail -50
```

Evidence: screenshot of System Preferences → Security & Privacy → Privacy → Automation; error code if denied (`-1743`).
Decides ADR "process model": engine calls DT3 directly vs. the signed app performs DT3 calls on the engine's behalf.

### S6 — Vision helper on macOS 11 (1 h)

Swift probe compiled with `swiftc` (Xcode 13.2):

| Check | Expected evidence |
|---|---|
| `VNRecognizeTextRequest.supportedRecognitionLanguages(for: .accurate, revision: 2)` | list contains de, fr, it, en (assumed for macOS 11, to verify) |
| OCR of a synthetic scanned PDF page (PDFKit → CGImage) in de/fr/it | recognised text vs ground truth |
| `VNDetectBarcodesRequest` on a synthetic Swiss QR-bill PDF | decoded payload byte-equal to the generated one |
| Runtime | ms per page |

Synthetic QR-bills are generated on any machine with a dev-only tool (e.g. the `qrbill` Python package) — no real data.

### S7 — launchd LaunchAgent + Unix socket (45 min)

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/codes.modular.dt3agent.spike.plist
launchctl print gui/$(id -u)/codes.modular.dt3agent.spike | head -40
kill <pid>   # KeepAlive restarts it?
launchctl bootout gui/$(id -u)/codes.modular.dt3agent.spike
```

Also: socket at `~/Library/Application Support/DT3 Agent/engine.sock` — mode `0600`, path ≤ 104 bytes (`sun_path` limit) for the longest realistic username; survives logout/login; runs with the app closed.

### S8 — App toolchain smoke test (1 h)

Minimal app built with Xcode 13.2 `swiftc` per architecture + `lipo` (no project file needed for the spike): `NSStatusItem` + `NSPopover` hosting SwiftUI, target 11.0. Also measures whether the Automation permission survives a rebuild, ad-hoc vs. self-signed (R9).

```bash
./spike/run.sh s8 1    # build 1, ad-hoc signed, then click "Ask DEVONthink 3"
./spike/run.sh s8 2    # simulated update: is the Automation permission kept?
```

Evidence: universal binary, runs on floor, Dark Mode + VoiceOver reads the menu item, screenshot.

### S9 — Report + ADRs (1 h)

| Output | Content |
|---|---|
| `docs/spike/phase0-report.md` | every step: verified / assumed / failed, numbers, open risks |
| `docs/adr/0001-python-runtime.md` | runtime choice + pinned version + SHA-256 |
| `docs/adr/0002-llama-cpp-build.md` | prebuilt vs CI build, pinned tag |
| `docs/adr/0003-default-models.md` | 8 GB default + larger option, licenses |
| `docs/adr/0004-dt3-api-surface.md` | supported DT3 range, command list, DT4 refusal |
| `docs/adr/0005-process-model-and-tcc.md` | who sends AppleEvents to DT3 |
| `docs/adr/0006-vision-helper.md` | OCR languages, QR decode |
| `docs/adr/0007-launchd-and-socket.md` | install/uninstall commands, socket path |
| `docs/adr/0008-app-toolchain.md` | Xcode 13.2, SwiftUI macOS 11 limits |

**Gate:** Gianni reviews the report. Then Phase 1 (spec + plan).

---

## Risks found while planning

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | Floor machine has **16 GB** (confirmed, Q2), not 8 GB → it cannot prove the 8 GB promise directly | 8 GB claim untested | Budget by peak RSS (engine + model ≤ ~3 GB, assumed), test under `memory_pressure`, plus one real 8 GB machine before release |
| R2 | TCC Automation prompt for a background process may never appear or attach to the wrong binary | Engine cannot talk to DT3 | S5 decides; fallback: the signed app sends AppleEvents |
| R3 | Current llama.cpp may not build with Xcode 13.2 or may target newer macOS | No local AI on floor | Pin last working tag; CI-built binary with deployment target 11.0 |
| R4 | `Application("DNtp")` may resolve to DT4 when both are installed | Writes into the wrong app | Address DT3 by path/bundle id, check `version()` |
| R5 | Small models are weak in fr/it | Bad names/tags | Rules-first extraction; AI fields go to Review Queue below threshold |
| R6 | Model licenses (Llama, Gemma, some Qwen sizes) are not Apache/MIT | Redistribution/terms issues | Recommend only permissive models by default; show license before download |
| R7 | "DT3" in the product name may still read as DEVONthink branding | Trademark complaint | Final name in Phase 8 with a trademark screen; "not affiliated" note |
| R8 | GitHub Intel macOS runners retire after Fall 2027 | No Intel CI | Documented; floor machine remains the Intel test |
| R9 | **No Apple Developer ID (Q7)** → no notarization | Gatekeeper blocks the downloaded app (macOS 15+: only via System Settings → "Open Anyway"); Automation and Keychain grants may reset on every update (ad-hoc signature changes) | S8 measures ad-hoc vs. self-signed certificate across a simulated update; ADR decides; build-from-source path documented |
| R10 | Bundle ID prefix not decided (Q9) | Changes TCC grants, paths and LaunchAgent label later | Spike uses neutral `spike.dt3agent`; decide before Phase 2 (see below) |

---

## Open decisions

| # | Decision | Recommendation | Why |
|---|---|---|---|
| D1 (Q9) | Bundle ID prefix | **One** ID for all users: `codes.modular.dt3agent` | Reverse-DNS of the domain you own (`modular.codes` → `codes.modular`). Two IDs = two apps for macOS: separate permissions, settings and data; a user switching plan loses them. Business support is a service, not a different binary |
