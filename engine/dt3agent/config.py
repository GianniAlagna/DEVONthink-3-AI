"""config.json: safe defaults, schema check, atomic write with backup (SPEC §4.1)."""
import copy
import json
import os
from pathlib import Path

SCHEMA_VERSION = 1

DEFAULTS = {
    "schema_version": SCHEMA_VERSION,
    "dry_run": True,
    "scopes": [],  # [{"database": str, "group": str}]; nothing is processed unless listed
    "ai": {"backend": None, "url": None, "model": None, "context": 8192},
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
                   "tribunal", "precetto esecutivo", "esecuzione", "tribunale"],
    },
    # Vision OCR helper (ADR-0006); helper path is set by the installer
    "vision": {"helper": None, "languages": ["de-DE", "fr-FR", "it-IT", "en-US"], "max_pages": 5},
    "identity": {"name": None},          # brief A5: inbound mail is addressed to this name
    "summary": {"target": "comment"},     # brief A9: 3-line summary into the DT3 comment
    # brief A8: filing only into groups listed here; off until the user sets the allowlist
    "filing": {"enabled": False, "groups": {}, "review_group": "/_AI-Review/"},
    # A10 (brief §5.2): near-duplicate threshold and the group for marked duplicates (user deletes manually)
    "duplicates": {"near_threshold": 0.8, "group": "/_Duplicates/"},
    # Case folders: [{"name": str, "group": "/Path/", "words": [str, ...]}] -> matches become review items
    "cases": [],
    "update_check": False,
    "logs": {"content": False},
}

# Expected type per key; nested dicts are checked one level deep.
TYPES = {
    "schema_version": int, "dry_run": bool, "scopes": list, "ai": dict, "naming": dict,
    "thresholds": dict, "update_check": bool, "logs": dict, "tags": dict, "keywords": dict, "vision": dict,
    "identity": dict, "summary": dict, "filing": dict, "duplicates": dict, "cases": list,
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
    for scope in cfg.get("scopes", []):
        if not (isinstance(scope, dict) and set(scope) == {"database", "group"}
                and all(isinstance(v, str) and v for v in scope.values())):
            raise ConfigError("scopes: each entry needs non-empty 'database' and 'group'")
    return cfg


def _with_defaults(cfg: dict) -> dict:
    merged = copy.deepcopy(DEFAULTS)
    for key, value in cfg.items():
        merged[key] = {**merged[key], **value} if isinstance(DEFAULTS[key], dict) else value
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


def import_config(path: Path, new: dict, confirm_shrink: bool = False) -> None:
    current = load(path)
    dropped = [s for s in current["scopes"] if s not in new.get("scopes", [])]
    if dropped and not confirm_shrink:
        raise ShrinkError(f"import would disable {len(dropped)} enabled scope(s)")
    save(path, _with_defaults(validate(new)))
