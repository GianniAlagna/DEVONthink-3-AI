# S0 - inventory of the floor machine. Read-only.
. "$(dirname "$0")/lib.sh"

log "== S0 inventory"
run sw_vers
run uname -m
for k in machdep.cpu.brand_string hw.memsize hw.physicalcpu hw.logicalcpu; do
    printf '%-26s %s\n' "$k" "$(sysctl -n $k)"
done
log "CPU features relevant for llama.cpp (want AVX1.0 AVX2 FMA F16C):"
sysctl -n machdep.cpu.features machdep.cpu.leaf7_features | tr ' ' '\n' | grep -xE 'AVX1.0|AVX2|FMA|F16C|BMI2' | sort -u | tr '\n' ' '; echo
run xcodebuild -version
run swift --version
run xcrun --show-sdk-version
run git --version
curl --version | head -1
log "DEVONthink apps installed:"
ls -d /Applications/DEVONthink*.app 2>/dev/null
run mdls -name kMDItemVersion -name kMDItemCFBundleIdentifier "/Applications/DEVONthink 3.app"
run df -h "$HOME"
pmset -g batt | head -2
log "== S0 done"
