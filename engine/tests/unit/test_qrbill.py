"""B-2 Swiss QR-bill parser against synthetic payloads (SIX IG QR-bill v2.4, chapter 4)."""
import pytest

from dt3agent.qrbill import QRBillError, parse

QR_IBAN, IBAN = "CH4431999123000889012", "CH9300762011623852957"
QRR, SCOR = "210000000003139471430009017", "RF18539007547034"


def payload(iban=QR_IBAN, amount="1957.04", ccy="CHF", tp="QRR", ref=QRR, adr="S", debtor=True, extra=(),
            sep="\r\n", trailer="EPD", version="0200"):
    lines = ["SPC", version, "1", iban,
             adr, "Muster Treuhand AG", "Musterstrasse", "1", "8000", "Zürich", "CH",
             "", "", "", "", "", "", "",
             amount, ccy,
             *(["S", "Pia Rutschmann", "Marktgasse", "28", "9400", "Rorschach", "CH"] if debtor else [""] * 7),
             tp, ref, "Rechnung Nr. 2026-0417", trailer, *extra]
    return sep.join(lines)


def test_qr_iban_with_qr_reference():
    b = parse(payload())
    assert b["iban"] == QR_IBAN and b["qr_iban"] is True
    assert b["amount"] == 195704 and b["currency"] == "CHF"
    assert b["reference_type"] == "QRR" and b["reference"] == QRR
    assert b["creditor"] == {"name": "Muster Treuhand AG", "street": "Musterstrasse", "building": "1",
                             "postal_code": "8000", "town": "Zürich", "country": "CH"}
    assert b["debtor"]["name"] == "Pia Rutschmann" and b["message"] == "Rechnung Nr. 2026-0417"


@pytest.mark.parametrize("tp, ref", [("SCOR", SCOR), ("NON", "")])
def test_iban_with_scor_or_without_reference(tp, ref):
    b = parse(payload(iban=IBAN, tp=tp, ref=ref, ccy="EUR"))
    assert b["qr_iban"] is False and b["reference_type"] == tp and b["reference"] == ref
    assert b["currency"] == "EUR"


def test_lf_only_open_amount_no_debtor_and_billing_info():
    b = parse(payload(sep="\n", amount="", debtor=False, extra=["//S1/10/10201409/11/260417"]))
    assert b["amount"] is None and b["debtor"] is None and b["billing_info"] == "//S1/10/10201409/11/260417"


def test_trailing_newline_and_spaces_in_iban_are_tolerated():
    assert parse(payload(iban="CH44 3199 9123 0008 8901 2") + "\r\n")["iban"] == QR_IBAN


def test_combined_address_from_older_bills_is_read():
    # v2.3 removed address type K (from 21.11.2025); bills printed before are still read, never rejected
    assert parse(payload(adr="K"))["creditor"]["name"] == "Muster Treuhand AG"


@pytest.mark.parametrize("kwargs, code", [
    ({"iban": "CH4431999123000889013"}, "qr_iban_invalid"),
    ({"iban": "DE89370400440532013000"}, "qr_iban_country"),
    ({"iban": IBAN}, "qr_reference_needs_qr_iban"),
    ({"tp": "SCOR", "ref": SCOR}, "qr_iban_needs_qr_reference"),
    ({"ref": "210000000003139471430009018"}, "qr_reference_invalid"),
    ({"iban": IBAN, "tp": "SCOR", "ref": "RF19539007547034"}, "qr_scor_invalid"),
    ({"iban": IBAN, "tp": "NON", "ref": "123"}, "qr_reference_unexpected"),
    ({"iban": IBAN, "tp": "XYZ", "ref": ""}, "qr_reference_type"),
    ({"ccy": "USD"}, "qr_currency"),
    ({"amount": "0.00"}, "qr_amount"),
    ({"amount": "1000000000.00"}, "qr_amount"),
    ({"amount": "12,50"}, "qr_amount"),
    ({"amount": "1.234"}, "qr_amount"),
    ({"trailer": "XXX"}, "qr_trailer"),
    ({"version": "0100"}, "qr_version"),
    ({"adr": "X"}, "qr_address"),
])
def test_invalid_bills_are_refused_with_a_code(kwargs, code):
    with pytest.raises(QRBillError) as e:
        parse(payload(**kwargs))
    assert e.value.code == code


@pytest.mark.parametrize("text", ["", "https://example.org", "SPC\r\n0200\r\n1", "BCD\n002\n1\nSCT"])
def test_other_qr_codes_are_not_bills(text):
    with pytest.raises(QRBillError) as e:
        parse(text)
    assert e.value.code in ("qr_not_a_bill", "qr_incomplete")


def test_too_long_payload_is_refused():
    with pytest.raises(QRBillError) as e:
        parse(payload(extra=["x" * 140, "y" * 101]))
    assert e.value.code in ("qr_too_long", "qr_line_too_long")


def test_creditor_name_is_required():
    text = payload().replace("Muster Treuhand AG", "")
    with pytest.raises(QRBillError) as e:
        parse(text)
    assert e.value.code == "qr_address"


def six(account, amount, debtor, tp, ref, message, tail):
    """Payloads of SIX IG v2.4 Annex A, Tables 17-19 and 21 (creditor shortened, values as printed)."""
    return "\r\n".join(["SPC", "0200", "1", account, "S", "Max Muster & Söhne", "Musterstrasse", "123", "8000",
                        "Seldwyla", "CH", *[""] * 7, amount, "CHF", *debtor, tp, ref, message, "EPD", *tail])


SIMON = ["S", "Simon Muster", "Musterstrasse", "1", "8000", "Seldwyla", "CH"]


@pytest.mark.parametrize("text, expect", [
    (six("CH6431961000004421557", "50.00", SIMON, "QRR", "000008207791225857421286694", "Payment of travel",
         ["", "", ""]), {"amount": 5000, "qr_iban": True, "reference_type": "QRR"}),
    (six("CH4431999123000889012", "1949.75", SIMON, "QRR", "210000000003139471430009017", "Order from 15.10.2020",
         ["//S1/10/1234/11/201021/30/102673386/32/7.7/40/0:30", "eBill/B/simon.muster@example.com", ""]),
     {"amount": 194975, "billing_info": "//S1/10/1234/11/201021/30/102673386/32/7.7/40/0:30"}),
    (six("CH5204835012345671000", "", [""] * 7, "NON", "", "", ["", "", ""]),
     {"amount": None, "debtor": None, "reference_type": "NON"}),
    (six("CH5800791123000889012", "199.95", SIMON, "SCOR", "RF18539007547034", "", ["", "", ""]),
     {"amount": 19995, "qr_iban": False, "reference": "RF18539007547034"}),
])
def test_six_annex_a_examples(text, expect):
    b = parse(text)
    assert {k: b[k] for k in expect} == expect


def test_six_example_4_reference_fails_its_check_digits():
    # SIX IG Annex A Table 20 (unchanged since v2.2) prints RF720191230100405JSH0438; ISO 11649 MOD 97-10 gives
    # check digits 24 for this body, not 72. Checksums are never lenient, so the code is refused.
    with pytest.raises(QRBillError) as e:
        parse(six("CH5800791123000889012", "211.00", SIMON, "SCOR", "RF720191230100405JSH0438", "", []))
    assert e.value.code == "qr_scor_invalid"
    assert parse(six("CH5800791123000889012", "211.00", SIMON, "SCOR", "RF240191230100405JSH0438", "", []))


# --- B-2 in the pipeline: decoded values beat text rules for payment fields and beat the AI (brief B2) ---

def test_plan_takes_payment_fields_from_the_qr_bill():
    from dt3agent.plan import plan
    from tests.unit.test_plan import AI, TEXT, by_field, cfg
    bill = parse(payload(amount="1957.05"))  # text says CHF 1957.04: an OCR or typing slip loses to the code
    p = by_field(plan({}, TEXT, {**AI, "sender": "Treuhand"}, cfg(), bill=bill))
    assert p[("metadata", "dt3agenttotal")].value == "CHF 1957.05"
    assert p[("metadata", "dt3agenttotal")].source == "qr"
    assert p[("metadata", "dt3agentiban")].value == QR_IBAN
    assert p[("metadata", "dt3agentreference")].value == QRR
    assert "Muster-Treuhand-AG" in p[("name", None)].value  # creditor name beats the AI sender


def test_plan_without_a_bill_is_unchanged():
    from dt3agent.plan import plan
    from tests.unit.test_plan import AI, TEXT, by_field, cfg
    p = by_field(plan({}, TEXT, AI, cfg()))
    assert p[("metadata", "dt3agenttotal")].source == "rule" and ("metadata", "dt3agentreference") not in p


def test_non_reference_is_not_written():
    from dt3agent.plan import plan
    from tests.unit.test_plan import AI, TEXT, by_field, cfg
    p = by_field(plan({}, TEXT, AI, cfg(), bill=parse(payload(iban=IBAN, tp="NON", ref=""))))
    assert ("metadata", "dt3agentreference") not in p


class FakeVision:
    def __init__(self, payloads=None, error=None):
        self.payloads, self.error, self.calls = payloads or [], error, 0

    def ocr(self, path):
        raise AssertionError("text layer present: no OCR")

    def qr(self, path):
        self.calls += 1
        if self.error:
            from dt3agent.vision import VisionError
            raise VisionError(self.error)
        return self.payloads


def run_pipeline(tmp_path, vision):
    from dt3agent import store
    from dt3agent.adapter import DT3Adapter
    from dt3agent.audit import AuditLog
    from dt3agent.pipeline import Pipeline
    from dt3agent.service import ENGINE_MIGRATIONS
    from dt3agent.undo import MIGRATIONS as UNDO
    from dt3agent.undo import UndoJournal
    from tests.fakes import FakeDT3
    from tests.unit.test_pipeline import FakeAI
    from tests.unit.test_plan import TEXT, cfg
    uuid = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"
    dt3 = FakeDT3({uuid: {"name": "r.pdf", "tags": [], "contentHash": "h", "text": TEXT, "path": "/db/r.pdf"}})
    con = store.open_db(tmp_path / "e.db", ENGINE_MIGRATIONS)
    adapter = DT3Adapter(dt3, UndoJournal(store.open_db(tmp_path / "u.db", UNDO)), AuditLog(tmp_path / "a"))
    out = Pipeline(adapter, FakeAI(["Rechnung"]), con, dry_run=False, vision=vision,
                   settings=cfg()).process(uuid, batch_id="b1")
    return out, dt3.records[uuid].get("metadata", {})


def test_pipeline_writes_the_qr_values(tmp_path):
    vision = FakeVision(["https://example.org", payload(amount="1957.05")])
    out, meta = run_pipeline(tmp_path, vision)
    assert vision.calls == 1 and out.status == "applied"
    assert meta["mddt3agenttotal"] == "CHF 1957.05" and meta["mddt3agentreference"] == QRR


@pytest.mark.parametrize("vision", [FakeVision(error="qr_failed"), FakeVision(["SPC\nbroken"]), None])
def test_no_bill_or_helper_failure_falls_back_to_text_rules(tmp_path, vision):
    out, meta = run_pipeline(tmp_path, vision)
    assert out.status == "applied" and meta["mddt3agenttotal"] == "CHF 1957.04"
    assert "mddt3agentreference" not in meta


@pytest.mark.parametrize("name, ref_type, amount", [("qrr", "QRR", 195704), ("scor", "SCOR", 24998)])
def test_phase0_fixture_payloads(name, ref_type, amount):
    # byte-exact payloads read by the Vision helper on the floor machine in Phase 0 (S6)
    from pathlib import Path
    path = Path(__file__).resolve().parents[3] / "fixtures" / "spike" / f"qrbill-{name}.payload.txt"
    b = parse(path.read_text(encoding="utf-8", newline=""))
    assert (b["reference_type"], b["amount"], b["creditor"]["name"]) == (ref_type, amount, "Muster Treuhand AG")
