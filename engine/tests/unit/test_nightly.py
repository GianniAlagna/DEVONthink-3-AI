"""J-3 nightly incremental (SPEC §4.21 D1): changed records of each enabled scope go to the queue."""
from datetime import UTC, datetime

from dt3agent import nightly, queue, store
from tests.fakes import FakeDT3

A = "00000000-0000-4000-8000-00000000000A"
B = "00000000-0000-4000-8000-00000000000B"
C = "00000000-0000-4000-8000-00000000000C"
SCOPE = [{"database": "DT3Agent-Test", "group": "/Inbox/"}]


class Adapter:
    def __init__(self, dt3):
        from dt3agent.adapter import DT3Adapter
        self.inner = DT3Adapter(dt3, None, None)

    def list_scope(self, *a, **k):
        return self.inner.list_scope(*a, **k)


def setup(records):
    dt3 = FakeDT3(records)
    q = queue.Queue(store.open_db(":memory:", queue.MIGRATIONS), lambda: datetime(2026, 11, 6, tzinfo=UTC))
    return dt3, Adapter(dt3), q


def queued(q):
    return sorted(r[0] for r in q.con.execute("SELECT uuid FROM jobs WHERE state = 'queued'"))


def test_first_night_sets_the_watermark_and_queues_nothing():
    dt3, ad, q = setup({A: {"location": "/Inbox/", "modified": "2026-11-01T08:00:00.000Z", "kind": "PDF"}})
    assert nightly.run(ad, q, SCOPE) == "ok"
    assert queued(q) == [] and q.pull_since("DT3Agent-Test", "/Inbox/") == "2026-11-01T08:00:00.000Z"


def test_later_nights_queue_only_changed_records():
    dt3, ad, q = setup({A: {"location": "/Inbox/", "modified": "2026-11-01T08:00:00.000Z", "kind": "PDF"}})
    nightly.run(ad, q, SCOPE)
    dt3.records[B] = {"uuid": B, "location": "/Inbox/", "modified": "2026-11-05T08:00:00.000Z", "kind": "PDF"}
    dt3.records[C] = {"uuid": C, "location": "/Archiv/", "modified": "2026-11-05T09:00:00.000Z", "kind": "PDF"}
    assert nightly.run(ad, q, SCOPE) == "ok"
    assert queued(q) == [B]                                     # C is outside the scope
    assert q.pull_since("DT3Agent-Test", "/Inbox/") == "2026-11-05T08:00:00.000Z"
    assert q.con.execute("SELECT source FROM jobs").fetchone()[0] == "pull"
    assert nightly.run(ad, q, SCOPE) == "ok" and queued(q) == [B]   # nothing new


def test_empty_scope_list_does_nothing():
    _, ad, q = setup({})
    assert nightly.run(ad, q, []) == "no_scopes"


def test_a_broken_scope_does_not_stop_the_others():
    dt3, ad, q = setup({A: {"location": "/Inbox/", "modified": "2026-11-01T08:00:00.000Z", "kind": "PDF"}})
    scopes = [{"database": "DT3Agent-Test", "group": "/Fehlt/"}] + SCOPE
    assert nightly.run(ad, q, scopes) == "group_not_found"      # the first problem is reported
    assert q.pull_since("DT3Agent-Test", "/Inbox/") is not None


def test_more_than_500_changes_is_reported():
    recs = {f"00000000-0000-4000-8000-{i:012d}": {"location": "/Inbox/", "kind": "PDF",
                                                  "modified": f"2026-11-0{1 + i // 300}T08:00:{i % 60:02d}.{i:03d}Z"}
            for i in range(600)}
    dt3, ad, q = setup({A: {"location": "/Inbox/", "modified": "2026-10-01T00:00:00.000Z", "kind": "PDF"}})
    nightly.run(ad, q, SCOPE)
    dt3.records.update({u: dict(r, uuid=u) for u, r in recs.items()})
    assert nightly.run(ad, q, SCOPE) == "capped"
    assert len(queued(q)) == 500


def test_service_runs_the_nightly_job_from_the_schedule(tmp_path):
    from datetime import timedelta, timezone

    from dt3agent.service import Service
    tz = timezone(timedelta(hours=1))
    dt3 = FakeDT3({A: {"location": "/Inbox/", "modified": "2026-11-01T08:00:00.000Z", "kind": "PDF"}})
    svc = Service(tmp_path, dt3)
    svc.cfg["scopes"] = SCOPE
    svc.local_clock = lambda: datetime(2026, 11, 4, 9, 0, tzinfo=tz)
    svc.tick()                                                   # baseline
    svc.local_clock = lambda: datetime(2026, 11, 5, 3, 0, tzinfo=tz)
    assert svc.tick() == "job:nightly:ok"                        # first night: watermark only
    dt3.records[B] = {"uuid": B, "location": "/Inbox/", "modified": "2026-11-05T12:00:00.000Z", "kind": "PDF"}
    svc.local_clock = lambda: datetime(2026, 11, 6, 3, 0, tzinfo=tz)
    assert svc.tick() == "job:nightly:ok"
    assert svc.queue.counts().get("queued") == 1
    assert not [v for v, _ in dt3.calls if v.startswith("set_") or v in ("move", "create_markdown")]
