"""IBAN, QR-IBAN, QR reference and SCOR reference checks (SPEC §4.10). Pure functions, no AI.

Sources:
- IBAN check digits: ISO 13616-1, MOD 97-10 from ISO/IEC 7064 (move the first 4 characters to the end,
  letters A..Z -> 10..35, the number mod 97 must be 1).
- QR-IBAN: SIX "Swiss Implementation Guidelines for the QR-bill" — a CH/LI IBAN whose institution ID
  (IBAN positions 5-9) lies in 30000-31999.
- QR reference: same guidelines — 27 digits, last digit is the check digit by modulo 10, recursive.
- SCOR: ISO 11649 creditor reference "RF" + 2 check digits + up to 21 characters, checked by MOD 97-10.
"""
import re
from dataclasses import dataclass

# IBAN length per country (ISO 13616 registry) for the countries a Swiss user meets most; others: 15-34.
IBAN_LENGTH = {"CH": 21, "LI": 21, "DE": 22, "AT": 20, "FR": 27, "IT": 27, "LU": 20, "NL": 18, "BE": 16,
               "ES": 24, "GB": 22}
MOD10_TABLE = (0, 9, 4, 6, 8, 2, 7, 1, 3, 5)
IBAN_IN_TEXT = re.compile(r"(?<![A-Z0-9])([A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?)(?![A-Z0-9])")


def _compact(s: str) -> str:
    return re.sub(r"\s", "", s).upper()


def _mod97(s: str) -> int:
    return int("".join(str(int(c, 36)) for c in s)) % 97


def iban_valid(iban: str) -> bool:
    s = _compact(iban)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", s):
        return False
    if len(s) != IBAN_LENGTH.get(s[:2], len(s)):
        return False
    return _mod97(s[4:] + s[:4]) == 1


def is_qr_iban(iban: str) -> bool:
    s = _compact(iban)
    return s[:2] in ("CH", "LI") and s[4:9].isdigit() and 30000 <= int(s[4:9]) <= 31999


def qr_reference_valid(ref: str) -> bool:
    s = re.sub(r"\s", "", ref)
    if not re.fullmatch(r"\d{27}", s):
        return False
    carry = 0
    for digit in s[:-1]:
        carry = MOD10_TABLE[(carry + int(digit)) % 10]
    return (10 - carry) % 10 == int(s[-1])


def scor_valid(ref: str) -> bool:
    s = _compact(ref)
    if not re.fullmatch(r"RF\d{2}[A-Z0-9]{1,21}", s):
        return False
    return _mod97(s[4:] + s[:4]) == 1


@dataclass(frozen=True)
class IbanFound:
    iban: str   # compact, upper case
    valid: bool
    qr: bool
    start: int
    end: int


def find_ibans(text: str) -> list[IbanFound]:
    out = []
    for m in IBAN_IN_TEXT.finditer(text):
        s = _compact(m.group(1))
        out.append(IbanFound(s, iban_valid(s), is_qr_iban(s), m.start(1), m.end(1)))
    return out
