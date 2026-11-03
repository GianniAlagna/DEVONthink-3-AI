"""Client for the DT3 bridge in the Swift engine host (SPEC §4.4, ADR-0005).

The host is the only process that sends Apple events to DEVONthink 3. The engine talks to it over its own
stdin/stdout: one JSON request per line out, one JSON response per line back. stdout is reserved for this
protocol; the engine logs to stderr. Requests are validated here and again in the host.
"""
import json

from dt3agent.audit import UUID_RE

MAX_TAGS = 100
MAX_TAG_LEN = 255
# verb -> required argument names. There is no delete verb (brief §2.7).
VERBS = {"info": set(), "read": {"uuid"}, "set_tags": {"uuid", "tags"}}


class BridgeError(RuntimeError):
    pass


def validate(verb: str, args: dict) -> None:
    if verb not in VERBS:
        raise BridgeError(f"verb not allowed: {verb!r}")
    if set(args) != VERBS[verb]:
        raise BridgeError(f"{verb}: expected arguments {sorted(VERBS[verb])}")
    if "uuid" in args and not (isinstance(args["uuid"], str) and UUID_RE.fullmatch(args["uuid"])):
        raise BridgeError("uuid malformed")
    if "tags" in args:
        tags = args["tags"]
        if not (isinstance(tags, list) and len(tags) <= MAX_TAGS
                and all(isinstance(t, str) and 0 < len(t) <= MAX_TAG_LEN for t in tags)):
            raise BridgeError("tags must be a list of short strings")


class Bridge:
    def __init__(self, rfile, wfile):
        self.rfile = rfile
        self.wfile = wfile
        self.next_id = 1

    def call(self, verb: str, **args):
        validate(verb, args)
        request_id = self.next_id
        self.next_id += 1
        self.wfile.write(json.dumps({"id": request_id, "verb": verb, "args": args}) + "\n")
        self.wfile.flush()
        line = self.rfile.readline()
        if not line:
            raise BridgeError("host_closed")
        try:
            response = json.loads(line)
        except ValueError as e:
            raise BridgeError("protocol: response is not JSON") from e
        if not isinstance(response, dict) or response.get("id") != request_id:
            raise BridgeError("protocol: response does not match request")
        if not response.get("ok"):
            raise BridgeError(str(response.get("error", "unknown_error")))
        return response.get("result")
