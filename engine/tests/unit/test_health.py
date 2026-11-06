"""E-1 health (SPEC §4.22): status adds embed_ok, queue_backlog (minutes), last_job."""
from datetime import UTC, datetime, timedelta

from dt3agent import queue, store

U = "00000000-0000-4000-8000-000000000001"
V = "00000000-0000-4000-8000-000000000002"


def q_at(clock):
    return queue.Queue(store.open_db(":memory:", queue.MIGRATIONS), clock)


def test_backlog_is_the_age_of_the_oldest_waiting_job():
    now = [datetime(2026, 11, 6, 8, 0, tzinfo=UTC)]
    q = q_at(lambda: now[0])
    assert q.backlog_minutes() is None
    q.enqueue(U, "cli")
    now[0] += timedelta(minutes=95)
    q.enqueue(V, "cli")
    assert q.backlog_minutes() == 95


def test_last_finished_job_has_state_and_time_only():
    now = [datetime(2026, 11, 6, 8, 0, tzinfo=UTC)]
    q = q_at(lambda: now[0])
    assert q.last_finished() is None
    job = q.enqueue(U, "cli")
    q.claim()
    now[0] += timedelta(minutes=1)
    q.finish(job, "done")
    assert q.last_finished() == {"state": "done", "error": None, "at": now[0].isoformat()}
    assert q.backlog_minutes() is None


def test_status_reports_health(tmp_path):
    from dt3agent.service import Service
    from tests.fakes import FakeDT3
    st = Service(tmp_path, FakeDT3()).handle("status", {})
    assert st["embed_ok"] is None and st["queue_backlog"] is None and st["last_job"] is None
