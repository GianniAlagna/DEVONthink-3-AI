# S1 - bundled relocatable Python (python-build-standalone) on macOS 11 Intel.
. "$(dirname "$0")/lib.sh"

log "== S1 python-build-standalone $PY_VER+$PY_TAG"
arch=$(uname -m)   # x86_64 on the floor
base="https://github.com/astral-sh/python-build-standalone/releases/download/$PY_TAG"
asset="cpython-$PY_VER+$PY_TAG-$arch-apple-darwin-install_only.tar.gz"
url_asset="cpython-$PY_VER%2B$PY_TAG-$arch-apple-darwin-install_only.tar.gz"

cd "$WORK" || exit 1
fetch "$base/SHA256SUMS" "$WORK/SHA256SUMS-$PY_TAG" || { log "Could not get SHA256SUMS - open https://github.com/astral-sh/python-build-standalone/releases/tag/$PY_TAG and tell Claude the exact asset name"; exit 1; }
want=$(awk -v a="$asset" '$2==a{print $1}' "$WORK/SHA256SUMS-$PY_TAG")
[ -n "$want" ] || { log "Asset $asset not listed in SHA256SUMS - tell Claude"; exit 1; }
fetch "$base/$url_asset" "$WORK/$asset" "$want" || exit 1

rm -rf "$WORK/python"
run tar xzf "$WORK/$asset" -C "$WORK"
log "Binary targets (want minos <= 11.0):"
minos "$WORK/python/bin/python$(echo $PY_VER | cut -d. -f1,2)"
[ -f "$WORK/python/lib/libpython3.12.dylib" ] && minos "$WORK/python/lib/libpython3.12.dylib"
xattr -l "$WORK/python/bin/python3" | head -3   # quarantine flag? (curl downloads should have none)

run "$PY" -I -c 'import sys,sqlite3,ssl,json,hashlib,unicodedata,re,urllib.request,subprocess,plistlib;print(sys.version);print("sqlite",sqlite3.sqlite_version);print(ssl.OPENSSL_VERSION)'
run "$PY" -I -c '
import sqlite3, tempfile, os
p = os.path.join(tempfile.mkdtemp(), "t.db")
c = sqlite3.connect(p)
print("journal_mode", c.execute("pragma journal_mode=wal").fetchone()[0])
print("json1", c.execute("select json_extract(?, \"$.a\")", ("{\"a\": 42}",)).fetchone()[0])
print("fts5", c.execute("create virtual table f using fts5(x)") is not None)
'
log "Relocatability: move the folder and run again"
mv "$WORK/python" "$WORK/python-moved" && run "$WORK/python-moved/bin/python3" -I -c 'import sys;print("relocated ok", sys.prefix)'
mv "$WORK/python-moved" "$WORK/python"
log "Startup time (5 runs):"
for i in 1 2 3 4 5; do /usr/bin/time -p "$PY" -I -c pass 2>&1 | awk '/^real/{print "real " $2 " s"}'; done
log "== S1 done"
