"""J-1 (SPEC §4.21): read-only scope listing over the bridge."""
import io

import pytest

from dt3agent.adapter import DT3Adapter
from dt3agent.audit import AuditLog
from dt3agent.bridge import Bridge, BridgeError, validate
from dt3agent.undo import UndoJournal
from tests.fakes import FakeDT3

A = "00000000-0000-4000-8000-00000000000A"
B = "00000000-0000-4000-8000-00000000000B"
C = "00000000-0000-4000-8000-00000000000C"
D = "00000000-0000-4000-8000-00000000000D"


def fake():
    dt3 = FakeDT3({
        A: {"location": "/Inbox/", "modified": "2026-11-01T08:00:00.000Z", "kind": "PDF document"},
        B: {"location": "/Inbox/Steuern/", "modified": "2026-11-05T08:00:00.000Z", "kind": "Markdown"},
        C: {"location": "/Archiv/", "modified": "2026-11-06T08:00:00.000Z", "kind": "PDF document"},
        D: {"location": "/Inbox/", "modified": "2026-10-01T08:00:00.000Z", "kind": "PDF document",
            "database": "Andere"},
    })
    dt3.groups |= {"/Archiv/", "/Inbox/Steuern/"}
    return dt3


def adapter(dt3, tmp_path):
    import sqlite3
    return DT3Adapter(dt3, UndoJournal(sqlite3.connect(":memory:")), AuditLog(tmp_path / "audit"))


def test_list_returns_records_deep_inside_the_scope_newest_first(tmp_path):
    got = adapter(fake(), tmp_path).list_scope("DT3Agent-Test", "/Inbox/")
    assert [r["uuid"] for r in got] == [B, A]  # deep record included, other group and database not
    assert got[0] == {"uuid": B, "modified": "2026-11-05T08:00:00.000Z", "kind": "Markdown"}


def test_list_since_keeps_only_newer_records(tmp_path):
    got = adapter(fake(), tmp_path).list_scope("DT3Agent-Test", "/Inbox/", since="2026-11-02")
    assert [r["uuid"] for r in got] == [B]


def test_list_never_writes(tmp_path):
    dt3 = fake()
    before = {u: dict(r) for u, r in dt3.records.items()}
    adapter(dt3, tmp_path).list_scope("DT3Agent-Test", "/Inbox/")
    assert dt3.records == before
    assert [v for v, _ in dt3.calls] == ["list"]


def test_list_drops_malformed_answers_and_caps_at_500(tmp_path):
    class Host:
        def call(self, verb, **args):
            ok = [{"uuid": f"00000000-0000-4000-8000-{i:012d}", "modified": "2026-11-01T00:00:00.000Z",
                   "kind": "PDF"} for i in range(600)]
            return {"records": [{"uuid": "x; rm", "modified": "", "kind": ""}, "junk"] + ok}
    got = adapter(Host(), tmp_path).list_scope("DT3Agent-Test", "/Inbox/")
    assert len(got) == 500 and all(r["uuid"].startswith("00000000") for r in got)


def test_unknown_group_is_an_error_not_a_new_group(tmp_path):
    dt3 = fake()
    with pytest.raises(BridgeError, match="group_not_found"):
        adapter(dt3, tmp_path).list_scope("DT3Agent-Test", "/Neu/")
    assert "/Neu/" not in dt3.groups


@pytest.mark.parametrize("args", [
    {"database": "", "group": "/Inbox/", "since": ""},
    {"database": "x" * 201, "group": "/Inbox/", "since": ""},
    {"database": "DB\n", "group": "/Inbox/", "since": ""},
    {"database": "DB", "group": "Inbox", "since": ""},
    {"database": "DB", "group": "/../", "since": ""},
    {"database": "DB", "group": "/Inbox/", "since": "gestern"},
    {"database": "DB", "group": "/Inbox/", "since": "2026-11-01'); delete("},
    {"database": "DB", "group": "/Inbox/"},
])
def test_bad_list_requests_never_leave_the_engine(args):
    wfile = io.StringIO()
    with pytest.raises(BridgeError):
        Bridge(io.StringIO(), wfile).call("list", **args)
    assert wfile.getvalue() == ""


@pytest.mark.parametrize("since", ["", "2026-11-01", "2026-11-01T08:00:00Z", "2026-11-01T08:00:00.123Z"])
def test_good_since_values_pass(since):
    validate("list", {"database": "DT3Agent-T1", "group": "/Inbox/", "since": since})


def service(tmp_path, scopes):
    from dt3agent import config
    from dt3agent.service import Service
    cfg = config.load(tmp_path / "config.json")
    cfg["scopes"] = scopes
    config.save(tmp_path / "config.json", cfg)
    dt3 = fake()
    return Service(tmp_path, dt3), dt3


def test_list_rpc_covers_every_enabled_scope_and_reports_errors(tmp_path):
    svc, dt3 = service(tmp_path, [{"database": "DT3Agent-Test", "group": "/Inbox/"},
                                  {"database": "DT3Agent-Test", "group": "/Fehlt/"}])
    got = svc.handle("list", {})["scopes"]
    assert got[0]["count"] == 2 and got[0]["newest"] == "2026-11-05T08:00:00.000Z" and "seconds" in got[0]
    assert got[1]["error"] == "group_not_found"
    assert svc.handle("list", {"since": "2026-11-02"})["scopes"][0]["count"] == 1
    assert not [v for v, _ in dt3.calls if v.startswith("set_") or v in ("move", "create_markdown")]


def test_list_rpc_rejects_unknown_params(tmp_path):
    from dt3agent.rpc import RPCError
    svc, _ = service(tmp_path, [])
    with pytest.raises(RPCError, match="bad_params"):
        svc.handle("list", {"database": "X"})


def test_cli_list(monkeypatch):
    from dt3agent import cli
    calls = []
    monkeypatch.setattr(cli.rpc, "call", lambda path, m, p, timeout=120.0: calls.append((m, p, timeout)) or {})
    assert cli.main(["list"]) == 0 and cli.main(["list", "2026-11-01"]) == 0
    assert calls == [("list", {}, 600.0), ("list", {"since": "2026-11-01"}, 600.0)]
