"""What the pipeline proposes for one record (brief A3-A9, SPEC §4.13 steps 5-6).

Turns rule fields + the AI answer into proposals: name (A6), summary as comment (A9), metadata from rules,
filing into allowed groups only (A8), urgent flag. Each proposal carries the confidence of the weakest
field it is built from, so a name with an AI sender goes to review until the user trusts the AI.
"""
from dataclasses import dataclass
from datetime import UTC, datetime

from dt3agent import fields as fieldsmod
from dt3agent.naming import build_name


@dataclass(frozen=True)
class Proposal:
    field: str          # name | comment | metadata | location | urgent
    value: object
    confidence: float
    source: str
    key: str | None = None   # metadata key


def _created(record: dict) -> datetime:
    try:
        return datetime.fromisoformat(str(record.get("created", "")).replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def plan(record: dict, text: str, ai: dict, cfg: dict, bill: dict | None = None) -> list[Proposal]:
    """bill: a parsed QR-bill (B-2) or None."""
    merged = fieldsmod.merge(fieldsmod.rule_fields(text, cfg), ai, identity=cfg["identity"]["name"],
                             qr=fieldsmod.qr_fields(bill))
    out: list[Proposal] = []

    used = ("document_date", "sender", "receiver", "subject")
    values = {k: f.value for k, f in merged.items()}
    name = build_name(cfg["naming"]["template"], values, created=_created(record), unknown=cfg["naming"]["unknown"])
    weakest = min((merged[k].confidence if k in merged else 0.0) for k in used)
    if name.value != record.get("name"):
        out.append(Proposal("name", name.value, weakest, "rule" if weakest >= fieldsmod.CONF_RULE else "ai"))

    if cfg["summary"]["target"] == "comment" and "summary" in merged:
        lines = [str(x).strip() for x in merged["summary"].value if str(x).strip()][:3]
        if lines:
            out.append(Proposal("comment", "\n".join(lines), merged["summary"].confidence, merged["summary"].source))

    meta = {"dt3agentdate": ("document_date", lambda v: v.isoformat()), "dt3agentiban": ("iban", str),
            "dt3agentlang": ("lang", str), "dt3agentreference": ("reference", str)}
    for key, (field, fmt) in meta.items():
        if field in merged and merged[field].source in ("rule", "qr"):
            f = merged[field]
            out.append(Proposal("metadata", fmt(f.value), f.confidence, f.source, key))
    if "amount_cents" in merged:
        c = merged["amount_cents"]
        out.append(Proposal("metadata", f"{merged['currency'].value} {c.value // 100}.{c.value % 100:02d}",
                            c.confidence, c.source, "dt3agenttotal"))

    filing = cfg["filing"]
    if filing["enabled"]:
        t = merged.get("type")
        group = filing["groups"].get(t.value) if t else None
        if group and t.confidence >= cfg["thresholds"]["apply"]:
            out.append(Proposal("location", group, t.confidence, t.source))
        elif filing["review_group"]:  # A8: not sure where it belongs -> the review group, never a guess
            out.append(Proposal("location", filing["review_group"], 1.0, "rule"))

    if "urgent" in merged:
        out.append(Proposal("urgent", merged["urgent"].value, 1.0, "rule"))
    return out
