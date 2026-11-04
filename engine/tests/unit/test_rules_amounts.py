"""P3-3 amounts (SPEC §4.10): value in Rappen/cents as int, currency, label. Table-driven, no AI."""
from pathlib import Path

import pytest

from dt3agent.rules.amounts import find_amounts, total

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "spike"


@pytest.mark.parametrize("text, cents, currency", [
    ("CHF 1'957.04", 195704, "CHF"),
    ("CHF 1’957.04", 195704, "CHF"),
    ("1 957,04 CHF", 195704, "CHF"),
    ("Fr. 249.98", 24998, "CHF"),
    ("249.98 Fr.", 24998, "CHF"),
    ("CHF 540.–", 54000, "CHF"),
    ("CHF 540.-", 54000, "CHF"),
    ("CHF 12", 1200, "CHF"),
    ("EUR 1.234,56", 123456, "EUR"),
    ("1.234,56 €", 123456, "EUR"),
    ("€ 99.90", 9990, "EUR"),
])
def test_formats(text, cents, currency):
    found = find_amounts(text)
    assert [(a.cents, a.currency) for a in found] == [(cents, currency)]
    assert text[found[0].start:found[0].end] == found[0].raw


@pytest.mark.parametrize("line, label", [
    ("Total                            CHF 1'957.04", "total"),
    ("Totale                            CHF 499.96", "total"),
    ("Rechnungsbetrag CHF 100.00", "total"),
    ("Montant total CHF 100.00", "total"),
    ("Total exkl. MWST CHF 100.00", "net"),
    ("MWST 8.1 %                       CHF   146.64", "vat"),
    ("TVA 8,1 %                         CHF  18.73", "vat"),
    ("Zwischensumme CHF 100.00", "net"),
    ("Buchhaltung 1. Quartal 2026     CHF 1'810.40", None),
])
def test_labels_from_the_line(line, label):
    assert find_amounts(line)[0].label == label


@pytest.mark.parametrize("text", [
    "MWST 8.1 %",
    "IBAN CH44 3199 9123 0008 8901 2",
    "Rechnung Nr. 2026-0417",
    "17.04.2026",
    "Telefon 044 123 45 67",
])
def test_not_amounts(text):
    assert find_amounts(text) == []


@pytest.mark.parametrize("lang, cents", [("de", 195704), ("fr", 24998), ("it", 49996), ("en", 100000)])
def test_invoice_total(lang, cents):
    text = (FIXTURES / f"invoice-{lang}.txt").read_text(encoding="utf-8")
    t = total(find_amounts(text))
    assert t is not None and (t.cents, t.currency, t.label) == (cents, "CHF", "total")


def test_total_is_none_when_no_line_says_total():
    assert total(find_amounts("Buchhaltung CHF 10.00\nBeratung CHF 20.00")) is None
