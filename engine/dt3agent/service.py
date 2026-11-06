"""Engine service (Phase 2 T9): spool → queue → pipeline, plus the methods the CLI calls over rpc.

Single-threaded on purpose: the DT3 bridge is one pipe, so rpc requests and pipeline work take turns.
"""
import copy
import json
import os
import re
import sqlite3
import time
from datetime import UTC, date, datetime
from pathlib import Path

from dt3agent import __version__, config, duplicates, jobs, naming, pipeline, review, store
from dt3agent import queue as queuemod
from dt3agent.adapter import DT3Adapter
from dt3agent.ai import AIError, LlamaClient
from dt3agent.audit import UUID_RE, AuditLog
from dt3agent.bridge import BridgeError
from dt3agent.embed import EmbedClient, EmbedError
from dt3agent.ics import build_event
from dt3agent.index import Index
from dt3agent.intake import ingest_spool
from dt3agent.knowledge import AskError, ask, summarize
from dt3agent.power import Power
from dt3agent.rpc import RPCError
from dt3agent.undo import MIGRATIONS as UNDO_MIGRATIONS
from dt3agent.undo import UndoJournal
from dt3agent.vision import VisionClient

STATE_MIGRATIONS = ["CREATE TABLE state (key TEXT PRIMARY KEY, value TEXT NOT NULL)"]
# Order is part of the schema: append only.
ENGINE_MIGRATIONS = (queuemod.MIGRATIONS + pipeline.MIGRATIONS + STATE_MIGRATIONS + review.MIGRATIONS
                     + duplicates.MIGRATIONS + review.MIGRATIONS_2 + jobs.MIGRATIONS)
# Settings the app may not change over rpc: the vision helper is a program the engine runs (set by the installer).
RPC_LOCKED = {"schema_version", "vision"}
DEFAULT_DATA = Path.home() / "Library/Application Support/DT3 Agent"
EMBED_MODEL = "Qwen3-Embedding-0.6B-Q8_0"  # ADR-0011; a different name clears index.db


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
        self.queue.recover_interrupted()  # one engine per data dir: anything 'running' now was cut off
        self.adapter = DT3Adapter(bridge, UndoJournal(self.undo_con), AuditLog(self.data / "audit"))
        self.index = None
        self.power = Power()
        self.scheduler = jobs.Scheduler(self.con)
        self.job_runners = {}  # name -> callable returning "ok" or a short error code (J-3, J-4 add theirs)
        self.local_clock = lambda: datetime.now().astimezone()
        self._use_config(self.cfg)

    def _use_config(self, cfg: dict) -> None:
        """Puts settings into effect at once: AI client, vision helper and pipeline are rebuilt from them."""
        self.cfg = cfg
        ai_cfg = cfg["ai"]
        self.ai = LlamaClient(ai_cfg["url"], context=ai_cfg["context"]) if ai_cfg.get("url") else None
        v = cfg["vision"]
        self.vision = VisionClient(v["helper"], v["languages"], v["max_pages"]) if v.get("helper") else None
        if ai_cfg.get("embed_url"):  # K-2: the index exists once an embedding server is set (ADR-0011)
            embedder = EmbedClient(ai_cfg["embed_url"])
            if self.index is None:
                self.index = Index(self.data / "index.db", embedder, model=EMBED_MODEL)
            self.index.embedder = embedder
        elif self.index is not None:
            self.index.con.close()
            self.index = None
        self.pipeline = pipeline.Pipeline(self.adapter, self.ai, self.con, dry_run=cfg["dry_run"],
                                          vocabulary=cfg["tags"]["vocabulary"], vision=self.vision,
                                          settings=cfg, index=self.index)

    def _change_config(self, changes: dict) -> dict:
        """Starts from the file, never from a copy in memory (floor 2026-11-05: a stale copy was written back)."""
        if set(changes) & RPC_LOCKED:
            raise RPCError("config_forbidden")
        try:
            new = config.merge(config.load(self.config_path), changes)
            config.save(self.config_path, new)
        except config.ConfigError as e:
            raise RPCError("config_invalid") from e
        self._use_config(config.load(self.config_path))
        return self.cfg

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
        if self._paused() or self.power.hold(self.cfg.get("power", {})):
            return None  # E-6: the queue keeps filling; work resumes when the Mac is on power again
        job = self._run_due_job()
        if job:
            return job
        if self.ai is None:
            return None
        return self.pipeline.run_once(self.queue)

    def _run_due_job(self) -> str | None:
        """J-2: at most one scheduled job per tick; a job without a runner yet is left alone."""
        now = self.local_clock()
        for name in self.scheduler.due(self.cfg.get("jobs", {}), now):
            runner = self.job_runners.get(name)
            if runner is None:
                continue
            try:
                result = runner()
            except Exception as e:  # a job failure never stops the engine; a short code is kept, never content
                code = str(e)
                result = code if isinstance(e, BridgeError) and re.fullmatch(r"[a-z][a-z0-9_]{0,39}", code) \
                    else "job_failed"
            self.scheduler.done(name, now, result)
            return f"job:{name}:{result}"
        return None

    # rpc -----------------------------------------------------------------
    def handle(self, method: str, params: dict):
        expected = {"status": set(), "process": {"uuid"}, "process_selected": set(),
                    "review": {"kind"} if "kind" in params else set(),
                    "undo": set(), "pause": set(), "resume": set(), "live": {"on"},
                    "config_get": set(), "config_set": {"changes"}, "naming_preview": {"template"},
                    "dt3_info": set(), "ask": {"question"}, "summary": {"uuid", "lang"}, "selected": set(),
                    "list": {"since"} if "since" in params else set()}
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
                                                    "AND decided_at IS NULL").fetchone()[0],
                    "index_docs": self.index.count() if self.index else None,
                    "power": {**self.power.state(), "held": self.power.hold(self.cfg.get("power", {}))},
                    "jobs": {n: self.scheduler.last(n) for n in jobs.ORDER}}
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
            kind = params.get("kind")
            if kind is not None and kind not in review.KINDS:
                raise RPCError("bad_params")
            rows = self.con.execute("SELECT id, uuid, kind, code, payload_json, created_at, record_missing "
                                    "FROM review_items WHERE decided_at IS NULL AND (? IS NULL OR kind = ?) "
                                    "ORDER BY id DESC LIMIT 20", (kind, kind)).fetchall()
            out, records = [], {}
            for i, u, k, c, p, t, missing in rows:
                if u not in records:
                    records[u] = self._record_state(u, bool(missing))
                missing, rec = records[u]
                review.set_missing(self.con, i, missing)
                payload = json.loads(p)
                row = self._review_row(i, u, k, c, payload, t)
                row.update(record_name=rec.get("name") if rec else None, before=self._before(k, payload, rec))
                if k == "urgent":
                    row["group"] = self.cfg["urgent"]["group"]
                actions = (["reject"] if missing else ["accept", "reject"] if k == "urgent"
                           else ["accept", "edit", "reject"])
                row.update(record_missing=missing, actions=actions)
                out.append(row)
            return out
        if method == "decide":
            return self._decide(params)
        if method == "ask":
            return self._ask(params["question"])
        if method == "summary":
            return self._summary(params["uuid"], params["lang"])
        if method == "list":  # J-1 floor check: read-only listing of every enabled scope, with timing
            out = []
            for scope in self.cfg.get("scopes", []):
                started = time.monotonic()
                row = {"database": scope["database"], "group": scope["group"]}
                try:
                    recs = self.adapter.list_scope(scope["database"], scope["group"], params.get("since", ""))
                    row.update(count=len(recs), newest=recs[0]["modified"] if recs else None)
                except BridgeError as e:
                    row["error"] = str(e)
                row["seconds"] = round(time.monotonic() - started, 1)
                out.append(row)
            return {"scopes": out}
        if method == "selected":  # read-only: which records are selected in DT3 (for the summary button)
            try:
                return {"uuids": self.adapter.selected()[:100]}
            except Exception as e:
                raise RPCError("dt3_unreachable") from e
        if method == "undo":
            try:
                return self.adapter.undo_last_batch()
            except Exception as e:
                raise RPCError("undo_failed") from e
        if method == "naming_preview":
            return {"name": self._naming_preview(params["template"])}
        if method == "dt3_info":
            try:
                info = self.adapter.bridge.call("info")
            except Exception as e:
                raise RPCError("dt3_unreachable") from e
            return {"version": info.get("version"), "databases": list(info.get("databases", []))}
        if method == "config_get":
            return copy.deepcopy(self.cfg)
        if method == "config_set":
            if not isinstance(params["changes"], dict) or not params["changes"]:
                raise RPCError("bad_params")
            return copy.deepcopy(self._change_config(params["changes"]))
        if method in ("pause", "resume"):
            self._set_paused(method == "pause")
            return {"paused": method == "pause"}
        if not isinstance(params["on"], bool):
            raise RPCError("bad_params")
        return {"dry_run": self._change_config({"dry_run": not params["on"]})["dry_run"]}

    def _ask(self, question) -> dict:
        """K-3: answer from the index with sources. Read-only: no write path exists from here."""
        if not isinstance(question, str):
            raise RPCError("bad_params")
        if self.index is None:
            raise RPCError("index_unavailable")
        if self.ai is None:
            raise RPCError("ai_unavailable")
        try:
            answer = ask(question, self.index, self.ai,
                         min_score=self.cfg.get("knowledge", {}).get("min_score", 0.35))
        except (AskError, AIError, EmbedError) as e:
            raise RPCError(e.code) from e
        sources = []
        for uuid in answer.sources:
            try:
                name = self.adapter.read(uuid).get("name")
            except Exception:  # deleted in DT3 since it was indexed: drop it from the index and the answer
                self.index.remove(uuid)
                continue
            sources.append({"uuid": uuid, "name": name, "link": "x-devonthink-item://" + uuid})
        # best: the closest excerpt's similarity, so "not found" can be calibrated on real documents (Q-1)
        return {"answer": answer.text, "sources": sources, "filtered": answer.filtered,
                "best": answer.best, "not_found": answer.not_found}

    def _summary(self, uuid, lang) -> dict:
        """K-6: summary of one record in de/fr/it/en. Read-only."""
        if not (isinstance(uuid, str) and UUID_RE.fullmatch(uuid)) or not isinstance(lang, str):
            raise RPCError("bad_params")
        if self.ai is None:
            raise RPCError("ai_unavailable")
        try:
            text, _ = self.adapter.read_text(uuid)
        except Exception as e:
            raise RPCError("record_missing" if _not_found(e) else "dt3_unreachable") from e
        try:
            result = summarize(text, lang, self.ai)
        except (AskError, AIError) as e:
            raise RPCError(e.code) from e
        return {"summary": result.text, "lang": lang, "partial": result.partial}

    @staticmethod
    def _naming_preview(template) -> str:
        """The template applied to a fixed synthetic sample, for the live preview in onboarding and settings."""
        if not (isinstance(template, str) and 0 < len(template) <= 200):
            raise RPCError("naming_invalid")
        sample = {"document_date": date(2026, 12, 17), "sender": "Muster Treuhand AG", "receiver": "Erika Beispiel",
                  "subject": "Rechnung 2026-0417", "type": "invoice", "lang": "de", "amount_cents": 195704,
                  "currency": "CHF", "reference": "21 00000 00003 13947 14300 09017"}
        try:
            return naming.build_name(template, sample, created=datetime(2026, 12, 17, tzinfo=UTC),
                                     unknown=config.DEFAULTS["naming"]["unknown"]).value
        except naming.NamingError as e:
            raise RPCError("naming_invalid") from e

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
        elif k == "deadline":
            after = p.get("after") or {}
            row.update(date=after.get("date"), title=after.get("title"), phrase=p.get("phrase"))
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
        if kind and kind[0] == "deadline" and value is not None:
            value = " ".join(value) if isinstance(value, list) else value
            try:
                ok = isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) and date.fromisoformat(value)
            except ValueError:
                ok = False
            if not ok:
                raise RPCError("bad_value")  # edit = another date, YYYY-MM-DD
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
        return self._record_state(uuid, known)[0]

    def _record_state(self, uuid: str, known: bool) -> tuple[bool, dict | None]:
        """(missing, record) — does DT3 still have it? Any other failure (DT3 closed, host gone) keeps what we knew."""
        try:
            return False, self.adapter.read(uuid)
        except BridgeError as e:
            return (True if str(e) == "not_found" else known), None

    @staticmethod
    def _before(kind: str, payload: dict, rec: dict | None):
        """The current value in DT3 that a proposal would replace (review window: before/after)."""
        if rec is None:
            return None
        if kind == "planned":
            return list(rec.get("tags") or [])
        if kind != "field":
            return None
        field = payload.get("field")
        if field == "metadata":
            meta = rec.get("metadata") or {}
            key = payload.get("key") or ""
            return meta.get("md" + key, meta.get(key))
        return rec.get({"name": "name", "comment": "comment", "location": "location"}.get(field, ""))

    def _apply(self, result: dict, params: dict) -> dict:
        if result["kind"] in ("duplicate", "case"):
            return self._a10(result, params["id"])
        if result["kind"] == "urgent":
            return self._urgent(result, params["id"])
        if result["kind"] == "deadline":
            return self._deadline(result, params["id"])
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

    def _deadline(self, result: dict, item_id: int) -> dict:
        """B5 after the user's OK: calendar event (.ics) into DT3 next to the record + DT3 reminder."""
        if result["apply"] is None:
            return {"applied": False}
        p, uuid = result["payload"]["after"], result["uuid"]
        when = result["apply"] if isinstance(result["apply"], str) else p["date"]
        title = p["title"]
        ics = build_event(uid=f"{uuid}-{when}", when=date.fromisoformat(when), title=title, notes=p["notes"],
                          url=f"x-devonthink-item://{uuid}", stamp=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
        name = re.sub(r"[/:\x00-\x1f]", "-", f"{title} {when}")[:110] + ".ics"
        try:
            self.adapter.add_event(uuid, name, ics, when, batch_id=f"review-{item_id}")
        except Exception as e:
            code = str(e)
            if code not in ("reminder_exists", "group_not_found", "not_dt3"):
                # host codes are short machine codes (e.g. compile_failed, dt3_error_1728): pass them on for the
                # floor diagnosis; anything else (a sentence) stays generic
                code = f"apply_failed_{code}" if re.fullmatch(r"[a-z][a-z0-9_]{0,39}", code) else "apply_failed"
            raise RPCError(code) from e
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
        if self.index is not None:
            self.index.con.close()
        for con in (self.con, self.undo_con):
            try:
                con.close()
            except sqlite3.Error:
                pass
