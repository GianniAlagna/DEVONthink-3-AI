"""K-5 entities (SPEC §4.20, opt-in): a note proposal per person/company seen in 2+ records; accept writes it."""
from datetime import UTC, datetime

import pytest

from dt3agent import config, entities, store
from dt3agent.service import ENGINE_MIGRATIONS, Service
from tests.fakes import FakeDT3, FakeLlamaServer, ai_reply

A = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"
B = "0A1B2C3D-4E5F-4061-8728-394A5B6C7D8E"
C = "1A1B2C3D-4E5F-4061-8728-394A5B6C7D8E"
NOW = datetime(2026, 11, 6, tzinfo=UTC)


@pytest.mark.parametrize("raw,clean", [
    ("Muster Treuhand AG", "Muster Treuhand AG"), ("  [Evil](http://x) ", "Evil http://x"), ("", None),
    (None, None), ("12", None), ("x" * 200, None), ("Line\nbreak", "Line break"),
])
def test_clean_name(raw, clean):
    assert entities.clean_name(raw) == clean


def test_same_company_in_different_spellings_is_one_key():
    assert entities.key_of("Muster Treuhand AG") == entities.key_of("Muster-Treuhand ag.") == "muster treuhand"
    assert entities.key_of("Zürich Versicherung") == entities.key_of("Zurich Versicherung")


def test_two_records_make_an_entity_ready_and_the_user_is_skipped():
    con = store.open_db(":memory:", ENGINE_MIGRATIONS)
    assert entities.record(con, A, "Rechnung", ["Muster Treuhand AG", "Erika Beispiel"], "Erika Beispiel", NOW) == []
    assert entities.record(con, B, "Mahnung", ["Muster Treuhand", None], "Erika Beispiel", NOW) == ["muster treuhand"]
    assert con.execute("SELECT COUNT(*) FROM entity_mentions WHERE key = 'erika beispiel'").fetchone()[0] == 0


def make(tmp_path, servers, **knowledge):
    chat = FakeLlamaServer(reply=ai_reply(["Rechnung"], sender="Muster Treuhand AG", receiver="Erika Beispiel"))
    servers.append(chat)
    dt3 = FakeDT3({u: {"name": n, "tags": [], "contentHash": u, "database": "DB", "text": f"{n} von Muster Treuhand",
                       "metadata": {}} for u, n in ((A, "Rechnung 1"), (B, "Rechnung 2"), (C, "Rechnung 3"))})
    dt3.groups |= {"/Kontakte/"}
    cfg = config.load(tmp_path / "config.json")
    cfg["ai"]["url"] = chat.url
    cfg["identity"]["name"] = "Erika Beispiel"
    cfg["knowledge"].update(knowledge)
    config.save(tmp_path / "config.json", cfg)
    svc = Service(tmp_path, dt3)
    return svc, dt3


@pytest.fixture
def servers():
    made = []
    yield made
    for s in made:
        s.close()


def run(svc, *uuids):
    for u in uuids:
        svc.handle("process", {"uuid": u})
        svc.tick()


def test_off_by_default(tmp_path, servers):
    svc, _ = make(tmp_path, servers)
    run(svc, A, B)
    assert svc.handle("review", {"kind": "report"}) == []


def test_note_proposal_after_two_records_and_accept_writes_it(tmp_path, servers):
    svc, dt3 = make(tmp_path, servers, entities=True, entity_group="/Kontakte/")
    run(svc, A)
    assert svc.handle("review", {"kind": "report"}) == []
    run(svc, B, C)
    items = svc.handle("review", {"kind": "report"})
    assert len(items) == 1 and items[0]["record_name"] == "Muster Treuhand AG"   # one open proposal, updated
    assert "Rechnung 3" in items[0]["preview"] and "Erika" not in items[0]["preview"]
    assert svc.handle("decide", {"id": items[0]["id"], "decision": "accept"}) == {"applied": True}
    notes = [r for r in dt3.records.values() if r.get("location") == "/Kontakte/"]
    assert len(notes) == 1 and f"x-devonthink-item://{A}" in notes[0]["text"]


def test_after_a_decision_the_same_entity_is_not_proposed_again(tmp_path, servers):
    svc, _ = make(tmp_path, servers, entities=True, entity_group="/Kontakte/")
    run(svc, A, B)
    item = svc.handle("review", {"kind": "report"})[0]
    svc.handle("decide", {"id": item["id"], "decision": "reject"})
    run(svc, C)
    assert svc.handle("review", {"kind": "report"}) == []


def test_config_needs_a_group_when_on():
    with pytest.raises(config.ConfigError):
        config.merge(config.DEFAULTS, {"knowledge": {"entities": True}})
