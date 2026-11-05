"""B-5 stated deadlines (brief B5) and the calendar event (.ics, RFC 5545) for DT3."""
from datetime import date

import pytest

from dt3agent.ics import build_event
from dt3agent.rules.deadlines import find_deadlines

U = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"


@pytest.mark.parametrize("text, when", [
    ("Total CHF 1957.04, zahlbar bis 17. Mai 2026.", date(2026, 5, 17)),
    ("Fällig am 30.06.2026", date(2026, 6, 30)),
    ("Zahlungsfrist: 15.07.2026", date(2026, 7, 15)),
    ("à payer jusqu'au 31 mai 2026", date(2026, 5, 31)),
    ("Échéance : 12/06/2026", date(2026, 6, 12)),
    ("da pagare entro il 20 giugno 2026", date(2026, 6, 20)),
    ("Payment due by 2026-07-01.", date(2026, 7, 1)),
    ("Bitte reichen Sie die Unterlagen bis spätestens 3. August 2026 ein.", date(2026, 8, 3)),
])
def test_stated_deadlines(text, when):
    found = find_deadlines(text)
    assert found and found[0].date == when


@pytest.mark.parametrize("text", ["zahlbar innert 30 Tagen", "payable dans les 30 jours", "da pagare entro 30 giorni",
                                  "payable within 30 days"])
def test_relative_deadline_is_a_hint_without_date(text):
    found = find_deadlines(text)
    assert found and found[0].date is None and "30" in found[0].phrase


def test_plain_dates_are_not_deadlines():
    assert find_deadlines("Zürich, 17. April 2026. Rechnung Nr. 4711 vom 17.04.2026") == []


def test_ics_event_with_alarm_and_link():
    ics = build_event(uid=f"{U}-20260517", when=date(2026, 5, 17), title="Zahlung fällig: Muster AG, CHF 1957.04",
                      notes="Betrag: CHF 1957.04\nIBAN: CH44 3199 9123 0008 8901 2; Ref, x",
                      url=f"x-devonthink-item://{U}", stamp="20261105T090000Z")
    lines = ics.split("\r\n")
    assert lines[0] == "BEGIN:VCALENDAR" and lines[-2] == "END:VCALENDAR" and lines[-1] == ""
    assert "DTSTART;VALUE=DATE:20260517" in lines and "DTEND;VALUE=DATE:20260518" in lines
    assert "TRIGGER:-P1D" in lines and "ACTION:DISPLAY" in lines
    assert f"URL:x-devonthink-item://{U}" in lines
    unfolded = ics.replace("\r\n ", "")
    assert "DESCRIPTION:Betrag: CHF 1957.04\\nIBAN: CH44 3199 9123 0008 8901 2\\; Ref\\, x\\n" in unfolded
    assert all(len(line.encode()) <= 75 for line in lines)  # RFC 5545 3.1 folding


def test_ics_refuses_control_characters_in_title():
    with pytest.raises(ValueError):
        build_event(uid="x", when=date(2026, 5, 17), title="a\x00b", notes="", url="", stamp="20261105T090000Z")


# --- in the pipeline and the review queue ---
from dt3agent import config  # noqa: E402
from dt3agent.rpc import RPCError  # noqa: E402
from dt3agent.service import Service  # noqa: E402
from tests.fakes import FakeDT3, FakeLlamaServer, ai_reply  # noqa: E402

TEXT = ("Muster Treuhand AG, Zürich, 17. April 2026\nRechnung Nr. 2026-0417\nTotal CHF 1957.04\n"
        "IBAN CH44 3199 9123 0008 8901 2\nZahlbar bis 17. Mai 2026.")


@pytest.fixture
def svc(tmp_path):
    server = FakeLlamaServer(reply=ai_reply(["Rechnung"]))
    dt3 = FakeDT3({U: {"name": "r.pdf", "tags": [], "contentHash": "h1", "text": TEXT, "location": "/Inbox/"}})
    c = config.load(tmp_path / "config.json")
    c["ai"]["url"], c["dry_run"] = server.url, False
    config.save(tmp_path / "config.json", c)
    s = Service(tmp_path, dt3)
    s.dt3 = dt3
    s.handle("process", {"uuid": U})
    s.tick()
    yield s
    s.close()
    server.close()


def deadline(s):
    return [i for i in s.handle("review", {}) if i["kind"] == "deadline"]


def test_deadline_becomes_a_review_item_never_an_action(svc):
    row = deadline(svc)[0]
    assert row["date"] == "2026-05-17" and row["phrase"] == "Zahlbar bis"
    assert row["title"].startswith("Frist: ") and "CHF 1957.04" in row["title"]
    assert row["actions"] == ["accept", "edit", "reject"]
    assert not [c for c in svc.dt3.calls if c[0] == "add_event"]


def test_accept_imports_the_event_and_sets_the_reminder(svc):
    assert svc.handle("decide", {"id": deadline(svc)[0]["id"], "decision": "accept"}) == {"applied": True}
    call = next(a for v, a in svc.dt3.calls if v == "add_event")
    assert call["uuid"] == U and call["date"] == "2026-05-17" and call["name"].endswith(".ics")
    assert "DTSTART;VALUE=DATE:20260517" in call["ics"] and f"x-devonthink-item://{U}" in call["ics"]
    assert "IBAN: CH4431999123000889012" in call["ics"].replace("\r\n ", "")
    assert svc.dt3.records[U]["reminder"] == "2026-05-17"


def test_edit_takes_another_date_and_bad_dates_are_refused(svc):
    item = deadline(svc)[0]
    for bad in (["17.05.2026"], ["2026-02-30"], ["morgen"]):
        with pytest.raises(RPCError):
            svc.handle("decide", {"id": item["id"], "decision": "edit", "value": bad})
    svc.handle("decide", {"id": item["id"], "decision": "edit", "value": ["2026-05-10"]})
    assert svc.dt3.records[U]["reminder"] == "2026-05-10"


def test_existing_reminder_is_never_overwritten(svc):
    svc.dt3.records[U]["reminder"] = "2026-01-01"
    item = deadline(svc)[0]
    with pytest.raises(RPCError) as e:
        svc.handle("decide", {"id": item["id"], "decision": "accept"})
    assert str(e.value) == "reminder_exists" and deadline(svc)


def test_reject_does_nothing(svc):
    assert svc.handle("decide", {"id": deadline(svc)[0]["id"], "decision": "reject"}) == {"applied": False}
    assert "reminder" not in svc.dt3.records[U]


def test_relative_period_is_a_hint_without_an_item(tmp_path):
    from dt3agent.plan import plan
    from tests.unit.test_plan import by_field, cfg
    p = by_field(plan({}, "Rechnung, zahlbar innert 30 Tagen", {"summary": []}, cfg()))
    assert ("deadline", None) not in p


@pytest.mark.parametrize("args", [
    {"name": "a/b.ics"}, {"name": "x.txt"}, {"name": "a\x00.ics"}, {"ics": "hello"},
    {"ics": "BEGIN:VCALENDAR" + "x" * 9000}, {"date": "17.05.2026"},
])
def test_bridge_fence_for_add_event(args):
    from dt3agent.bridge import BridgeError, validate
    good = {"uuid": U, "name": "Frist 2026-05-17.ics", "ics": "BEGIN:VCALENDAR\r\n", "date": "2026-05-17"}
    validate("add_event", good)
    with pytest.raises(BridgeError):
        validate("add_event", {**good, **args})


@pytest.mark.parametrize("host_error, code", [("dt3_error_1728", "apply_failed_dt3_error_1728"),
                                              ("compile_failed", "apply_failed_compile_failed"),
                                              ("Some sentence with text", "apply_failed")])
def test_host_error_code_is_passed_on(svc, host_error, code):
    from dt3agent.bridge import BridgeError
    real = svc.dt3.call

    def failing(verb, **args):
        if verb == "add_event":
            raise BridgeError(host_error)
        return real(verb, **args)
    svc.dt3.call = failing
    with pytest.raises(RPCError) as e:
        svc.handle("decide", {"id": deadline(svc)[0]["id"], "decision": "accept"})
    assert str(e.value) == code and deadline(svc)
