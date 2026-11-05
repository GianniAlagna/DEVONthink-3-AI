"""Standard document names (brief §5.1, SPEC §4.11).

Default `{datetime}_{sender}_{receiver}_{subject}`. "_" only between fields, "-" inside a field.
A missing field becomes the placeholder; a sender or subject is never invented here.
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

TOKENS = {"datetime", "date", "sender", "receiver", "subject", "type", "lang", "amount", "reference"}
FORBIDDEN = re.compile(r'[/:\\*?"<>|]')
TOKEN = re.compile(r"\{([a-z]+)\}")
SHORTEN_FIRST = ("subject", "sender", "receiver", "reference", "type")  # order in which long names are cut


class NamingError(ValueError):
    pass


@dataclass(frozen=True)
class Name:
    value: str
    date_source: str  # document | creation


def clean(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text)).replace("ß", "ss")
    text = FORBIDDEN.sub("", text)
    text = re.sub(r"[\s_\u2010-\u2015\u2212]+", "-", text)  # spaces and dashes (– — ‐ −) become one "-"
    return re.sub(r"-{2,}", "-", text).strip("-")


def _cut(value: str, limit: int) -> str:
    """Shorten to `limit`, between words where that keeps at least half (floor 2026-11-05: cut inside a word)."""
    if len(value) <= limit:
        return value
    cut = value[:limit]
    if value[limit] != "-":
        i = cut.rfind("-")
        if i >= limit // 2:
            cut = cut[:i]
    return cut.rstrip("-")


def build_name(template: str, fields: dict, *, created: datetime, unknown: str = "unknown",
               time_default: str = "000000", max_field: int = 60, max_total: int = 200,
               taken=frozenset()) -> Name:
    tokens = TOKEN.findall(template)
    if not tokens or set(tokens) - TOKENS:
        raise NamingError(f"unknown tokens: {sorted(set(tokens) - TOKENS) or 'none'}")
    doc_date = fields.get("document_date")
    if doc_date:
        hhmm = (fields.get("document_time") or "").replace(":", "")
        stamp, source = doc_date.strftime("%Y%m%d") + (hhmm + "00" if len(hhmm) == 4 else time_default), "document"
    else:
        stamp, source = created.strftime("%Y%m%d%H%M%S"), "creation"
    cents = fields.get("amount_cents")
    amount = f"{fields.get('currency', '')}-{cents // 100}.{cents % 100:02d}".lstrip("-") if cents is not None else ""
    raw = {"datetime": stamp, "date": stamp[:8], "sender": fields.get("sender"), "receiver": fields.get("receiver"),
           "subject": fields.get("subject"), "type": fields.get("type"), "lang": fields.get("lang"),
           "amount": amount, "reference": re.sub(r"\s", "", fields.get("reference") or "")}
    placeholder = clean(unknown) or "unknown"
    values = {t: _cut(clean(raw[t] or "") or placeholder, max_field) for t in tokens}

    def render() -> str:
        return TOKEN.sub(lambda m: values[m.group(1)], template)

    for t in SHORTEN_FIRST:  # too long: shorten the free-text fields first, never the date
        excess = len(render()) - max_total
        if excess <= 0:
            break
        if t in values:
            values[t] = _cut(values[t], max(len(placeholder), len(values[t]) - excess))
    value = render()[:max_total].rstrip("-_")
    taken_cf = {n.casefold() for n in taken}
    if value.casefold() in taken_cf:
        n = 2
        while f"{value}_{n}".casefold() in taken_cf:
            n += 1
        value = f"{value[:max_total - len(str(n)) - 1]}_{n}"
    return Name(value, source)
