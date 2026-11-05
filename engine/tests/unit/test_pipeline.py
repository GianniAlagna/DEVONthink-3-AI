"""Pipeline skeleton (SPEC §4.13, Phase 2 T8): read → text → AI tags → dry-run plan | live write with undo."""
import json
from datetime import UTC, datetime

import pytest

from dt3agent import queue as queuemod
from dt3agent import store
from dt3agent.adapter import DT3Adapter
from dt3agent.ai import AIError, Extraction
from dt3agent.audit import AuditLog
from dt3agent.pipeline import MIGRATIONS, Pipeline
from dt3agent.undo import MIGRATIONS as UNDO_MIGRATIONS
from dt3agent.undo import UndoJournal
from tests.fakes import FakeDT3

A = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"


class FakeAI:
    def __init__(self, tags=None, error=None):
        self.tags, self.error, self.calls, self.extra = tags or [], error, 0, {}

    def extract(self, text, schema, lang_hint=None, task=None):
        self.calls += 1
        self.schema, self.task = schema, task
        if self.error:
            raise self.error
        obj = {**self.extra, "tags": self.tags}
        return Extraction(obj, json.dumps(obj))


@pytest.fixture
def env(tmp_path):
    dt3 = FakeDT3({A: {"name": "scan.pdf", "tags": ["inbox"], "contentHash": "h1", "text": "Rechnung 4711"}})
    con = store.open_db(tmp_path / "engine.db", MIGRATIONS + queuemod.MIGRATIONS)
    adapter = DT3Adapter(dt3, UndoJournal(store.open_db(tmp_path / "undo.db", UNDO_MIGRATIONS)),
                         AuditLog(tmp_path / "audit"))
    return dt3, con, adapter, tmp_path


def make(env, ai, dry_run, vocabulary=None):
    _, con, adapter, _ = env
    return Pipeline(adapter, ai, con, dry_run=dry_run, vocabulary=vocabulary)


def audit(tmp_path):
    return [json.loads(x) for f in (tmp_path / "audit").glob("*.jsonl") for x in f.read_text().splitlines()]


def test_dry_run_plans_and_writes_nothing(env):
    dt3, con, _, tmp = env
    out = make(env, FakeAI(["invoice"]), dry_run=True).process(A, batch_id="b1")
    assert out.status == "planned" and out.tags_add == ["invoice"]
    assert dt3.records[A]["tags"] == ["inbox"]
    assert not [c for c in dt3.calls if c[0] == "set_tags"]
    kind, payload = con.execute("SELECT kind, payload_json FROM review_items").fetchone()
    assert kind == "planned" and json.loads(payload) == {"tags_add": ["invoice"]}
    assert audit(tmp)[-1]["result"] == "dry_run"


def test_live_run_writes_with_undo_and_is_idempotent(env):
    dt3, _, adapter, _ = env
    ai = FakeAI(["invoice", "inbox"])
    p = make(env, ai, dry_run=False)
    out = p.process(A, batch_id="b1")
    assert out.status == "applied" and out.tags_add == ["invoice"]
    assert dt3.records[A]["tags"] == ["inbox", "invoice"]
    # same contentHash -> skipped, AI not asked again
    assert p.process(A, batch_id="b2").status == "skipped" and ai.calls == 1
    # undo restores exactly
    assert adapter.undo_last_batch()["restored"] == 1 and dt3.records[A]["tags"] == ["inbox"]


def test_changed_content_is_processed_again(env):
    dt3, _, _, _ = env
    ai = FakeAI(["invoice"])
    p = make(env, ai, dry_run=False)
    p.process(A, batch_id="b1")
    dt3.records[A]["contentHash"] = "h2"
    p.process(A, batch_id="b2")
    assert ai.calls == 2


def test_dry_run_does_not_mark_processed(env):
    ai = FakeAI(["invoice"])
    make(env, ai, dry_run=True).process(A, batch_id="b1")
    assert make(env, ai, dry_run=False).process(A, batch_id="b2").status == "applied"


@pytest.mark.parametrize("code", ["ai_invalid_json", "ai_schema_mismatch", "ai_too_long"])
def test_bad_ai_output_goes_to_review_never_written(env, code):
    dt3, con, _, tmp = env
    out = make(env, FakeAI(error=AIError(code, raw="garbage")), dry_run=False).process(A, batch_id="b1")
    assert out.status == "review" and out.code == code
    assert dt3.records[A]["tags"] == ["inbox"]
    kind, rcode, payload = con.execute("SELECT kind, code, payload_json FROM review_items").fetchone()
    assert (kind, rcode) == ("error", code) and json.loads(payload) == {"raw": "garbage"}
    assert "garbage" not in json.dumps(audit(tmp))


def test_transient_ai_error_is_raised_for_retry(env):
    with pytest.raises(AIError):
        make(env, FakeAI(error=AIError("ai_unreachable")), dry_run=False).process(A, batch_id="b1")


def test_empty_text_goes_to_review_without_ai(env):
    dt3, _, _, _ = env
    dt3.records[A]["text"] = "   "
    ai = FakeAI(["x"])
    out = make(env, ai, dry_run=False).process(A, batch_id="b1")
    assert (out.status, out.code, ai.calls) == ("review", "no_text", 0)


def test_vocabulary_limits_and_normalises_tags(env):
    dt3, _, _, _ = env
    out = make(env, FakeAI(["Invoice", "secret-new-tag", " ", "a,b"]), dry_run=False,
               vocabulary=["invoice", "contract"]).process(A, batch_id="b1")
    assert out.tags_add == ["invoice"] and dt3.records[A]["tags"] == ["inbox", "invoice"]


def test_no_usable_tags_goes_to_review(env):
    out = make(env, FakeAI(["unknown"]), dry_run=False, vocabulary=["invoice"]).process(A, batch_id="b1")
    assert (out.status, out.code) == ("review", "no_valid_tags")


def test_run_once_maps_outcomes_to_queue_states(env):
    _, con, _, _ = env
    clock = lambda: datetime(2026, 11, 4, tzinfo=UTC)  # noqa: E731
    q = queuemod.Queue(con, clock)
    q.enqueue(A, "spool")
    assert make(env, FakeAI(["invoice"]), dry_run=True).run_once(q) == "planned"
    assert q.counts() == {"review": 1}
    q.enqueue(A, "spool")
    assert make(env, FakeAI(error=AIError("ai_unreachable")), dry_run=False).run_once(q) == "ai_unreachable"
    assert q.counts() == {"review": 1, "failed": 1}
    assert make(env, FakeAI(), dry_run=False).run_once(q) is None  # nothing due (back-off)


def test_bridge_errors_are_retried_with_a_safe_code(env):
    _, con, _, _ = env
    q = queuemod.Queue(con, lambda: datetime(2026, 11, 4, tzinfo=UTC))
    q.enqueue("727717FF-9696-4520-8BD9-9F413AE2A7FB", "spool")  # unknown record
    assert make(env, FakeAI(["x"]), dry_run=False).run_once(q) == "not_found"
    assert q.counts() == {"failed": 1}


def test_vocabulary_becomes_a_schema_enum_and_the_task_asks_for_tags(env):
    ai = FakeAI(["invoice"])
    make(env, ai, dry_run=True, vocabulary=["invoice", "contract"]).process(A, batch_id="b1")
    assert ai.schema["properties"]["tags"]["items"]["enum"] == ["invoice", "contract"]
    assert "tags" in ai.task and "allowed list" in ai.task
