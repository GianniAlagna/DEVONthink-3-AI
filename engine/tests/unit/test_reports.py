"""J-4 weekly digest and hygiene report (SPEC §4.21 D2, D3): proposals only; accept writes a note."""
import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from dt3agent import reports
from dt3agent.rpc import RPCError
from dt3agent.service import Service
from tests.fakes import FakeDT3

TZ = timezone(timedelta(hours=1))
NOW = datetime(2026, 11, 9, 7, 31, tzinfo=TZ)
A = "00000000-0000-4000-8000-00000000000A"
B = "00000000-0000-4000-8000-00000000000B"
C = "00000000-0000-4000-8000-00000000000C"
WRITES = ("set_", "move", "replicate", "duplicate", "add_event")


def make(tmp_path, records=None, **digest):
    dt3 = FakeDT3(records or {})
    dt3.groups |= {"/_Berichte/"}
    svc = Service(tmp_path, dt3)
    svc.handle("config_set", {"changes": {"jobs": {"digest": {"enabled": True, "group": "/_Berichte/", **digest},
                                                   "hygiene": {"enabled": True, "group": "/_Berichte/"}},
                                          "scopes": [{"database": "DT3Agent-Test", "group": "/"}]}})
    svc.local_clock = lambda: NOW
    return svc, dt3


def processed(svc, uuid, when):
    with svc.con:
        svc.con.execute("INSERT INTO processed (uuid, content_hash, pipeline_version, done_at) VALUES (?, 'h', 1, ?)",
                        (uuid, when.astimezone(UTC).isoformat()))


def test_digest_lists_new_records_and_open_deadlines(tmp_path):
    svc, dt3 = make(tmp_path, {A: {"name": "Rechnung [Muster]", "tags": []}, B: {"name": "Alt", "tags": []}})
    processed(svc, A, NOW - timedelta(days=2))
    processed(svc, B, NOW - timedelta(days=20))                 # older than a week
    with svc.con:
        svc.con.execute("INSERT INTO review_items (uuid, kind, payload_json, created_at) VALUES (?, 'deadline', ?, ?)",
                        (A, json.dumps({"after": {"date": "2026-12-17", "title": "Nebenkosten"}}), NOW.isoformat()))
    title, text = reports.digest(svc.con, svc.adapter, NOW, "de")
    assert title == "DT3 Agent – Wochenübersicht 2026-11-09"
    assert f"[Rechnung  Muster](x-devonthink-item://{A})" in text and "Alt" not in text
    assert "2026-12-17: [Nebenkosten]" in text and "Offene Vorschläge in der Prüfliste: 1" in text
    assert "ß" not in text


@pytest.mark.parametrize("lang,word", [("fr", "Aperçu"), ("it", "Riepilogo"), ("en", "Weekly digest")])
def test_digest_languages(tmp_path, lang, word):
    svc, _ = make(tmp_path)
    assert word in reports.digest(svc.con, svc.adapter, NOW, lang)[0]


def test_hygiene_finds_untagged_and_stale_inbox_records(tmp_path):
    old = (NOW - timedelta(days=30)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    new = (NOW - timedelta(days=1)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    svc, _ = make(tmp_path, {A: {"name": "Ohne Tags", "tags": [], "location": "/Archiv/", "modified": new},
                             B: {"name": "Liegt rum", "tags": ["x"], "location": "/Inbox/", "modified": old},
                             C: {"name": "Frisch", "tags": ["x"], "location": "/Inbox/", "modified": new}})
    _, text = reports.hygiene(svc.adapter, svc.cfg["scopes"], svc.cfg["jobs"]["hygiene"], NOW)
    assert "## Ohne Tags (1)" in text and "Ohne Tags](" in text
    assert "## Seit über 14 Tagen in /Inbox/ (1)" in text and "Liegt rum" in text and "Frisch" not in text


def test_scheduled_digest_becomes_one_review_item_and_accept_writes_the_note(tmp_path):
    svc, dt3 = make(tmp_path)
    assert svc._report("digest") == "ok" and svc._report("digest") == "ok"   # the newer replaces the older
    items = svc.handle("review", {"kind": "report"})
    assert len(items) == 1 and items[0]["actions"] == ["accept", "reject"]
    assert items[0]["record_name"].startswith("DT3 Agent – Wochenübersicht") and items[0]["group"] == "/_Berichte/"
    assert not [v for v, _ in dt3.calls if v.startswith(WRITES)]
    with pytest.raises(RPCError, match="bad_value"):
        svc.handle("decide", {"id": items[0]["id"], "decision": "edit", "value": ["x"]})
    assert svc.handle("decide", {"id": items[0]["id"], "decision": "accept"}) == {"applied": True}
    notes = [r for r in dt3.records.values() if r.get("location") == "/_Berichte/"]
    assert len(notes) == 1 and notes[0]["text"].startswith("# DT3 Agent – Wochenübersicht")


def test_reject_writes_nothing_and_a_missing_group_keeps_the_item(tmp_path):
    svc, dt3 = make(tmp_path)
    svc._report("digest")
    item = svc.handle("review", {"kind": "report"})[0]
    dt3.groups.discard("/_Berichte/")
    with pytest.raises(RPCError, match="group_not_found"):
        svc.handle("decide", {"id": item["id"], "decision": "accept"})
    assert svc.handle("review", {"kind": "report"})                          # still open
    assert svc.handle("decide", {"id": item["id"], "decision": "reject"}) == {"applied": False}
    assert not [r for r in dt3.records.values() if r.get("location") == "/_Berichte/"]


def test_long_reports_are_capped(tmp_path):
    recs = {f"00000000-0000-4000-8000-{i:012d}": {"name": "N" * 120, "tags": []} for i in range(100)}
    svc, _ = make(tmp_path, recs)
    for u in recs:
        processed(svc, u, NOW - timedelta(days=1))
    _, text = reports.digest(svc.con, svc.adapter, NOW, "en")
    assert len(text) <= reports.MAX_TEXT and "… and 60 more" in text


def test_upgrade_keeps_existing_review_items(tmp_path):
    from dt3agent import review, store
    from dt3agent.service import ENGINE_MIGRATIONS
    old = ENGINE_MIGRATIONS[:-len(review.MIGRATIONS_3)]
    con = store.open_db(tmp_path / "engine.db", old)
    con.execute("INSERT INTO review_items (uuid, kind, payload_json, created_at, record_missing) "
                "VALUES (?, 'urgent', '{}', 't', 1)", (A,))
    con.commit()
    con.close()
    con = store.open_db(tmp_path / "engine.db", ENGINE_MIGRATIONS)
    assert con.execute("SELECT uuid, kind, record_missing FROM review_items").fetchall() == [(A, "urgent", 1)]
    assert list(tmp_path.glob("engine.db.v*.bak"))                           # backup before the upgrade
