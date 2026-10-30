# S5 - Automation permission (TCC) when a background LaunchAgent sends AppleEvents to DT3.
# Approved by Gianni (2026-10-30): resetting AppleEvents permissions on the floor machine.
# Usage: bash spike/run.sh s5          reset, start agent with DT3 probe, watch what macOS asks
#        bash spike/run.sh s5 again    restart agent only (does the grant persist?)
. "$(dirname "$0")/lib.sh"
need_py

LABEL="codes.modular.dt3agent.spike.engine"
log "== S5 TCC / Automation from a LaunchAgent"
if [ "${1:-}" != "again" ]; then
    printf 'This resets Automation permissions for ALL apps on this Mac (they ask again on next use). Continue? [y/N] '
    read -r answer
    [ "$answer" = "y" ] || { log "aborted"; exit 1; }
    run tccutil reset AppleEvents
fi
: > "$WORK/agent.log"
run /bin/bash "$SPIKE_DIR/s7-launchd.sh" probe > "$WORK/s5-s7.log" 2>&1
log "Agent started. WATCH THE SCREEN NOW: a dialog '... wants access to control DEVONthink 3' may appear."
log "Write down WHICH app name the dialog shows, click OK, take a screenshot (Cmd+Shift+4)."
log "Waiting 90 s for the probe result ..."
sleep 90
log "-- agent log"
grep -E 'start|dt3 probe' "$WORK/agent.log"
log "-- TCC decisions in the unified log (last 5 min)"
log show --last 5m --style compact --predicate 'subsystem == "com.apple.TCC" AND eventMessage CONTAINS[c] "AppleEvents"' 2>/dev/null | tail -25
cat <<'EOT'

NEXT (manual):
 1. Open System Preferences > Security & Privacy > Privacy > Automation.
    Screenshot the entry that now controls "DEVONthink 3" (which app/binary is listed?).
 2. Run again without reset to test persistence:   bash spike/run.sh s5 again
 3. After a restart of the Mac, run once more:      bash spike/run.sh s5 again
EOT
log "== S5 done"
