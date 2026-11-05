"""P3-7 review store + decisions (SPEC §4.12)."""
import pytest

from dt3agent import config
from dt3agent.rpc import RPCError
from dt3agent.service import Service
from tests.fakes import FakeDT3, FakeLlamaServer, ai_reply

A = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"


@pytest.fixture
def svc(tmp_path):
    server = FakeLlamaServer(reply=ai_reply(["Rechnung"]))
    dt3 = FakeDT3({A: {"name": "x", "tags": ["inbox"], "contentHash": "h1", "text": "Rechnung"}})
    cfg = config.load(tmp_path / "config.json")
    cfg["ai"]["url"] = server.url
    config.save(tmp_path / "config.json", cfg)
    s = Service(tmp_path, dt3)
    s.dt3 = dt3
    s.handle("process", {"uuid": A})
    assert s.tick() == "planned"   # dry-run: a planned item
    yield s
    s.close()
    server.close()


def item_id(s):
    return next(i["id"] for i in s.handle("review", {}) if i["kind"] == "planned")


def planned(s):
    return [i for i in s.handle("review", {}) if i["kind"] == "planned"]


def test_accept_applies_the_planned_tags_with_undo(svc):
    out = svc.handle("decide", {"id": item_id(svc), "decision": "accept"})
    assert out == {"applied": True}
    assert svc.dt3.records[A]["tags"] == ["inbox", "Rechnung"]
    assert planned(svc) == []
    assert svc.handle("undo", {})["restored"] == 1 and svc.dt3.records[A]["tags"] == ["inbox"]


def test_edit_applies_the_users_value(svc):
    svc.handle("decide", {"id": item_id(svc), "decision": "edit", "value": ["Vertrag"]})
    assert svc.dt3.records[A]["tags"] == ["inbox", "Vertrag"]


def test_reject_applies_nothing(svc):
    assert svc.handle("decide", {"id": item_id(svc), "decision": "reject"}) == {"applied": False}
    assert svc.dt3.records[A]["tags"] == ["inbox"] and planned(svc) == []


@pytest.mark.parametrize("params, code", [
    ({"id": 999, "decision": "accept"}, "no_open_item"),
    ({"decision": "maybe"}, "bad_decision"),
    ({"decision": "edit"}, "edit_needs_value"),
    ({"decision": "edit", "value": ["a,b"]}, "bad_value"),
])
def test_bad_decisions_are_refused(svc, params, code):
    params = {"id": item_id(svc), **params}   # the planned tags item unless the case sets an id
    with pytest.raises(RPCError) as e:
        svc.handle("decide", params)
    assert str(e.value) == code


def test_decided_twice_is_refused(svc):
    i = item_id(svc)
    svc.handle("decide", {"id": i, "decision": "reject"})
    with pytest.raises(RPCError):
        svc.handle("decide", {"id": i, "decision": "accept"})


def test_migration_keeps_old_items(tmp_path):
    from dt3agent import pipeline, queue, store
    from dt3agent.service import ENGINE_MIGRATIONS, STATE_MIGRATIONS
    old = queue.MIGRATIONS + pipeline.MIGRATIONS + STATE_MIGRATIONS   # schema before P3-7
    assert ENGINE_MIGRATIONS[:len(old)] == old
    con = store.open_db(tmp_path / "engine.db", old)
    with con:
        con.execute("INSERT INTO review_items (uuid, kind, code, payload_json, created_at) "
                    "VALUES (?, 'error', 'no_text', '{}', 't')", (A,))
    con.close()
    con = store.open_db(tmp_path / "engine.db", ENGINE_MIGRATIONS)
    assert con.execute("SELECT uuid, code, decision FROM review_items").fetchall() == [(A, "no_text", None)]
