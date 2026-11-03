"""Intake: UUIDs from the DT3 spool folder, or pulled by addition date (SPEC §4.6).

DT3 scripts only write a tiny JSON file and return at once (brief §2.6).
"""
import json
import os
import time
from pathlib import Path

from dt3agent.audit import UUID_RE
from dt3agent.queue import Queue

MAX_SPOOL_BYTES = 4096
MIN_AGE_SECONDS = 2.0  # DT3 scripts write files in place; skip ones that may still be open


def ingest_spool(spool: Path, queue: Queue, source: str = "spool", min_age: float = MIN_AGE_SECONDS) -> int:
    """Queue every valid spool file and remove it; invalid files go to spool/rejected/. Returns new jobs.

    Files younger than `min_age` seconds are left for the next poll (the writer may not be done).
    """
    spool = Path(spool)
    if not spool.is_dir():
        return 0
    before = sum(queue.counts().values())
    now = time.time()
    for f in sorted(spool.glob("*.json")):
        try:
            if now - f.stat().st_mtime < min_age:
                continue
        except OSError:
            continue
        uuid = _read_uuid(f)
        if uuid is None:
            rejected = spool / "rejected"
            rejected.mkdir(exist_ok=True)
            os.replace(f, rejected / f.name)
            continue
        queue.enqueue(uuid, source)
        f.unlink()  # only after the job is committed
    return sum(queue.counts().values()) - before


def _read_uuid(f: Path) -> str | None:
    try:
        if f.stat().st_size > MAX_SPOOL_BYTES:
            return None
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    uuid = data.get("uuid") if isinstance(data, dict) else None
    return uuid if isinstance(uuid, str) and UUID_RE.fullmatch(uuid) else None


def pull_new(adapter, queue: Queue, scopes: list[dict]) -> int:
    """Queue records added since the last pull, per enabled scope only. Returns new jobs.

    `adapter.list_added_since` returns (uuid, addition_date) with dates as UTC ISO-8601 strings,
    so string order is time order.
    """
    before = sum(queue.counts().values())
    for scope in scopes:
        database, group = scope["database"], scope["group"]
        since = queue.pull_since(database, group)
        newest = since
        for uuid, added in adapter.list_added_since(database, group, since):
            if UUID_RE.fullmatch(uuid):
                queue.enqueue(uuid, "pull")
                newest = max(newest or added, added)
        if newest and newest != since:
            queue.set_pull_since(database, group, newest)
    return sum(queue.counts().values()) - before
