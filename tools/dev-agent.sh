#!/bin/bash
# Floor test for Phase 2 T5: run the engine host as a LaunchAgent and check whose name the Automation
# permission carries. Developer tool, not the installer (that is Phase 5).
# Usage: tools/dev-agent.sh install [osakit|osascript] [record-UUID] | status | uninstall
set -euo pipefail
cd "$(dirname "$0")/.."
REPO=$(pwd)
LABEL="codes.modular.dt3agent.engine.dev"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/DT3 Agent/engine-dev.log"
PY="${DT3A_PYTHON:-$HOME/dt3agent-spike/python/bin/python3}"   # bundled runtime from the Phase 0 kit
APP="$REPO/build/DT3 Agent Engine.app"
DOMAIN="gui/$(id -u)"

stop() { launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true; rm -f "$PLIST"; }

case "${1:-}" in
install)
    mode=${2:-osakit}
    uuid=${3:-}
    [ -x "$PY" ] || { echo "Python not found at $PY (set DT3A_PYTHON)"; exit 1; }
    stop
    tools/build-swift.sh build
    tccutil reset AppleEvents codes.modular.dt3agent.engine 2>/dev/null || true   # this app only
    mkdir -p "$(dirname "$LOG")" "$HOME/Library/LaunchAgents"
    : > "$LOG"
    "$PY" -I - "$PLIST" "$LABEL" "$APP/Contents/MacOS/DT3AgentEngine" "$PY" "$REPO/engine" "$mode" "$LOG" "$uuid" <<'PYEOF'
import plistlib, sys
plist, label, host, py, engine, mode, log, uuid = sys.argv[1:9]
args = [host, "--python", py, "--engine-dir", engine, "--mode", mode, "--"] + (["--read", uuid] if uuid else [])
with open(plist, "wb") as f:
    plistlib.dump({"Label": label, "ProgramArguments": args, "RunAtLoad": True, "KeepAlive": True,
                   "StandardOutPath": log, "StandardErrorPath": log}, f)
PYEOF
    launchctl bootstrap "$DOMAIN" "$PLIST"
    echo "Started ($mode). If macOS asks to allow \"DT3 Agent Engine\" to control DEVONthink 3: click OK."
    echo "Then: tools/dev-agent.sh status   and take a screenshot of System Preferences > Security & Privacy > Privacy > Automation"
    ;;
status)
    launchctl print "$DOMAIN/$LABEL" 2>/dev/null | grep -E '^[[:space:]]*(state|pid|runs|last exit code) =' || echo "not loaded"
    tail -20 "$LOG" 2>/dev/null || true
    ;;
uninstall)
    stop
    echo "LaunchAgent removed. Log kept at: $LOG"
    ;;
*)
    echo "usage: tools/dev-agent.sh install [osakit|osascript] [record-UUID] | status | uninstall"
    exit 2
    ;;
esac
