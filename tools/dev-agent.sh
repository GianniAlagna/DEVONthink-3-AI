#!/bin/bash
# Floor test for Phase 2 T5: run the engine host as a LaunchAgent and check whose name the Automation
# permission carries. Developer tool, not the installer (that is Phase 5).
# Usage: tools/dev-agent.sh python | install [osakit|osascript] [record-UUID] | status | uninstall
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
DOMAIN="gui/$(id -u)"

stop() { launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true; rm -f "$PLIST"; }

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
install)
    mode=${2:-osakit}
    uuid=${3:-}
    uuid=${uuid#x-devonthink-item://}   # accept the full link from Edit > Copy Item Link
    uuid=${uuid%%\?*}
    if [ -n "$uuid" ] && ! echo "$uuid" | grep -Eq '^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$'; then
        echo "Not a DEVONthink record ID: $uuid (copy it with Edit > Copy Item Link)"; exit 2
    fi
    [ -x "$PY" ] || { echo "Python not found at $PY - run: tools/dev-agent.sh python"; exit 1; }
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
    echo "usage: tools/dev-agent.sh python | install [osakit|osascript] [record-UUID] | status | uninstall"
    exit 2
    ;;
esac
