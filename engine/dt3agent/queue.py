"""Job queue: one job at a time, retry with growing back-off, partial = retry (SPEC §4.7)."""
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from dt3agent.audit import UUID_RE

MIGRATIONS = [
    """CREATE TABLE jobs (
        id INTEGER PRIMARY KEY,
        uuid TEXT NOT NULL,
        source TEXT NOT NULL CHECK (source IN ('spool', 'pull', 'menu', 'cli')),
        state TEXT NOT NULL CHECK (state IN ('queued', 'running', 'partial', 'failed', 'done', 'review',
                                             'skipped', 'dead')),
        attempts INTEGER NOT NULL DEFAULT 0,
        next_attempt_at TEXT,
        last_error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL)""",
    # at most one open job per record; finished ones may be queued again later
    "CREATE UNIQUE INDEX jobs_open_uuid ON jobs (uuid) WHERE state IN ('queued', 'running', 'partial', 'failed')",
    "CREATE INDEX jobs_state ON jobs (state, next_attempt_at)",
    """CREATE TABLE pull_state (database TEXT NOT NULL, grp TEXT NOT NULL, since TEXT NOT NULL,
        PRIMARY KEY (database, grp))""",
]

ERROR_RE = re.compile(r"[a-z][a-z0-9_]{0,39}")  # short machine codes only, never document text
FINAL = {"done", "review", "skipped"}


@dataclass(frozen=True)
class Job:
    id: int
    uuid: str
    source: str
    attempts: int


class Queue:
    MAX_ATTEMPTS = 5
    BACKOFF = timedelta(seconds=30)
    BACKOFF_CAP = timedelta(hours=1)

    def __init__(self, con: sqlite3.Connection, clock):
        self.con = con
        self.clock = clock

    def _now(self) -> str:
        return self.clock().isoformat()

    def enqueue(self, uuid: str, source: str) -> int:
        if not UUID_RE.fullmatch(uuid):
            raise ValueError("uuid malformed")
        now = self._now()
        with self.con:
            row = self.con.execute("SELECT id FROM jobs WHERE uuid = ? AND state IN "
                                   "('queued', 'running', 'partial', 'failed')", (uuid,)).fetchone()
            if row:
                return row[0]
            cur = self.con.execute("INSERT INTO jobs (uuid, source, state, created_at, updated_at) "
                                   "VALUES (?, ?, 'queued', ?, ?)", (uuid, source, now, now))
            return cur.lastrowid

    def claim(self) -> Job | None:
        """Next due job, or None while one is running or none is due."""
        now = self._now()
        with self.con:
            if self.con.execute("SELECT 1 FROM jobs WHERE state = 'running'").fetchone():
                return None
            row = self.con.execute(
                "SELECT id, uuid, source, attempts FROM jobs WHERE state = 'queued' OR "
                "(state IN ('partial', 'failed') AND next_attempt_at <= ?) ORDER BY id LIMIT 1", (now,)).fetchone()
            if not row:
                return None
            self.con.execute("UPDATE jobs SET state = 'running', updated_at = ? WHERE id = ?", (now, row[0]))
        return Job(*row)

    def finish(self, job_id: int, state: str) -> None:
        if state not in FINAL:
            raise ValueError(f"finish state must be one of {sorted(FINAL)}")
        with self.con:
            self.con.execute("UPDATE jobs SET state = ?, next_attempt_at = NULL, updated_at = ? WHERE id = ?",
                             (state, self._now(), job_id))

    def fail(self, job_id: int, error_code: str, partial: bool = False) -> None:
        if not ERROR_RE.fullmatch(error_code):
            raise ValueError("error_code must be a short machine code")
        now = self.clock()
        with self.con:
            attempts = self.con.execute("SELECT attempts FROM jobs WHERE id = ?", (job_id,)).fetchone()[0] + 1
            if attempts >= self.MAX_ATTEMPTS:
                state, nxt = "dead", None
            else:
                state = "partial" if partial else "failed"
                nxt = (now + min(self.BACKOFF * 2 ** (attempts - 1), self.BACKOFF_CAP)).isoformat()
            self.con.execute("UPDATE jobs SET state = ?, attempts = ?, next_attempt_at = ?, last_error = ?, "
                             "updated_at = ? WHERE id = ?", (state, attempts, nxt, error_code, now.isoformat(), job_id))

    def next_attempt_at(self, job_id: int) -> datetime | None:
        value = self.con.execute("SELECT next_attempt_at FROM jobs WHERE id = ?", (job_id,)).fetchone()[0]
        return datetime.fromisoformat(value) if value else None

    def counts(self) -> dict[str, int]:
        return dict(self.con.execute("SELECT state, COUNT(*) FROM jobs GROUP BY state").fetchall())

    def pull_since(self, database: str, group: str) -> str | None:
        row = self.con.execute("SELECT since FROM pull_state WHERE database = ? AND grp = ?",
                               (database, group)).fetchone()
        return row[0] if row else None

    def set_pull_since(self, database: str, group: str, since: str) -> None:
        with self.con:
            self.con.execute("INSERT INTO pull_state (database, grp, since) VALUES (?, ?, ?) "
                             "ON CONFLICT (database, grp) DO UPDATE SET since = excluded.since",
                             (database, group, since))
