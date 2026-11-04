"""Fake DEVONthink 3 behind the bridge protocol: deterministic, in memory (SPEC §8 integration tests)."""
from dt3agent.bridge import BridgeError, validate


class FakeDT3:
    """Answers the same verbs as the Swift host. Records are plain dicts keyed by UUID."""

    def __init__(self, records=None, version="3.9.17"):
        self.version = version
        self.records = {u: dict(r, uuid=u) for u, r in (records or {}).items()}
        self.calls = []

    def call(self, verb, **args):
        validate(verb, args)  # same fence as the real bridge client
        self.calls.append((verb, args))
        if verb == "info":
            return {"version": self.version, "databases": ["DT3Agent-Test"]}
        rec = self.records.get(args["uuid"])
        if rec is None:
            raise BridgeError("not_found")
        if verb == "read":
            return dict(rec)
        if verb == "set_tags":
            if not self.version.startswith("3."):  # the host refuses writes to non-DT3 (main.swift requireDT3)
                raise BridgeError("not_dt3")
            rec["tags"] = list(args["tags"])
            return {"uuid": rec["uuid"], "tags": rec["tags"]}
        raise BridgeError("verb_not_allowed")
