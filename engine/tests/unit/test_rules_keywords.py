"""P3-5 keywords: document-type and urgent hints from user-editable lists (brief A3/B6, SPEC §4.10)."""
from pathlib import Path

import pytest

from dt3agent import config
from dt3agent.rules.keywords import scan

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "spike"
LISTS = config.DEFAULTS["keywords"]


@pytest.mark.parametrize("lang", ["de", "fr", "it", "en"])
def test_invoices_are_invoices(lang):
    hits = scan((FIXTURES / f"invoice-{lang}.txt").read_text(encoding="utf-8"), LISTS)
    assert hits.doc_type() == "invoice" and hits.urgent == []


@pytest.mark.parametrize("text, doc_type", [
    ("2. Mahnung: bitte begleichen Sie die offene Rechnung", "reminder"),
    ("Mietvertrag zwischen den Parteien", None),        # compounds are not split: no false hint
    ("Vertrag über die Lieferung", "contract"),
    ("Offerte Nr. 12 für Ihre Anfrage", "offer"),
    ("Relevé de compte au 31 mars", "statement"),
    ("Grüezi mitenand", None),
])
def test_doc_type_hints(text, doc_type):
    assert scan(text, LISTS).doc_type() == doc_type


@pytest.mark.parametrize("text, word", [
    ("Zahlungsbefehl Nr. 123456 des Betreibungsamtes Bern", "Zahlungsbefehl"),
    ("Commandement de payer, Office des poursuites", "commandement de payer"),
    ("Precetto esecutivo dell'Ufficio esecuzione", "precetto esecutivo"),
    ("Vorladung vor das Bezirksgericht", "Vorladung"),
])
def test_urgent_hints_with_positions(text, word):
    hits = scan(text, LISTS)
    assert hits.urgent and hits.urgent[0].word.casefold() == word.casefold()
    first = hits.urgent[0]
    assert text[first.start:first.end].casefold() == word.casefold()


def test_user_lists_replace_the_defaults():
    lists = {"doc_types": {"payslip": ["Lohnabrechnung"]}, "urgent": ["Kündigung"]}
    hits = scan("Lohnabrechnung März und Kündigung", lists)
    assert hits.doc_type() == "payslip" and [h.word for h in hits.urgent] == ["Kündigung"]


def test_a_tie_goes_to_the_type_named_first():
    assert scan("Vertrag und Rechnung", LISTS).doc_type() == "contract"


def test_config_checks_the_lists():
    for bad in ({"doc_types": {"x": "Rechnung"}, "urgent": []}, {"doc_types": {}, "urgent": [""]},
                {"doc_types": {"": ["a"]}, "urgent": []}):
        with pytest.raises(config.ConfigError):
            config.validate({"keywords": bad})
