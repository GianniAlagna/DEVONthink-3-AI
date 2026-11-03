"""Engine entry point, started by the Swift engine host (`DT3 Agent Engine.app`).

Phase 2 walking skeleton: proves the host <-> engine <-> DT3 path. The queue/pipeline loop is wired in T8.
Only field names and counts are logged, never record content (brief §7).
"""
import argparse
import sys
import time

from dt3agent import __version__
from dt3agent.bridge import Bridge, BridgeError


def log(message: str) -> None:
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} engine {message}", file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dt3agent.engine")
    ap.add_argument("--read", metavar="UUID", help="read one record through the bridge (floor test)")
    ap.add_argument("--heartbeat", type=float, default=60.0)
    a = ap.parse_args(argv)

    bridge = Bridge(sys.stdin, sys.stdout)
    log(f"start version={__version__}")
    try:
        info = bridge.call("info")
        log(f"dt3 version={info.get('version')} databases={len(info.get('databases', []))}")
        if a.read:
            record = bridge.call("read", uuid=a.read)
            log(f"read ok fields={sorted(record)}")
    except BridgeError as e:
        log(f"bridge error={e}")
        return 1
    while True:  # idle until the host stops us; replaced by the queue loop in T8
        time.sleep(a.heartbeat)
        log("heartbeat")


if __name__ == "__main__":
    sys.exit(main())
