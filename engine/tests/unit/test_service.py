"""Engine service (T9): config + queue + pipeline + rpc methods, driven tick by tick."""
import json

import pytest

from dt3agent import config
from dt3agent.service import Service
from tests.fakes import FakeDT3, FakeLlamaServer, ai_reply

A = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"


@pytest.fixture
def env(tmp_path):
    server = FakeLlamaServer(reply=ai_reply(["Rechnung"]))
    dt3 = FakeDT3({A: {"name": "x", "tags": [], "contentHash": "h1", "text": "Rechnung"}})
    cfg = config.load(tmp_path / "config.json")
    cfg["ai"]["url"] = server.url
    config.save(tmp_path / "config.json", cfg)
    svc = Service(tmp_path, dt3)
    yield svc, dt3, tmp_path
    svc.close()
    server.close()


def test_status_reports_safe_defaults(env):
    svc, _, _ = env
    s = svc.handle("status", {})
    assert s["dry_run"] is True and s["paused"] is False and s["ai_configured"] is True
    assert s["dt3_version"] == "3.9.17" and s["queue"] == {} and s["review_items"] == 0


def test_process_then_tick_in_dry_run_writes_nothing(env):
    svc, dt3, _ = env
    assert svc.handle("process", {"uuid": A}) == {"queued": True}
    assert svc.tick() == "planned"
    assert dt3.records[A]["tags"] == [] and dt3.records[A]["name"] == "x"
    kinds = sorted(i["kind"] for i in svc.handle("review", {}))
    assert kinds.count("planned") == 1 and set(kinds) <= {"planned", "field"}  # tags + field proposals, no write
    assert not [c for c in dt3.calls if c[0].startswith("set_") or c[0] == "move"]


def test_live_mode_writes_and_undo_restores(env):
    svc, dt3, tmp = env
    assert svc.handle("live", {"on": True}) == {"dry_run": False}
    assert config.load(tmp / "config.json")["dry_run"] is False  # persisted
    svc.handle("process", {"uuid": A})
    assert svc.tick() == "applied" and dt3.records[A]["tags"] == ["Rechnung"]
    assert svc.handle("undo", {}) == {"restored": 1, "conflicts": []}
    assert dt3.records[A]["tags"] == []


def test_pause_stops_processing_and_survives_restart(env):
    svc, dt3, tmp = env
    svc.handle("pause", {})
    svc.handle("process", {"uuid": A})
    assert svc.tick() is None
    svc.close()
    svc2 = Service(tmp, dt3)
    try:
        assert svc2.handle("status", {})["paused"] is True
        svc2.handle("resume", {})
        assert svc2.tick() == "planned"
    finally:
        svc2.close()


def test_spool_files_are_picked_up(env):
    svc, _, tmp = env
    spool = tmp / "spool"
    assert spool.is_dir() and (spool.stat().st_mode & 0o077) == 0  # created private
    (spool / f"{A}.json").write_text(json.dumps({"uuid": A}))
    import os
    import time
    old = time.time() - 10
    os.utime(spool / f"{A}.json", (old, old))
    assert svc.tick() == "planned"


def test_no_ai_configured_means_jobs_wait(tmp_path):
    dt3 = FakeDT3({A: {"name": "x", "tags": [], "contentHash": "h1", "text": "t"}})
    svc = Service(tmp_path, dt3)
    try:
        svc.handle("process", {"uuid": A})
        assert svc.tick() is None and svc.handle("status", {})["ai_configured"] is False
    finally:
        svc.close()


@pytest.mark.parametrize("method, params", [
    ("process", {"uuid": "nope"}), ("live", {"on": "yes"}), ("delete", {}), ("status", {"x": 1}),
])
def test_bad_calls_are_refused(env, method, params):
    from dt3agent.rpc import RPCError
    with pytest.raises(RPCError):
        env[0].handle(method, params)


def test_default_vocabulary_is_sent_as_enum(tmp_path):
    server = FakeLlamaServer(reply=ai_reply(["Rechnung"]))
    dt3 = FakeDT3({A: {"name": "x", "tags": [], "contentHash": "h1", "text": "Rechnung"}})
    cfg = config.load(tmp_path / "config.json")
    cfg["ai"]["url"] = server.url
    config.save(tmp_path / "config.json", cfg)
    svc = Service(tmp_path, dt3)
    try:
        svc.handle("process", {"uuid": A})
        assert svc.tick() == "planned"
        schema = server.requests[0]["body"]["response_format"]["json_schema"]["schema"]
        assert schema["properties"]["tags"]["items"]["enum"] == config.DEFAULTS["tags"]["vocabulary"]
    finally:
        svc.close()
        server.close()


def test_process_selected_queues_the_records_selected_in_dt3(env):
    svc, dt3, _ = env
    dt3.selected = [A]
    assert svc.handle("process_selected", {}) == {"queued": 1}
    assert svc.handle("status", {})["queue"] == {"queued": 1}


def test_process_selected_with_nothing_selected(env):
    svc, dt3, _ = env
    dt3.selected = []
    from dt3agent.rpc import RPCError
    with pytest.raises(RPCError) as e:
        svc.handle("process_selected", {})
    assert str(e.value) == "nothing_selected"


def test_review_shows_field_proposals(env):
    svc, _, _ = env
    svc.handle("process", {"uuid": A})
    svc.tick()
    fields = [i for i in svc.handle("review", {}) if i["kind"] == "field"]
    assert fields and all({"field", "after", "confidence", "planned"} <= set(i) for i in fields)


def test_review_lists_codes_never_raw_output(env):
    svc, dt3, _ = env
    dt3.records[A]["text"] = " "
    svc.handle("process", {"uuid": A})
    svc.tick()
    items = svc.handle("review", {})
    assert len(items) == 1 and items[0]["code"] == "no_text" and items[0]["uuid"] == A
    assert set(items[0]) == {"id", "uuid", "kind", "code", "tags_add", "created_at"}   # error item: no raw
