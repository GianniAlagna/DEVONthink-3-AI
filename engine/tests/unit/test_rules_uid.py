"""B-3 UID / MWST number (brief B3). Check digit per eCH-0097 v5.2.0 §2.4 (example CHE-109.322.551)."""
import pytest

from dt3agent.rules.uid import find_uids, uid_valid


@pytest.mark.parametrize("uid, valid", [
    ("CHE-109.322.551", True),     # eCH-0097 worked example
    ("CHE109322551", True),
    ("che-109.322.551", True),
    ("CHE-109.322.552", False),    # wrong check digit
    ("CHE-123.456.789", False),    # the usual placeholder does not pass
    ("CHE-109.322.55", False),     # 8 digits
    ("ADM-109.322.551", False),
])
def test_uid_valid(uid, valid):
    assert uid_valid(uid) is valid


def test_check_digit_zero_and_ten():
    # 1*5 + 7*4 = 33, 33 % 11 == 0 -> check digit 0 (eCH-0097 §2.4)
    assert uid_valid("CHE-100.000.070")
    # 1*5 + 1*5 + 6*4 = 34, 34 % 11 == 1 -> "10": never issued, so no 9th digit makes it valid
    assert not any(uid_valid(f"CHE-100.000.16{d}") for d in range(10))


def test_find_uids_with_vat_suffix():
    text = ("Muster Treuhand AG · MWST-Nr. CHE-109.322.551 MWST\n"
            "Kundin: UID CHE-123.456.789\nN° TVA CHE109322551 TVA · IVA: CHE-109.322.551 IVA")
    found = find_uids(text)
    assert [(u.uid, u.valid, u.vat) for u in found] == [
        ("CHE-109.322.551", True, True), ("CHE-123.456.789", False, False),
        ("CHE-109.322.551", True, True), ("CHE-109.322.551", True, True)]


def test_no_match_inside_longer_tokens():
    assert find_uids("XCHE-109.322.5519 and CHE-109.322.5512") == []


def test_first_valid_uid_becomes_metadata():
    from dt3agent.plan import plan
    from tests.unit.test_plan import AI, TEXT, by_field, cfg
    # the invoice fixture's letterhead says CHE-123.456.788 MWST (check digit 8: valid)
    p = by_field(plan({}, TEXT, AI, cfg()))
    assert p[("metadata", "dt3agentuid")].value == "CHE-123.456.788 MWST"
    text = TEXT.replace("CHE-123.456.788", "CHE-123.456.789") + "\nUID CHE-109.322.551\n"
    assert by_field(plan({}, text, AI, cfg()))[("metadata", "dt3agentuid")].value == "CHE-109.322.551"
    assert ("metadata", "dt3agentuid") not in by_field(plan({}, TEXT.replace("CHE", "XXX"), AI, cfg()))
