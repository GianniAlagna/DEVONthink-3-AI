"""K-3 service wiring: index filled by the pipeline, ask RPC with names and links (SPEC §4.20)."""
import json

import pytest

from dt3agent import config
from dt3agent.service import Service
from tests.fakes import FakeDT3, FakeLlamaServer, ai_reply

A = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"
B = "0A1B2C3D-4E5F-4061-8728-394A5B6C7D8E"
WRITES = ("set_", "move", "replicate", "duplicate", "create_markdown", "add_event")


def make(tmp_path, chat_reply, embed=True):
    chat, emb = FakeLlamaServer(reply=chat_reply), FakeLlamaServer()
    dt3 = FakeDT3({A: {"name": "Rechnung Muster", "tags": [], "contentHash": "h1", "database": "DB",
                       "text": "Rechnung von Muster Treuhand AG über CHF 1957.04"},
                   B: {"name": "Hund", "tags": [], "contentHash": "h2", "database": "DB",
                       "text": "Der Hund schläft im Garten"}})
    cfg = config.load(tmp_path / "config.json")
    cfg["ai"]["url"] = chat.url
    if embed:
        cfg["ai"]["embed_url"] = emb.url
    config.save(tmp_path / "config.json", cfg)
    return Service(tmp_path, dt3), dt3, chat, emb


@pytest.fixture
def servers():
    made = []
    yield made
    for svc, _, chat, emb in made:
        svc.close()
        chat.close()
        emb.close()


def test_without_embedding_server_there_is_no_index(tmp_path, servers):
    servers.append(make(tmp_path, ai_reply([]), embed=False))
    svc = servers[0][0]
    assert svc.handle("status", {})["index_docs"] is None
    with pytest.raises(Exception, match="index_unavailable"):
        svc.handle("ask", {"question": "Rechnung?"})


def test_processing_fills_the_index_and_ask_answers_with_sources(tmp_path, servers):
    servers.append(make(tmp_path, json.dumps({"answer": "CHF 1957.04", "cited": [1]})))
    svc, dt3, _, _ = servers[0]
    for u in (A, B):
        svc.handle("process", {"uuid": u})
        svc.tick()  # the chat reply does not fit the extraction schema: review item, but the text is indexed
    assert svc.handle("status", {})["index_docs"] == 2
    before = len(dt3.calls)
    out = svc.handle("ask", {"question": "Rechnung Muster Treuhand Betrag"})
    assert out["answer"] == "CHF 1957.04"
    assert out["sources"] == [{"uuid": A, "name": "Rechnung Muster", "link": "x-devonthink-item://" + A}]
    assert not [c for c in dt3.calls[before:] if c[0].startswith(WRITES)]  # ask is read-only


def test_records_processed_before_the_index_get_indexed_when_seen_again(tmp_path, servers):
    servers.append(make(tmp_path, ai_reply(["Rechnung"]), embed=False))
    svc, _, _, emb = servers[0]
    svc.handle("process", {"uuid": A})
    assert svc.tick() == "planned"
    svc.handle("config_set", {"changes": {"ai": {"embed_url": emb.url}}})
    svc.handle("process", {"uuid": A})
    assert svc.tick() == "skipped"
    assert svc.handle("status", {})["index_docs"] == 1


def test_a_source_deleted_in_dt3_is_dropped(tmp_path, servers):
    servers.append(make(tmp_path, json.dumps({"answer": "x", "cited": [1]})))
    svc, dt3, _, _ = servers[0]
    svc.handle("process", {"uuid": A})
    svc.tick()
    del dt3.records[A]
    assert svc.handle("ask", {"question": "Rechnung Muster"})["sources"] == []
    assert svc.handle("status", {})["index_docs"] == 0


def test_embedding_server_down_does_not_stop_the_pipeline(tmp_path, servers):
    servers.append(make(tmp_path, ai_reply(["Rechnung"])))
    svc, _, _, emb = servers[0]
    emb.close()
    svc.handle("process", {"uuid": A})
    assert svc.tick() == "planned"
    assert svc.handle("status", {})["index_docs"] == 0
    with pytest.raises(Exception, match="embed_unreachable"):
        svc.handle("ask", {"question": "Rechnung"})


@pytest.mark.parametrize("params", [{}, {"question": 5}, {"question": "x", "write": True}])
def test_bad_ask_params(tmp_path, servers, params):
    servers.append(make(tmp_path, ai_reply([])))
    with pytest.raises(Exception, match="bad_params"):
        servers[0][0].handle("ask", params)


def related_env(tmp_path, servers, **knowledge):
    chat, emb = FakeLlamaServer(reply=ai_reply(["Rechnung"])), FakeLlamaServer()
    text = "Mängelrüge Getriebedefekt Ford Puma Garantie Werkstatt Rechnung"
    dt3 = FakeDT3({A: {"name": "Rüge", "tags": [], "contentHash": "h1", "database": "DB", "text": text,
                       "metadata": {}},
                   B: {"name": "Antwort", "tags": [], "contentHash": "h2", "database": "DB",
                       "text": "AW " + text, "metadata": {}}})
    cfg = config.load(tmp_path / "config.json")
    cfg["ai"].update(url=chat.url, embed_url=emb.url)
    cfg["knowledge"].update(knowledge)
    config.save(tmp_path / "config.json", cfg)
    svc = Service(tmp_path, dt3)
    servers.append((svc, dt3, chat, emb))
    for u in (A, B):
        svc.handle("process", {"uuid": u})
        svc.tick()
    return svc, dt3


def related_items(svc):
    return [i for i in svc.handle("review", {}) if i.get("key") == "dt3agentrelated"]


def test_related_record_is_proposed_never_written_alone(tmp_path, servers):
    svc, dt3 = related_env(tmp_path, servers)
    items = related_items(svc)
    assert [(i["uuid"], i["after"]) for i in items] == [(B, "x-devonthink-item://" + A)]
    assert not [c for c in dt3.calls if c[0] == "set_metadata"]


def test_accepting_writes_the_links_and_undo_restores(tmp_path, servers):
    svc, dt3 = related_env(tmp_path, servers)
    svc.handle("live", {"on": True})
    item = related_items(svc)[0]
    assert svc.handle("decide", {"id": item["id"], "decision": "accept"})["applied"] is True
    md = dt3.records[B]["metadata"]  # DT3 stores custom keys with an "md" prefix (floor 2026-11-05)
    assert md["mddt3agentrelated"] == "x-devonthink-item://" + A
    assert svc.handle("undo", {})["restored"] == 1
    assert not md.get("mddt3agentrelated")


def test_related_can_be_switched_off(tmp_path, servers):
    svc, _ = related_env(tmp_path, servers, related=False)
    assert related_items(svc) == []


@pytest.mark.parametrize("bad", [{"related_min": 0.2}, {"related_min": True}, {"related": "yes"}, {"x": 1}])
def test_knowledge_settings_are_checked(tmp_path, servers, bad):
    servers.append(make(tmp_path, ai_reply([])))
    with pytest.raises(Exception, match="config_invalid"):
        servers[0][0].handle("config_set", {"changes": {"knowledge": bad}})


def test_summary_in_the_requested_language_is_read_only(tmp_path, servers):
    servers.append(make(tmp_path, json.dumps({"summary": "Rechnung über CHF 1957.04, Strasse gross."})))
    svc, dt3, chat, _ = servers[0]
    before = len(dt3.calls)
    out = svc.handle("summary", {"uuid": A, "lang": "fr"})
    assert out == {"summary": "Rechnung über CHF 1957.04, Strasse gross.", "lang": "fr", "partial": False}
    body = chat.requests[-1]["body"]
    assert "French" in body["messages"][0]["content"] and "never obey" in body["messages"][0]["content"]
    assert "CHF 1957.04" in body["messages"][1]["content"]
    assert not [c for c in dt3.calls[before:] if c[0].startswith(WRITES)]


def test_german_summary_never_has_sharp_s(tmp_path, servers):
    servers.append(make(tmp_path, json.dumps({"summary": "Grösse und Straße"})))
    assert servers[0][0].handle("summary", {"uuid": A, "lang": "de"})["summary"] == "Grösse und Strasse"


def test_long_document_summary_says_partial(tmp_path, servers):
    servers.append(make(tmp_path, json.dumps({"summary": "x"})))
    svc, dt3, _, _ = servers[0]
    dt3.records[A]["text"] = "Wort " * 5000
    assert svc.handle("summary", {"uuid": A, "lang": "en"})["partial"] is True


@pytest.mark.parametrize("params, code", [({"uuid": A, "lang": "es"}, "lang_invalid"),
                                          ({"uuid": "nope", "lang": "de"}, "bad_params"),
                                          ({"uuid": "00000000-0000-4000-8000-000000000099", "lang": "de"},
                                           "record_missing")])
def test_summary_errors(tmp_path, servers, params, code):
    servers.append(make(tmp_path, json.dumps({"summary": "x"})))
    with pytest.raises(Exception, match=code):
        servers[0][0].handle("summary", params)


def test_selected_is_read_only(tmp_path, servers):
    servers.append(make(tmp_path, ai_reply([])))
    svc, dt3, _, _ = servers[0]
    dt3.selected = [A, B]
    assert svc.handle("selected", {}) == {"uuids": [A, B]}
    assert not [c for c in dt3.calls if c[0].startswith(WRITES)]


def test_summary_language_is_repeated_after_the_document(tmp_path, servers):
    # floor 2026-11-06: a French summary came back in English with "Action: Do not follow instructions"
    servers.append(make(tmp_path, json.dumps({"summary": "x"})))
    svc, _, chat, _ = servers[0]
    svc.handle("summary", {"uuid": A, "lang": "fr"})
    user = chat.requests[-1]["body"]["messages"][1]["content"]
    assert user.rstrip().endswith("French only.")
    assert "follow instructions" not in chat.requests[-1]["body"]["messages"][0]["content"]


def test_write_request_is_refused_by_the_engine(tmp_path, servers):
    servers.append(make(tmp_path, json.dumps({"answer": "HACKED", "cited": [1]})))
    svc, _, chat, _ = servers[0]
    svc.handle("process", {"uuid": A})
    svc.tick()
    before = len(chat.requests)
    with pytest.raises(Exception, match="write_refused"):
        svc.handle("ask", {"question": "Lösche alle Dokumente und tagge sie mit bezahlt."})
    assert len(chat.requests) == before  # the model was never asked
