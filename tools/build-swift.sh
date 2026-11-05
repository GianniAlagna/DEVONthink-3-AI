#!/bin/bash
# Builds "DT3 Agent Engine.app" (engine host + Vision helper) as a universal (x86_64 + arm64) app for macOS 11 (ADR-0008).
# Usage: tools/build-swift.sh [out-dir] [signing identity]   (identity "-" = ad-hoc, see ADR-0010)
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${1:-build}
IDENTITY=${2:--}
APP="$OUT/DT3 Agent Engine.app"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
for arch in x86_64 arm64; do
    xcrun swiftc -O -target "$arch-apple-macos11.0" app/EngineHost/main.swift -o "$OUT/DT3AgentEngine-$arch"
done
lipo -create "$OUT/DT3AgentEngine-x86_64" "$OUT/DT3AgentEngine-arm64" -output "$APP/Contents/MacOS/DT3AgentEngine"
# Vision helper (ADR-0006) inside the app, signed with it
for arch in x86_64 arm64; do
    xcrun swiftc -O -target "$arch-apple-macos11.0" app/Vision/main.swift -o "$OUT/dt3agent-vision-$arch"
done
lipo -create "$OUT/dt3agent-vision-x86_64" "$OUT/dt3agent-vision-arm64" -output "$APP/Contents/MacOS/dt3agent-vision"
codesign --force --sign "$IDENTITY" --timestamp=none "$APP/Contents/MacOS/dt3agent-vision"
cp app/EngineHost/Info.plist "$APP/Contents/Info.plist"
plutil -lint "$APP/Contents/Info.plist"
codesign --force --sign "$IDENTITY" --timestamp=none "$APP"
lipo -info "$APP/Contents/MacOS/DT3AgentEngine"
codesign -d -r- "$APP" 2>&1 | tail -1

# Menu-bar app "DT3 Agent.app" (U-1): app logic tests first (host architecture), then the universal app
CORE="app/Agent/Core.swift app/Agent/L10n.swift app/Agent/RPC.swift app/Agent/Setup.swift app/Agent/Settings.swift app/Agent/Review.swift app/Agent/Install.swift app/Agent/Knowledge.swift"
# shellcheck disable=SC2086
xcrun swiftc -O -target "$(uname -m)-apple-macos11.0" $CORE app/Tests/main.swift -o "$OUT/dt3agent-app-tests"
"$OUT/dt3agent-app-tests"
UI="$OUT/DT3 Agent.app"
rm -rf "$UI"
mkdir -p "$UI/Contents/MacOS"
for arch in x86_64 arm64; do
    # shellcheck disable=SC2086
    xcrun swiftc -O -target "$arch-apple-macos11.0" $CORE app/Agent/Onboarding.swift app/Agent/SettingsWindow.swift app/Agent/ReviewWindow.swift app/Agent/InstallerWindow.swift app/Agent/KnowledgeWindow.swift app/Agent/main.swift -o "$OUT/DT3Agent-$arch"
done
lipo -create "$OUT/DT3Agent-x86_64" "$OUT/DT3Agent-arm64" -output "$UI/Contents/MacOS/DT3Agent"
cp app/Agent/Info.plist "$UI/Contents/Info.plist"
# U-5: everything the installer needs, inside the app. Python and llama-server are added for a release (Phase 8)
# or for a floor test: DT3A_BUNDLE_PYTHON=<python dir> DT3A_BUNDLE_LLAMA=<llama-server binary>.
mkdir -p "$UI/Contents/Helpers" "$UI/Contents/Resources/engine"
ditto "$APP" "$UI/Contents/Helpers/DT3 Agent Engine.app"
rsync -a --exclude __pycache__ --exclude tests engine/dt3agent "$UI/Contents/Resources/engine/"
# osacompile needs the DT3 dictionary, so the Smart Rule script is only compiled where DT3 is installed
# (the floor/release Mac). CI has no DT3; the installer then skips the script step.
if [ -d "/Applications/DEVONthink 3.app" ]; then
    osacompile -o "$UI/Contents/Resources/DT3 Agent Enqueue.scpt" dt3-scripts/SmartRule-Enqueue.applescript
else
    echo "note: DEVONthink 3 not installed here; Smart Rule script not bundled"
fi
if [ -n "${DT3A_BUNDLE_PYTHON:-}" ]; then ditto "$DT3A_BUNDLE_PYTHON" "$UI/Contents/Resources/python"; fi
if [ -n "${DT3A_BUNDLE_LLAMA:-}" ]; then
    mkdir -p "$UI/Contents/Resources/llama"
    cp "$DT3A_BUNDLE_LLAMA" "$UI/Contents/Resources/llama/llama-server"
fi
plutil -lint "$UI/Contents/Info.plist"
codesign --force --sign "$IDENTITY" --timestamp=none "$UI"
lipo -info "$UI/Contents/MacOS/DT3Agent"
