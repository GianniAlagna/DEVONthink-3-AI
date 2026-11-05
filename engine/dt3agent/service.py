"""Engine service (Phase 2 T9): spool → queue → pipeline, plus the methods the CLI calls over rpc.

Single-threaded on purpose: the DT3 bridge is one pipe, so rpc requests and pipeline work take turns.
"""
import json
import os
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from dt3agent import __version__, config, duplicates, pipeline, review, store
from dt3agent import queue as queuemod
from dt3agent.adapter import DT3Adapter
from dt3agent.ai import LlamaClient
from dt3agent.audit import UUID_RE, AuditLog
from dt3agent.bridge import BridgeError
from dt3agent.intake import ingest_spool
from dt3agent.rpc import RPCError
from dt3agent.undo import MIGRATIONS as UNDO_MIGRATIONS
from dt3agent.undo import UndoJournal
from dt3agent.vision import VisionClient

STATE_MIGRATIONS = ["CREATE TABLE state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"]
# Order is part of the schema: append only.
ENGINE_MIGRATIONS = (queuemod.MIGRATIONS + pipeline.MIGRATIONS + STATE_MIGRATIONS + review.MIGRATIONS
                     + duplicates.MIGRATIONS + review.MIGRATIONS_2)
DEFAULT_DATA = Path.home() / "Library/Application Support/DT3 Agent"


def _not_found(e: BaseException | None) -> bool:
    """True when the bridge said the record does not exist, also when wrapped in an RPCError."""
    while e is not None:
        if isinstance(e, BridgeError) and str(e) == "not_found":
            return True
        e = e.__cause__ or e.__context__
    return False


class Service:
    def __init__(self, data: Path, bridge):
        self.data = Path(data)
        self.data.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.spool = self.data / "spool"
        self.spool.mkdir(exist_ok=True, mode=0o700)
        os.chmod(self.spool, 0o700)
        self.config_path = self.data / "config.json"
        self.cfg = config.load(self.config_path)
        self.con = store.open_db(self.data / "engine.db", ENGINE_MIGRATIONS)
        self.undo_con = store.open_db(self.data / "undo.db", UNDO_MIGRATIONS)
        self.queue = queuemod.Queue(self.con, lambda: datetime.now(UTC))
        self.adapter = DT3Adapter(bridge, UndoJournal(self.undo_con), AuditLog(self.data / "audit"))
        ai_cfg = self.cfg["ai"]
        self.ai = LlamaClient(ai_cfg["url"], context=ai_cfg["context"]) if ai_cfg.get("url") else None
        v = self.cfg["vision"]
        self.vision = VisionClient(v["helper"], v["languages"], v["max_pages"]) if v.get("helper") else None
        self.pipeline = pipeline.Pipeline(self.adapter, self.ai, self.con, dry_run=self.cfg["dry_run"],
                                          vocabulary=self.cfg["tags"]["vocabulary"], vision=self.vision,
                                          settings=self.cfg)

    # state ---------------------------------------------------------------
    def _paused(self) -> bool:
        row = self.con.execute("SELECT value FROM state WHERE key = 'paused'").fetchone()
        return bool(row and row[0] == "1")

    def _set_paused(self, value: bool) -> None:
        with self.con:
            self.con.execute("INSERT OR REPLACE INTO state (key, value) VALUES ('paused', ?)", ("1" if value else "0",))

    # work ----------------------------------------------------------------
    def tick(self) -> str | None:
        """Pick up spool files, then process at most one job. Returns the outcome or error code."""
        ingest_spool(self.spool, self.queue)
        if self._paused() or self.ai is None:
            return None
        return self.pipeline.run_once(self.queue)

    # rpc -----------------------------------------------------------------
    def handle(self, method: str, params: dict):
        expected = {"status": set(), "process": {"uuid"}, "process_selected": set(), "review": set(),
                    "undo": set(), "pause": set(), "resume": set(), "live": {"on"}}
        expected["decide"] = {"id", "decision"} | ({"value"} if "value" in params else set())
        if method not in expected:
            raise RPCError("unknown_method")  # there is no delete method
        if set(params) != expected[method]:
            raise RPCError("bad_params")
        if method == "status":
            try:
                dt3 = self.adapter.bridge.call("info").get("version")
            except Exception:
                dt3 = None
            return {"version": __version__, "dt3_version": dt3, "paused": self._paused(),
                    "dry_run": self.pipeline.dry_run, "ai_configured": self.ai is not None,
                    "ai_ok": self.ai.health() if self.ai else False, "queue": self.queue.counts(),
                    "review_items": self.con.execute("SELECT COUNT(*) FROM review_items "
                                                     "WHERE decided_at IS NULL").fetchone()[0],
                    "urgent_open": self.con.execute("SELECT COUNT(*) FROM review_items WHERE kind = 'urgent' "
                                                    "AND decided_at IS NULL").fetchone()[0]}
        if method == "process":
            uuid = params["uuid"]
            if not (isinstance(uuid, str) and UUID_RE.fullmatch(uuid)):
                raise RPCError("bad_uuid")
            self.queue.enqueue(uuid, "cli")
            return {"queued": True}
        if method == "process_selected":
            uuids = self.adapter.selected()
            if not uuids:
                raise RPCError("nothing_selected")
            for uuid in uuids:
                self.queue.enqueue(uuid, "cli")
            return {"queued": len(uuids)}
        if method == "review":
            # codes and planned tags only: raw model output may echo document text and stays in the database
            rows = self.con.execute("SELECT id, uuid, kind, code, payload_json, created_at, record_missing "
                                    "FROM review_items WHERE decided_at IS NULL ORDER BY id DESC LIMIT 20").fetchall()
            out = []
            for i, u, k, c, p, t, missing in rows:
                missing = self._record_missing(u, bool(missing))
                review.set_missing(self.con, i, missing)
                row = self._review_row(i, u, k, c, json.loads(p), t)
                if k == "urgent":
                    row["group"] = self.cfg["urgent"]["group"]
                actions = (["reject"] if missing else ["accept", "reject"] if k == "urgent"
                           else ["accept", "edit", "reject"])
                row.update(record_missing=missing, actions=actions)
                out.append(row)
            return out
        if method == "decide":
            return self._decide(params)
        if method == "undo":
            try:
                return self.adapter.undo_last_batch()
            except Exception as e:
                raise RPCError("undo_failed") from e
        if method in ("pause", "resume"):
            self._set_paused(method == "pause")
            return {"paused": method == "pause"}
        if not isinstance(params["on"], bool):
            raise RPCError("bad_params")
        self.cfg["dry_run"] = not params["on"]
        config.save(self.config_path, self.cfg)
        self.pipeline.dry_run = self.cfg["dry_run"]
        return {"dry_run": self.pipeline.dry_run}

    @staticmethod
    def _review_row(i, u, k, c, p, t) -> dict:
        """Proposal details for the user's decision; raw model output (error items) is never shown."""
        row = {"id": i, "uuid": u, "kind": k, "code": c, "created_at": t,
               "tags_add": p.get("tags_add", []) if k == "planned" else []}
        if k == "field":
            row.update(field=p.get("field"), key=p.get("key"), after=p.get("after"),
                       confidence=p.get("confidence"), planned=bool(p.get("planned")))
        elif k == "duplicate":
            row.update(other=p.get("other"), method=p.get("method"), score=p.get("score"))
        elif k == "case":
            row.update(case=p.get("case"), group=p.get("group"))
        elif k == "urgent":
            row.update(words=p.get("after"), hints=p.get("hints", []))
        return row

    def _decide(self, params: dict) -> dict:
        if not isinstance(params["id"], int):
            raise RPCError("bad_params")
        value = params.get("value")
        kind = self.con.execute("SELECT kind FROM review_items WHERE id = ?", (params["id"],)).fetchone()
        if kind and kind[0] == "planned" and value is not None \
                and pipeline.clean_tags(value if isinstance(value, list) else [], None) != value:
            raise RPCError("bad_value")  # same rules as AI tags: no separators, printable, short
        if kind and kind[0] == "field" and isinstance(value, list):
            value = " ".join(value)  # the CLI sends words; a field value is one text
        if kind and kind[0] == "field" and value is not None and not (isinstance(value, str) and value.strip()):
            raise RPCError("bad_value")
        if kind and kind[0] == "urgent" and value is not None:
            raise RPCError("bad_value")  # accept (move to the urgent group) or reject
        if kind and kind[0] in ("duplicate", "case") and value is not None:
            value = " ".join(value) if isinstance(value, list) else value
            if not (isinstance(value, str) and re.fullmatch(r"(replicate|copy|link) /\S.*", value)):
                raise RPCError("bad_value")  # edit = "replicate /Group/" | "copy /Group/" | "link /Group/"
        try:
            result = review.decide(self.con, params["id"], params["decision"], value)
        except review.ReviewError as e:
            raise RPCError(str(e)) from None
        try:
            return self._apply(result, params)
        except Exception as e:
            review.reopen(self.con, params["id"])  # a failed write must not lose the item
            if _not_found(e):
                review.set_missing(self.con, params["id"], True)
                raise RPCError("record_missing") from None
            raise

    def _record_missing(self, uuid: str, known: bool) -> bool:
        """Does DT3 still have this record? Any other failure (DT3 closed, host gone) keeps what we knew."""
        try:
            self.adapter.read(uuid)
            return False
        except BridgeError as e:
            return True if str(e) == "not_found" else known

    def _apply(self, result: dict, params: dict) -> dict:
        if result["kind"] in ("duplicate", "case"):
            return self._a10(result, params["id"])
        if result["kind"] == "urgent":
            return self._urgent(result, params["id"])
        if result["apply"] is None:
            return {"applied": False}
        if result["kind"] == "field":  # name, comment, metadata, location: through the adapter with undo
            p = result["payload"]
            try:
                self.adapter.set_field(result["uuid"], p["field"], result["apply"], key=p.get("key"),
                                       batch_id=f"review-{params['id']}", actor="user")
            except Exception as e:
                raise RPCError("apply_failed") from e
            return {"applied": True}
        uuid, add = result["uuid"], [t for t in result["apply"] if isinstance(t, str)]
        current = list(self.adapter.read(uuid).get("tags") or [])
        self.adapter.set_tags(uuid, current + [t for t in add if t not in current],
                              batch_id=f"review-{params['id']}", actor="user")
        return {"applied": True}

    def _urgent(self, result: dict, item_id: int) -> dict:
        """B6: accept moves the letter to the urgent group; the group must exist (never created here)."""
        group = self.cfg["urgent"]["group"]
        if result["decision"] == "reject" or not group:
            return {"applied": False}
        try:
            self.adapter.set_field(result["uuid"], "location", group, batch_id=f"review-{item_id}", actor="user")
        except Exception as e:
            raise RPCError(str(e) if str(e) in ("group_not_found", "not_dt3") else "apply_failed") from e
        return {"applied": True}

    def _a10(self, result: dict, item_id: int) -> dict:
        """Execute the user's A10 choice (brief §5.2). Nothing is ever deleted."""
        uuid, p, decision, batch = result["uuid"], result["payload"], result["decision"], f"review-{item_id}"
        try:
            if decision == "reject":
                if result["kind"] == "duplicate":
                    duplicates.dismiss(self.con, uuid, p["other"])  # never ask again for this pair
                return {"applied": False}
            if decision == "accept" and result["kind"] == "case":
                self.adapter.replicate(uuid, p["group"], batch_id=batch)
            elif decision == "accept":  # mark as duplicate: tag + move to the duplicates group if it exists
                current = list(self.adapter.read(uuid).get("tags") or [])
                if "duplicate" not in current:
                    self.adapter.set_tags(uuid, current + ["duplicate"], batch_id=batch, actor="user")
                try:
                    self.adapter.set_field(uuid, "location", self.cfg["duplicates"]["group"], batch_id=batch,
                                           actor="user")
                except Exception:
                    pass  # no such group: the tag is enough, the user moves or deletes manually
            else:
                action, location = result["apply"].split(" ", 1)
                if action == "replicate":
                    self.adapter.replicate(uuid, location, batch_id=batch)
                elif action == "copy":
                    self.adapter.duplicate_copy(uuid, location, batch_id=batch)
                else:
                    self.adapter.link_note(uuid, location, self.adapter.read(uuid).get("name", ""), batch_id=batch)
        except RPCError:
            raise
        except Exception as e:
            raise RPCError(str(e) if str(e) in ("group_not_found", "not_dt3") else "apply_failed") from e
        return {"applied": True}

    def close(self) -> None:
        for con in (self.con, self.undo_con):
            try:
                con.close()
            except sqlite3.Error:
                pass
