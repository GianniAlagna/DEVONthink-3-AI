"""Stated deadlines in letters and invoices, de/fr/it/en (brief B5, SPEC §4.10). Pure, no AI.

Only a date the document states after a deadline phrase counts ("zahlbar bis 17. Mai 2026"). A relative
period ("innert 30 Tagen") is returned as a hint without a date: the start of such a period (receipt,
service) is not in the text, so no date is ever computed (brief B5/B6).
"""
import re
from dataclasses import dataclass
from datetime import date

from dt3agent.rules.dates import find_dates

PHRASES = [
    # de
    r"zahlbar\s+bis(?:\s+(?:spätestens|am))?", r"fällig\s+(?:am|bis)", r"fälligkeit(?:sdatum)?", r"zahlungsfrist",
    r"(?:bis\s+)?spätestens(?:\s+(?:am|bis))?", r"frist(?:ende)?", r"einzureichen\s+bis", r"zu\s+bezahlen\s+bis",
    # fr
    r"(?:à\s+)?payer\s+jusqu['’]au", r"payable\s+jusqu['’]au", r"échéance", r"au\s+plus\s+tard\s+le", r"délai",
    # it
    r"(?:da\s+)?pagare\s+entro\s+il", r"pagabile\s+entro\s+il", r"scadenza", r"entro\s+il", r"termine",
    # en
    r"due\s+(?:date|by|on)", r"payable\s+by", r"deadline", r"no\s+later\s+than",
]
DEADLINE = re.compile(r"(?<!\w)(" + "|".join(PHRASES) + r")\b\s*:?", re.IGNORECASE)
RELATIVE = re.compile(r"(?<!\w)((?:zahlbar\s+)?(?:innert|innerhalb(?:\s+von)?|binnen)\s+(\d{1,3})\s+tagen"
                      r"|dans\s+les\s+(\d{1,3})\s+jours|entro\s+(\d{1,3})\s+giorni|within\s+(\d{1,3})\s+days)",
                      re.IGNORECASE)
GAP = 25  # characters allowed between the phrase and its date


@dataclass(frozen=True)
class Deadline:
    date: date | None  # None: relative period, hint only
    phrase: str
    start: int


def find_deadlines(text: str) -> list[Deadline]:
    dates = find_dates(text)
    out = []
    for m in DEADLINE.finditer(text):
        d = next((f for f in dates if 0 <= f.start - m.end() <= GAP), None)
        if d and not any(x.start == d.start for x in out):
            out.append(Deadline(d.date, " ".join(m.group(1).split()), d.start))
    for m in RELATIVE.finditer(text):
        out.append(Deadline(None, " ".join(m.group(1).split()), m.start()))
    return sorted(out, key=lambda x: x.start)
