# S3 - model speed, memory and JSON-schema reliability on the floor machine.
# Models: permissive license (Apache-2.0) and German/French/Italian support, pinned by revision + SHA-256
# (values read from the Hugging Face API on 2026-10-30).
# Usage: bash spike/run.sh s3            all models
#        bash spike/run.sh s3 qwen3-1.7b one model
. "$(dirname "$0")/lib.sh"
need_py
[ -x "$LLAMA_BIN/llama-server" ] || { log "llama-server missing: run s2 first"; exit 1; }

# name | repo | revision | file | sha256
MODELS="qwen3-1.7b|ggml-org/Qwen3-1.7B-GGUF|daeb8e2d528a760970442092f6bf1e55c3b659eb|Qwen3-1.7B-Q4_K_M.gguf|d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5
granite-4.0-micro-3b|ibm-granite/granite-4.0-micro-GGUF|ec48475f0c811d812fbfb61975717a9c36eeb652|granite-4.0-micro-Q4_K_M.gguf|97c417dcc0534b0737c74016fb2af083cb17c3b51eaac621192d23961b7024eb"

only=${1:-}
threads=$(sysctl -n hw.physicalcpu)
port=8089
mkdir -p "$WORK/models"

# /usr/bin/time ignores SIGINT itself, so signal its child (llama-server)
stop_server() { [ -n "${srv:-}" ] && pkill -INT -P "$srv" 2>/dev/null; wait "${srv:-}" 2>/dev/null; srv=; }
trap stop_server EXIT

while IFS='|' read -r name repo rev file sha <&3; do
    [ -n "$only" ] && [ "$only" != "$name" ] && continue
    log "==== $name"
    model="$WORK/models/$file"
    fetch "https://huggingface.co/$repo/resolve/$rev/$file" "$model" "$sha" || continue

    log "-- llama-bench (pp512 / tg128, $threads threads)"
    run "$LLAMA_BIN/llama-bench" -m "$model" -p 512 -n 128 -t "$threads"

    log "-- llama-server, ctx 8192, real extraction requests"
    /usr/bin/time -l "$LLAMA_BIN/llama-server" -m "$model" -c 8192 -t "$threads" -np 1 \
        --host 127.0.0.1 --port "$port" --no-webui --reasoning-budget 0 \
        > "$WORK/server-$name.log" 2> "$WORK/server-$name.err" &
    srv=$!
    for i in $(seq 1 120); do
        curl -fs "http://127.0.0.1:$port/health" >/dev/null 2>&1 && break
        sleep 1
    done
    run "$PY" -I "$SPIKE_DIR/s3_bench.py" --url "http://127.0.0.1:$port" --model "$name" \
        --fixtures "$FIXTURES" --runs 5 --json-out "$OUT/s3-$name.json"

    log "-- same, under real memory pressure (memory_pressure -l warn allocates memory; UNVERIFIED flags on macOS 11), 1 run per language"
    memory_pressure -l warn > /dev/null 2>&1 &
    mp=$!
    sleep 10
    run "$PY" -I "$SPIKE_DIR/s3_bench.py" --url "http://127.0.0.1:$port" --model "$name-pressure" \
        --fixtures "$FIXTURES" --runs 1 --json-out "$OUT/s3-$name-pressure.json"
    kill "$mp" 2>/dev/null; wait "$mp" 2>/dev/null

    stop_server
    log "-- peak memory of llama-server:"
    grep -E 'maximum resident set size|peak memory footprint' "$WORK/server-$name.err"
done 3<<< "$MODELS"
log "== S3 done"
