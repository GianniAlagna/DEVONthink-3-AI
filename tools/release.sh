#!/bin/bash
# R-3 release build (SPEC §4.23, ADR-0010): one DMG per architecture.
# Usage: tools/release.sh VERSION ARCH [IDENTITY]
#   VERSION   must equal the version in the engine and both Info.plists (set in the release PR)
#   ARCH      x86_64 (Intel) | arm64 (Apple Silicon)
#   IDENTITY  code-signing identity of the project's self-signed certificate; "-" (default) = ad-hoc,
#             and the DMG is named ...-NOT-FOR-RELEASE (floor tests only)
# Needs Xcode command line tools, cmake (or downloads the pinned one), git, network. Never bundles model weights.
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION=${1:?usage: tools/release.sh VERSION ARCH [IDENTITY]}
ARCH=${2:?usage: tools/release.sh VERSION ARCH [IDENTITY]}
IDENTITY=${3:--}
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-z0-9.]+)?$ ]] || { echo "bad version: $VERSION"; exit 2; }
case "$ARCH" in x86_64) PYARCH=x86_64; NAME=Intel;; arm64) PYARCH=aarch64; NAME=AppleSilicon;; *) echo "bad arch: $ARCH"; exit 2;; esac

# 1. the version is set in the release PR, never here
ENGINE_VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' engine/dt3agent/__init__.py)
for plist in app/Agent/Info.plist app/EngineHost/Info.plist; do
    v=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$plist")   # plutil raw needs macOS 12
    [ "$v" = "$VERSION" ] || { echo "$plist has $v, expected $VERSION"; exit 1; }
done
[ "$ENGINE_VERSION" = "$VERSION" ] || { echo "engine has $ENGINE_VERSION, expected $VERSION"; exit 1; }

WORK="build/release-$ARCH"
rm -rf "$WORK" && mkdir -p "$WORK"

# 2. Python runtime (ADR-0001), pinned release, checksum from the same release
PY_TAG="20261026"
PY_ASSET="cpython-3.12.16+${PY_TAG}-${PYARCH}-apple-darwin-install_only.tar.gz"
base="https://github.com/astral-sh/python-build-standalone/releases/download/$PY_TAG"
curl -fsSL -o "$WORK/SHA256SUMS" "$base/SHA256SUMS"
curl -fsSL -o "$WORK/$PY_ASSET" "$base/${PY_ASSET//+/%2B}"
want=$(awk -v a="$PY_ASSET" '$2==a{print $1}' "$WORK/SHA256SUMS")
got=$(shasum -a 256 "$WORK/$PY_ASSET" | awk '{print $1}')
[ -n "$want" ] && [ "$want" = "$got" ] || { echo "SHA-256 mismatch for $PY_ASSET"; exit 1; }
tar xzf "$WORK/$PY_ASSET" -C "$WORK"
rm -rf "$WORK/python/lib/python3.12/test"   # the engine needs the standard library, not its test suite

# 3. llama-server (ADR-0002), pinned tag. No CPU tuning to the build machine: a fixed instruction set
#    (x86_64: AVX2/FMA/F16C = Haswell, 2013 and later) so it runs on every supported Mac. UNVERIFIED on
#    pre-Haswell Intel Macs (they are told so in the guide's requirements).
LLAMA_TAG="b12015"
git clone -q --depth 1 --branch "$LLAMA_TAG" https://github.com/ggml-org/llama.cpp "$WORK/llama.cpp"
CPU_FLAGS=(-DGGML_NATIVE=OFF)
[ "$ARCH" = x86_64 ] && CPU_FLAGS+=(-DGGML_AVX=ON -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON)
CMAKE=$(command -v cmake || true)
if [ -z "$CMAKE" ]; then
    CMAKE_VER="3.31.12"; CMAKE_SHA256="cf096d869d45b79f5ce82f3d6abffa44f983fc146fee13cfe59024911e6975af"
    curl -fsSL -o "$WORK/cmake.tar.gz" "https://cmake.org/files/v3.31/cmake-$CMAKE_VER-macos10.10-universal.tar.gz"
    [ "$(shasum -a 256 "$WORK/cmake.tar.gz" | awk '{print $1}')" = "$CMAKE_SHA256" ] || { echo "cmake checksum"; exit 1; }
    tar xzf "$WORK/cmake.tar.gz" -C "$WORK"
    CMAKE="$WORK/cmake-$CMAKE_VER-macos10.10-universal/CMake.app/Contents/bin/cmake"
fi
"$CMAKE" -S "$WORK/llama.cpp" -B "$WORK/llama.cpp/build" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_OSX_ARCHITECTURES="$ARCH" -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0 -DBUILD_SHARED_LIBS=OFF "${CPU_FLAGS[@]}" \
    -DGGML_METAL=OFF -DGGML_ACCELERATE=OFF -DGGML_BLAS=OFF -DGGML_OPENMP=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_CURL=OFF \
    -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF >/dev/null
"$CMAKE" --build "$WORK/llama.cpp/build" -j "$(sysctl -n hw.ncpu)" --target llama-server >/dev/null
LLAMA="$WORK/llama.cpp/build/bin/llama-server"
lipo -info "$LLAMA" | grep -q "$ARCH" || { echo "llama-server is not $ARCH"; exit 1; }

# 4. the apps (universal Swift), with this architecture's Python and llama-server inside
DT3A_BUNDLE_PYTHON="$WORK/python" DT3A_BUNDLE_LLAMA="$LLAMA" tools/build-swift.sh "$WORK/out" "$IDENTITY"
APP="$WORK/out/DT3 Agent.app"
if find "$APP" -name '*.gguf' | grep -q .; then echo "model weights inside the app - stopped"; exit 1; fi

# 5. sign every Mach-O inside Resources (Python, its extensions, llama-server), then the app again
while IFS= read -r -d '' f; do
    if file -b "$f" | grep -q Mach-O; then codesign --force --sign "$IDENTITY" --timestamp=none "$f"; fi
done < <(find "$APP/Contents/Resources" -type f -print0)
codesign --force --sign "$IDENTITY" --timestamp=none "$APP"
codesign --verify --deep --strict "$APP"

# 6. DMG: app, Applications link, licence, first-launch note, checksum
SUFFIX=""; [ "$IDENTITY" = "-" ] && SUFFIX="-NOT-FOR-RELEASE"
DMG="build/DT3-Agent-$VERSION-$NAME$SUFFIX.dmg"
STAGE="$WORK/dmg"
mkdir -p "$STAGE"
ditto "$APP" "$STAGE/DT3 Agent.app"
ln -s /Applications "$STAGE/Applications"
cp LICENSE "$STAGE/LICENSE.txt"
cp tools/release/README-first-launch.txt "$STAGE/README-first-launch.txt"
rm -f "$DMG"
hdiutil create -quiet -volname "DT3 Agent $VERSION" -srcfolder "$STAGE" -format UDZO -ov "$DMG"
(cd build && shasum -a 256 "$(basename "$DMG")" > "$(basename "$DMG").sha256")
echo "Built: $DMG ($(du -h "$DMG" | cut -f1)) signed with: $IDENTITY"
