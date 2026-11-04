"""Engine service (Phase 2 T9): spool → queue → pipeline, plus the methods the CLI calls over rpc.

Single-threaded on purpose: the DT3 bridge is one pipe, so rpc requests and pipeline work take turns.
"""
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from dt3agent import __version__, config, pipeline, store
from dt3agent import queue as queuemod
from dt3agent.adapter import DT3Adapter
from dt3agent.ai import LlamaClient
from dt3agent.audit import UUID_RE, AuditLog
from dt3agent.intake import ingest_spool
from dt3agent.rpc import RPCError
from dt3agent.undo import MIGRATIONS as UNDO_MIGRATIONS
from dt3agent.undo import UndoJournal

STATE_MIGRATIONS = ["CREATE TABLE state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"]
# Order is part of the schema: append only.
ENGINE_MIGRATIONS = queuemod.MIGRATIONS + pipeline.MIGRATIONS + STATE_MIGRATIONS
DEFAULT_DATA = Path.home() / "Library/Application Support/DT3 Agent"


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
        self.pipeline = pipeline.Pipeline(self.adapter, self.ai, self.con, dry_run=self.cfg["dry_run"],
                                          vocabulary=self.cfg["tags"]["vocabulary"])

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
                                                     "WHERE decided_at IS NULL").fetchone()[0]}
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
            rows = self.con.execute("SELECT id, uuid, kind, code, payload_json, created_at FROM review_items "
                                    "WHERE decided_at IS NULL ORDER BY id DESC LIMIT 20").fetchall()
            return [{"id": i, "uuid": u, "kind": k, "code": c, "created_at": t,
                     "tags_add": json.loads(p).get("tags_add", []) if k == "planned" else []}
                    for i, u, k, c, p, t in rows]
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

    def close(self) -> None:
        for con in (self.con, self.undo_con):
            try:
                con.close()
            except sqlite3.Error:
                pass
