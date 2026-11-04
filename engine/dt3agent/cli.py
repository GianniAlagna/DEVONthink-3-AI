"""dt3agent command line (Phase 2 T9). Talks to the running engine over its private socket.

  dt3agent status | process <UUID or item link> | undo | pause | resume | live on|off
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
    p = sub.add_parser("process", help="queue one record (UUID or x-devonthink-item:// link)")
    p.add_argument("record")
    sub.add_parser("undo", help="undo the last batch of changes")
    sub.add_parser("pause", help="stop processing (queue keeps filling)")
    sub.add_parser("resume", help="continue processing")
    p = sub.add_parser("live", help="on: write to DT3 · off: dry-run (plan only, the default)")
    p.add_argument("state", choices=["on", "off"])
    a = ap.parse_args(argv)

    if a.cmd == "process":
        method, params = "process", {"uuid": a.record.removeprefix("x-devonthink-item://").split("?", 1)[0]}
    elif a.cmd == "live":
        method, params = "live", {"on": a.state == "on"}
    else:
        method, params = a.cmd, {}
    try:
        result = rpc.call(a.data / "engine.sock", method, params)
    except rpc.RPCError as e:
        print(f"dt3agent: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
