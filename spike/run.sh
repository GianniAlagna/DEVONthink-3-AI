#!/bin/bash
# Runs one spike step and saves its full output to spike/out/<step>-<time>.log
#   ./spike/run.sh s0          (steps: s0 s1 s2 s3 s4 s7 s5 s6 s8, in this order)
#   ./spike/run.sh collect     (zip all logs for Claude, see spike/README.md)
set -u
cd "$(dirname "$0")/.." || exit 1
step=${1:-}
shift || true
case "$step" in
    s0) script=s0-inventory.sh ;;
    s1) script=s1-python.sh ;;
    s2) script=s2-llama.sh ;;
    s3) script=s3-models.sh ;;
    s4) script=s4-dt3.sh ;;
    s5) script=s5-tcc.sh ;;
    s6) script=s6-vision.sh ;;
    s7) script=s7-launchd.sh ;;
    s8) script=s8-app.sh ;;
    collect) exec /bin/bash spike/collect.sh ;;
    *) echo "usage: ./spike/run.sh s0|s1|s2|s3|s4|s7|s5|s6|s8|collect [args]"; exit 2 ;;
esac
mkdir -p spike/out
logfile="spike/out/$step-$(date +%Y%m%d-%H%M%S).log"
echo "Logging to $logfile"
/bin/bash "spike/$script" "$@" 2>&1 | tee "$logfile"
echo "Done. Log: $logfile"
