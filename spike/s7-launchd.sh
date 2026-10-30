# S7 - LaunchAgent install / restart / uninstall + Unix socket checks.
# Usage: ./spike/run.sh s7            install, test, keep running
#        ./spike/run.sh s7 probe      same, and the agent also sends one AppleEvent to DT3 at start (used by S5)
#        ./spike/run.sh s7 uninstall  stop and remove the LaunchAgent
# Label is neutral on purpose (bundle ID prefix not decided yet, Q9).
. "$(dirname "$0")/lib.sh"
need_py

LABEL="spike.dt3agent.engine"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
SOCK="$HOME/Library/Application Support/DT3 Agent Spike/engine.sock"
DOMAIN="gui/$(id -u)"

uninstall() {
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null && log "booted out" || log "was not loaded"
    rm -f "$PLIST"
}

if [ "${1:-}" = "uninstall" ]; then
    log "== S7 uninstall"; uninstall; log "== done"; exit 0
fi

probe_arg=""
[ "${1:-}" = "probe" ] && probe_arg="$SPIKE_DIR/dt3/probe.js"
log "== S7 LaunchAgent (DT3 probe at start: ${probe_arg:-no})"
uninstall
mkdir -p "$HOME/Library/LaunchAgents"
# Plist written by plistlib: no string building, paths with spaces stay intact.
"$PY" -I - "$PLIST" "$LABEL" "$PY" "$SPIKE_DIR/s7_agent.py" "$SOCK" "$WORK/agent.log" "$probe_arg" <<'EOF'
import plistlib, sys
plist, label, py, agent, sock, logf, probe = sys.argv[1:8]
args = [py, "-I", agent, "--sock", sock] + (["--probe-js", probe] if probe else [])
with open(plist, "wb") as f:
    plistlib.dump({
        "Label": label,
        "ProgramArguments": args,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": logf,
        "StandardErrorPath": logf,
    }, f)
EOF
run plutil -lint "$PLIST"
run launchctl bootstrap "$DOMAIN" "$PLIST"
sleep 5
launchctl print "$DOMAIN/$LABEL" | grep -E '^[[:space:]]*(state|pid|program|last exit code) ='
pid=$(launchctl print "$DOMAIN/$LABEL" | awk '/^\tpid =/{print $3}')
log "-- socket checks"
run "$PY" -I "$SPIKE_DIR/s7_client.py" "$SOCK"

log "-- KeepAlive: kill pid $pid, launchd should restart it (throttle ~10 s)"
kill -9 "$pid"
sleep 15
launchctl print "$DOMAIN/$LABEL" | grep -E '^[[:space:]]*(state|pid|runs|last exit code) ='
run "$PY" -I "$SPIKE_DIR/s7_client.py" "$SOCK"

log "-- agent log (last 20 lines)"
tail -20 "$WORK/agent.log"
log "== S7 done. The agent keeps running. After your next logout/login, check it came back:"
echo "   launchctl print $DOMAIN/$LABEL | grep -E 'state|pid'"
