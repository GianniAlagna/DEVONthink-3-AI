"""Pipeline skeleton (SPEC §4.13, Phase 2 T8): read → text → AI tags → dry-run plan | live write with undo.

Phase 3 adds rules, naming, filing and the full review store; the shape stays: every outcome is one of
planned / applied / skipped / review, and transient failures are raised so the queue retries them.
"""
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime

from dt3agent import fields as fieldsmod
from dt3agent.ai import AIError
from dt3agent.plan import plan
from dt3agent.queue import ERROR_RE
from dt3agent.vision import VisionError

PIPELINE_VERSION = 1
MIGRATIONS = [
    """CREATE TABLE processed (
        uuid TEXT PRIMARY KEY,
        content_hash TEXT NOT NULL,
        pipeline_version INTEGER NOT NULL,
        done_at TEXT NOT NULL)""",
    """CREATE TABLE review_items (
        id INTEGER PRIMARY KEY,
        uuid TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('planned', 'error')),
        code TEXT,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        decided_at TEXT)""",
]
TAG_TASK = ("Task: choose up to 3 tags that describe what kind of document this is. "
            "Use only tags from the allowed list; return an empty list if none fits.")
TAG_SCHEMA = {
    "type": "object",
    "properties": {"tags": {"type": "array", "items": {"type": "string", "maxLength": 64}, "maxItems": 3}},
    "required": ["tags"],
    "additionalProperties": False,
}
# Bad output of the model: no write, a review item instead. Other AI errors (server down, HTTP) are retried.
REVIEW_CODES = {"ai_invalid_json", "ai_schema_mismatch", "ai_too_long", "ai_bad_response"}
QUEUE_STATE = {"planned": "review", "review": "review", "applied": "done", "skipped": "skipped"}


def tag_schema(vocabulary) -> dict:
    """With a vocabulary the schema carries an enum, so llama-server can only produce allowed tags."""
    if not vocabulary:
        return TAG_SCHEMA
    item = {"type": "string", "enum": list(vocabulary)}
    return {**TAG_SCHEMA, "properties": {"tags": {**TAG_SCHEMA["properties"]["tags"], "items": item}}}


@dataclass
class Outcome:
    status: str  # planned | applied | skipped | review
    tags_add: list[str] = field(default_factory=list)
    code: str | None = None


def clean_tags(candidates, vocabulary) -> list[str]:
    """AI tags are untrusted: printable, no separators, at most 64 characters, and from the vocabulary if one is set."""
    vocab = {v.casefold(): v for v in vocabulary} if vocabulary else None
    out = []
    for t in candidates:
        t = t.strip()
        if not t or len(t) > 64 or not t.isprintable() or any(c in t for c in ",;"):
            continue
        if vocab is not None:
            t = vocab.get(t.casefold())
            if t is None:
                continue
        if t not in out:
            out.append(t)
    return out


class Pipeline:
    def __init__(self, adapter, ai, con: sqlite3.Connection, *, dry_run: bool, vocabulary=None, vision=None,
                 settings: dict | None = None):
        """settings: the engine config. Without it the pipeline only tags (Phase 2 behaviour)."""
        self.adapter, self.ai, self.con, self.vision = adapter, ai, con, vision
        self.dry_run, self.vocabulary, self.settings = dry_run, vocabulary, settings

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    def _review(self, uuid, kind, code, payload, batch_id, result) -> None:
        with self.con:
            self.con.execute("INSERT INTO review_items (uuid, kind, code, payload_json, created_at) "
                             "VALUES (?, ?, ?, ?, ?)", (uuid, kind, code, json.dumps(payload), self._now()))
        action = "set_tags" if kind == "planned" else "review"
        field = payload.get("field")
        changed = ["tags"] if kind == "planned" else [field] if field in ("name", "comment", "metadata", "location") \
            else []
        self.adapter.audit.write(actor="ai", action=action, uuid=uuid, fields_changed=changed, batch_id=batch_id,
                                 result=result)

    def process(self, uuid: str, *, batch_id: str) -> Outcome:
        self.adapter.check_dt3()
        record = self.adapter.read(uuid)
        key = record.get("contentHash") or ""
        row = self.con.execute("SELECT content_hash, pipeline_version FROM processed WHERE uuid = ?",
                               (uuid,)).fetchone()
        if key and row == (key, PIPELINE_VERSION):
            self.adapter.audit.write(actor="engine", action="skip", uuid=uuid, fields_changed=[],
                                     batch_id=batch_id, result="skipped")
            return Outcome("skipped")
        text, complete = self.adapter.read_text(uuid)
        if not text.strip() and self.vision is not None:  # A1: no text layer -> Vision OCR, analysis only
            try:
                text, complete = self.vision.ocr(self.adapter.read_path(uuid)), True
            except VisionError as e:
                self._review(uuid, "error", e.code, {}, batch_id, "review")
                return Outcome("review", code=e.code)
        if not text.strip() or not complete:
            code = "no_text" if not text.strip() else "text_too_long"
            self._review(uuid, "error", code, {}, batch_id, "review")
            return Outcome("review", code=code)
        schema, task = tag_schema(self.vocabulary), TAG_TASK
        if self.settings is not None:  # one AI call for tags and the fields rules cannot know
            schema = {**schema, "properties": {**fieldsmod.AI_SCHEMA["properties"], **schema["properties"]},
                      "required": fieldsmod.AI_SCHEMA["required"] + schema["required"]}
            task = f"{fieldsmod.AI_TASK} {TAG_TASK}"
        try:
            result = self.ai.extract(text, schema, task=task)
        except AIError as e:
            if e.code not in REVIEW_CODES:
                raise
            self._review(uuid, "error", e.code, {"raw": e.raw}, batch_id, "review")
            return Outcome("review", code=e.code)
        wrote = False
        if self.settings is not None:
            proposals = plan(record, text, result.obj, self.settings)
            wrote = self._handle_fields(uuid, proposals, batch_id)
        current = list(record.get("tags") or [])
        add = [t for t in clean_tags(result.obj["tags"], self.vocabulary) if t not in current]
        if not add and self.settings is not None:
            self._mark(uuid, key)
            return Outcome("applied" if wrote else "planned" if self._planned else "skipped")
        if not add:
            if not clean_tags(result.obj["tags"], self.vocabulary):
                self._review(uuid, "error", "no_valid_tags", {"raw": result.raw}, batch_id, "review")
                return Outcome("review", code="no_valid_tags")
            self._mark(uuid, key)
            return Outcome("skipped")
        if self.dry_run:
            self._review(uuid, "planned", None, {"tags_add": add}, batch_id, "dry_run")
            if self.settings is not None:
                self._mark(uuid, key)
            return Outcome("planned", add)
        self.adapter.set_tags(uuid, current + add, batch_id=batch_id, actor="ai")
        self._mark(uuid, key)
        return Outcome("applied", add)

    _planned = False

    def _handle_fields(self, uuid: str, proposals: list, batch_id: str) -> bool:
        """Dry-run: every proposal becomes a planned review item. Live: apply what reaches the threshold,
        the rest becomes a review item. Urgent letters always go to review, never act on their own."""
        threshold = self.settings["thresholds"]["apply"]
        wrote, self._planned = False, False
        for p in proposals:
            payload = {"field": p.field, "key": p.key, "after": p.value, "confidence": p.confidence,
                       "source": p.source}
            if p.field == "urgent":
                self._review(uuid, "urgent", "urgent_letter", payload, batch_id, "review")
            elif self.dry_run:
                self._review(uuid, "field", None, {**payload, "planned": True}, batch_id, "dry_run")
                self._planned = True
            elif p.confidence >= threshold:
                wrote |= self.adapter.set_field(uuid, p.field, p.value, key=p.key, batch_id=batch_id,
                                                actor="rule" if p.source == "rule" else "ai")
            else:
                self._review(uuid, "field", None, payload, batch_id, "review")
        return wrote

    def _mark(self, uuid: str, key: str) -> None:
        if not key:
            return
        with self.con:
            self.con.execute("INSERT OR REPLACE INTO processed (uuid, content_hash, pipeline_version, done_at) "
                             "VALUES (?, ?, ?, ?)", (uuid, key, PIPELINE_VERSION, self._now()))

    def run_once(self, queue) -> str | None:
        """Process the next due job. Returns the outcome status or the error code; None when nothing is due."""
        job = queue.claim()
        if job is None:
            return None
        batch_id = f"job-{job.id}"
        try:
            out = self.process(job.uuid, batch_id=batch_id)
        except AIError as e:
            queue.fail(job.id, e.code)
            return e.code
        except Exception as e:  # bridge or DT3 errors: retry with back-off; only a short code is stored
            code = str(e) if ERROR_RE.fullmatch(str(e)) else "engine_error"
            queue.fail(job.id, code)
            return code
        queue.finish(job.id, QUEUE_STATE[out.status])
        return out.status
