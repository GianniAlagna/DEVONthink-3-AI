"""Undo journal: the old value of every field is stored before any write (SPEC §4.8, brief §3.2-4)."""
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

MIGRATIONS = [
    """CREATE TABLE snapshots (
        id INTEGER PRIMARY KEY,
        batch_id TEXT NOT NULL,
        uuid TEXT NOT NULL,
        field TEXT NOT NULL CHECK (field IN ('name', 'tags', 'comment', 'metadata', 'location')),
        old_json TEXT NOT NULL,
        new_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        undone_at TEXT)""",
    "CREATE INDEX snapshots_batch ON snapshots (batch_id)",
    "CREATE INDEX snapshots_uuid ON snapshots (uuid)",
]


@dataclass(frozen=True)
class Entry:
    id: int
    batch_id: str
    uuid: str
    field: str
    old: object
    new: object


class UndoJournal:
    def __init__(self, con: sqlite3.Connection):
        self.con = con

    def record(self, batch_id: str, uuid: str, field: str, old, new) -> int:
        with self.con:
            cur = self.con.execute(
                "INSERT INTO snapshots (batch_id, uuid, field, old_json, new_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (batch_id, uuid, field, json.dumps(old), json.dumps(new), datetime.now(UTC).isoformat()))
            return cur.lastrowid

    def _entries(self, where: str, args: tuple) -> list[Entry]:
        rows = self.con.execute(f"SELECT id, batch_id, uuid, field, old_json, new_json FROM snapshots "
                                f"WHERE undone_at IS NULL AND {where} ORDER BY id DESC", args).fetchall()
        return [Entry(i, b, u, f, json.loads(o), json.loads(n)) for i, b, u, f, o, n in rows]

    def entries(self, batch_id: str) -> list[Entry]:
        """Open entries of a batch, newest first (the order to undo them in)."""
        return self._entries("batch_id = ?", (batch_id,))

    def entries_for(self, uuid: str) -> list[Entry]:
        return self._entries("uuid = ?", (uuid,))

    def last_batch(self) -> str | None:
        row = self.con.execute(
            "SELECT batch_id FROM snapshots WHERE undone_at IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        return row[0] if row else None

    def mark_undone(self, entry_id: int) -> None:
        with self.con:
            self.con.execute("UPDATE snapshots SET undone_at = ? WHERE id = ?",
                             (datetime.now(UTC).isoformat(), entry_id))
