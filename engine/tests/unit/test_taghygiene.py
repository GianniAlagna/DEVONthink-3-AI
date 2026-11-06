"""J-5 tag hygiene (SPEC §4.21 D4): near-duplicate tags → add-the-kept-tag proposals, never a removal."""
import pytest

from dt3agent import taghygiene

U1 = "00000000-0000-4000-8000-000000000001"
U2 = "00000000-0000-4000-8000-000000000002"
U3 = "00000000-0000-4000-8000-000000000003"
VOCAB = ["Rechnung", "Steuern", "Vertrag"]


@pytest.mark.parametrize("a,b", [
    ("Rechnung", "rechnung"),            # case
    ("Prämie", "Pramie"),                # diacritics
    ("Rechnung", "Rechnungen"),          # plural
    ("Vertrag", "Verträge"),             # umlaut plural
    ("Versicherung", "Versicherng"),     # typo, edit distance 1
    ("invoice", "invoices"),
])
def test_near_duplicates(a, b):
    assert taghygiene.similar(a, b)


@pytest.mark.parametrize("a,b", [
    ("AHV", "IV"),                       # short tags: no edit distance
    ("Steuern", "Mietvertrag"),
    ("Bank", "Band"),
    ("2025", "2026"),                    # years are different tags
])
def test_different_tags(a, b):
    assert not taghygiene.similar(a, b)


def test_vocabulary_tag_is_kept_and_only_missing_ones_are_proposed():
    seen = [(U1, ["rechnung"]), (U2, ["Rechnungen", "Rechnung"]), (U3, ["Rechnung"])]
    got = taghygiene.proposals(seen, VOCAB)
    assert got == [(U1, "Rechnung", "rechnung")]          # U2 already has the kept tag


def test_without_vocabulary_the_more_frequent_tag_is_kept():
    seen = [(U1, ["Offerte"]), (U2, ["Offerte"]), (U3, ["Offerten"])]
    assert taghygiene.proposals(seen, []) == [(U3, "Offerte", "Offerten")]


def test_proposals_are_capped():
    seen = [(f"00000000-0000-4000-8000-{i:012d}", ["rechnung"]) for i in range(200)]
    assert len(taghygiene.proposals(seen, VOCAB)) == taghygiene.MAX_PROPOSALS


def test_hygiene_job_creates_tag_proposals_and_accept_only_adds(tmp_path):
    from datetime import datetime, timedelta, timezone

    from dt3agent.service import Service
    from tests.fakes import FakeDT3
    when = "2026-11-01T00:00:00.000Z"
    dt3 = FakeDT3({U1: {"name": "A", "tags": ["rechnung", "Bank"], "location": "/", "modified": when},
                   U2: {"name": "B", "tags": ["Rechnung"], "location": "/", "modified": when}})
    dt3.groups |= {"/_Berichte/"}
    svc = Service(tmp_path, dt3)
    svc.handle("config_set", {"changes": {"jobs": {"hygiene": {"enabled": True, "group": "/_Berichte/"}},
                                          "scopes": [{"database": "DT3Agent-Test", "group": "/"}]}})
    svc.local_clock = lambda: datetime(2026, 11, 8, 3, 31, tzinfo=timezone(timedelta(hours=1)))
    assert svc._report("hygiene") == "ok" and svc._report("hygiene") == "ok"     # no second copy
    items = svc.handle("review", {"kind": "planned"})
    assert [(i["uuid"], i["tags_add"], i["code"]) for i in items] == [(U1, ["Rechnung"], "tag_hygiene")]
    assert dt3.records[U1]["tags"] == ["rechnung", "Bank"]                       # nothing written yet
    svc.handle("decide", {"id": items[0]["id"], "decision": "accept"})
    assert dt3.records[U1]["tags"] == ["rechnung", "Bank", "Rechnung"]           # added, nothing removed
