import json
from datetime import UTC, datetime

import pytest

from dt3agent import intake, store
from dt3agent.queue import MIGRATIONS, Queue

A = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"
B = "727717FF-9696-4520-8BD9-9F413AE2A7FB"
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)


@pytest.fixture
def queue(tmp_path):
    return Queue(store.open_db(tmp_path / "queue.db", MIGRATIONS), lambda: NOW)


def drop(spool, name, payload):
    spool.mkdir(exist_ok=True)
    (spool / name).write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")


def test_spool_files_become_jobs_and_are_removed(tmp_path, queue):
    spool = tmp_path / "spool"
    drop(spool, "1.json", {"uuid": A})
    drop(spool, "2.json", {"uuid": A})  # same record twice -> one job
    drop(spool, "3.json", {"uuid": B})
    assert intake.ingest_spool(spool, queue) == 2
    assert queue.counts() == {"queued": 2}
    assert not list(spool.glob("*.json"))


def test_bad_spool_files_are_set_aside_not_queued(tmp_path, queue):
    spool = tmp_path / "spool"
    drop(spool, "bad.json", "{not json")
    drop(spool, "evil.json", {"uuid": "../../etc"})
    drop(spool, "big.json", {"uuid": A, "pad": "x" * 10_000})
    assert intake.ingest_spool(spool, queue) == 0
    assert queue.counts() == {}
    assert sorted(p.name for p in (spool / "rejected").iterdir()) == ["bad.json", "big.json", "evil.json"]


class FakeAdapter:
    def __init__(self, records):
        self.records = records  # (database, group, uuid, addition_date)
        self.calls = []

    def list_added_since(self, database, group, since):
        self.calls.append((database, group, since))
        return [(u, d) for db, g, u, d in self.records
                if db == database and g == group and (since is None or d > since)]


def test_pull_queues_new_records_of_enabled_scopes_only(queue):
    t1, t2 = "2026-11-03T10:00:00Z", "2026-11-03T11:00:00Z"
    adapter = FakeAdapter([("Inbox", "/", A, t1), ("Inbox", "/", B, t2), ("Private", "/", "C" * 8 + A[8:], t2)])
    scopes = [{"database": "Inbox", "group": "/"}]
    assert intake.pull_new(adapter, queue, scopes) == 2
    assert intake.pull_new(adapter, queue, scopes) == 0  # watermark: nothing new the second time
    assert adapter.calls[-1] == ("Inbox", "/", t2)
    assert all(c[0] == "Inbox" for c in adapter.calls)  # Private was never read
