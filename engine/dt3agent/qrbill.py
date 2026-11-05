"""Swiss QR-bill payload parser (brief B2, SPEC §4.16). Pure function, no AI, no I/O.

Source: SIX Interbank Clearing, "Swiss Implementation Guidelines for the QR-bill", Version 2.4 of 24.02.2026
(introduced with the SIC release of 13.11.2026; Version 2.3 of 21.11.2025 stays valid until November 2027).
https://www.six-group.com/dam/download/banking-services/standardization/qr-bill/ig-qr-bill-v2.4-en.pdf
- 4.1.4: elements separated by CR LF or LF; every element present (empty = empty line); the final line break
  is dropped; elements with status "A" (billing information, alternative procedures) may be left out.
- 4.2.2: element order and rules used below (line numbers 1-34 of Table 8).
- 6.2: at most 997 characters including separators.
- 2.8: QR-IID 30000-31999; a QR-IBAN goes only with a QR reference.

This is a reader for bills the user received, so it is lenient where older bills differ but still valid:
address type "K" (removed in v2.3) is read; EUR with a QR reference (allowed up to v2.3) is read.
Checksums are never lenient: a wrong IBAN or reference means the code is refused.
"""
import re

from dt3agent.rules.payment import iban_valid, is_qr_iban, qr_reference_valid, scor_valid

MAX_CHARS = 997
FIXED = 31  # lines 1-31 are always present (QRType ... Trailer)
ADDRESS = ("name", "street", "building", "postal_code", "town", "country")


class QRBillError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _address(lines: list[str], required: bool) -> dict | None:
    kind, values = lines[0], lines[1:]
    if not kind and not any(values):
        if required:
            raise QRBillError("qr_address")
        return None
    if kind not in ("S", "K") or not values[0]:
        raise QRBillError("qr_address")
    return dict(zip(ADDRESS, values, strict=True))


def _amount(text: str) -> int | None:
    """Amount in Rappen/cents; empty = the payer fills it in. 0.01 to 999,999,999.99 (4.2.2, line 19)."""
    if not text:
        return None
    m = re.fullmatch(r"(\d{1,9})(?:\.(\d{1,2}))?", text)
    if not m:
        raise QRBillError("qr_amount")
    value = int(m[1]) * 100 + int((m[2] or "0").ljust(2, "0"))
    if not 1 <= value <= 99_999_999_999:
        raise QRBillError("qr_amount")
    return value


def parse(text: str) -> dict:
    """Decode one QR code payload. Raises QRBillError with a short code; never returns partial data."""
    if not text.startswith("SPC"):
        raise QRBillError("qr_not_a_bill")
    if len(text) > MAX_CHARS:
        raise QRBillError("qr_too_long")
    lines = text.split("\r\n") if "\r\n" in text else text.split("\n")
    if lines and lines[-1] == "" and len(lines) > FIXED:
        lines.pop()  # a final line break is tolerated
    if len(lines) < FIXED or len(lines) > FIXED + 3:
        raise QRBillError("qr_incomplete")
    if lines[0] != "SPC" or lines[2] != "1":
        raise QRBillError("qr_not_a_bill")
    if not re.fullmatch(r"02\d\d", lines[1]):
        raise QRBillError("qr_version")
    if lines[30] != "EPD":
        raise QRBillError("qr_trailer")
    if any(len(line) > 140 for line in lines[:FIXED + 1]) or any(len(line) > 100 for line in lines[FIXED + 1:]):
        raise QRBillError("qr_line_too_long")

    iban = re.sub(r"\s", "", lines[3]).upper()
    if iban[:2] not in ("CH", "LI"):
        raise QRBillError("qr_iban_country")
    if not iban_valid(iban):
        raise QRBillError("qr_iban_invalid")
    qr_iban = is_qr_iban(iban)

    creditor = _address(lines[4:11], required=True)
    # lines 12-18: ultimate creditor, "for future use", must be empty; ignored when reading
    amount = _amount(lines[18])
    currency = lines[19]
    if currency not in ("CHF", "EUR"):
        raise QRBillError("qr_currency")
    debtor = _address(lines[20:27], required=False)

    ref_type, ref = lines[27], re.sub(r"\s", "", lines[28])
    if ref_type == "QRR":
        if not qr_iban:
            raise QRBillError("qr_reference_needs_qr_iban")
        if not qr_reference_valid(ref):
            raise QRBillError("qr_reference_invalid")
    elif ref_type in ("SCOR", "NON"):
        if qr_iban:
            raise QRBillError("qr_iban_needs_qr_reference")
        if ref_type == "SCOR" and not scor_valid(ref):
            raise QRBillError("qr_scor_invalid")
        if ref_type == "NON" and ref:
            raise QRBillError("qr_reference_unexpected")
    else:
        raise QRBillError("qr_reference_type")

    return {"version": lines[1], "iban": iban, "qr_iban": qr_iban, "creditor": creditor, "amount": amount,
            "currency": currency, "debtor": debtor, "reference_type": ref_type, "reference": ref,
            "message": lines[29], "billing_info": lines[31] if len(lines) > FIXED else "",
            "alternative": lines[32:]}
