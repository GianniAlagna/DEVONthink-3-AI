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
    "update_check": False,
    "logs": {"content": False},
}

# Expected type per key; nested dicts are checked one level deep.
TYPES = {
    "schema_version": int, "dry_run": bool, "scopes": list, "ai": dict, "naming": dict,
    "thresholds": dict, "update_check": bool, "logs": dict,
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
