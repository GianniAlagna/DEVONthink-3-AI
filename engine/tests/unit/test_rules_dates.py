"""P3-2 dates and times (brief A4, SPEC §4.10): table-driven, no AI."""
from datetime import date
from pathlib import Path

import pytest

from dt3agent.rules.dates import find_dates

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "spike"


@pytest.mark.parametrize("text, expected", [
    ("Zürich, 17. April 2026", date(2026, 4, 17)),
    ("Bern, 17.04.2026", date(2026, 4, 17)),
    ("Datum: 7.4.26", date(2026, 4, 7)),
    ("am 1. März 2026", date(2026, 3, 1)),
    ("am 1. Maerz 2026", date(2026, 3, 1)),
    ("Zurich, le 3 mars 2026", date(2026, 3, 3)),
    ("le 1er février 2026", date(2026, 2, 1)),
    ("le 15 aout 2026", date(2026, 8, 15)),
    ("Genève, 03/03/2026", date(2026, 3, 3)),
    ("Zurigo, 9 febbraio 2026", date(2026, 2, 9)),
    ("entro l'11 marzo 2026", date(2026, 3, 11)),
    ("Zurich, 20 January 2026", date(2026, 1, 20)),
    ("January 20, 2026", date(2026, 1, 20)),
    ("issued 2026-01-20", date(2026, 1, 20)),
])
def test_single_date(text, expected):
    found = find_dates(text)
    assert [f.date for f in found] == [expected]
    f = found[0]
    assert text[f.start:f.end] == f.raw and f.time is None


@pytest.mark.parametrize("text, time", [
    ("Termin am 17.04.2026 um 14:30 Uhr", "14:30"),
    ("Termin am 17.04.2026, 14.30 Uhr", "14:30"),
    ("rendez-vous le 3 mars 2026 à 9h15", "09:15"),
    ("appuntamento il 9 febbraio 2026 alle ore 08:05", "08:05"),
    ("meeting on 20 January 2026 at 16:45", "16:45"),
])
def test_time_next_to_a_date(text, time):
    assert find_dates(text)[0].time == time


@pytest.mark.parametrize("text", [
    "31.02.2026",            # no such day
    "17.13.2026",            # no month 13
    "Total CHF 1'957.04",    # amount, not a date
    "Version 2.1.3",
    "Telefon 044 123 45 67",
    "Rechnung Nr. 2026-0417",
    "MWST 8.1 %",
])
def test_not_dates(text):
    assert find_dates(text) == []


def test_invoice_dates_in_order():
    text = (FIXTURES / "invoice-de.txt").read_text(encoding="utf-8")
    assert [f.date for f in find_dates(text)] == [date(2026, 4, 17), date(2026, 5, 17)]


@pytest.mark.parametrize("lang, expected", [
    ("fr", [date(2026, 3, 3), date(2026, 4, 2)]),
    ("it", [date(2026, 2, 9), date(2026, 3, 11)]),
    ("en", [date(2026, 1, 20), date(2026, 2, 19)]),
])
def test_other_invoices(lang, expected):
    text = (FIXTURES / f"invoice-{lang}.txt").read_text(encoding="utf-8")
    assert [f.date for f in find_dates(text)] == expected


def test_date_range_gives_two_dates_and_no_time():
    found = find_dates("Ferien 17.04.2026 - 18.04.2026")
    assert [f.date for f in found] == [date(2026, 4, 17), date(2026, 4, 18)]
    assert [f.time for f in found] == [None, None]
