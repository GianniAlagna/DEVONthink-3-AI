# S2 - build llama.cpp on the floor machine (Xcode 13.2, macOS 11, CPU only).
# Verified facts behind this script (llama.cpp b12015, .github/workflows/release.yml + CMake files):
#   - official macOS x64 release binaries target macOS 13.3 -> cannot run on macOS 11, so no prebuilt route
#   - GGML_ACCELERATE uses ACCELERATE_NEW_LAPACK (macOS 13.3 SDK) -> must be OFF with Xcode 13.2
# Usage: bash spike/run.sh s2 [TAG]   (default: try $LLAMA_TAGS newest first, stop at the first that builds)
. "$(dirname "$0")/lib.sh"

log "== S2 llama.cpp"
cd "$WORK" || exit 1
fetch "https://cmake.org/files/v3.31/cmake-$CMAKE_VER-macos10.10-universal.tar.gz" \
      "$WORK/cmake-$CMAKE_VER.tar.gz" "$CMAKE_SHA256" || exit 1
[ -x "$CMAKE" ] || run tar xzf "$WORK/cmake-$CMAKE_VER.tar.gz" -C "$WORK"
run "$CMAKE" --version | head -1

tags=${1:-$LLAMA_TAGS}
jobs=$(sysctl -n hw.physicalcpu)
for tag in $tags; do
    log "---- trying llama.cpp $tag"
    rm -rf "$WORK/llama.cpp"
    run git clone -q --depth 1 --branch "$tag" https://github.com/ggml-org/llama.cpp "$WORK/llama.cpp" || continue
    cd "$WORK/llama.cpp" || exit 1
    start=$(date +%s)
    if run "$CMAKE" -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0 \
            -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=ON -DGGML_METAL=OFF -DGGML_ACCELERATE=OFF \
            -DGGML_BLAS=OFF -DGGML_OPENMP=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_CURL=OFF \
            -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF > "$WORK/cmake-configure.log" 2>&1 \
       && run "$CMAKE" --build build -j "$jobs" --target llama-server llama-bench > "$WORK/cmake-build.log" 2>&1; then
        log "BUILD OK: $tag in $(( $(date +%s) - start )) s"
        minos "$LLAMA_BIN/llama-server"
        otool -L "$LLAMA_BIN/llama-server"
        run "$LLAMA_BIN/llama-server" --version
        echo "$tag" > "$WORK/llama-tag.txt"
        log "== S2 done (tag $tag)"
        exit 0
    fi
    log "BUILD FAILED: $tag - first errors:"
    grep -m 15 -E 'error|Error' "$WORK/cmake-configure.log" "$WORK/cmake-build.log"
    cp "$WORK/cmake-build.log" "$OUT/s2-build-failed-$tag.log" 2>/dev/null
    cd "$WORK" || exit 1
done
log "== S2 FAILED for all tags: $tags"
exit 1
