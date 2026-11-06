"""J-2 scheduler (SPEC §4.21): engine-internal due times, no cron or launchd job per task.

A job is due when its most recent due time (local time) is later than the one it last ran for. Missed runs
(Mac asleep) run once, not once per missed day. The first start only records a baseline, so nothing runs
right after an install. The engine loop runs at most one job per tick, never two at once.
"""
import sqlite3
from datetime import datetime, timedelta

MIGRATIONS = [
    """CREATE TABLE jobs_runs (name TEXT PRIMARY KEY, due TEXT NOT NULL, ran_at TEXT, result TEXT)""",
]
ORDER = ("nightly", "feeds", "hygiene", "digest")  # fixed order when several are due
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def last_due(spec: dict, now: datetime) -> datetime:
    """Most recent due time at or before `now` (an aware local time). DST shifts can move one run by an hour."""
    hh, mm = (int(x) for x in spec["time"].split(":"))
    due = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if "day" in spec:
        due -= timedelta(days=(now.weekday() - WEEKDAYS.index(spec["day"])) % 7)
        if due > now:
            due -= timedelta(days=7)
    elif due > now:
        due -= timedelta(days=1)
    return due


class Scheduler:
    def __init__(self, con: sqlite3.Connection):
        self.con = con
        self._pending: dict[str, datetime] = {}  # due time each job was found due for

    def due(self, jobs_cfg: dict, now: datetime) -> list[str]:
        out = []
        for name in ORDER:
            spec = jobs_cfg.get(name)
            if not spec or not spec.get("enabled"):
                continue
            when = last_due(spec, now)
            row = self.con.execute("SELECT due FROM jobs_runs WHERE name = ?", (name,)).fetchone()
            if row is None:
                with self.con:
                    self.con.execute("INSERT INTO jobs_runs (name, due, result) VALUES (?, ?, 'baseline')",
                                     (name, when.isoformat()))
            elif datetime.fromisoformat(row[0]) < when:
                self._pending[name] = when
                out.append(name)
        return out

    def done(self, name: str, now: datetime, result: str) -> None:
        """Record a run (ok or a short error code). It counts for the due time it was found due for."""
        when = self._pending.pop(name, now)
        with self.con:
            self.con.execute("INSERT INTO jobs_runs (name, due, ran_at, result) VALUES (?, ?, ?, ?) "
                             "ON CONFLICT (name) DO UPDATE SET due = excluded.due, ran_at = excluded.ran_at, "
                             "result = excluded.result", (name, when.isoformat(), now.isoformat(), result))

    def last(self, name: str) -> dict | None:
        row = self.con.execute("SELECT due, ran_at, result FROM jobs_runs WHERE name = ?", (name,)).fetchone()
        return dict(zip(("due", "ran_at", "result"), row, strict=True)) if row else None
