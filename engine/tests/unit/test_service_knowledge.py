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
