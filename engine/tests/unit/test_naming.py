"""P3-6 naming engine: brief §5.1, table-driven."""
from datetime import date, datetime

import pytest

from dt3agent.naming import NamingError, build_name

T = "{datetime}_{sender}_{receiver}_{subject}"
CREATED = datetime(2026, 11, 4, 9, 15, 30)


def name(fields, **kw):
    return build_name(kw.pop("template", T), fields, created=CREATED, **kw)


def test_standard_invoice():
    n = name({"document_date": date(2026, 4, 17), "sender": "Muster Treuhand AG", "receiver": "Erika Beispiel",
              "subject": "Rechnung 2026-0417"})
    assert n.value == "20260417000000_Muster-Treuhand-AG_Erika-Beispiel_Rechnung-2026-0417"
    assert n.date_source == "document"


def test_time_when_stated():
    n = name({"document_date": date(2026, 4, 17), "document_time": "14:30", "sender": "A", "receiver": "B",
              "subject": "C"})
    assert n.value.startswith("20260417143000_")


def test_creation_date_when_no_document_date():
    n = name({"sender": "A", "receiver": "B", "subject": "C"})
    assert n.value.startswith("20261104091530_") and n.date_source == "creation"


def test_missing_fields_are_placeholders_never_invented():
    n = name({"document_date": date(2026, 4, 17)})
    assert n.value == "20260417000000_unknown_unknown_unknown"
    assert name({"document_date": date(2026, 4, 17)}, unknown="unbekannt").value.endswith("_unbekannt")


@pytest.mark.parametrize("raw, clean", [
    ("A/B:C\\D*E?F\"G<H>I|J", "ABCDEFGHIJ"),           # forbidden characters stripped
    ("Straße Müller", "Strasse-Müller"),               # de-CH: no ß
    ("Société Générale", "Société-Générale"),          # fr accents kept
    ("Città   di  Lugano", "Città-di-Lugano"),         # it accents, runs of spaces
    ("under_score name", "under-score-name"),          # "_" only between fields
    ("  - trim -  ", "trim"),
    ("Mängelrüge – erneuter Defekt", "Mängelrüge-erneuter-Defekt"),  # floor 2026-11-05: en dash gave "-–-"
    ("A — B - C", "A-B-C"),                            # em dash and hyphen between words
    ("Café", "Café"),                            # NFC: e + combining accent -> é
])
def test_field_cleaning(raw, clean):
    n = name({"document_date": date(2026, 1, 1), "sender": raw, "receiver": "B", "subject": "C"})
    assert n.value.split("_")[1] == clean


def test_per_field_and_total_length():
    long = "Wort " * 100
    n = name({"document_date": date(2026, 1, 1), "sender": long, "receiver": long, "subject": long},
             max_field=40)
    parts = n.value.split("_")
    assert all(len(p) <= 40 for p in parts) and len(n.value) <= 200
    assert not any(p.endswith("-") for p in parts)
    n = name({"document_date": date(2026, 1, 1), "sender": long, "receiver": long, "subject": long},
             max_field=120)
    assert len(n.value) <= 200


def test_long_field_is_cut_between_words():
    # floor 2026-11-05: "…Getriebedefekt-2.-Gang-nach-Garanti" was cut inside a word
    n = name({"document_date": date(2026, 1, 1), "sender": "A", "receiver": "B",
              "subject": "erneuter Getriebedefekt 2. Gang nach Garantie Getriebeersatz"}, max_field=50)
    assert n.value.split("_")[3] == "erneuter-Getriebedefekt-2.-Gang-nach-Garantie"


def test_one_long_word_is_still_cut():
    n = name({"document_date": date(2026, 1, 1), "sender": "A", "receiver": "B", "subject": "x" * 80},
             max_field=40)
    assert n.value.split("_")[3] == "x" * 40


def test_collision_suffix_same_second():
    fields = {"document_date": date(2026, 4, 17), "sender": "A", "receiver": "B", "subject": "C"}
    first = name(fields).value
    assert name(fields, taken={first}).value == first + "_2"
    assert name(fields, taken={first, first + "_2"}).value == first + "_3"
    assert name(fields, taken={first.upper()}).value == first + "_2"   # case-insensitive like macOS


def test_other_tokens():
    n = name({"document_date": date(2026, 4, 17), "type": "invoice", "lang": "de", "amount_cents": 195704,
              "currency": "CHF", "reference": "21 00000 00003 13947 14300 09017"},
             template="{date}_{type}_{lang}_{amount}_{reference}")
    assert n.value == "20260417_invoice_de_CHF-1957.04_210000000003139471430009017"


def test_unknown_token_is_refused():
    with pytest.raises(NamingError):
        name({}, template="{datetime}_{author}")
