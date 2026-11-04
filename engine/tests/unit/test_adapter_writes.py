"""P3-9b write verbs with undo: name, comment, metadata, move (SPEC §4.5, §4.8)."""
import pytest

from dt3agent import store
from dt3agent.adapter import DT3Adapter
from dt3agent.audit import AuditLog
from dt3agent.bridge import BridgeError, validate
from dt3agent.undo import MIGRATIONS, UndoJournal
from tests.fakes import FakeDT3

A = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"


@pytest.fixture
def env(tmp_path):
    dt3 = FakeDT3({A: {"name": "scan.pdf", "tags": [], "comment": "", "location": "/Inbox/", "metadata": {}}})
    adapter = DT3Adapter(dt3, UndoJournal(store.open_db(tmp_path / "u.db", MIGRATIONS)), AuditLog(tmp_path / "a"))
    return dt3, adapter


def test_all_fields_written_then_undone_exactly(env):
    dt3, ad = env
    ad.set_field(A, "name", "20260417000000_A_B_C", batch_id="b", actor="rule")
    ad.set_field(A, "comment", "Zeile 1\nZeile 2\nZeile 3", batch_id="b", actor="ai")
    ad.set_field(A, "metadata", "rule", key="dt3agentsource", batch_id="b", actor="rule")
    ad.set_field(A, "location", "/_AI-Review/", batch_id="b", actor="rule")
    r = dt3.records[A]
    assert (r["name"], r["location"], r["metadata"]["mddt3agentsource"]) == (
        "20260417000000_A_B_C", "/_AI-Review/", "rule")
    assert ad.undo_last_batch() == {"restored": 4, "conflicts": []}
    assert (r["name"], r["comment"], r["location"]) == ("scan.pdf", "", "/Inbox/")
    assert r["metadata"]["mddt3agentsource"] == ""   # DT3 cannot remove a key; undo empties it


def test_unchanged_value_writes_nothing(env):
    dt3, ad = env
    assert ad.set_field(A, "name", "scan.pdf", batch_id="b", actor="rule") is False
    assert not [c for c in dt3.calls if c[0] == "set_name"]


def test_user_change_after_write_is_a_conflict(env):
    dt3, ad = env
    ad.set_field(A, "name", "new", batch_id="b", actor="rule")
    dt3.records[A]["name"] = "renamed by user"
    assert ad.undo_last_batch() == {"restored": 0, "conflicts": [A]}
    assert dt3.records[A]["name"] == "renamed by user"


def test_move_only_into_existing_groups(env):
    _, ad = env
    with pytest.raises(BridgeError):
        ad.set_field(A, "location", "/Does/Not/Exist/", batch_id="b", actor="rule")


@pytest.mark.parametrize("verb, args", [
    ("set_name", {"uuid": A, "name": ""}),
    ("set_name", {"uuid": A, "name": "x" * 256}),
    ("set_name", {"uuid": A, "name": "a\nb"}),
    ("set_comment", {"uuid": A, "comment": "x" * 4001}),
    ("set_metadata", {"uuid": A, "key": "Bad Key", "value": "v"}),
    ("set_metadata", {"uuid": A, "key": "ok", "value": "x" * 1001}),
    ("move", {"uuid": A, "location": "relative/path"}),
    ("move", {"uuid": A, "location": "/a/../b/"}),
    ("delete", {"uuid": A}),
])
def test_bridge_refuses_bad_writes(verb, args):
    with pytest.raises(BridgeError):
        validate(verb, args)


def test_writes_refused_for_dt4(tmp_path):
    from dt3agent.adapter import NotDT3Error
    dt4 = FakeDT3({A: {"name": "x", "tags": []}}, version="4.0")
    ad = DT3Adapter(dt4, UndoJournal(store.open_db(tmp_path / "u.db", MIGRATIONS)), AuditLog(tmp_path / "a"))
    with pytest.raises(NotDT3Error):
        ad.set_field(A, "name", "y", batch_id="b", actor="rule")
