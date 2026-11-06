"""E-8 diagnostics export (SPEC §4.22): a zip for support, without personal data.

Safe by default: from the settings only true/false, numbers and a short list of fixed values are kept; every
other text becomes "<set>" or "" and every list becomes its length. No document text, names, group paths or
UUIDs: queue and review data are counts, errors are short codes, the audit log is counted by action and result.
"""
import json
import os
import subprocess
import zipfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

LABELS = ("codes.modular.dt3agent.engine", "codes.modular.dt3agent.llama", "codes.modular.dt3agent.embed")
# settings whose text is a fixed choice, not personal data
KEEP_TEXT = {("jobs", "*", "time"), ("jobs", "*", "day"), ("jobs", "*", "lang"), ("ai", "model"),
             ("naming", "template"), ("naming", "unknown")}


def redact(value, path: tuple = ()):
    if isinstance(value, bool) or value is None or isinstance(value, (int, float)):
        return value
    if isinstance(value, dict):
        return {k: redact(v, path + (k,)) for k, v in value.items()}
    if isinstance(value, list):
        return {"items": len(value)}
    keep = any(len(p) == len(path) and all(a in ("*", b) for a, b in zip(p, path, strict=True)) for p in KEEP_TEXT)
    if keep and isinstance(value, str) and len(value) <= 200:
        return value
    return "<set>" if value else ""


def _launchd(label: str, runner) -> str:
    plist = Path.home() / "Library/LaunchAgents" / f"{label}.plist"
    if not plist.exists():
        return "not_installed"
    try:
        loaded = runner(["/bin/launchctl", "print", f"gui/{os.getuid()}/{label}"]) == 0
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return "loaded" if loaded else "installed_not_loaded"


def _run(argv: list[str]) -> int:
    return subprocess.run(argv, capture_output=True, timeout=5, check=False).returncode


def collect(svc, *, runner=_run, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    week = (now - timedelta(days=7)).isoformat()
    con = svc.con
    errors = Counter(dict(con.execute("SELECT last_error, COUNT(*) FROM jobs WHERE last_error IS NOT NULL "
                                      "AND updated_at >= ? GROUP BY last_error", (week,)).fetchall()))
    review = dict(con.execute("SELECT kind, COUNT(*) FROM review_items WHERE decided_at IS NULL "
                              "GROUP BY kind").fetchall())
    audit = Counter()
    for f in sorted((svc.data / "audit").glob("audit-*.jsonl"))[-7:]:
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            audit[f"{e.get('actor')}:{e.get('action')}:{e.get('result')}"] += 1
    status = svc.handle("status", {})
    models = svc.data / "models"
    return {
        "created": now.isoformat(timespec="seconds"),
        "engine_version": status.get("version"), "dt3_version": status.get("dt3_version"),
        "health": {k: status.get(k) for k in ("paused", "dry_run", "ai_configured", "ai_ok", "embed_ok",
                                              "queue_backlog", "index_docs", "power")},
        "last_job": {k: v for k, v in (status.get("last_job") or {}).items() if k in ("state", "error", "at")},
        "jobs": {n: {k: v for k, v in (r or {}).items() if k in ("ran_at", "result")}
                 for n, r in (status.get("jobs") or {}).items()},
        "queue": status.get("queue"), "review_open": review, "errors_7d": dict(errors),
        "audit_7d": dict(audit),
        "launch_agents": {label.rsplit(".", 1)[1]: _launchd(label, runner) for label in LABELS},
        "models": {p.name: p.stat().st_size for p in sorted(models.glob("*.gguf"))} if models.is_dir() else {},
        "config": redact(svc.cfg),
    }


def export(svc, folder: Path, *, runner=_run, now: datetime | None = None) -> Path:
    now = now or datetime.now(UTC)
    data = collect(svc, runner=runner, now=now)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"DT3-Agent-Diagnose-{now:%Y%m%d-%H%M%S}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("diagnostics.json", json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False))
        z.writestr("README.txt", "DT3 Agent diagnostics: settings without personal values, counts and short "
                                 "error codes. No document text, names, group paths or record IDs.\n")
    os.chmod(path, 0o600)
    return path
