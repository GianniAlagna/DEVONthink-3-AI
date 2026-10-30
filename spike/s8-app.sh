# S8 - menu-bar app toolchain test + "does the Automation permission survive an update?"
# Gianni has no Apple Developer ID (Q7), so releases can only be ad-hoc or self-signed. TCC ties a permission
# to the code signature; this step measures what happens after a rebuild for both signing modes.
# Usage: bash spike/run.sh s8 1                          build 1, ad-hoc signed
#        bash spike/run.sh s8 2                          build 2, ad-hoc signed (simulated update)
#        bash spike/run.sh s8 1 "DT3 Agent Spike Signing" build 1, self-signed certificate (optional, see README)
#        bash spike/run.sh s8 2 "DT3 Agent Spike Signing" build 2, self-signed certificate
. "$(dirname "$0")/lib.sh"
need_py
need_clt

build=${1:-1}
identity=${2:--}      # "-" = ad-hoc
BUNDLE_ID="codes.modular.dt3agent.spike.menu"
APP="$WORK/SpikeMenu.app"
log "== S8 app build $build, signing identity: $identity"

osascript -e 'tell application "SpikeMenu" to quit' >/dev/null 2>&1
[ "$build" = "1" ] && run tccutil reset AppleEvents "$BUNDLE_ID"   # clean start for each signing mode
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
for arch in x86_64 arm64; do
    run xcrun swiftc -O -target "$arch-apple-macos11.0" "$SPIKE_DIR/app/main.swift" -o "$WORK/SpikeMenu-$arch" || exit 1
done
run lipo -create "$WORK/SpikeMenu-x86_64" "$WORK/SpikeMenu-arm64" -output "$APP/Contents/MacOS/SpikeMenu"
run lipo -info "$APP/Contents/MacOS/SpikeMenu"

"$PY" -I - "$APP/Contents/Info.plist" "$BUNDLE_ID" "$build" <<'EOF'
import plistlib, sys
path, bundle_id, build = sys.argv[1:4]
with open(path, "wb") as f:
    plistlib.dump({
        "CFBundleIdentifier": bundle_id, "CFBundleName": "SpikeMenu", "CFBundleExecutable": "SpikeMenu",
        "CFBundlePackageType": "APPL", "CFBundleShortVersionString": "0.0." + build, "CFBundleVersion": build,
        "LSMinimumSystemVersion": "11.0", "LSUIElement": True,
        "NSAppleEventsUsageDescription": "Spike test: read the DEVONthink 3 version.",
    }, f)
EOF
run codesign --force --sign "$identity" --timestamp=none "$APP"
codesign -dv --verbose=4 "$APP" 2>&1 | grep -E 'Identifier|Signature|Authority|CDHash|TeamIdentifier'
run codesign -d -r- "$APP"
spctl -a -vv "$APP" 2>&1 | head -3     # Gatekeeper verdict (expected: rejected, not notarized)

run open "$APP"
next="bash spike/run.sh s8 2"
[ "$identity" != "-" ] && next="$next '$identity'"
cat <<EOT

NEXT (manual):
 1. Click the new menu-bar icon (magnifier on a page) > "Ask DEVONthink 3 for its version".
 2. Note: did macOS ask for permission? What does the popover show? Screenshot.
 3. Build $build done. If this was build 1, now run build 2 with the same signing and repeat 1-2:
      $next
    Expected evidence: after build 2, is the permission kept, asked again, or silently denied (-1743)?
EOT
log "== S8 build $build done"
