"""P3-9a field merge: rules first, AI only for what rules cannot know (ADR-0009, SPEC §4.13 steps 3-6)."""
from datetime import date
from pathlib import Path

from dt3agent import config
from dt3agent.fields import AI_SCHEMA, decide, merge, rule_fields

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "spike"
CFG = config.DEFAULTS


def invoice(lang="de"):
    return (FIXTURES / f"invoice-{lang}.txt").read_text(encoding="utf-8")


def test_rules_read_the_invoice():
    f = rule_fields(invoice(), CFG)
    assert f["lang"].value == "de" and f["lang"].source == "rule"
    assert f["document_date"].value == date(2026, 4, 17)
    assert (f["amount_cents"].value, f["currency"].value) == (195704, "CHF")
    assert f["iban"].value == "CH4431999123000889012" and f["qr_iban"].value is True
    assert f["type"].value == "invoice"
    assert "urgent" not in f


def test_urgent_letter_is_flagged():
    f = rule_fields("Zahlungsbefehl Nr. 123 des Betreibungsamtes Bern vom 3. März 2026", CFG)
    assert f["urgent"].value == ["Zahlungsbefehl", "Betreibungsamtes"]


def test_rules_win_over_ai_and_ai_fills_the_rest():
    ai = {"type": "letter", "lang": "fr", "sender": "Muster Treuhand AG", "receiver": None,
          "subject": "Rechnung 2026-0417", "summary": ["a", "b", "c"], "document_date": "2026-01-01"}
    merged = merge(rule_fields(invoice(), CFG), ai, identity="Erika Beispiel")
    assert merged["type"].value == "invoice" and merged["type"].source == "rule"
    assert merged["lang"].value == "de"
    assert merged["document_date"].value == date(2026, 4, 17)   # AI date ignored when a rule found one
    assert merged["sender"].value == "Muster Treuhand AG" and merged["sender"].source == "ai"
    assert merged["receiver"].value == "Erika Beispiel" and merged["receiver"].source == "settings"
    assert merged["summary"].value == ["a", "b", "c"]


def test_ai_date_used_only_when_rules_found_none_and_it_parses():
    merged = merge({}, {"document_date": "2026-02-30"}, identity=None)
    assert "document_date" not in merged
    merged = merge({}, {"document_date": "2026-02-28"}, identity=None)
    assert merged["document_date"].value == date(2026, 2, 28) and merged["document_date"].source == "ai"


def test_ai_never_invents_empty_values():
    merged = merge({}, {"sender": "", "subject": None, "summary": []}, identity=None)
    assert "sender" not in merged and "subject" not in merged and "summary" not in merged


def test_decide_splits_by_threshold():
    merged = merge(rule_fields(invoice(), CFG), {"sender": "Muster Treuhand AG", "subject": "Rechnung"},
                   identity=None)
    apply, review = decide(merged, threshold=0.85)
    assert "document_date" in apply and "amount_cents" in apply
    assert "sender" in review   # AI fields stay below the default threshold until the user lowers it


def test_ai_schema_is_closed():
    assert AI_SCHEMA["additionalProperties"] is False
    assert set(AI_SCHEMA["properties"]) >= {"type", "sender", "receiver", "subject", "summary"}
