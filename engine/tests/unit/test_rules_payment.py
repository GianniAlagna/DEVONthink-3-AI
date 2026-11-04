"""P3-4 IBAN, QR-IBAN, QR reference, SCOR (SPEC §4.10). Values from the Phase 0 QR-bill fixtures."""
from pathlib import Path

import pytest

from dt3agent.rules.payment import find_ibans, iban_valid, is_qr_iban, qr_reference_valid, scor_valid

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "spike"


@pytest.mark.parametrize("iban, valid, qr", [
    ("CH4431999123000889012", True, True),       # QR-IBAN: IID 31999
    ("CH5800791123000889012", True, False),      # normal IBAN: IID 00791
    ("CH44 3199 9123 0008 8901 2", True, True),  # with spaces
    ("ch5800791123000889012", True, False),      # lower case
    ("CH4431999123000889013", False, True),      # last digit changed
    ("CH443199912300088901", False, True),       # one digit short for CH (21)
    ("DE89370400440532013000", True, False),     # Germany, 22 chars
    ("XX00", False, False),
])
def test_iban(iban, valid, qr):
    assert iban_valid(iban) is valid
    assert is_qr_iban(iban) is qr


@pytest.mark.parametrize("ref, valid", [
    ("210000000003139471430009017", True),        # QR-bill fixture
    ("21 00000 00003 13947 14300 09017", True),   # printed with spaces
    ("210000000003139471430009016", False),       # wrong check digit
    ("21000000000313947143000901", False),        # 26 digits
    ("21000000000313947143000901A", False),
])
def test_qr_reference(ref, valid):
    assert qr_reference_valid(ref) is valid


@pytest.mark.parametrize("ref, valid", [
    ("RF18539007547034", True),          # SCOR fixture
    ("RF18 5390 0754 7034", True),
    ("RF19539007547034", False),
    ("RF18", False),
    ("XX18539007547034", False),
])
def test_scor(ref, valid):
    assert scor_valid(ref) is valid


def test_ibans_in_invoice_text():
    text = (FIXTURES / "invoice-de.txt").read_text(encoding="utf-8")
    found = find_ibans(text)
    assert [(f.iban, f.valid, f.qr) for f in found] == [("CH4431999123000889012", True, True)]
    assert text[found[0].start:found[0].end] == "CH44 3199 9123 0008 8901 2"


def test_qr_bill_payloads_check_out():
    qrr = (FIXTURES / "qrbill-qrr.payload.txt").read_text(encoding="utf-8").splitlines()
    scor = (FIXTURES / "qrbill-scor.payload.txt").read_text(encoding="utf-8").splitlines()
    assert iban_valid(qrr[3]) and is_qr_iban(qrr[3]) and qr_reference_valid(qrr[28])
    assert iban_valid(scor[3]) and not is_qr_iban(scor[3]) and scor_valid(scor[28])


def test_no_iban_in_other_numbers():
    assert find_ibans("Rechnung Nr. 2026-0417, CHE-123.456.788 MWST, Telefon 044 123 45 67") == []
