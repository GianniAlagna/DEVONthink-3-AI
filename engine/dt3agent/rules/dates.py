"""Dates and times in document text, de/fr/it/en (brief A4, SPEC §4.10). Pure function, no AI.

Finds every date with its position; choosing the document date among them is the pipeline's job.
A time is attached only when it follows its date closely ("17.04.2026 um 14:30 Uhr").
Impossible dates (31.02.) are dropped by `datetime.date` itself.
"""
import re
from dataclasses import dataclass
from datetime import date

MONTHS = {
    1: "januar jan janvier janv gennaio gen january",
    2: "februar feb février fevrier févr fevr febbraio february",
    3: "märz maerz mär mrz mars marzo mar march",
    4: "april apr avril avr aprile",
    5: "mai maggio mag may",
    6: "juni jun juin giugno giu june",
    7: "juli jul juillet juil luglio lug july",
    8: "august aug août aout agosto ago",
    9: "september sep sept septembre settembre set",
    10: "oktober okt octobre oct ottobre ott october",
    11: "november nov novembre",
    12: "dezember dez décembre decembre dicembre dic december dec",
}
MONTH_OF = {name: n for n, names in MONTHS.items() for name in names.split()}
_MONTH = "|".join(sorted(map(re.escape, MONTH_OF), key=len, reverse=True))

PATTERNS = [
    # 17.04.2026 · 7.4.26 (Swiss numeric, day first)
    ("dmy", re.compile(r"(?<![\d.])(\d{1,2})\.(\d{1,2})\.(\d{4}|\d{2})(?![\d]|\.\d)")),
    # 03/03/2026 (fr/it, day first)
    ("dmy", re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4})(?![\d/])")),
    # 2026-01-20 (ISO)
    ("ymd", re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?![\d-])")),
    # 17. April 2026 · 3 mars 2026 · 1er février 2026 · l'11 marzo 2026 · 20 January 2026
    ("dMy", re.compile(rf"(?<!\d)(\d{{1,2}})(?:\.|er)?\s+({_MONTH})\.?\s+(\d{{4}})(?!\d)", re.IGNORECASE)),
    # January 20, 2026
    ("Mdy", re.compile(rf"\b({_MONTH})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})(?!\d)", re.IGNORECASE)),
]
TIME = re.compile(r"\D{0,20}?(?:(\d{1,2}):(\d{2})(?!\d)|(\d{1,2})\.(\d{2})\s*Uhr|(\d{1,2})h(\d{2}))")


@dataclass(frozen=True)
class Found:
    date: date
    time: str | None  # "HH:MM"
    start: int
    end: int
    raw: str


def _to_date(kind: str, g: tuple) -> date | None:
    if kind == "dmy":
        d, m, y = int(g[0]), int(g[1]), int(g[2])
    elif kind == "ymd":
        y, m, d = int(g[0]), int(g[1]), int(g[2])
    elif kind == "dMy":
        d, m, y = int(g[0]), MONTH_OF[g[1].casefold()], int(g[2])
    else:  # Mdy
        m, d, y = MONTH_OF[g[0].casefold()], int(g[1]), int(g[2])
    if y < 100:
        y += 2000
    if not 1900 <= y <= 2099:
        return None
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _time_after(text: str, end: int) -> str | None:
    m = TIME.match(text, end, min(len(text), end + 40))
    if not m:
        return None
    h, mi = next((m.group(i), m.group(i + 1)) for i in (1, 3, 5) if m.group(i))
    h, mi = int(h), int(mi)
    return f"{h:02d}:{mi:02d}" if h < 24 and mi < 60 else None


def find_dates(text: str) -> list[Found]:
    hits = []
    for kind, pattern in PATTERNS:
        for m in pattern.finditer(text):
            d = _to_date(kind, m.groups())
            if d:
                hits.append(Found(d, _time_after(text, m.end()), m.start(), m.end(), m.group(0)))
    hits.sort(key=lambda f: (f.start, -f.end))
    out = []
    for f in hits:  # keep the first, longest match where two patterns overlap
        if not out or f.start >= out[-1].end:
            out.append(f)
    return out
