"""P3-1 language rule (brief A2, SPEC §4.10): table-driven, no AI."""
from pathlib import Path

import pytest

from dt3agent.rules.language import detect

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "spike"


@pytest.mark.parametrize("lang", ["de", "fr", "it", "en"])
def test_synthetic_invoices(lang):
    found, score = detect((FIXTURES / f"invoice-{lang}.txt").read_text(encoding="utf-8"))
    assert found == lang and score >= 0.6


@pytest.mark.parametrize("text, lang", [
    ("Sehr geehrte Damen und Herren, die Rechnung ist bis Ende Monat zahlbar.", "de"),
    ("Madame, Monsieur, veuillez trouver ci-joint la facture du mois de janvier.", "fr"),
    ("Gentile cliente, in allegato trova la fattura del mese di gennaio.", "it"),
    ("Dear customer, please find attached the invoice for the month of January.", "en"),
    ("Zahlungsbefehl des Betreibungsamtes: die Forderung ist innert 20 Tagen zu bezahlen.", "de"),
])
def test_sentences(text, lang):
    assert detect(text)[0] == lang


@pytest.mark.parametrize("text", [
    "",
    "Total CHF 1'957.04",                       # numbers and shared words only
    "IBAN CH44 3199 9123 0008 8901 2",
    "Rechnung facture",                           # too few hints
])
def test_too_little_evidence_gives_none(text):
    found, score = detect(text)
    assert found is None and score < 0.6


def test_evenly_mixed_text_gives_none():
    text = ("Die Rechnung ist bis Ende Monat zahlbar und wir danken für die Zahlung. "
            "La facture est payable dans les 30 jours et nous vous remercions.")
    assert detect(text)[0] is None


def test_every_word_belongs_to_exactly_one_language():
    from dt3agent.rules.language import WORDS
    seen = {}
    for lang, words in WORDS.items():
        for w in words.split():
            assert w not in seen, f"{w!r} listed for {seen[w]} and {lang}"
            seen[w] = lang
