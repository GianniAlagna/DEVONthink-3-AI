"""Fake DEVONthink 3 behind the bridge protocol: deterministic, in memory (SPEC §8 integration tests)."""
from dt3agent.bridge import BridgeError, validate

MAX_TEXT = 200_000  # same cap as app/EngineHost/main.swift readText


class FakeDT3:
    """Answers the same verbs as the Swift host. Records are plain dicts keyed by UUID."""

    def __init__(self, records=None, version="3.9.17"):
        self.version = version
        self.records = {u: dict(r, uuid=u) for u, r in (records or {}).items()}
        self.calls = []
        self.selected = []  # UUIDs selected in the fake DT3 window
        self.groups = {"/", "/Inbox/", "/_AI-Review/"}  # existing group locations

    def call(self, verb, **args):
        validate(verb, args)  # same fence as the real bridge client
        self.calls.append((verb, args))
        if verb == "info":
            return {"version": self.version, "databases": ["DT3Agent-Test"]}
        if verb == "selected":
            return {"uuids": list(self.selected)}
        if verb == "create_markdown":
            if args["location"] not in self.groups:
                raise BridgeError("group_not_found")
            new = f"00000000-0000-4000-8000-{len(self.records):012d}"
            self.records[new] = {"uuid": new, "name": args["name"], "text": args["text"], "tags": [],
                                 "location": args["location"], "metadata": {}}
            return {"uuid": new}
        rec = self.records.get(args["uuid"])
        if rec is None:
            raise BridgeError("not_found")
        if verb == "read":
            return {k: v for k, v in rec.items() if k not in ("text", "path")}
        if verb == "read_path":
            return {"uuid": rec["uuid"], "path": rec.get("path", "")}
        if verb == "read_text":  # same shape as the host: text capped at MAX_TEXT, full length reported
            text = rec.get("text", "")
            return {"uuid": rec["uuid"], "text": text[:MAX_TEXT], "length": len(text)}
        if verb == "duplicates":
            return {"uuids": list(rec.get("duplicates", []))}
        if verb in ("replicate", "duplicate"):
            if args["location"] not in self.groups:
                raise BridgeError("group_not_found")
            if verb == "replicate":
                rec.setdefault("replicants", []).append(args["location"])
                return {"uuid": rec["uuid"]}
            new = f"00000000-0000-4000-9000-{len(self.records):012d}"
            self.records[new] = {**rec, "uuid": new, "location": args["location"], "metadata": {}}
            return {"uuid": new}
        if verb in ("set_name", "set_comment", "set_metadata", "move") and not self.version.startswith("3."):
            raise BridgeError("not_dt3")
        if verb == "set_name":
            rec["name"] = args["name"]
            return {"uuid": rec["uuid"], "name": rec["name"]}
        if verb == "set_comment":
            rec["comment"] = args["comment"]
            return {"uuid": rec["uuid"], "comment": rec["comment"]}
        if verb == "set_metadata":
            rec.setdefault("metadata", {})["md" + args["key"]] = args["value"]
            return {"uuid": rec["uuid"]}
        if verb == "move":
            if args["location"] not in self.groups:
                raise BridgeError("group_not_found")  # the host never creates groups
            rec["location"] = args["location"]
            return {"uuid": rec["uuid"], "location": rec["location"]}
        if verb == "add_event":
            if rec.get("reminder"):
                raise BridgeError("reminder_exists")  # the host never overwrites a reminder
            new = f"00000000-0000-4000-a000-{len(self.records):012d}"
            self.records[new] = {"uuid": new, "name": args["name"], "text": args["ics"], "tags": [],
                                 "location": rec.get("location", "/"), "metadata": {}}
            rec["reminder"] = args["date"]
            return {"uuid": new}
        if verb == "set_tags":
            if not self.version.startswith("3."):  # the host refuses writes to non-DT3 (main.swift requireDT3)
                raise BridgeError("not_dt3")
            rec["tags"] = list(args["tags"])
            return {"uuid": rec["uuid"], "tags": rec["tags"]}
        raise BridgeError("verb_not_allowed")


class FakeLlamaServer:
    """A local HTTP server that answers like llama-server (b12015): /health and /v1/chat/completions.

    `reply` is the assistant message content to return (any string, also invalid JSON); `status` the HTTP code.
    Every request body is kept in `requests` so tests can check the exact request form.
    """

    def __init__(self, reply="{}", status=200):
        import http.server
        import json
        import threading

        self.reply, self.status, self.requests = reply, status, []
        fake = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):  # keep test output clean
                pass

            def _send(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._send(200, {"status": "ok"}) if self.path == "/health" else self._send(404, {})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append({"path": self.path, "body": body})
                if fake.status != 200:
                    return self._send(fake.status, {"error": {"message": "fake failure"}})
                self._send(200, {"choices": [{"message": {"role": "assistant", "content": fake.reply}}],
                                 "timings": {"prompt_n": 42, "predicted_n": 17, "prompt_ms": 10.0,
                                             "predicted_ms": 20.0}})

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def ai_reply(tags, **fields) -> str:
    """A complete answer as llama-server returns it under the field + tag schema (all required keys present)."""
    base = {"type": None, "sender": None, "receiver": None, "subject": None, "summary": [], "tags": list(tags)}
    import json
    return json.dumps({**base, **fields})
