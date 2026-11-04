"""Money amounts with currency and a label from their line (SPEC §4.10). Pure function, no AI.

Values are integer Rappen/cents, never floats. A number counts only next to a currency (CHF, Fr., EUR, €),
so dates, percentages, IBANs and phone numbers are not amounts. The label comes from words on the same line:
total ("Total", "Totale", "Rechnungsbetrag", …), net ("exkl.", "Zwischensumme", …) or vat ("MWST", "TVA", …).
A QR-bill amount, when present, wins over these (SPEC §4.13, Phase 4).
"""
import re
from dataclasses import dataclass

_NUM = (r"\d{1,3}(?:\.\d{3})+,\d{2}"                          # 1.234,56 (EUR style)
        r"|\d{1,3}(?:['’   ]\d{3})+(?:[.,](?:\d{2}|[-–]))?"  # 1'957.04 · 1 957,04 · 1'000.–
        r"|\d+(?:[.,](?:\d{2}|[-–]))?")                       # 249.98 · 540.– · 12
_CUR = r"CHF|Fr\.|EUR|€"
AMOUNT = re.compile(
    rf"(?<![\w.])(?P<c1>{_CUR})\s*(?P<n1>{_NUM})(?![\d'’])"
    rf"|(?<![\d.,'’])(?P<n2>{_NUM})\s?(?P<c2>{_CUR})(?!\s*\d)")
CURRENCY = {"CHF": "CHF", "Fr.": "CHF", "EUR": "EUR", "€": "EUR"}

TOTAL = ("total", "totale", "gesamt", "rechnungsbetrag", "endbetrag", "zu bezahlen", "montant total",
         "importo totale", "amount due", "total due")
NET = ("exkl", "excl", "hors", "senza", "zwischensumme", "sous-total", "subtotale", "subtotal", "netto", "net ")
VAT = ("mwst", "mwst.", "tva", "iva", "vat", "mehrwertsteuer")


@dataclass(frozen=True)
class Amount:
    cents: int
    currency: str
    label: str | None  # total | net | vat
    start: int
    end: int
    raw: str


def _cents(number: str) -> int:
    m = re.search(r"[.,](\d{2}|[-–])$", number)
    whole, frac = (number[:m.start()], m.group(1)) if m else (number, "00")
    frac = "00" if frac in "-–" else frac
    return int(re.sub(r"\D", "", whole) or "0") * 100 + int(frac)


def _label(line: str) -> str | None:
    words = line.casefold()
    has = lambda keys: any(re.search(rf"(?<!\w){re.escape(k)}", words) for k in keys)  # noqa: E731
    if has(TOTAL):
        return "net" if has(NET) else "total"
    if has(VAT):
        return "vat"
    return "net" if has(NET) else None


def find_amounts(text: str) -> list[Amount]:
    out = []
    for m in AMOUNT.finditer(text):
        number = m.group("n1") or m.group("n2")
        currency = CURRENCY[m.group("c1") or m.group("c2")]
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.end())
        line = text[line_start:line_end if line_end != -1 else len(text)]
        out.append(Amount(_cents(number), currency, _label(line), m.start(), m.end(), m.group(0)))
    return out


def total(amounts: list[Amount]) -> Amount | None:
    """The last amount labelled total (invoices put the total at the bottom), or None."""
    return next((a for a in reversed(amounts) if a.label == "total"), None)
