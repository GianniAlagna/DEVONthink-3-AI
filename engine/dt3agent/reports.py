"""J-4 weekly digest and hygiene report (SPEC §4.21 D2, D3).

No AI call: the facts come from the engine's own tables and read-only DT3 lists. Each report becomes one
review item of kind `report`; only the user's accept writes it as a Markdown note into an existing group.
Names come from DT3 (user data); they are escaped for Markdown links. German texts without "ß" (de-CH).
"""
import json
import re
from datetime import UTC, datetime, timedelta

from dt3agent.bridge import BridgeError
from dt3agent.review import REPORT_UUID

MAX_TEXT = 8000   # also the bridge limit for a note
MAX_LINES = 40    # per section
MAX_READS = 300   # DT3 reads per hygiene report

T = {
    "de": {"digest": "Wochenübersicht", "hygiene": "Aufräum-Bericht", "new": "Neu verarbeitet",
           "deadlines": "Offene Fristen", "open": "Offene Vorschläge in der Prüfliste", "none": "keine",
           "untagged": "Ohne Tags", "inbox": "Seit über {days} Tagen in {group}", "more": "… und {n} weitere",
           "missing": "(nicht mehr in DT3)", "errors": "Nicht lesbar: {scopes}"},
    "fr": {"digest": "Aperçu de la semaine", "hygiene": "Rapport de rangement", "new": "Nouveaux traités",
           "deadlines": "Délais ouverts", "open": "Propositions ouvertes dans la liste de contrôle", "none": "aucun",
           "untagged": "Sans tags", "inbox": "Depuis plus de {days} jours dans {group}", "more": "… et {n} autres",
           "missing": "(plus dans DT3)", "errors": "Illisible : {scopes}"},
    "it": {"digest": "Riepilogo settimanale", "hygiene": "Rapporto di riordino", "new": "Nuovi elaborati",
           "deadlines": "Scadenze aperte", "open": "Proposte aperte nella lista di controllo", "none": "nessuno",
           "untagged": "Senza tag", "inbox": "Da oltre {days} giorni in {group}", "more": "… e altri {n}",
           "missing": "(non più in DT3)", "errors": "Non leggibile: {scopes}"},
    "en": {"digest": "Weekly digest", "hygiene": "Hygiene report", "new": "Newly processed",
           "deadlines": "Open deadlines", "open": "Open proposals in the review list", "none": "none",
           "untagged": "Without tags", "inbox": "In {group} for more than {days} days", "more": "… and {n} more",
           "missing": "(no longer in DT3)", "errors": "Not readable: {scopes}"},
}


def _link(name: str, uuid: str) -> str:
    name = re.sub(r"[\[\]\r\n\x00-\x1f]", " ", name or "?").strip()[:120] or "?"
    return f"[{name}](x-devonthink-item://{uuid})"


def _section(title: str, lines: list[str], t: dict, total: int | None = None) -> str:
    total = len(lines) if total is None else total
    shown = lines[:MAX_LINES]
    body = "\n".join(shown) if shown else f"- {t['none']}"
    if total > len(shown):
        body += f"\n- {t['more'].format(n=total - len(shown))}"
    return f"## {title} ({total})\n\n{body}\n"


def _cap(text: str) -> str:
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT - 2].rsplit("\n", 1)[0] + "\n…"


def _name(adapter, uuid: str, t: dict) -> str:
    try:
        return adapter.read(uuid).get("name") or "?"
    except BridgeError:
        return t["missing"]


def digest(con, adapter, now: datetime, lang: str) -> tuple[str, str]:
    """New records of the last 7 days, open deadlines, open proposals. `now` is an aware local time."""
    t = T[lang]
    since = (now - timedelta(days=7)).astimezone(UTC).isoformat()  # processed.done_at is UTC
    rows = con.execute("SELECT uuid FROM processed WHERE done_at >= ? ORDER BY done_at DESC", (since,)).fetchall()
    new = [f"- {_link(_name(adapter, u, t), u)}" for (u,) in rows[:MAX_LINES]]  # the rest is counted, not read
    deadlines = []
    for u, p in con.execute("SELECT uuid, payload_json FROM review_items WHERE kind = 'deadline' "
                            "AND decided_at IS NULL").fetchall():
        after = json.loads(p).get("after") or {}
        deadlines.append((str(after.get("date") or ""), str(after.get("title") or "?"), u))
    deadlines.sort()
    dl = [f"- {d}: {_link(title, u)}" for d, title, u in deadlines]
    open_n = con.execute("SELECT COUNT(*) FROM review_items WHERE decided_at IS NULL "
                         "AND kind != 'report'").fetchone()[0]
    title = f"DT3 Agent – {t['digest']} {now.date().isoformat()}"
    text = (f"# {title}\n\n" + _section(t["new"], new, t, total=len(rows)) + "\n"
            + _section(t["deadlines"], dl, t) + f"\n## {t['open']}: {open_n}\n")
    return title, _cap(text)


def hygiene(adapter, scopes: list[dict], spec: dict, now: datetime) -> tuple[str, str]:
    """Untagged records and records still in the inbox group after N days, within the enabled scopes."""
    t = T[spec["lang"]]
    cutoff = (now - timedelta(days=spec["days"])).astimezone()
    untagged, stale, broken, reads = [], [], [], 0
    for scope in scopes:
        try:
            rows = adapter.list_scope(scope["database"], scope["group"], "")
        except BridgeError:
            broken.append(f"{scope['database']} {scope['group']}")
            continue
        for r in rows:
            if reads >= MAX_READS:
                break
            reads += 1
            try:
                rec = adapter.read(r["uuid"])
            except BridgeError:
                continue
            link = f"- {_link(rec.get('name'), r['uuid'])}"
            if not rec.get("tags"):
                untagged.append(link)
            try:
                old = r["modified"] and datetime.fromisoformat(r["modified"].replace("Z", "+00:00")) < cutoff
            except ValueError:
                old = False
            if old and str(rec.get("location") or "").startswith(spec["inbox"]):
                stale.append(link)
    title = f"DT3 Agent – {t['hygiene']} {now.date().isoformat()}"
    text = (f"# {title}\n\n" + _section(t["untagged"], untagged, t) + "\n"
            + _section(t["inbox"].format(days=spec["days"], group=spec["inbox"]), stale, t))
    if broken:
        text += "\n" + t["errors"].format(scopes=", ".join(broken)) + "\n"
    return title, _cap(text)


def propose(con, job: str, title: str, text: str, group: str, now: datetime) -> int:
    """One open report per job: a newer one replaces the older open one (closed without a decision)."""
    with con:
        con.execute("UPDATE review_items SET decided_at = ? WHERE kind = 'report' AND decided_at IS NULL "
                    "AND json_extract(payload_json, '$.job') = ?", (now.isoformat(), job))
        cur = con.execute("INSERT INTO review_items (uuid, kind, code, payload_json, created_at) "
                          "VALUES (?, 'report', ?, ?, ?)",
                          (REPORT_UUID, job, json.dumps({"job": job, "title": title, "text": text, "group": group}),
                           now.isoformat()))
    return cur.lastrowid
