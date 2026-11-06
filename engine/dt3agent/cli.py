"""dt3agent command line (Phase 2 T9). Talks to the running engine over its private socket.

  dt3agent status | process [<UUID or item link>] | review | undo | pause | resume | live on|off | list [SINCE]
  process without a record takes the records selected in DEVONthink 3.
"""
import argparse
import json
import sys
from pathlib import Path

from dt3agent import rpc
from dt3agent.service import DEFAULT_DATA


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dt3agent", description="Control the DT3 Agent engine.")
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="engine, DT3, AI and queue state")
    p = sub.add_parser("process", help="queue a record (UUID or item link); without one: the DT3 selection")
    p.add_argument("record", nargs="?")
    p = sub.add_parser("review", help="open review items (reason codes, planned tags); optional: one kind")
    p.add_argument("kind", nargs="?", choices=["planned", "error", "field", "duplicate", "case", "deadline", "urgent",
                                               "report"])
    p = sub.add_parser("decide", help="decide a review item: accept | reject | edit TAG [TAG …]")
    p.add_argument("id", type=int)
    p.add_argument("decision", choices=["accept", "reject", "edit"])
    p.add_argument("value", nargs="*")
    sub.add_parser("undo", help="undo the last batch of changes")
    sub.add_parser("pause", help="stop processing (queue keeps filling)")
    sub.add_parser("resume", help="continue processing")
    p = sub.add_parser("ask", help="ask the documents (read-only); shows sources and the best similarity")
    p.add_argument("question", nargs="+")
    p = sub.add_parser("list", help="list the records of every enabled scope (read-only); count and seconds")
    p.add_argument("since", nargs="?", help="only records changed after this date (YYYY-MM-DD)")
    p = sub.add_parser("job", help="run a scheduled job now: nightly | digest | hygiene")
    p.add_argument("name", choices=["nightly", "digest", "hygiene"])
    sub.add_parser("diagnostics", help="write a zip without personal data to ~/Downloads (for support)")
    p = sub.add_parser("live", help="on: write to DT3 · off: dry-run (plan only, the default)")
    p.add_argument("state", choices=["on", "off"])
    a = ap.parse_args(argv)

    if a.cmd == "process" and not a.record:
        method, params = "process_selected", {}
    elif a.cmd == "process":
        method, params = "process", {"uuid": a.record.removeprefix("x-devonthink-item://").split("?", 1)[0]}
    elif a.cmd == "decide":
        method, params = "decide", {"id": a.id, "decision": a.decision}
        if a.decision == "edit":  # one word list for tags; joined text for a field such as the name
            params["value"] = a.value
    elif a.cmd == "review":
        method, params = "review", ({"kind": a.kind} if a.kind else {})
    elif a.cmd == "ask":
        method, params = "ask", {"question": " ".join(a.question)}
    elif a.cmd == "job":
        method, params = "run_job", {"name": a.name}
    elif a.cmd == "list":
        method, params = "list", ({"since": a.since} if a.since else {})
    elif a.cmd == "live":
        method, params = "live", {"on": a.state == "on"}
    else:
        method, params = a.cmd, {}
    try:
        if method in ("ask", "list", "run_job"):
            result = rpc.call(a.data / "engine.sock", method, params, timeout=600.0)
        else:
            result = rpc.call(a.data / "engine.sock", method, params)
    except rpc.RPCError as e:
        print(f"dt3agent: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
