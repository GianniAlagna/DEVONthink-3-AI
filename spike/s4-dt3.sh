# S4 - DEVONthink 3.9 scripting surface.
# Usage: bash spike/run.sh s4 "DT3Agent-Spike" ["DT3Agent-Spike-2"]   probes + installs the Smart Rule / Menu probes
#        bash spike/run.sh s4 check                                    after you triggered the Smart Rule / Menu script
. "$(dirname "$0")/lib.sh"
need_py

SCRIPTS_BASE="$HOME/Library/Application Scripts/$( /usr/libexec/PlistBuddy -c 'Print CFBundleIdentifier' '/Applications/DEVONthink 3.app/Contents/Info.plist' )"
PROBE="$SPIKE_DIR/dt3/probe.js"

if [ "${1:-}" = "check" ]; then
    log "== S4 check: files written by the Smart Rule / Menu probes"
    ls -l "$WORK/smartrule" 2>/dev/null || log "none yet"
    for f in "$WORK"/smartrule/*.json; do [ -f "$f" ] && cat "$f" && echo; done
    exit 0
fi

db=${1:-}
db2=${2:-}
[ -n "$db" ] || { log "usage: bash spike/run.sh s4 \"<Spike database name>\" [\"<second Spike database>\"]"; exit 2; }

log "== S4 DT3 scripting surface"
log "-- dictionary (kept local in $WORK/dt3.sdef, not committed)"
sdef "/Applications/DEVONthink 3.app" > "$WORK/dt3.sdef"
log "commands:";   grep -oE '<command name="[^"]+"' "$WORK/dt3.sdef" | cut -d'"' -f2 | sort -u | tr '\n' ',' ; echo
log "classes:";    grep -oE '<class name="[^"]+"' "$WORK/dt3.sdef" | cut -d'"' -f2 | sort -u | tr '\n' ',' ; echo
log "record properties:"
awk '/<class name="record"/{f=1} f&&/<\/class>/{exit} f' "$WORK/dt3.sdef" | grep -oE '<property name="[^"]+"' | cut -d'"' -f2 | tr '\n' ','; echo
log "reminder class:"
awk '/<class name="reminder"/{f=1} f&&/<\/class>/{exit} f' "$WORK/dt3.sdef" | grep -oE '<property name="[^"]+"' | cut -d'"' -f2 | tr '\n' ','; echo
for c in "replicate" "duplicate" "create record with" "add custom meta data" "ocr" "convert image"; do
    log "command '$c' parameters:"
    awk -v c="$c" '$0 ~ "<command name=\""c"\""{f=1} f&&/<\/command>/{exit} f' "$WORK/dt3.sdef" | grep -oE '<(parameter|direct-parameter|result)[^>]*>' | sed -E 's/description="[^"]*"//'
done

log "-- info"
run osascript -l JavaScript "$PROBE" info

log "-- selftest in '$db' (writes only into /_spike/<timestamp>, never deletes)"
run osascript -l JavaScript "$PROBE" selftest "$db" "$FIXTURES" ${db2:+"$db2"}

log "-- AppleEvent round trip latency (10 runs, warm)"
"$PY" -I - "$PROBE" <<'EOF'
import subprocess, sys, time, statistics
probe = sys.argv[1]
times = []
for _ in range(10):
    t0 = time.monotonic()
    subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", probe, "info"], capture_output=True, timeout=60)
    times.append((time.monotonic() - t0) * 1000)
print("osascript info: median %.0f ms, min %.0f, max %.0f" % (statistics.median(times), min(times), max(times)))
EOF

log "-- install Smart Rule + Menu probes"
for sub in "Smart Rules" "Menu"; do
    [ -d "$SCRIPTS_BASE/$sub" ] && log "exists before: $SCRIPTS_BASE/$sub" || log "did NOT exist: $SCRIPTS_BASE/$sub (created now)"
    mkdir -p "$SCRIPTS_BASE/$sub"
done
run osacompile -l JavaScript -o "$SCRIPTS_BASE/Smart Rules/DT3Agent Spike Enqueue.scpt" "$SPIKE_DIR/dt3/SmartRule-Enqueue.js"
run osacompile -l JavaScript -o "$SCRIPTS_BASE/Menu/DT3Agent Spike Enqueue.scpt" "$SPIKE_DIR/dt3/Menu-Enqueue.js"
cat <<'EOT'

NEXT (manual, 3 minutes - see spike/README.md step S4):
 1. In DT3, in the Spike database: Tools > New Smart Rule.
    Search in: the Spike database. Condition: Kind is Any Document. Trigger: On Demand.
    Action: Execute Script > External > "DT3Agent Spike Enqueue". Save.
 2. Select 2-3 records in the Spike database, right-click > Apply Rules > your rule.
 3. Select 2 records, then the Scripts menu (scroll icon) > "DT3Agent Spike Enqueue".
 4. Run: bash spike/run.sh s4 check
EOT
log "== S4 done"
