"""K-5 entities (SPEC §4.20, opt-in): one note per person or company that appears in two or more records.

Names come from the pipeline's sender and receiver (rules, QR bill or AI; untrusted text, cleaned here) and never
include the user's own name. Each entity seen in 2+ records becomes one review item of kind `report`
(job `entity:<key>`): a Markdown note with links to its records, written only after the user's accept into
`knowledge.entity_group`, which must exist. A newer proposal for the same entity replaces the open one.
"""
import re
import unicodedata
from datetime import datetime

from dt3agent import reports

MIGRATIONS = [
    """CREATE TABLE entity_mentions (key TEXT NOT NULL, name TEXT NOT NULL, uuid TEXT NOT NULL,
        record_name TEXT NOT NULL, seen_at TEXT NOT NULL, PRIMARY KEY (key, uuid))""",
]
MIN_RECORDS = 2
MAX_LINKS = 50
LEGAL = re.compile(r"\b(ag|gmbh|sa|sàrl|sarl|srl|ltd|inc|kg|co)\b\.?", re.I)


def clean_name(name) -> str | None:
    if not isinstance(name, str):
        return None
    name = re.sub(r"[\[\]()<>*_`#|\\\r\n\t\x00-\x1f]", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" .,;:-–")
    if not (2 < len(name) <= 120) or not any(c.isalpha() for c in name):
        return None
    return name


def key_of(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name.casefold())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    plain = LEGAL.sub(" ", plain)
    return re.sub(r"[^0-9a-z]+", " ", plain).strip()


def record(con, uuid: str, record_name: str, names: list, identity: str | None, now: datetime) -> list[str]:
    """Remember who appears in this record. Returns the keys that now have enough records for a note."""
    own = key_of(identity) if identity else None
    ready = []
    for raw in names:
        name = clean_name(raw)
        key = key_of(name) if name else ""
        if not key or key == own:
            continue
        with con:
            con.execute("INSERT OR REPLACE INTO entity_mentions (key, name, uuid, record_name, seen_at) "
                        "VALUES (?, ?, ?, ?, ?)", (key, name, uuid, (record_name or "?")[:200], now.isoformat()))
        n = con.execute("SELECT COUNT(*) FROM entity_mentions WHERE key = ?", (key,)).fetchone()[0]
        if n >= MIN_RECORDS:
            ready.append(key)
    return ready


def decided(con, key: str) -> bool:
    """The user already accepted (note exists) or rejected a note for this entity: do not ask again."""
    return con.execute("SELECT 1 FROM review_items WHERE kind = 'report' AND decision IN ('accept', 'reject') "
                       "AND json_extract(payload_json, '$.job') = ?", (f"entity:{key}",)).fetchone() is not None


def propose(con, key: str, group: str, now: datetime) -> int:
    rows = con.execute("SELECT name, uuid, record_name FROM entity_mentions WHERE key = ? "
                       "ORDER BY seen_at DESC LIMIT ?", (key, MAX_LINKS)).fetchall()
    total = con.execute("SELECT COUNT(*) FROM entity_mentions WHERE key = ?", (key,)).fetchone()[0]
    name = rows[0][0]
    lines = "\n".join(f"- {reports._link(rn, u)}" for _, u, rn in rows)
    more = f"\n- … ({total - len(rows)})" if total > len(rows) else ""
    title = f"{name}"
    text = f"# {name}\n\n{lines}{more}\n"
    return reports.propose(con, f"entity:{key}", title, text, group, now)
