"""P3-10 duplicates and case folders (brief A10 / §5.2): review items only, actions after the user's choice."""
import pytest

from dt3agent import config, duplicates, store
from dt3agent.rpc import RPCError
from dt3agent.service import Service
from tests.fakes import FakeDT3, FakeLlamaServer, ai_reply

A = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"
B = "727717FF-9696-4520-8BD9-9F413AE2A7FB"
TEXT = ("Muster Treuhand AG stellt Rechnung Nr. 2026-0417 für die Buchhaltung des ersten Quartals 2026. "
        "Der Betrag von CHF 1957.04 ist zahlbar innert 30 Tagen auf das Konto der Muster Treuhand AG.")


def test_sketch_similarity():
    a, b = duplicates.sketch(TEXT), duplicates.sketch(TEXT + " Freundliche Grüsse")
    assert duplicates.similarity(a, a) == 1.0 and duplicates.similarity(a, b) >= 0.8
    assert duplicates.similarity(a, duplicates.sketch("Ganz anderer Text über Ferien in den Bergen")) < 0.2
    assert all(isinstance(h, int) for h in a)   # only hashes are stored, never text


def test_near_stores_and_finds_and_respects_dismissal(tmp_path):
    con = store.open_db(tmp_path / "d.db", duplicates.MIGRATIONS)
    assert duplicates.near(con, A, TEXT, 0.8) == []
    assert [u for u, _ in duplicates.near(con, B, TEXT, 0.8)] == [A]
    duplicates.dismiss(con, B, A)
    assert duplicates.near(con, B, TEXT, 0.8) == []


@pytest.fixture
def svc(tmp_path):
    server = FakeLlamaServer(reply=ai_reply(["Rechnung"]))
    dt3 = FakeDT3({A: {"name": "a.pdf", "tags": [], "contentHash": "h1", "text": TEXT, "location": "/Inbox/"},
                   B: {"name": "b.pdf", "tags": [], "contentHash": "h2", "text": TEXT, "location": "/Inbox/",
                       "duplicates": [A]}})
    dt3.groups |= {"/Recht/Fall-X/", "/_Duplicates/"}
    c = config.load(tmp_path / "config.json")
    c["ai"]["url"], c["dry_run"] = server.url, False
    c["cases"] = [{"name": "Fall X", "group": "/Recht/Fall-X/", "words": ["Muster Treuhand AG"]}]
    config.save(tmp_path / "config.json", c)
    s = Service(tmp_path, dt3)
    s.dt3 = dt3
    for u in (A, B):
        s.handle("process", {"uuid": u})
        s.tick()
    yield s
    s.close()
    server.close()


def items(s, kind):
    return [i for i in s.handle("review", {}) if i["kind"] == kind]


def test_duplicate_and_case_become_review_items_only(svc):
    dups = items(svc, "duplicate")
    assert [d["uuid"] for d in dups] == [B] and dups[0]["code"] == "duplicate_exact"
    assert {c["uuid"] for c in items(svc, "case")} == {A, B}
    assert "duplicate" not in svc.dt3.records[B]["tags"] and "replicants" not in svc.dt3.records[A]


def test_not_a_duplicate_is_remembered(svc):
    d = items(svc, "duplicate")[0]
    assert svc.handle("decide", {"id": d["id"], "decision": "reject"}) == {"applied": False}
    assert duplicates.dismissed(svc.con, B, A)


def test_mark_as_duplicate_tags_and_moves(svc):
    svc.handle("decide", {"id": items(svc, "duplicate")[0]["id"], "decision": "accept"})
    r = svc.dt3.records[B]
    assert "duplicate" in r["tags"] and r["location"] == "/_Duplicates/"
    assert svc.handle("undo", {})["restored"] == 2 and r["location"] == "/Inbox/"


@pytest.mark.parametrize("choice", ["replicate /Recht/Fall-X/", "copy /Recht/Fall-X/", "link /Recht/Fall-X/"])
def test_case_choices(svc, choice):
    case = next(c for c in items(svc, "case") if c["uuid"] == A)
    assert svc.handle("decide", {"id": case["id"], "decision": "edit", "value": choice.split()}) == {"applied": True}
    recs = svc.dt3.records
    if choice.startswith("replicate"):
        assert recs[A]["replicants"] == ["/Recht/Fall-X/"]
    elif choice.startswith("copy"):
        copy = next(r for u, r in recs.items() if u not in (A, B))
        assert copy["metadata"]["mddt3agentoriginal"] == f"x-devonthink-item://{A}"
    else:
        note = next(r for u, r in recs.items() if u not in (A, B))
        assert f"x-devonthink-item://{A}" in note["text"] and note["location"] == "/Recht/Fall-X/"


def test_case_accept_replicates(svc):
    case = next(c for c in items(svc, "case") if c["uuid"] == A)
    svc.handle("decide", {"id": case["id"], "decision": "accept"})
    assert svc.dt3.records[A]["replicants"] == ["/Recht/Fall-X/"]


@pytest.mark.parametrize("value", [["delete"], ["replicate", "relative"], ["copy"]])
def test_bad_a10_choices_are_refused(svc, value):
    with pytest.raises(RPCError):
        svc.handle("decide", {"id": items(svc, "case")[0]["id"], "decision": "edit", "value": value})


def test_missing_group_is_reported(svc):
    case = next(c for c in items(svc, "case") if c["uuid"] == A)
    with pytest.raises(RPCError) as e:
        svc.handle("decide", {"id": case["id"], "decision": "edit", "value": ["replicate", "/Nope/"]})
    assert str(e.value) == "group_not_found"


def test_failed_decision_keeps_the_item_open(svc):
    # Floor 2026-11-05: decide on a case with a missing group said group_not_found, but the item vanished.
    case = next(c for c in items(svc, "case") if c["uuid"] == A)
    with pytest.raises(RPCError):
        svc.handle("decide", {"id": case["id"], "decision": "edit", "value": ["replicate", "/Nope/"]})
    assert case["id"] in [c["id"] for c in items(svc, "case")]
