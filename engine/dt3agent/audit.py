"""Audit log: one JSON line per action, never document content (SPEC §4.3, brief §7).

Every field is checked against an allowlist, so free text cannot reach the log by accident.
"""
import json
import re
from datetime import UTC, datetime
from pathlib import Path

ACTORS = {"rule", "ai", "user", "engine"}
ACTIONS = {"set_name", "set_tags", "set_comment", "set_metadata", "move", "replicate", "duplicate",
           "create_markdown", "import", "undo", "skip", "review"}
FIELDS = {"name", "tags", "comment", "metadata", "location", "replicants", "note"}
RESULTS = {"ok", "skipped", "review", "failed", "undone", "dry_run"}
UUID_RE = re.compile(r"[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}")
BATCH_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")


class AuditLog:
    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def write(self, *, actor: str, action: str, uuid: str, fields_changed: list[str], batch_id: str,
              result: str) -> None:
        if actor not in ACTORS:
            raise ValueError("actor not allowed")
        if action not in ACTIONS:
            raise ValueError("action not allowed")
        if not UUID_RE.fullmatch(uuid):
            raise ValueError("uuid malformed")
        if not (isinstance(fields_changed, list) and set(fields_changed) <= FIELDS):
            raise ValueError("fields_changed must list known field names only")
        if not BATCH_RE.fullmatch(batch_id):
            raise ValueError("batch_id malformed")
        if result not in RESULTS:
            raise ValueError("result not allowed")
        now = datetime.now(UTC)
        event = {"ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "actor": actor, "action": action, "uuid": uuid,
                 "fields_changed": fields_changed, "batch_id": batch_id, "result": result}
        self.directory.mkdir(parents=True, exist_ok=True)
        with open(self.directory / f"audit-{now:%Y-%m-%d}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
