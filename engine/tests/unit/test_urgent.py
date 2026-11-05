"""B-6 urgent letters (brief B6): review item with legal hints marked "verify"; accept moves to _Urgent."""
import pytest

from dt3agent import config
from dt3agent.rpc import RPCError
from dt3agent.service import Service
from tests.fakes import FakeDT3, FakeLlamaServer, ai_reply

A = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"
TEXT = ("Betreibungsamt Zürich 1. Zahlungsbefehl Betreibung Nr. 26001234 vom 3. März 2026. "
        "Schuldner: Erika Beispiel. Forderung CHF 1957.04 nebst Zins.")


def test_hint_for_a_payment_order_says_verify():
    from dt3agent.plan import plan
    from tests.unit.test_plan import by_field, cfg
    p = by_field(plan({}, TEXT, {"summary": []}, cfg()))[("urgent", None)]
    assert "Zahlungsbefehl" in p.value
    assert p.hints == ("Rechtsvorschlag: innert 10 Tagen nach Zustellung (SchKG Art. 74 Abs. 1) – bitte prüfen",)


def test_no_hint_without_a_known_deadline():
    from dt3agent.plan import plan
    from tests.unit.test_plan import by_field, cfg
    p = by_field(plan({}, "Vorladung vor Gericht am 3. März 2026", {"summary": []}, cfg()))[("urgent", None)]
    assert p.hints == ()


def test_tax_office_is_urgent_by_default():
    from dt3agent.rules import keywords
    assert keywords.scan("Kantonales Steueramt Zürich, Mahnung", config.DEFAULTS["keywords"]).urgent


@pytest.fixture
def svc(tmp_path):
    server = FakeLlamaServer(reply=ai_reply(["Betreibung"]))
    dt3 = FakeDT3({A: {"name": "zb.pdf", "tags": [], "contentHash": "h1", "text": TEXT, "location": "/Inbox/"}})
    dt3.groups |= {"/_Urgent/"}
    c = config.load(tmp_path / "config.json")
    c["ai"]["url"], c["dry_run"] = server.url, False
    config.save(tmp_path / "config.json", c)
    s = Service(tmp_path, dt3)
    s.dt3 = dt3
    s.handle("process", {"uuid": A})
    s.tick()
    yield s
    s.close()
    server.close()


def urgent(s):
    return [i for i in s.handle("review", {}) if i["kind"] == "urgent"]


def test_review_row_and_status_count(svc):
    row = urgent(svc)[0]
    assert row["words"][0] == "Betreibungsamt" and row["group"] == "/_Urgent/"
    assert row["hints"][0].endswith("bitte prüfen") and row["actions"] == ["accept", "reject"]
    assert svc.handle("status", {})["urgent_open"] == 1  # the app notifies on this (Phase 5)


def test_accept_moves_to_the_urgent_group_and_never_tags(svc):
    assert svc.handle("decide", {"id": urgent(svc)[0]["id"], "decision": "accept"}) == {"applied": True}
    r = svc.dt3.records[A]
    assert r["location"] == "/_Urgent/" and "Zahlungsbefehl" not in r["tags"]
    assert svc.handle("status", {})["urgent_open"] == 0
    assert svc.handle("undo", {})["restored"] == 1 and r["location"] == "/Inbox/"


def test_missing_urgent_group_is_reported_and_item_stays(svc):
    svc.dt3.groups.discard("/_Urgent/")  # the engine never creates groups
    item = urgent(svc)[0]
    with pytest.raises(RPCError) as e:
        svc.handle("decide", {"id": item["id"], "decision": "accept"})
    assert str(e.value) == "group_not_found" and urgent(svc)


def test_reject_and_edit(svc):
    item = urgent(svc)[0]
    with pytest.raises(RPCError):
        svc.handle("decide", {"id": item["id"], "decision": "edit", "value": ["x"]})
    assert svc.handle("decide", {"id": item["id"], "decision": "reject"}) == {"applied": False}
    assert svc.dt3.records[A]["location"] == "/Inbox/"
