"""Field extraction and merge: rules first, AI second (ADR-0009, SPEC §4.13 steps 3-6).

Every field is Field(value, source, confidence). Rule fields come from the pure rule modules; the AI only
fills what rules cannot know (sender, subject, summary, …) and never overrides a rule. Empty AI values are
dropped, so nothing is invented. `decide` splits fields into apply / review by the confidence threshold.
"""
from dataclasses import dataclass
from datetime import date

from dt3agent.rules import amounts, dates, keywords, language, payment

# Confidence per source. Rules are deterministic; AI answers are not calibrated, so they stay below the
# default apply threshold (0.85) and go to review until the user trusts them (SPEC §4.13 step 6).
CONF_RULE_STRONG = 0.95
CONF_RULE = 0.8
CONF_AI = 0.7
CONF_SETTINGS = 0.9

AI_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": ["string", "null"], "maxLength": 40},
        "lang": {"type": ["string", "null"], "enum": ["de", "fr", "it", "en", None]},
        "document_date": {"type": ["string", "null"], "maxLength": 10},
        "sender": {"type": ["string", "null"], "maxLength": 120},
        "receiver": {"type": ["string", "null"], "maxLength": 120},
        "subject": {"type": ["string", "null"], "maxLength": 160},
        "summary": {"type": "array", "items": {"type": "string", "maxLength": 200}, "maxItems": 3},
    },
    "required": ["type", "sender", "receiver", "subject", "summary"],
    "additionalProperties": False,
}
AI_TASK = ("Task: name the document type, the sender (who wrote it), the receiver, a short subject and a "
           "3-line summary. Use null when a field is not stated in the document.")


@dataclass(frozen=True)
class Field:
    value: object
    source: str      # rule | ai | settings
    confidence: float


def rule_fields(text: str, cfg: dict) -> dict[str, Field]:
    f: dict[str, Field] = {}
    lang, share = language.detect(text)
    if lang:
        f["lang"] = Field(lang, "rule", round(min(CONF_RULE_STRONG, share), 2))
    found = dates.find_dates(text)
    if found:  # the document date is the first stated date (letterhead "Zürich, 17. April 2026")
        f["document_date"] = Field(found[0].date, "rule", CONF_RULE_STRONG)
        if found[0].time:
            f["document_time"] = Field(found[0].time, "rule", CONF_RULE_STRONG)
    total = amounts.total(amounts.find_amounts(text))
    if total:
        f["amount_cents"] = Field(total.cents, "rule", CONF_RULE_STRONG)
        f["currency"] = Field(total.currency, "rule", CONF_RULE_STRONG)
    ibans = [i for i in payment.find_ibans(text) if i.valid]
    if ibans:
        f["iban"] = Field(ibans[0].iban, "rule", CONF_RULE_STRONG)
        f["qr_iban"] = Field(ibans[0].qr, "rule", CONF_RULE_STRONG)
    hits = keywords.scan(text, cfg["keywords"])
    if hits.doc_type():
        f["type"] = Field(hits.doc_type(), "rule", CONF_RULE)
    if hits.urgent:
        f["urgent"] = Field([h.word for h in hits.urgent], "rule", CONF_RULE_STRONG)
    return f


def _ai_date(value) -> date | None:
    try:
        return date.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None


def merge(rules: dict[str, Field], ai: dict, *, identity: str | None) -> dict[str, Field]:
    merged = dict(rules)
    for key in ("type", "lang", "sender", "receiver", "subject", "summary"):
        value = ai.get(key)
        if key in merged or value in (None, "", []):
            continue
        if isinstance(value, str):
            value = value.strip()
            if not value:
                continue
        merged[key] = Field(value, "ai", CONF_AI)
    if "document_date" not in merged and (d := _ai_date(ai.get("document_date"))):
        merged["document_date"] = Field(d, "ai", CONF_AI)
    if "receiver" not in merged and identity:  # brief A5: inbound mail is addressed to the user
        merged["receiver"] = Field(identity, "settings", CONF_SETTINGS)
    return merged


def decide(fields: dict[str, Field], threshold: float) -> tuple[dict[str, Field], dict[str, Field]]:
    apply = {k: v for k, v in fields.items() if v.confidence >= threshold}
    return apply, {k: v for k, v in fields.items() if k not in apply}
