"""config.json: safe defaults, schema check, atomic write with backup (SPEC §4.1)."""
import copy
import json
import os
import re
from pathlib import Path

from dt3agent.naming import TOKEN, TOKENS

SCHEMA_VERSION = 1
JOB_TIME_RE = re.compile(r"([01]\d|2[0-3]):[0-5]\d")

DEFAULTS = {
    "schema_version": SCHEMA_VERSION,
    "dry_run": True,
    "scopes": [],  # [{"database": str, "group": str}]; nothing is processed unless listed
    # use_key (E-7): send the API key from the Keychain (service codes.modular.dt3agent.ai); never stored here
    "ai": {"backend": None, "url": None, "model": None, "context": 8192, "embed_url": None, "use_key": False},
    "naming": {"template": "{datetime}_{sender}_{receiver}_{subject}", "unknown": "unknown"},
    "thresholds": {"apply": 0.85},
    # Starter list (de-CH); the AI may only pick from it. Edited by the user (onboarding, Phase 5).
    "tags": {"vocabulary": ["Rechnung", "Mahnung", "Quittung", "Vertrag", "Brief", "Kontoauszug", "Steuern",
                            "Versicherung", "Lohn", "Betreibung", "Gericht", "Behörde", "Gesundheit", "Wohnung"]},
    # Keyword hints (SPEC §4.10), de/fr/it/en; the user edits them (Phase 5 settings)
    "keywords": {
        "doc_types": {
            "invoice": ["Rechnung", "Facture", "Fattura", "Invoice"],
            "reminder": ["Mahnung", "Zahlungserinnerung", "Rappel", "Sollecito", "Payment reminder"],
            "contract": ["Vertrag", "Contrat", "Contratto", "Contract"],
            "offer": ["Offerte", "Angebot", "Offre", "Offerta", "Quotation"],
            "receipt": ["Quittung", "Beleg", "Reçu", "Quittance", "Ricevuta", "Receipt"],
            "statement": ["Kontoauszug", "Relevé de compte", "Estratto conto", "Bank statement"],
            "official": ["Verfügung", "Entscheid", "Décision", "Decisione", "Steuerveranlagung"],
        },
        "urgent": ["Zahlungsbefehl", "Betreibung", "Betreibungsamt", "Betreibungsamtes", "Pfändung", "Konkurs",
                   "Vorladung", "Gericht", "commandement de payer", "poursuite", "office des poursuites",
                   "tribunal", "precetto esecutivo", "esecuzione", "tribunale",
                   "Steueramt", "Steuerverwaltung", "administration fiscale", "amministrazione fiscale"],
    },
    # Vision OCR helper (ADR-0006); helper path is set by the installer
    "vision": {"helper": None, "languages": ["de-DE", "fr-FR", "it-IT", "en-US"], "max_pages": 5},
    "identity": {"name": None},          # brief A5: inbound mail is addressed to this name
    "summary": {"target": "comment"},     # brief A9: 3-line summary into the DT3 comment
    # brief A8: filing only into groups listed here; off until the user sets the allowlist
    "filing": {"enabled": False, "groups": {}, "review_group": "/_AI-Review/"},
    # A10 (brief §5.2): near-duplicate threshold and the group for marked duplicates (user deletes manually)
    "duplicates": {"near_threshold": 0.8, "group": "/_Duplicates/"},
    # Phase 6 (SPEC §4.20): related records are proposed when their similarity reaches related_min (UNVERIFIED)
    # K-5: entity notes are opt-in and need an existing group (SPEC §4.20)
    "knowledge": {"related": True, "related_min": 0.75, "min_score": 0.35, "entities": False, "entity_group": ""},
    # Case folders: [{"name": str, "group": "/Path/", "words": [str, ...]}] -> matches become review items
    "cases": [],
    # brief B4: user-editable retention table; a hint in metadata only, never deletes (UI: not legal advice).
    # Example default: accounting records 10 years, OR Art. 958f.
    "retention": {"enabled": True, "classes": {"invoice": {"years": 10, "basis": "OR Art. 958f"},
                                               "receipt": {"years": 10, "basis": "OR Art. 958f"},
                                               "statement": {"years": 10, "basis": "OR Art. 958f"}}},
    # brief B6: accepted urgent letters move to this group (the user creates it; the engine never does).
    # Hints name a known legal deadline only as a hint to verify; no deadline is ever computed (brief B6).
    "urgent": {"group": "/_Urgent/", "hints": [
        {"words": ["Zahlungsbefehl", "commandement de payer", "precetto esecutivo"],
         "text": "Rechtsvorschlag: innert 10 Tagen nach Zustellung (SchKG Art. 74 Abs. 1) – bitte prüfen"}]},
    "update_check": False,
    "logs": {"content": False},
    # E-6 (SPEC §4.22): hold processing on battery and under memory pressure (brief §2.4)
    "power": {"pause_on_battery": True, "pause_on_memory_pressure": True},
    # J-2 (SPEC §4.21): local times; digest and hygiene need a target group and stay off until set
    # J-4: reports go to an existing group as Markdown, after the user's OK in the review list
    "jobs": {"nightly": {"enabled": True, "time": "02:30"},
             "digest": {"enabled": False, "day": "mon", "time": "07:30", "group": "", "lang": "de"},
             "hygiene": {"enabled": False, "day": "sun", "time": "03:30", "group": "", "lang": "de",
                         "inbox": "/Inbox/", "days": 14, "tags": True}},
}

# Expected type per key; nested dicts are checked one level deep.
TYPES = {
    "schema_version": int, "dry_run": bool, "scopes": list, "ai": dict, "naming": dict,
    "thresholds": dict, "update_check": bool, "logs": dict, "tags": dict, "keywords": dict, "vision": dict,
    "identity": dict, "summary": dict, "filing": dict, "duplicates": dict, "cases": list,
    "retention": dict, "urgent": dict, "knowledge": dict, "power": dict, "jobs": dict,
}


class ConfigError(ValueError):
    pass


class ShrinkError(ConfigError):
    """An import would disable scopes that are enabled now."""


def validate(cfg: dict) -> dict:
    if not isinstance(cfg, dict):
        raise ConfigError("config must be a JSON object")
    unknown = set(cfg) - set(DEFAULTS)
    if unknown:
        raise ConfigError(f"unknown keys: {sorted(unknown)}")
    for key, expected in TYPES.items():
        if key in cfg and not (isinstance(cfg[key], expected) and not (expected is int and isinstance(cfg[key], bool))):
            raise ConfigError(f"{key}: expected {expected.__name__}")
        if expected is dict and key in cfg:
            extra = set(cfg[key]) - set(DEFAULTS[key])
            if extra:
                raise ConfigError(f"{key}: unknown keys {sorted(extra)}")
    vocab = cfg.get("tags", {}).get("vocabulary", [])
    if not (isinstance(vocab, list) and len(vocab) <= 500
            and all(isinstance(t, str) and 0 < len(t) <= 64 and t.isprintable() for t in vocab)):
        raise ConfigError("tags.vocabulary: a list of up to 500 short tag names")
    kw = cfg.get("keywords", {})
    words_ok = lambda ws: isinstance(ws, list) and all(isinstance(w, str) and w.strip() for w in ws)  # noqa: E731
    if not (isinstance(kw.get("doc_types", {}), dict)
            and all(isinstance(t, str) and t and words_ok(ws) for t, ws in kw.get("doc_types", {}).items())
            and words_ok(kw.get("urgent", []))):
        raise ConfigError("keywords: doc_types maps names to word lists; urgent is a word list")
    filing = cfg.get("filing", {})
    groups = filing.get("groups", {})
    good_loc = lambda g: isinstance(g, str) and g.startswith("/") and ".." not in g.split("/")  # noqa: E731
    if not (isinstance(groups, dict) and all(isinstance(k, str) and good_loc(v) for k, v in groups.items())
            and (filing.get("review_group") is None or good_loc(filing.get("review_group")))):
        raise ConfigError("filing: groups map doc types to absolute group paths")
    for case in cfg.get("cases", []):
        if not (isinstance(case, dict) and set(case) == {"name", "group", "words"} and isinstance(case["name"], str)
                and case["name"].strip() and good_loc(case["group"]) and words_ok(case["words"]) and case["words"]):
            raise ConfigError("cases: each needs name, group (absolute path) and a non-empty word list")
    retention = cfg.get("retention", {})
    classes = retention.get("classes", {})
    if not (isinstance(retention.get("enabled", True), bool) and isinstance(classes, dict) and all(
            isinstance(t, str) and t.strip() and isinstance(c, dict) and set(c) == {"years", "basis"}
            and isinstance(c["years"], int) and not isinstance(c["years"], bool) and 0 <= c["years"] <= 100
            and isinstance(c["basis"], str) and 0 < len(c["basis"]) <= 120 for t, c in classes.items())):
        raise ConfigError("retention: enabled is true/false; classes map doc types to {years 0-100, basis}")
    urgent = cfg.get("urgent", {})
    if not ((urgent.get("group") is None or good_loc(urgent.get("group"))) and isinstance(urgent.get("hints", []), list)
            and all(isinstance(h, dict) and set(h) == {"words", "text"} and words_ok(h["words"]) and h["words"]
                    and isinstance(h["text"], str) and 0 < len(h["text"]) <= 200 for h in urgent.get("hints", []))):
        raise ConfigError("urgent: group is an absolute path; hints are {words, text}")
    know = cfg.get("knowledge", {})
    egroup = know.get("entity_group", "")
    if not (isinstance(know.get("entities", False), bool) and isinstance(egroup, str) and len(egroup) <= 500
            and ".." not in egroup.split("/") and (egroup.startswith("/") or not know.get("entities", False))):
        raise ConfigError("knowledge: entities is true/false and needs entity_group like /Group/ when on")
    rmin = know.get("related_min", 0.75)
    smin = know.get("min_score", 0.35)
    if not (isinstance(know.get("related", True), bool) and isinstance(rmin, (int, float))
            and not isinstance(rmin, bool) and 0.5 <= rmin <= 0.99
            and isinstance(smin, (int, float)) and not isinstance(smin, bool) and 0.0 <= smin <= 0.9):
        raise ConfigError("knowledge: related is true/false, related_min 0.5-0.99, min_score 0-0.9")
    if not all(isinstance(v, bool) for v in cfg.get("power", {}).values()):
        raise ConfigError("power: pause_on_battery and pause_on_memory_pressure are true/false")
    for name, spec in cfg.get("jobs", {}).items():
        # fields missing in an older file get their defaults when loaded
        _check_job(name, {**DEFAULTS["jobs"].get(name, {}), **spec} if isinstance(spec, dict) else spec)
    ident = cfg.get("identity", {}).get("name")
    if not (ident is None or (isinstance(ident, str) and len(ident) <= 200 and ident.isprintable())):
        raise ConfigError("identity.name: text up to 200 characters")
    naming = cfg.get("naming", {})
    if not all(isinstance(naming.get(k, "x"), str) and 0 < len(naming.get(k, "x")) <= 200
               for k in ("template", "unknown")):
        raise ConfigError("naming: template and unknown are non-empty text")
    tokens = TOKEN.findall(naming.get("template", "{date}"))
    if not tokens or set(tokens) - TOKENS:
        raise ConfigError("naming.template: use only known {tokens}")
    ai = cfg.get("ai", {})
    for key in ("url", "embed_url"):  # embed_url: second llama-server for the index (SPEC §4.20)
        url = ai.get(key)
        if not (url is None or (isinstance(url, str) and len(url) <= 300
                                and url.split("://")[0] in ("http", "https") and "://" in url)):
            raise ConfigError(f"ai.{key}: an http:// or https:// address")
    if not isinstance(ai.get("use_key", False), bool) or "api_key" in ai or "key" in ai:
        raise ConfigError("ai.use_key is true/false; the key itself belongs in the Keychain, never in config.json")
    if not (ai.get("model") is None or isinstance(ai.get("model"), str)) or not (
            isinstance(ai.get("context", 8192), int) and 512 <= ai.get("context", 8192) <= 262144):
        raise ConfigError("ai: model is text, context 512-262144")
    for scope in cfg.get("scopes", []):
        if not (isinstance(scope, dict) and set(scope) == {"database", "group"}
                and all(isinstance(v, str) and v for v in scope.values())):
            raise ConfigError("scopes: each entry needs non-empty 'database' and 'group'")
    return cfg


def _check_job(name: str, spec) -> None:
    default = DEFAULTS["jobs"].get(name)
    if default is None or not isinstance(spec, dict) or set(spec) != set(default):
        raise ConfigError(f"jobs.{name}: unknown job or wrong fields")
    ok = (isinstance(spec["enabled"], bool) and isinstance(spec["time"], str) and JOB_TIME_RE.fullmatch(spec["time"])
          and spec.get("day", "mon") in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
          and spec.get("lang", "de") in ("de", "fr", "it", "en") and isinstance(spec.get("tags", True), bool)
          and all(isinstance(spec.get(k, "/"), str) and len(spec.get(k, "/")) <= 500 and ".." not in spec.get(k, "/")
                  for k in ("group", "inbox"))
          and (not isinstance(spec.get("days"), bool) and isinstance(spec.get("days", 1), int)
               and 1 <= spec.get("days", 1) <= 365))
    if ok and spec["enabled"] and "group" in spec:
        ok = spec["group"].startswith("/")  # a report needs its target group (it must exist in DT3)
    if ok and "inbox" in spec:
        ok = spec["inbox"].startswith("/")
    if not ok:
        raise ConfigError(f"jobs.{name}: enabled true/false, time HH:MM, day mon-sun, lang de/fr/it/en, "
                          "group and inbox like /Group/ (group needed when enabled), days 1-365")


def _with_defaults(cfg: dict) -> dict:
    merged = copy.deepcopy(DEFAULTS)
    for key, value in cfg.items():
        merged[key] = {**merged[key], **value} if isinstance(DEFAULTS[key], dict) else value
    if isinstance(cfg.get("jobs"), dict):  # job settings are filled field by field (new fields get defaults)
        merged["jobs"] = {n: {**DEFAULTS["jobs"].get(n, {}), **v} if isinstance(v, dict) else v
                          for n, v in merged["jobs"].items()}
    return merged


def load(path: Path) -> dict:
    path = Path(path)
    if not path.exists():
        return copy.deepcopy(DEFAULTS)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ConfigError(f"config is not valid JSON: {e}") from e
    return _with_defaults(validate(raw))


def save(path: Path, cfg: dict) -> None:
    """Write via temp file + rename; the previous version is kept as <name>.bak."""
    path = Path(path)
    data = json.dumps(validate(cfg), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    if path.exists():
        os.replace(path, path.with_name(path.name + ".bak"))
    os.replace(tmp, path)


def merge(cfg: dict, changes: dict) -> dict:
    """New settings: top-level values replaced, dict sections updated one level deep (like loading a file)."""
    if not isinstance(changes, dict):
        raise ConfigError("changes must be an object")
    out = copy.deepcopy(cfg)
    for key, value in changes.items():
        if key not in DEFAULTS:
            raise ConfigError(f"unknown key: {key}")
        if key == "jobs" and isinstance(value, dict):  # one job's fields can change alone
            value = {n: {**out["jobs"].get(n, {}), **v} if isinstance(v, dict) else v for n, v in value.items()}
        out[key] = {**out[key], **value} if isinstance(DEFAULTS[key], dict) and isinstance(value, dict) else value
    return validate(out)


def import_config(path: Path, new: dict, confirm_shrink: bool = False) -> None:
    current = load(path)
    dropped = [s for s in current["scopes"] if s not in new.get("scopes", [])]
    if dropped and not confirm_shrink:
        raise ShrinkError(f"import would disable {len(dropped)} enabled scope(s)")
    save(path, _with_defaults(validate(new)))
