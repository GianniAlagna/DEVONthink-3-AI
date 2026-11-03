import json

import pytest

from dt3agent import store
from dt3agent.adapter import DT3Adapter, NotDT3Error
from dt3agent.audit import AuditLog
from dt3agent.undo import MIGRATIONS, UndoJournal
from tests.fakes import FakeDT3

A = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"
B = "727717FF-9696-4520-8BD9-9F413AE2A7FB"


@pytest.fixture
def env(tmp_path):
    dt3 = FakeDT3({A: {"name": "scan.pdf", "tags": ["inbox"]}, B: {"name": "b.pdf", "tags": []}})
    journal = UndoJournal(store.open_db(tmp_path / "undo.db", MIGRATIONS))
    adapter = DT3Adapter(dt3, journal, AuditLog(tmp_path / "audit"))
    return dt3, journal, adapter, tmp_path


def audit_lines(tmp_path):
    return [json.loads(x) for f in (tmp_path / "audit").glob("*.jsonl") for x in f.read_text().splitlines()]


def test_set_tags_journals_old_value_before_writing(env):
    dt3, journal, adapter, _ = env
    adapter.set_tags(A, ["invoice", "2026"], batch_id="b1", actor="ai")
    assert dt3.records[A]["tags"] == ["invoice", "2026"]
    (entry,) = journal.entries("b1")
    assert entry.uuid == A and entry.field == "tags" and entry.old == ["inbox"] and entry.new == ["invoice", "2026"]
    verbs = [v for v, _ in dt3.calls]
    assert verbs.index("read") < verbs.index("set_tags")  # snapshot taken before the write


def test_undo_last_batch_restores_exactly(env):
    dt3, _, adapter, tmp_path = env
    adapter.set_tags(A, ["x"], batch_id="b1", actor="ai")
    adapter.set_tags(B, ["y"], batch_id="b1", actor="ai")
    result = adapter.undo_last_batch()
    assert result == {"restored": 2, "conflicts": []}
    assert dt3.records[A]["tags"] == ["inbox"] and dt3.records[B]["tags"] == []
    assert [e["result"] for e in audit_lines(tmp_path)].count("undone") == 2
    assert adapter.undo_last_batch() == {"restored": 0, "conflicts": []}  # nothing left to undo


def test_undo_refuses_when_user_changed_record_since(env):
    dt3, _, adapter, _ = env
    adapter.set_tags(A, ["x"], batch_id="b1", actor="ai")
    dt3.records[A]["tags"] = ["edited-by-user"]
    assert adapter.undo_last_batch() == {"restored": 0, "conflicts": [A]}
    assert dt3.records[A]["tags"] == ["edited-by-user"]  # user's change is kept


def test_undo_single_record(env):
    dt3, _, adapter, _ = env
    adapter.set_tags(A, ["x"], batch_id="b1", actor="ai")
    adapter.set_tags(B, ["y"], batch_id="b1", actor="ai")
    assert adapter.undo_record(B) == {"restored": 1, "conflicts": []}
    assert dt3.records[A]["tags"] == ["x"] and dt3.records[B]["tags"] == []


def test_adapter_refuses_non_dt3(tmp_path):
    dt3 = FakeDT3({A: {"tags": []}}, version="4.0.1")
    adapter = DT3Adapter(dt3, UndoJournal(store.open_db(tmp_path / "u.db", MIGRATIONS)), AuditLog(tmp_path / "a"))
    with pytest.raises(NotDT3Error):
        adapter.set_tags(A, ["x"], batch_id="b1", actor="ai")
    assert ("set_tags", {"uuid": A, "tags": ["x"]}) not in dt3.calls
