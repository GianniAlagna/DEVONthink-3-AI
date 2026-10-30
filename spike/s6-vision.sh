# S6 - Vision on macOS 11: OCR languages, OCR quality, Swiss QR-bill decode. Also proves a universal
# (x86_64 + arm64) Swift CLI builds with Xcode 13.2.
. "$(dirname "$0")/lib.sh"
need_py

BIN="$WORK/vision-probe"
SRC="$SPIKE_DIR/vision/VisionProbe.swift"
log "== S6 Vision"
need_clt
run xcrun swiftc -O -target x86_64-apple-macos11.0 "$SRC" -o "$BIN-x86_64" || exit 1
run xcrun swiftc -O -target arm64-apple-macos11.0 "$SRC" -o "$BIN-arm64"
if [ -f "$BIN-arm64" ]; then
    run lipo -create "$BIN-x86_64" "$BIN-arm64" -output "$BIN"
else
    cp "$BIN-x86_64" "$BIN"
fi
run lipo -info "$BIN"
minos "$BIN-x86_64"

log "-- supported OCR languages"
run "$BIN" langs

for lang in de fr it en; do
    case $lang in de) code=de-DE ;; fr) code=fr-FR ;; it) code=it-IT ;; *) code=en-US ;; esac
    log "-- OCR ocr-$lang.pdf (languages $code,en-US)"
    "$BIN" ocr "$FIXTURES/ocr-$lang.pdf" "$code,en-US" > "$WORK/ocr-$lang.out"
    cat "$WORK/ocr-$lang.out"
    "$PY" -I - "$FIXTURES/ocr-$lang.txt" "$WORK/ocr-$lang.out" <<'EOF'
import difflib, sys
truth = open(sys.argv[1], encoding="utf-8").read().split()
got = open(sys.argv[2], encoding="utf-8").read().split()
print("word accuracy %.3f  char similarity %.3f" % (
    difflib.SequenceMatcher(None, truth, got).ratio(),
    difflib.SequenceMatcher(None, " ".join(truth), " ".join(got)).ratio()))
EOF
done

for kind in qrr scor; do
    log "-- QR decode qrbill-$kind.pdf"
    "$BIN" qr "$FIXTURES/qrbill-$kind.pdf" > "$WORK/qr-$kind.out"
    "$PY" -I - "$FIXTURES/qrbill-$kind.payload.txt" "$WORK/qr-$kind.out" <<'EOF'
import base64, sys
want = open(sys.argv[1], "rb").read()
codes = [base64.b64decode(l) for l in open(sys.argv[2]).read().split()]
print("codes found:", len(codes), "| byte-exact match:", any(c == want for c in codes))
EOF
done
log "== S6 done"
