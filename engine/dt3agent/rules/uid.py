"""Swiss UID (Unternehmens-Identifikationsnummer) and MWST/TVA/IVA number (brief B3, SPEC §4.10). Pure.

Source: eCH-0097 "Datenstandard Unternehmensidentifikation" v5.2.0 (approved 2021-07-02), §2.4:
https://www.ech.ch/sites/default/files/dosvers/hauptdokument/STAN_d_DEF_2021-07-02_eCH-0097_V5.2.0_Datenstandard%20Unternehmensidentifikation.pdf
- "CHE" + 9 digits; the 9th is a check digit by modulo 11.
- Weights per position 5, 4, 3, 2, 7, 6, 5, 4; sum of products mod 11; check digit = 11 - remainder.
- Remainder 0 -> check digit 0; a result of 10 is never issued (invalid). Worked example: CHE-109.322.551.
The VAT number is the UID followed by MWST (de), TVA (fr) or IVA (it).
"""
import re
from dataclasses import dataclass

WEIGHTS = (5, 4, 3, 2, 7, 6, 5, 4)
UID_IN_TEXT = re.compile(r"(?<![A-Z0-9])CHE-?(\d{3})\.?(\d{3})\.?(\d{3})(?![\d.]?\d)(?:\s+(MWST|TVA|IVA)\b)?",
                         re.IGNORECASE)


def check_digit(first8: str) -> int | None:
    """None when the check digit would be 10 (such numbers are not issued)."""
    rest = sum(int(d) * w for d, w in zip(first8, WEIGHTS, strict=True)) % 11
    digit = 0 if rest == 0 else 11 - rest
    return None if digit == 10 else digit


def uid_valid(uid: str) -> bool:
    m = re.fullmatch(r"CHE-?(\d{3})\.?(\d{3})\.?(\d{3})", uid.strip(), re.IGNORECASE)
    if not m:
        return False
    digits = "".join(m.groups())
    return check_digit(digits[:8]) == int(digits[8])


@dataclass(frozen=True)
class UidFound:
    uid: str      # CHE-123.456.789
    valid: bool
    vat: bool     # followed by MWST / TVA / IVA


def find_uids(text: str) -> list[UidFound]:
    out = []
    for m in UID_IN_TEXT.finditer(text):
        uid = f"CHE-{m[1]}.{m[2]}.{m[3]}"
        out.append(UidFound(uid, uid_valid(uid), bool(m[4])))
    return out
