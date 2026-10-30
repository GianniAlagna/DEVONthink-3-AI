# Shared helpers for the Phase 0 spike scripts. macOS /bin/bash is 3.2: no bash 4 features.
set -u

SPIKE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SPIKE_DIR")"
FIXTURES="$REPO_DIR/fixtures/spike"
WORK="${DT3A_SPIKE_WORK:-$HOME/dt3agent-spike}"   # downloads, builds, models (outside the repo)
OUT="$SPIKE_DIR/out"                              # logs that go back to Claude
mkdir -p "$WORK" "$OUT"

# Pinned versions (verified 2026-10-30 against the official sources)
PY_TAG="20261026"
PY_VER="3.12.16"
CMAKE_VER="3.31.12"
CMAKE_SHA256="cf096d869d45b79f5ce82f3d6abffa44f983fc146fee13cfe59024911e6975af"   # cmake.org SHA-256 list
LLAMA_TAGS="b12015 b11000 b10000 b9000 b6000"                                       # newest first; first that builds wins

PY="$WORK/python/bin/python3"
CMAKE="$WORK/cmake-$CMAKE_VER-macos10.10-universal/CMake.app/Contents/bin/cmake"
LLAMA_BIN="$WORK/llama.cpp/build/bin"

log() { printf '%s  %s\n' "$(date -u +%H:%M:%S)" "$*"; }

# run CMD...  prints the command, runs it, prints the exit code; never aborts the step
run() {
    log "\$ $*"
    "$@"
    local rc=$?
    log "rc=$rc"
    return $rc
}

# fetch URL DEST [SHA256]  download once; verify the hash when one is given (fail closed)
fetch() {
    local url=$1 dest=$2 want=${3:-}
    if [ ! -s "$dest" ]; then
        log "download $url"
        curl -fL --retry 3 --progress-bar -o "$dest.part" "$url" || { log "DOWNLOAD FAILED: $url"; rm -f "$dest.part"; return 1; }
        mv "$dest.part" "$dest"
    fi
    local got
    got=$(shasum -a 256 "$dest" | awk '{print $1}')
    log "sha256 $got  $(basename "$dest")"
    if [ -n "$want" ] && [ "$got" != "$want" ]; then
        log "SHA256 MISMATCH (want $want) - file removed"
        rm -f "$dest"
        return 1
    fi
}

# minos FILE  prints the minimum macOS version a Mach-O binary was built for
minos() {
    otool -l "$1" | awk '/LC_BUILD_VERSION/{f=1} f&&/minos/{print "minos " $2; exit} /LC_VERSION_MIN_MACOSX/{g=1} g&&/version/{print "minos " $2; exit}'
}

need_py() {
    [ -x "$PY" ] || { log "Bundled Python missing: run bash spike/run.sh s1 first"; exit 1; }
}
