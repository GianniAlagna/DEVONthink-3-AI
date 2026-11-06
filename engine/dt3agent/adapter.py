"""DT3 adapter: typed actions over the bridge; every write is journaled for undo first (SPEC §4.5)."""
from dt3agent.audit import UUID_RE, AuditLog
from dt3agent.undo import Entry, UndoJournal


class NotDT3Error(RuntimeError):
    """The scripting target is not DEVONthink 3 (DT4 also answers; it is not supported)."""


class DT3Adapter:
    def __init__(self, bridge, journal: UndoJournal, audit: AuditLog):
        self.bridge = bridge  # anything with .call(verb, **args): the real Bridge or tests.fakes.FakeDT3
        self.journal = journal
        self.audit = audit
        self._checked = False

    def check_dt3(self) -> None:
        if self._checked:
            return
        version = str(self.bridge.call("info").get("version", ""))
        if not version.startswith("3."):
            raise NotDT3Error(f"DEVONthink {version or 'unknown'} is not supported; DT3 Agent works with DEVONthink 3")
        self._checked = True

    def selected(self) -> list[str]:
        """UUIDs of the records selected in DT3 (at most 100; anything malformed is dropped)."""
        uuids = self.bridge.call("selected").get("uuids") or []
        return [u for u in uuids[:100] if isinstance(u, str) and UUID_RE.fullmatch(u)]

    LIST_MAX = 500

    def list_scope(self, database: str, group: str, since: str = "") -> list[dict]:
        """J-1: records inside a scope group (deep), newest first, at most 500. Read-only; malformed rows dropped."""
        rows = self.bridge.call("list", database=database, group=group, since=since).get("records") or []
        out = []
        for r in rows:
            if (isinstance(r, dict) and isinstance(r.get("uuid"), str) and UUID_RE.fullmatch(r["uuid"])
                    and isinstance(r.get("modified"), str) and isinstance(r.get("kind"), str)):
                out.append({"uuid": r["uuid"], "modified": r["modified"], "kind": r["kind"]})
            if len(out) == self.LIST_MAX:
                break
        return out

    def read(self, uuid: str) -> dict:
        return self.bridge.call("read", uuid=uuid)

    def read_text(self, uuid: str) -> tuple[str, bool]:
        """Plain text of a record and whether it is complete (the host caps very long text; never cut silently)."""
        r = self.bridge.call("read_text", uuid=uuid)
        return r["text"], len(r["text"]) >= r["length"]

    def read_path(self, uuid: str) -> str:
        """File path of the record inside the DT3 database (for OCR; read-only)."""
        return str(self.bridge.call("read_path", uuid=uuid).get("path") or "")

    def set_tags(self, uuid: str, tags: list[str], *, batch_id: str, actor: str) -> None:
        self.check_dt3()
        old = self.read(uuid)["tags"]
        if old == tags:
            return
        self.journal.record(batch_id, uuid, "tags", old, tags)  # before the write, never after
        self.bridge.call("set_tags", uuid=uuid, tags=tags)
        self.audit.write(actor=actor, action="set_tags", uuid=uuid, fields_changed=["tags"], batch_id=batch_id,
                         result="ok")

    # Generic writes with undo (SPEC §4.5, §4.8): journal the old value first, then write, then audit.
    WRITE = {"name": ("set_name", "set_name"), "comment": ("set_comment", "set_comment"),
             "location": ("move", "move"), "metadata": ("set_metadata", "set_metadata")}

    def _current(self, record: dict, field: str, key: str | None = None):
        if field == "metadata":
            return {"key": key, "value": (record.get("metadata") or {}).get("md" + key)}
        return record.get(field)

    def _write(self, uuid: str, field: str, value) -> None:
        verb = self.WRITE[field][0]
        if field == "metadata":
            self.bridge.call(verb, uuid=uuid, key=value["key"], value=value["value"] or "")
        else:
            self.bridge.call(verb, uuid=uuid, **{"name": {"name": value}, "comment": {"comment": value},
                                                 "location": {"location": value}}[field])

    def set_field(self, uuid: str, field: str, value, *, batch_id: str, actor: str, key: str | None = None) -> bool:
        """Write name, comment, location (move) or one metadata key. Returns False when nothing changed."""
        if field not in self.WRITE:
            raise ValueError("field not writable")
        self.check_dt3()
        old = self._current(self.read(uuid), field, key)
        new = {"key": key, "value": value} if field == "metadata" else value
        if old == new:
            return False
        self.journal.record(batch_id, uuid, field, old, new)  # before the write, never after
        self._write(uuid, field, new)
        self.audit.write(actor=actor, action=self.WRITE[field][1], uuid=uuid, fields_changed=[field],
                         batch_id=batch_id, result="ok")
        return True

    # A10 actions (brief §5.2). They create replicants, copies or notes; the engine has no delete verb, so
    # these are not undone by the engine — they run only after the user's explicit choice in the review queue.
    def duplicates(self, uuid: str) -> list[str]:
        return [u for u in (self.bridge.call("duplicates", uuid=uuid).get("uuids") or [])[:20]
                if isinstance(u, str) and UUID_RE.fullmatch(u)]

    def replicate(self, uuid: str, location: str, *, batch_id: str) -> None:
        self.check_dt3()
        self.bridge.call("replicate", uuid=uuid, location=location)
        self.audit.write(actor="user", action="replicate", uuid=uuid, fields_changed=["replicants"],
                         batch_id=batch_id, result="ok")

    def duplicate_copy(self, uuid: str, location: str, *, batch_id: str) -> str:
        self.check_dt3()
        new = self.bridge.call("duplicate", uuid=uuid, location=location)["uuid"]
        self.audit.write(actor="user", action="duplicate", uuid=uuid, fields_changed=[], batch_id=batch_id,
                         result="ok")
        self.set_field(new, "metadata", f"x-devonthink-item://{uuid}", key="dt3agentoriginal",
                       batch_id=batch_id, actor="user")  # backlink to the original
        return new

    def link_note(self, uuid: str, location: str, title: str, *, batch_id: str) -> str:
        self.check_dt3()
        title = (title or "Link")[:200]
        new = self.bridge.call("create_markdown", location=location, name=f"Link – {title}",
                               text=f"[{title}](x-devonthink-item://{uuid})\n")["uuid"]
        self.audit.write(actor="user", action="create_markdown", uuid=uuid, fields_changed=["note"],
                         batch_id=batch_id, result="ok")
        return new

    def create_note(self, location: str, name: str, text: str, *, batch_id: str) -> str:
        """J-4, after the user's OK: a Markdown note (report) into an existing group. Not part of undo, like the
        other notes: the engine cannot delete what it created."""
        self.check_dt3()
        new = self.bridge.call("create_markdown", location=location, name=name[:200], text=text)["uuid"]
        self.audit.write(actor="user", action="create_markdown", uuid=new, fields_changed=["note"],
                         batch_id=batch_id, result="ok")
        return new

    def add_event(self, uuid: str, name: str, ics: str, when: str, *, batch_id: str) -> str:
        """B-5, after the user's OK: import the .ics next to the record and set its DT3 reminder. Like the A10
        actions this creates something the engine cannot delete, so it is not part of undo."""
        self.check_dt3()
        new = self.bridge.call("add_event", uuid=uuid, name=name, ics=ics, date=when)["uuid"]
        self.audit.write(actor="user", action="add_event", uuid=uuid, fields_changed=["reminder", "event"],
                         batch_id=batch_id, result="ok")
        return new

    def undo_last_batch(self) -> dict:
        batch = self.journal.last_batch()
        return self._undo(self.journal.entries(batch)) if batch else {"restored": 0, "conflicts": []}

    def undo_record(self, uuid: str) -> dict:
        return self._undo(self.journal.entries_for(uuid))

    def _undo(self, entries: list[Entry]) -> dict:
        """Restore old values, newest first. A record the user changed since is left alone (conflict)."""
        self.check_dt3()
        restored, conflicts = 0, []
        for e in entries:
            record = self.read(e.uuid)
            key = e.new.get("key") if e.field == "metadata" else None
            current = record.get("tags") if e.field == "tags" else self._current(record, e.field, key)
            if current != e.new:
                conflicts.append(e.uuid)
                continue
            if e.field == "tags":
                self.bridge.call("set_tags", uuid=e.uuid, tags=e.old)
            else:
                self._write(e.uuid, e.field, e.old)
            self.journal.mark_undone(e.id)
            self.audit.write(actor="user", action="undo", uuid=e.uuid, fields_changed=[e.field], batch_id=e.batch_id,
                             result="undone")
            restored += 1
        return {"restored": restored, "conflicts": conflicts}
