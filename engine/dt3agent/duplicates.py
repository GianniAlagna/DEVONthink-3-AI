"""Duplicate detection (brief A10 / §5.2, SPEC §4.14). Results only ever become review items.

Exact: DT3's own `duplicates()` (verified Phase 0, S4). Near: 5-word shingles, compared with a bottom-k
sketch (the 256 smallest shingle hashes) so only hashes are stored, never text. Jaccard >= threshold.
Pairs the user marked "not a duplicate" are never proposed again.
"""
import json
import re
import sqlite3
import zlib
from datetime import UTC, datetime

SKETCH = 256
MIGRATIONS = [
    "CREATE TABLE fingerprints (uuid TEXT PRIMARY KEY, sketch_json TEXT NOT NULL, created_at TEXT NOT NULL)",
    """CREATE TABLE dup_pairs (a TEXT NOT NULL, b TEXT NOT NULL, decision TEXT NOT NULL,
        decided_at TEXT NOT NULL, PRIMARY KEY (a, b))""",
]
WORD = re.compile(r"[^\W_]+")


def sketch(text: str, k: int = 5) -> list[int]:
    words = WORD.findall(text.casefold())
    shingles = {" ".join(words[i:i + k]) for i in range(max(1, len(words) - k + 1))} if words else set()
    return sorted({zlib.crc32(s.encode()) for s in shingles})[:SKETCH]


def similarity(a: list[int], b: list[int]) -> float:
    """Bottom-k estimate of the Jaccard index of the two shingle sets."""
    if not a or not b:
        return 0.0
    union = sorted(set(a) | set(b))[:SKETCH]
    return round(len(set(union) & set(a) & set(b)) / len(union), 3)


def _pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def dismissed(con: sqlite3.Connection, a: str, b: str) -> bool:
    return con.execute("SELECT 1 FROM dup_pairs WHERE a = ? AND b = ?", _pair(a, b)).fetchone() is not None


def dismiss(con: sqlite3.Connection, a: str, b: str, decision: str = "not_duplicate") -> None:
    with con:
        con.execute("INSERT OR REPLACE INTO dup_pairs (a, b, decision, decided_at) VALUES (?, ?, ?, ?)",
                    (*_pair(a, b), decision, datetime.now(UTC).isoformat()))


def near(con: sqlite3.Connection, uuid: str, text: str, threshold: float, limit: int = 5000) -> list[tuple]:
    """Store this record's sketch and return [(other_uuid, score)] at or above the threshold."""
    mine = sketch(text)
    found = []
    for other, sk in con.execute("SELECT uuid, sketch_json FROM fingerprints WHERE uuid != ? "
                                 "ORDER BY created_at DESC LIMIT ?", (uuid, limit)):
        score = similarity(mine, json.loads(sk))
        if score >= threshold and not dismissed(con, uuid, other):
            found.append((other, score))
    with con:
        con.execute("INSERT OR REPLACE INTO fingerprints (uuid, sketch_json, created_at) VALUES (?, ?, ?)",
                    (uuid, json.dumps(mine), datetime.now(UTC).isoformat()))
    return sorted(found, key=lambda x: -x[1])
