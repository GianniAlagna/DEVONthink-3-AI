"""J-6 feed and mail summaries (SPEC §4.21 D5, opt-in): one note proposal per day.

New RSS, web and e-mail records inside the enabled scopes are summarised with the K-6 summary (sanitised input,
no tools, no write path); the summaries become one review item of kind `report`. Accept writes the note into
the configured group. Which `kind` texts DT3 3.9 uses for these records is UNVERIFIED until the floor check;
the match is by substring, case-insensitive.
"""
from datetime import UTC, datetime, timedelta

from dt3agent import reports
from dt3agent.ai import AIError
from dt3agent.bridge import BridgeError
from dt3agent.knowledge import AskError, summarize

FEED_WORDS = ("rss", "feed", "html", "web", "mail", "eml", "message")
MAX_ITEMS = 10
FIRST_RUN = timedelta(days=1)
TITLES = {"de": "Feeds und Mails", "fr": "Flux et courriels", "it": "Feed e e-mail", "en": "Feeds and mail"}
NO_SUMMARY = {"de": "(keine Zusammenfassung)", "fr": "(pas de résumé)", "it": "(nessun riassunto)",
              "en": "(no summary)"}


def is_feed(kind: str) -> bool:
    k = (kind or "").lower()
    return any(w in k for w in FEED_WORDS)


def collect(adapter, queue, scopes: list[dict], now: datetime) -> list[dict]:
    """Feed records changed since the last run (first run: the last day), newest first, at most MAX_ITEMS."""
    found = []
    for scope in scopes:
        key = "feeds:" + scope["group"]
        since = queue.pull_since(scope["database"], key) or (now - FIRST_RUN).astimezone(UTC).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z")
        try:
            rows = adapter.list_scope(scope["database"], scope["group"], since)
        except BridgeError:
            continue
        found += [r for r in rows if is_feed(r["kind"])]
        newest = max((r["modified"] for r in rows if r["modified"]), default=None)
        if newest and newest > since:
            queue.set_pull_since(scope["database"], key, newest)
    found.sort(key=lambda r: r["modified"], reverse=True)
    seen, out = set(), []
    for r in found:
        if r["uuid"] not in seen:
            seen.add(r["uuid"])
            out.append(r)
    return out[:MAX_ITEMS]


def build(adapter, llm, items: list[dict], lang: str, now: datetime) -> tuple[str, str]:
    title = f"DT3 Agent – {TITLES[lang]} {now.date().isoformat()}"
    parts = [f"# {title}\n"]
    for r in items:
        name, summary = "?", NO_SUMMARY[lang]
        try:
            name = adapter.read(r["uuid"]).get("name") or "?"
            text, _ = adapter.read_text(r["uuid"])
            summary = summarize(text, lang, llm).text
        except (BridgeError, AskError, AIError):
            pass  # the record is still listed, with a link
        parts.append(f"## {reports._link(name, r['uuid'])}\n\n{summary}\n")
    return title, reports._cap("\n".join(parts))
