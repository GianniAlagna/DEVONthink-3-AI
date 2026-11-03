from datetime import UTC, datetime, timedelta

import pytest

from dt3agent import store
from dt3agent.queue import MIGRATIONS, Queue

A = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"
B = "727717FF-9696-4520-8BD9-9F413AE2A7FB"


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)

    def __call__(self):
        return self.now


@pytest.fixture
def q(tmp_path):
    clock = Clock()
    return Queue(store.open_db(tmp_path / "queue.db", MIGRATIONS), clock), clock


def test_same_uuid_twice_gives_one_open_job(q):
    queue, _ = q
    first = queue.enqueue(A, "spool")
    assert queue.enqueue(A, "pull") == first
    assert queue.counts() == {"queued": 1}


def test_invalid_uuid_is_rejected(q):
    queue, _ = q
    with pytest.raises(ValueError):
        queue.enqueue("not-a-uuid; DROP TABLE jobs", "spool")


def test_jobs_run_one_at_a_time_in_order(q):
    queue, _ = q
    queue.enqueue(A, "spool")
    queue.enqueue(B, "spool")
    job = queue.claim()
    assert job.uuid == A
    assert queue.claim() is None  # one job at a time (brief §2.4)
    queue.finish(job.id, "done")
    assert queue.claim().uuid == B


def test_failed_job_retries_with_backoff_then_gives_up(q):
    queue, clock = q
    queue.enqueue(A, "spool")
    delays = []
    for _ in range(Queue.MAX_ATTEMPTS):
        job = queue.claim()
        assert job is not None
        queue.fail(job.id, "dt3_timeout")
        assert queue.claim() is None  # not before the back-off has passed
        nxt = queue.next_attempt_at(job.id)
        if nxt:
            delays.append(nxt - clock.now)
            clock.now = nxt
    assert delays == sorted(delays) and len(set(delays)) == len(delays)  # growing back-off
    assert queue.counts() == {"dead": 1}


def test_partial_is_retried_not_marked_done(q):
    queue, clock = q
    queue.enqueue(A, "spool")
    job = queue.claim()
    queue.fail(job.id, "ai_invalid_json", partial=True)
    clock.now += timedelta(hours=2)
    again = queue.claim()
    assert again.id == job.id and again.attempts == 1


def test_error_must_be_a_short_code_not_text(q):
    queue, _ = q
    queue.enqueue(A, "spool")
    job = queue.claim()
    with pytest.raises(ValueError):
        queue.fail(job.id, "Rechnung Muster AG über CHF 1'957.04")


def test_done_uuid_can_be_queued_again(q):
    queue, _ = q
    first = queue.enqueue(A, "spool")
    queue.finish(queue.claim().id, "done")
    assert queue.enqueue(A, "menu") != first
