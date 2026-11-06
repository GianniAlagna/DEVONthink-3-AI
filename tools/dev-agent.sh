#!/bin/bash
# Floor tests for Phase 2: run the engine host (and llama-server) as LaunchAgents.
# Developer tool, not the installer (that is Phase 5).
# Usage: tools/dev-agent.sh python | llama | smartrule | install [osakit|osascript] [record-UUID] [read|tag]
#                           | embed | bundle | status | uninstall
#   install without a record ID runs the engine service; control it with tools/dt3agent.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=$(pwd)
LABEL="codes.modular.dt3agent.engine.dev"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/DT3 Agent/engine-dev.log"
DEV="$HOME/dt3agent-dev"
PY="${DT3A_PYTHON:-$DEV/python/bin/python3}"
# Pinned runtime (ADR-0001); the checksum list comes from the same release and is checked before unpacking.
PY_TAG="20261026"
PY_ASSET="cpython-3.12.16+20261026-$(uname -m)-apple-darwin-install_only.tar.gz"
APP="$REPO/build/DT3 Agent Engine.app"
DATA="$HOME/Library/Application Support/DT3 Agent"
LLAMA_LABEL="codes.modular.dt3agent.llama.dev"
LLAMA_PLIST="$HOME/Library/LaunchAgents/$LLAMA_LABEL.plist"
LLAMA_LOG="$HOME/Library/Logs/DT3 Agent/llama-dev.log"
LLAMA_TAG="b12015"          # ADR-0002, built on the floor in Phase 0
LLAMA_DIR="$DEV/llama.cpp"
LLAMA_SERVER="$LLAMA_DIR/build/bin/llama-server"
CMAKE_VER="3.31.12"
CMAKE_SHA256="cf096d869d45b79f5ce82f3d6abffa44f983fc146fee13cfe59024911e6975af"
CMAKE="$DEV/cmake-$CMAKE_VER-macos10.10-universal/CMake.app/Contents/bin/cmake"
# ADR-0003: Qwen3-1.7B Q4_K_M (Apache-2.0), pinned by revision and SHA-256
MODEL_URL="https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/daeb8e2d528a760970442092f6bf1e55c3b659eb/Qwen3-1.7B-Q4_K_M.gguf"
MODEL_SHA256="d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5"
MODEL="$DEV/models/Qwen3-1.7B-Q4_K_M.gguf"
AI_URL="http://127.0.0.1:8080"
# ADR-0011: Qwen3-Embedding-0.6B Q8_0 (Apache-2.0) for the knowledge index, second llama-server on 8081
EMBED_URL_MODEL="https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/resolve/370f27d7550e0def9b39c1f16d3fbaa13aa67728/Qwen3-Embedding-0.6B-Q8_0.gguf"
EMBED_SHA256="06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439"
EMBED_MODEL="$DEV/models/Qwen3-Embedding-0.6B-Q8_0.gguf"
EMBED_URL="http://127.0.0.1:8081"
EMBED_LABEL="codes.modular.dt3agent.embed.dev"
EMBED_PLIST="$HOME/Library/LaunchAgents/$EMBED_LABEL.plist"
EMBED_LOG="$HOME/Library/Logs/DT3 Agent/embed-dev.log"
DOMAIN="gui/$(id -u)"

stop() { launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true; rm -f "$PLIST"; }
stop_llama() { launchctl bootout "$DOMAIN/$LLAMA_LABEL" 2>/dev/null || true; rm -f "$LLAMA_PLIST"; }
stop_embed() { launchctl bootout "$DOMAIN/$EMBED_LABEL" 2>/dev/null || true; rm -f "$EMBED_PLIST"; }
sha_ok() { [ -f "$1" ] && [ "$(shasum -a 256 "$1" | awk '{print $1}')" = "$2" ]; }
# fetch URL FILE SHA256: download once, resume after a dropped connection, keep only if the checksum matches
fetch() {
    sha_ok "$2" "$3" && return 0
    mkdir -p "$(dirname "$2")"
    local ok=0 i
    if sha_ok "$2.part" "$3"; then ok=1; fi
    for i in 1 2 3 4 5 6 7 8; do
        [ "$ok" = 1 ] && break
        echo "Downloading $(basename "$2") (attempt $i/8)"
        # -C -: continue where the last attempt stopped · abort a stalled transfer after 60 s below 1 KB/s
        # caffeinate -i: the Mac must not fall asleep during the download (floor: sleep dropped the connection)
        if caffeinate -i curl -fL -C - --connect-timeout 30 --speed-limit 1024 --speed-time 60 --progress-bar -o "$2.part" "$1"; then
            ok=1
        else
            echo "Connection dropped - continuing in 10 s"
            sleep 10
        fi
    done
    [ "$ok" = 1 ] || { echo "Download not finished. Check the internet connection, then run the same command again: it continues where it stopped."; exit 1; }
    sha_ok "$2.part" "$3" || { echo "SHA-256 mismatch for $(basename "$2") - file removed, run the command again"; rm -f "$2.part"; exit 1; }
    mv "$2.part" "$2"
}

case "${1:-}" in
python)
    mkdir -p "$DEV"
    base="https://github.com/astral-sh/python-build-standalone/releases/download/$PY_TAG"
    curl -fsSL -o "$DEV/SHA256SUMS" "$base/SHA256SUMS"
    curl -fsSL -o "$DEV/$PY_ASSET" "$base/$(echo "$PY_ASSET" | sed 's/+/%2B/')"
    want=$(awk -v a="$PY_ASSET" '$2==a{print $1}' "$DEV/SHA256SUMS")
    got=$(shasum -a 256 "$DEV/$PY_ASSET" | awk '{print $1}')
    [ -n "$want" ] && [ "$want" = "$got" ] || { echo "SHA-256 mismatch for $PY_ASSET - stopped"; rm -f "$DEV/$PY_ASSET"; exit 1; }
    rm -rf "$DEV/python" && tar xzf "$DEV/$PY_ASSET" -C "$DEV"
    "$PY" -I -c 'import sys; print("Python", sys.version.split()[0], "ready")'
    ;;
llama)
    # llama.cpp from source for macOS 11 (ADR-0002, about 6 minutes) + the default model (1.9 GB, ADR-0003)
    xcrun --find clang >/dev/null 2>&1 || { echo "Command Line Tools missing (see Phase 0 START-HERE)"; exit 1; }
    fetch "https://cmake.org/files/v3.31/cmake-$CMAKE_VER-macos10.10-universal.tar.gz" "$DEV/cmake.tar.gz" "$CMAKE_SHA256"
    [ -x "$CMAKE" ] || tar xzf "$DEV/cmake.tar.gz" -C "$DEV"
    if [ ! -x "$LLAMA_SERVER" ]; then
        rm -rf "$LLAMA_DIR"
        git clone -q --depth 1 --branch "$LLAMA_TAG" https://github.com/ggml-org/llama.cpp "$LLAMA_DIR"
        "$CMAKE" -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0 \
            -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=ON -DGGML_METAL=OFF -DGGML_ACCELERATE=OFF -DGGML_BLAS=OFF \
            -DGGML_OPENMP=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF >/dev/null
        caffeinate -i "$CMAKE" --build "$LLAMA_DIR/build" -j "$(sysctl -n hw.physicalcpu)" --target llama-server >/dev/null
    fi
    "$LLAMA_SERVER" --version 2>&1 | head -1
    fetch "$MODEL_URL" "$MODEL" "$MODEL_SHA256"
    echo "Model ready: $(basename "$MODEL") (Apache-2.0)"
    stop_llama
    mkdir -p "$(dirname "$LLAMA_LOG")" "$HOME/Library/LaunchAgents"
    : > "$LLAMA_LOG"
    "$PY" -I - "$LLAMA_PLIST" "$LLAMA_LABEL" "$LLAMA_SERVER" "$MODEL" "$(sysctl -n hw.physicalcpu)" "$LLAMA_LOG" <<'PYEOF'
import plistlib, sys
plist, label, server, model, threads, log = sys.argv[1:7]
# -c 8192 explicit (SPEC §4.9); localhost only; no web UI; thinking off
args = [server, "-m", model, "-c", "8192", "-t", threads, "-np", "1", "--host", "127.0.0.1", "--port", "8080",
        "--no-webui", "--reasoning-budget", "0"]
with open(plist, "wb") as f:
    plistlib.dump({"Label": label, "ProgramArguments": args, "RunAtLoad": True, "KeepAlive": True,
                   "StandardOutPath": log, "StandardErrorPath": log}, f)
PYEOF
    launchctl bootstrap "$DOMAIN" "$LLAMA_PLIST"
    for i in $(seq 1 60); do curl -fs "$AI_URL/health" >/dev/null 2>&1 && break; sleep 1; done
    curl -fs "$AI_URL/health" >/dev/null 2>&1 && echo "llama-server running on $AI_URL" || { echo "llama-server did not start - see $LLAMA_LOG"; exit 1; }
    ;;
smartrule)
    # Phase 2 T1: DT3 reads external scripts only at start, so install while DT3 is not running
    if pgrep -x "DEVONthink 3" >/dev/null; then echo "Please quit DEVONthink 3 first (Cmd+Q), then run this again."; exit 1; fi
    dir="$HOME/Library/Application Scripts/com.devon-technologies.think3/Smart Rules"
    mkdir -p "$dir" "$DATA/spool"
    chmod 700 "$DATA" "$DATA/spool"
    osacompile -o "$dir/DT3 Agent Enqueue.scpt" dt3-scripts/SmartRule-Enqueue.applescript
    echo "Installed: Smart Rules/DT3 Agent Enqueue.scpt - now start DEVONthink 3"
    ;;
testconfig)
    # Phase 3 floor gate: test settings without editing JSON by hand. The groups must exist in the TEST database.
    name=${2:-}
    [ -n "$name" ] || { echo 'usage: tools/dev-agent.sh testconfig "Your Name"'; exit 2; }
    "$PY" -I - "$REPO/engine" "$DATA" "$name" <<'PYEOF'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from dt3agent import config
path = Path(sys.argv[2]) / "config.json"
cfg = config.load(path)
cfg["identity"]["name"] = sys.argv[3]
cfg["filing"] = {"enabled": True, "groups": {"invoice": "/Finanzen/Rechnungen/"}, "review_group": "/_AI-Review/"}
cfg["duplicates"]["group"] = "/_Duplicates/"
cfg["cases"] = [{"name": "Fall Muster", "group": "/Recht/Fall-Muster/", "words": ["Muster Treuhand AG"]}]
# a config saved by an older kit keeps its old urgent words; the test uses the current defaults
cfg["keywords"]["urgent"] = list(config.DEFAULTS["keywords"]["urgent"])
config.save(path, cfg)
print("Test settings saved. In the TEST database create these groups (a / means: one group inside the other,")
print("never a / in a group name): Finanzen > Rechnungen,  Recht > Fall-Muster,  _AI-Review,  _Duplicates,  _Urgent")
PYEOF
    # floor 2026-11-05: a running engine keeps its old settings in memory and 'live on' wrote them back.
    # Restart it so it reads the new file.
    if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
        launchctl kickstart -k "$DOMAIN/$LABEL"
        for _ in $(seq 1 60); do
            "$REPO/tools/dt3agent" status >/dev/null 2>&1 && break
            sleep 1
        done
        echo "Engine restarted with the new settings."
    fi
    ;;
install)
    mode=${2:-osakit}
    uuid=${3:-}
    check=${4:-read}   # read: read the record · tag: add DT3Agent-Test, wait 20 s, undo, verify (T6)
                       # no record ID: run the engine service (T9)
    uuid=${uuid#x-devonthink-item://}   # accept the full link from Edit > Copy Item Link
    uuid=${uuid%%\?*}
    if [ -n "$uuid" ] && ! echo "$uuid" | grep -Eq '^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$'; then
        echo "Not a DEVONthink record ID: $uuid (copy it with Edit > Copy Item Link)"; exit 2
    fi
    case "$check" in read|tag) ;; *) echo "Last argument must be read or tag"; exit 2;; esac
    [ "$check" = tag ] && [ -z "$uuid" ] && { echo "tag needs a record ID"; exit 2; }
    [ -x "$PY" ] || { echo "Python not found at $PY - run: tools/dev-agent.sh python"; exit 1; }
    stop
    tools/build-swift.sh build
    tccutil reset AppleEvents codes.modular.dt3agent.engine 2>/dev/null || true   # this app only
    mkdir -p "$(dirname "$LOG")" "$HOME/Library/LaunchAgents"
    : > "$LOG"
    # Service mode needs the AI address; set it once if the config has none (dry-run stays on by default)
    "$PY" -I - "$REPO/engine" "$DATA" "$AI_URL" "$APP/Contents/MacOS/dt3agent-vision" <<'PYEOF'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from dt3agent import config
path = Path(sys.argv[2]) / "config.json"
cfg = config.load(path)
if not cfg["ai"]["url"]:
    cfg["ai"]["url"] = sys.argv[3]
cfg["vision"]["helper"] = sys.argv[4]   # the helper inside this build of the app
config.save(path, cfg)
PYEOF
    "$PY" -I - "$PLIST" "$LABEL" "$APP/Contents/MacOS/DT3AgentEngine" "$PY" "$REPO/engine" "$mode" "$LOG" "$uuid" "$check" <<'PYEOF'
import plistlib, sys
plist, label, host, py, engine, mode, log, uuid, check = sys.argv[1:10]
flag = "--tag-undo" if check == "tag" else "--read"
args = [host, "--python", py, "--engine-dir", engine, "--mode", mode, "--"] + ([flag, uuid] if uuid else [])
with open(plist, "wb") as f:
    plistlib.dump({"Label": label, "ProgramArguments": args, "RunAtLoad": True, "KeepAlive": True,
                   "StandardOutPath": log, "StandardErrorPath": log}, f)
PYEOF
    launchctl bootstrap "$DOMAIN" "$PLIST"
    what="service"; [ -n "$uuid" ] && what="$check test"
    if [ -z "$uuid" ]; then  # floor 2026-11-05: 'install && live on' raced the engine start; wait until it answers
        for _ in $(seq 1 60); do
            "$REPO/tools/dt3agent" status >/dev/null 2>&1 && break
            sleep 1
        done
        "$REPO/tools/dt3agent" status >/dev/null 2>&1 || echo "Engine not answering yet - run: tools/dev-agent.sh status"
    fi
    echo "Started ($mode, $what). If macOS asks to allow \"DT3 Agent Engine\" to control DEVONthink 3: click OK."
    echo "Then: tools/dev-agent.sh status   and take a screenshot of System Preferences > Security & Privacy > Privacy > Automation"
    ;;
embed)
    # K-1 (ADR-0011): embedding model (639 MB, Apache-2.0) + second llama-server on 8081, then a probe:
    # two sentences with the same meaning (de/fr) must be closer than an unrelated one.
    [ -x "$LLAMA_SERVER" ] || { echo "llama-server not built - run: tools/dev-agent.sh llama"; exit 1; }
    [ -x "$PY" ] || { echo "Python not found at $PY - run: tools/dev-agent.sh python"; exit 1; }
    fetch "$EMBED_URL_MODEL" "$EMBED_MODEL" "$EMBED_SHA256"
    echo "Model ready: $(basename "$EMBED_MODEL") (Apache-2.0)"
    stop_embed
    mkdir -p "$(dirname "$EMBED_LOG")" "$HOME/Library/LaunchAgents"
    : > "$EMBED_LOG"
    "$PY" -I - "$EMBED_PLIST" "$EMBED_LABEL" "$LLAMA_SERVER" "$EMBED_MODEL" "$(sysctl -n hw.physicalcpu)" "$EMBED_LOG" <<'PYEOF'
import plistlib, sys
plist, label, server, model, threads, log = sys.argv[1:7]
# model card: --embedding --pooling last; -ub = -b so a whole chunk fits one batch; localhost only
args = [server, "-m", model, "--embedding", "--pooling", "last", "-c", "8192", "-b", "8192", "-ub", "8192",
        "-t", threads, "-np", "1", "--host", "127.0.0.1", "--port", "8081", "--no-webui"]
with open(plist, "wb") as f:
    plistlib.dump({"Label": label, "ProgramArguments": args, "RunAtLoad": True, "KeepAlive": True,
                   "StandardOutPath": log, "StandardErrorPath": log}, f)
PYEOF
    launchctl bootstrap "$DOMAIN" "$EMBED_PLIST"
    for _ in $(seq 1 90); do curl -fs "$EMBED_URL/health" >/dev/null 2>&1 && break; sleep 1; done
    curl -fs "$EMBED_URL/health" >/dev/null 2>&1 || { echo "Embedding server did not start - see $EMBED_LOG"; tail -5 "$EMBED_LOG"; exit 1; }
    echo "Embedding server running on $EMBED_URL"
    "$PY" -I - "$REPO/engine" "$EMBED_URL" "$DATA" <<'PYEOF'
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from dt3agent import config
from dt3agent.embed import EmbedClient, EmbedError
c = EmbedClient(sys.argv[2])
texts = ["Die Rechnung ist innert 30 Tagen zu bezahlen.", "La facture est payable dans les 30 jours.",
         "Der Hund schläft im Garten."]
t0 = time.monotonic()
try:
    a, b, other = c.embed(texts)
except EmbedError as e:
    sys.exit(f"Probe failed: {e.code}")
dt = time.monotonic() - t0
same, diff = sum(x * y for x, y in zip(a, b)), sum(x * y for x, y in zip(a, other))
print(f"Probe: {len(a)} dimensions, 3 sentences in {dt:.1f} s")
print(f"  same meaning (de/fr): {same:.2f}   unrelated: {diff:.2f}   -> {'OK' if same > diff + 0.1 else 'CHECK'}")
path = Path(sys.argv[3]) / "config.json"
cfg = config.load(path)
cfg["ai"]["embed_url"] = sys.argv[2]
config.save(path, cfg)
print("Saved ai.embed_url in config.json")
PYEOF
    ;;
bundle)
    # Phase 5: the menu-bar app with Python and llama-server inside (as a release will have them), copied to
    # ~/Applications. The app's installer then sets up the real LaunchAgents. Stops the dev agents first.
    PYDIR=$(dirname "$(dirname "$PY")")
    [ -x "$PY" ] || { echo "Python not found at $PY - run: tools/dev-agent.sh python"; exit 1; }
    [ -x "$LLAMA_SERVER" ] || { echo "llama-server not built - run: tools/dev-agent.sh llama"; exit 1; }
    stop
    stop_llama
    for label in codes.modular.dt3agent.engine codes.modular.dt3agent.llama; do   # an older installed build
        launchctl bootout "$DOMAIN/$label" 2>/dev/null || true
    done
    DT3A_BUNDLE_PYTHON="$PYDIR" DT3A_BUNDLE_LLAMA="$LLAMA_SERVER" tools/build-swift.sh build
    [ -f "build/DT3 Agent.app/Contents/Resources/DT3 Agent Enqueue.scpt" ] || echo "Warning: Smart Rule script missing (is DT3 in /Applications?)"
    # floor 2026-11-05: replacing the app while it runs made 'open' fail (kLSNoExecutableErr); quit it first
    pkill -x DT3Agent 2>/dev/null && sleep 2 || true
    mkdir -p "$HOME/Applications"
    rm -rf "$HOME/Applications/DT3 Agent.app"
    ditto "build/DT3 Agent.app" "$HOME/Applications/DT3 Agent.app"
    # floor 2026-11-05: 'open' right after replacing the app failed with kLSNoExecutableErr even with the old
    # app quit: LaunchServices still knew the old copy. Register the new one before anyone opens it.
    LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
    [ -x "$LSREGISTER" ] && "$LSREGISTER" -f "$HOME/Applications/DT3 Agent.app" || true
    echo "Built: ~/Applications/DT3 Agent.app ($(du -sh "$HOME/Applications/DT3 Agent.app" | cut -f1))"
    ;;
app)
    # U-1: the menu-bar app; built by install (tools/build-swift.sh). Quit it from its own menu.
    [ -d "$REPO/build/DT3 Agent.app" ] || { echo "Run tools/dev-agent.sh install first"; exit 1; }
    open "$REPO/build/DT3 Agent.app"
    echo "DT3 Agent is in the menu bar (top right)."
    ;;
status)
    launchctl print "$DOMAIN/$LABEL" 2>/dev/null | grep -E '^[[:space:]]*(state|pid|runs|last exit code) =' || echo "not loaded"
    launchctl print "$DOMAIN/$LLAMA_LABEL" >/dev/null 2>&1 && echo "llama-server: $(curl -fs "$AI_URL/health" || echo 'not answering')"
    launchctl print "$DOMAIN/$EMBED_LABEL" >/dev/null 2>&1 && echo "embedding server: $(curl -fs "$EMBED_URL/health" || echo 'not answering')"
    tail -20 "$LOG" 2>/dev/null || true
    ;;
uninstall)
    stop
    stop_llama
    stop_embed
    echo "LaunchAgents removed. Logs kept in: $(dirname "$LOG"). Data kept in: $DATA"
    ;;
*)
    echo "usage: tools/dev-agent.sh python | llama | smartrule | testconfig NAME | install [osakit|osascript] [record-UUID] [read|tag] | embed | bundle | app | status | uninstall"
    exit 2
    ;;
esac
