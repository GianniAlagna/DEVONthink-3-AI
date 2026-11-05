"""P3-9c proposals and the full pipeline with settings (brief A3-A9)."""
import copy
from pathlib import Path

import pytest

from dt3agent import config, store
from dt3agent.adapter import DT3Adapter
from dt3agent.audit import AuditLog
from dt3agent.duplicates import MIGRATIONS as DUP
from dt3agent.pipeline import MIGRATIONS, Pipeline
from dt3agent.plan import plan
from dt3agent.review import MIGRATIONS as REVIEW
from dt3agent.undo import MIGRATIONS as UNDO
from dt3agent.undo import UndoJournal
from tests.fakes import FakeDT3
from tests.unit.test_pipeline import FakeAI

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "spike"
A = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"
TEXT = (FIXTURES / "invoice-de.txt").read_text(encoding="utf-8")
AI = {"type": "invoice", "sender": "Muster Treuhand AG", "receiver": None, "subject": "Rechnung 2026-0417",
      "summary": ["Rechnung Buchhaltung Q1", "Total CHF 1957.04", "Zahlbar bis 17. Mai 2026"]}


def cfg(**changes):
    c = copy.deepcopy(config.DEFAULTS)
    c["identity"]["name"] = "Erika Beispiel"
    for k, v in changes.items():
        c[k] = {**c[k], **v}
    return c


def by_field(props):
    return {(p.field, p.key): p for p in props}


def test_proposals_for_the_invoice():
    p = by_field(plan({"name": "scan.txt", "created": "2026-11-04T09:00:00Z"}, TEXT, AI, cfg()))
    assert p[("name", None)].value == "20260417000000_Muster-Treuhand-AG_Erika-Beispiel_Rechnung-2026-0417"
    assert p[("name", None)].confidence < 0.85          # sender and subject come from the AI
    assert p[("comment", None)].value.count("\n") == 2
    assert p[("metadata", "dt3agentdate")].value == "2026-04-17"
    assert p[("metadata", "dt3agenttotal")].value == "CHF 1957.04"
    assert p[("metadata", "dt3agentiban")].value == "CH4431999123000889012"
    assert ("location", None) not in p                   # filing is off by default


def test_filing_only_into_allowed_groups_or_the_review_group():
    on = cfg(filing={"enabled": True, "groups": {"invoice": "/Finanzen/Rechnungen/"}})
    assert by_field(plan({}, TEXT, AI, on))[("location", None)].value == "/_AI-Review/"   # type 0.8 < 0.85
    lowered = cfg(filing={"enabled": True, "groups": {"invoice": "/Finanzen/Rechnungen/"}}, thresholds={"apply": 0.8})
    assert by_field(plan({}, TEXT, AI, lowered))[("location", None)].value == "/Finanzen/Rechnungen/"


def test_urgent_letter_proposal():
    p = by_field(plan({}, "Zahlungsbefehl Nr. 1 vom 3. März 2026", {"summary": []}, cfg()))
    assert p[("urgent", None)].value == ["Zahlungsbefehl"]


@pytest.fixture
def run(tmp_path):
    dt3 = FakeDT3({A: {"name": "scan.txt", "tags": [], "comment": "", "location": "/Inbox/", "metadata": {},
                       "contentHash": "h", "text": TEXT, "created": "2026-11-04T09:00:00Z"}})
    con = store.open_db(tmp_path / "e.db", MIGRATIONS + REVIEW + DUP)
    ad = DT3Adapter(dt3, UndoJournal(store.open_db(tmp_path / "u.db", UNDO)), AuditLog(tmp_path / "a"))
    return dt3, con, ad


def test_live_applies_rule_fields_and_reviews_ai_fields(run):
    dt3, con, ad = run
    ai = FakeAI(["Rechnung"])
    ai.extra = AI
    out = Pipeline(ad, ai, con, dry_run=False, settings=cfg()).process(A, batch_id="b1")
    r = dt3.records[A]
    assert out.status == "applied" and r["tags"] == ["Rechnung"]
    assert r["metadata"]["mddt3agentdate"] == "2026-04-17" and r["metadata"]["mddt3agenttotal"] == "CHF 1957.04"
    assert r["name"] == "scan.txt"                       # AI-based name waits for the user
    fields = [f for (f,) in con.execute("SELECT json_extract(payload_json, '$.field') FROM review_items "
                                        "WHERE kind = 'field'")]
    assert sorted(fields) == ["comment", "name"]
    assert ad.undo_last_batch()["restored"] >= 4 and r["metadata"]["mddt3agentdate"] == ""


def test_dry_run_writes_nothing_and_plans_everything(run):
    dt3, con, ad = run
    ai = FakeAI(["Rechnung"])
    ai.extra = AI
    assert Pipeline(ad, ai, con, dry_run=True, settings=cfg()).process(A, batch_id="b1").status == "planned"
    assert not [c for c in dt3.calls if c[0] not in ("info", "duplicates") and not c[0].startswith("read")]
    assert con.execute("SELECT COUNT(*) FROM review_items WHERE kind = 'field'").fetchone()[0] >= 5


def test_field_review_item_accepted_through_the_service(tmp_path):
    import json as _json

    from dt3agent.service import Service
    from tests.fakes import FakeLlamaServer, ai_reply
    server = FakeLlamaServer(reply=ai_reply(["Rechnung"], sender="Muster Treuhand AG", subject="Rechnung 2026-0417"))
    dt3 = FakeDT3({A: {"name": "scan.txt", "tags": [], "comment": "", "location": "/Inbox/", "metadata": {},
                       "contentHash": "h", "text": TEXT, "created": "2026-11-04T09:00:00Z"}})
    c = config.load(tmp_path / "config.json")
    c["ai"]["url"], c["dry_run"], c["identity"]["name"] = server.url, False, "Erika Beispiel"
    config.save(tmp_path / "config.json", c)
    svc = Service(tmp_path, dt3)
    try:
        svc.handle("process", {"uuid": A})
        assert svc.tick() == "applied"
        name_item = next(i for i in svc.handle("review", {}) if i["kind"] == "field"
                         and _json.loads(svc.con.execute("SELECT payload_json FROM review_items WHERE id = ?",
                                                         (i["id"],)).fetchone()[0])["field"] == "name")
        assert svc.handle("decide", {"id": name_item["id"], "decision": "accept"}) == {"applied": True}
        assert dt3.records[A]["name"].startswith("20260417000000_Muster-Treuhand-AG_Erika-Beispiel")
        assert svc.handle("undo", {})["restored"] == 1 and dt3.records[A]["name"] == "scan.txt"
    finally:
        svc.close()
        server.close()
