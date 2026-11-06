"""Knowledge index (SPEC §4.20, K-2): chunks of document text with embeddings, in `index.db`.

The index is rebuildable from DT3 at any time. Chunk text is stored because answers quote their sources; it is
never logged. Search = cosine over all vectors in scope, fused with FTS5 keyword ranks when SQLite has FTS5.
"""
import hashlib
import operator
import re
import sqlite3
import time
from array import array
from dataclasses import dataclass
from pathlib import Path

from dt3agent.embed import normalise
from dt3agent.store import open_db

CHUNK = 1200
OVERLAP = 200
RRF_K = 60          # reciprocal-rank fusion constant
KEYWORD_TOP = 50

MIGRATIONS = [
    "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE docs (uuid TEXT PRIMARY KEY, database TEXT NOT NULL, content_hash TEXT NOT NULL,"
    " indexed_at REAL NOT NULL)",
    "CREATE TABLE chunks (uuid TEXT NOT NULL REFERENCES docs(uuid) ON DELETE CASCADE, n INTEGER NOT NULL,"
    " text TEXT NOT NULL, vec BLOB NOT NULL, PRIMARY KEY (uuid, n))",
]
_END = re.compile(r"\n\s*\n|[.!?]\s")


@dataclass(frozen=True)
class Hit:
    uuid: str
    n: int
    text: str
    score: float         # fused rank score (for ordering)
    cosine: float = 0.0  # vector similarity to the question, 0..1 (for "not found", Q-1)


def chunks(text: str, size: int = CHUNK, overlap: int = OVERLAP) -> list[str]:
    """Pieces of about `size` characters that overlap by `overlap`, cut at a paragraph or sentence end."""
    text = text.strip()
    out, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start + size // 2:end]
            cuts = [m.end() for m in _END.finditer(window)]
            if cuts:
                end = start + size // 2 + cuts[-1]
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return out


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class Index:
    def __init__(self, path: Path, embedder, *, model: str):
        self.con = open_db(Path(path), MIGRATIONS)
        self.embedder = embedder
        try:
            self.con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, uuid UNINDEXED,"
                             " n UNINDEXED)")
            self.fts = True
        except sqlite3.OperationalError:  # SQLite built without FTS5: vector search only
            self.fts = False
        row = self.con.execute("SELECT value FROM meta WHERE key='model'").fetchone()
        if row and row[0] != model:  # another embedding model: old vectors are not comparable
            self._clear()
        self.con.execute("INSERT OR REPLACE INTO meta VALUES ('model', ?)", (model,))
        self.con.commit()

    def _clear(self) -> None:
        self.con.execute("DELETE FROM chunks")
        self.con.execute("DELETE FROM docs")
        if self.fts:
            self.con.execute("DELETE FROM chunks_fts")

    def update(self, uuid: str, database: str, text: str) -> bool:
        """(Re)index one record; False when its text is unchanged. Embedding errors propagate (EmbedError)."""
        digest = content_hash(text)
        row = self.con.execute("SELECT content_hash FROM docs WHERE uuid=?", (uuid,)).fetchone()
        if row and row[0] == digest:
            return False
        pieces = chunks(text)
        vectors = self.embedder.embed(pieces) if pieces else []
        with self.con:
            self._remove(uuid)
            self.con.execute("INSERT INTO docs VALUES (?, ?, ?, ?)", (uuid, database, digest, time.time()))
            for n, (piece, vec) in enumerate(zip(pieces, vectors, strict=True)):
                self.con.execute("INSERT INTO chunks VALUES (?, ?, ?, ?)", (uuid, n, piece, vec.tobytes()))
                if self.fts:
                    self.con.execute("INSERT INTO chunks_fts (text, uuid, n) VALUES (?, ?, ?)", (piece, uuid, n))
        return True

    def _remove(self, uuid: str) -> None:
        self.con.execute("DELETE FROM chunks WHERE uuid=?", (uuid,))
        self.con.execute("DELETE FROM docs WHERE uuid=?", (uuid,))
        if self.fts:
            self.con.execute("DELETE FROM chunks_fts WHERE uuid=?", (uuid,))

    def remove(self, uuid: str) -> None:
        with self.con:
            self._remove(uuid)

    def has(self, uuid: str) -> bool:
        return self.con.execute("SELECT 1 FROM docs WHERE uuid=?", (uuid,)).fetchone() is not None

    def count(self) -> int:
        return self.con.execute("SELECT count(*) FROM docs").fetchone()[0]

    def _rows(self, databases):
        sql = "SELECT c.uuid, c.n, c.text, c.vec FROM chunks c JOIN docs d USING (uuid)"
        if databases is not None:
            marks = ",".join("?" * len(databases))
            return self.con.execute(f"{sql} WHERE d.database IN ({marks})", list(databases))
        return self.con.execute(sql)

    def search(self, query: str, k: int = 6, databases=None) -> list[Hit]:
        """Best `k` chunks for a question, from vector similarity and (if available) keyword rank."""
        if databases is not None and not databases:
            return []
        qvec = self.embedder.embed([query], query=True)[0]
        scored, texts = [], {}
        for uuid, n, text, blob in self._rows(databases):
            vec = array("f")
            vec.frombytes(blob)
            scored.append((sum(map(operator.mul, qvec, vec)), (uuid, n)))
            texts[(uuid, n)] = text
        scored.sort(reverse=True)
        cos = {key: c for c, key in scored}
        fused = {key: 1 / (RRF_K + rank) for rank, (_, key) in enumerate(scored)}
        for rank, key in enumerate(self._keyword(query, texts)):
            fused[key] = fused.get(key, 0) + 1 / (RRF_K + rank)
        best = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:k]
        return [Hit(uuid, n, texts[(uuid, n)], round(score, 6), round(max(0.0, cos[(uuid, n)]), 4))
                for (uuid, n), score in best]

    def _keyword(self, query: str, allowed: dict) -> list[tuple[str, int]]:
        if not self.fts:
            return []
        words = [w for w in re.findall(r"\w{3,}", query)][:20]
        if not words:
            return []
        match = " OR ".join('"' + w.replace('"', "") + '"' for w in words)  # quoted: no FTS syntax from users
        try:
            rows = self.con.execute("SELECT uuid, n FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
                                    (match, KEYWORD_TOP)).fetchall()
        except sqlite3.OperationalError:
            return []
        return [(u, int(n)) for u, n in rows if (u, int(n)) in allowed]

    def record_vector(self, uuid: str) -> array | None:
        """Mean of a record's chunk vectors, normalised (for related documents)."""
        total = None
        for (blob,) in self.con.execute("SELECT vec FROM chunks WHERE uuid=?", (uuid,)):
            vec = array("f")
            vec.frombytes(blob)
            total = vec if total is None else array("f", map(operator.add, total, vec))
        return None if total is None else normalise(total, len(total))

    def related(self, uuid: str, k: int = 5, min_score: float = 0.75, databases=None) -> list[tuple[str, float]]:
        """Other records whose mean vector is close to this one's, best first."""
        mine = self.record_vector(uuid)
        if mine is None:
            return []
        others = {row[0] for row in self._rows(databases)} - {uuid}
        scores = []
        for other in others:
            vec = self.record_vector(other)
            score = sum(map(operator.mul, mine, vec))
            if score >= min_score:
                scores.append((other, round(score, 4)))
        scores.sort(key=lambda kv: kv[1], reverse=True)
        return scores[:k]
