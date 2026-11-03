# Packs spike/out into one zip on the Desktop for Claude. Your home folder path and user name are
# replaced by "~" and "<user>"; nothing else leaves the Mac. Look inside before sending.
. "$(dirname "$0")/lib.sh"
stamp=$(date +%Y%m%d-%H%M)
tmp="$WORK/collect-$stamp"
zip="$HOME/Desktop/dt3agent-spike-results-$stamp.zip"
rm -rf "$tmp" && mkdir -p "$tmp"
for f in "$OUT"/*; do
    [ -f "$f" ] || continue
    sed -e "s#$HOME#~#g" -e "s#/Users/$USER#~#g" -e "s#[[:<:]]$USER[[:>:]]#<user>#g" "$f" > "$tmp/$(basename "$f")"
done
cp "$WORK"/server-*.err "$tmp/" 2>/dev/null
ditto -c -k --sequesterRsrc "$tmp" "$zip"
log "Created $zip ($(ls "$tmp" | wc -l | tr -d ' ') files). Attach it in the Claude app chat."
