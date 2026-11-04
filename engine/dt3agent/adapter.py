"""DT3 adapter: typed actions over the bridge; every write is journaled for undo first (SPEC §4.5)."""
from dt3agent.audit import AuditLog
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

    def read(self, uuid: str) -> dict:
        return self.bridge.call("read", uuid=uuid)

    def set_tags(self, uuid: str, tags: list[str], *, batch_id: str, actor: str) -> None:
        self.check_dt3()
        old = self.read(uuid)["tags"]
        if old == tags:
            return
        self.journal.record(batch_id, uuid, "tags", old, tags)  # before the write, never after
        self.bridge.call("set_tags", uuid=uuid, tags=tags)
        self.audit.write(actor=actor, action="set_tags", uuid=uuid, fields_changed=["tags"], batch_id=batch_id,
                         result="ok")

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
            current = self.read(e.uuid)[e.field]
            if current != e.new:
                conflicts.append(e.uuid)
                continue
            if e.field == "tags":
                self.bridge.call("set_tags", uuid=e.uuid, tags=e.old)
            self.journal.mark_undone(e.id)
            self.audit.write(actor="user", action="undo", uuid=e.uuid, fields_changed=[e.field], batch_id=e.batch_id,
                             result="undone")
            restored += 1
        return {"restored": restored, "conflicts": conflicts}
