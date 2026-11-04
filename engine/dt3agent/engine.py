"""Engine entry point, started by the Swift engine host (`DT3 Agent Engine.app`).

Without a test flag the engine runs the service: spool → queue → pipeline, and answers the `dt3agent` CLI on its
private socket. Only codes, field names and counts are logged, never record content (brief §7).
"""
import argparse
import sys
import time
from pathlib import Path

from dt3agent import __version__, rpc, store
from dt3agent.adapter import DT3Adapter
from dt3agent.audit import AuditLog
from dt3agent.bridge import Bridge, BridgeError
from dt3agent.service import DEFAULT_DATA, Service
from dt3agent.undo import MIGRATIONS, UndoJournal

TEST_TAG = "DT3Agent-Test"


def log(message: str) -> None:
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} engine {message}", file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dt3agent.engine")
    ap.add_argument("--read", metavar="UUID", help="read one record through the bridge (floor test)")
    ap.add_argument("--tag-undo", metavar="UUID", help="add a test tag, wait, undo it, verify (floor test)")
    ap.add_argument("--hold", type=float, default=20.0, help="seconds the test tag stays visible in DT3")
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA, help="data folder (config, databases, spool, socket)")
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
        if a.tag_undo:
            tag_undo(bridge, a.tag_undo, a.data, a.hold)
        if not (a.read or a.tag_undo):
            return serve(bridge, a.data)
    except BridgeError as e:
        log(f"bridge error={e}")
        return 1
    except RuntimeError as e:  # includes NotDT3Error
        log(f"check error={e}")
        return 1
    while True:  # idle until the host stops us; replaced by the queue loop in T8
        time.sleep(a.heartbeat)
        log("heartbeat")


def serve(bridge, data: Path) -> int:
    """The engine loop. Errors from DT3 or the host end the process; the host restarts it with back-off."""
    svc = Service(data, bridge)
    server = rpc.Server(data / "engine.sock")
    log(f"service ready dry_run={svc.pipeline.dry_run} ai_configured={svc.ai is not None}")
    try:
        busy = False
        while True:
            server.poll(svc.handle, timeout=0 if busy else 1.0)
            result = svc.tick()
            busy = result is not None
            if result:
                log(f"job {result}")  # an outcome or a short error code, never content
    finally:
        server.close()
        svc.close()


def tag_undo(bridge, uuid: str, data: Path, hold: float) -> None:
    """T6 floor check: the real write path (journal first, then write) and an exact undo through the host."""
    data.mkdir(parents=True, exist_ok=True)
    adapter = DT3Adapter(bridge, UndoJournal(store.open_db(data / "undo.db", MIGRATIONS)), AuditLog(data / "audit"))
    before = adapter.read(uuid)["tags"]
    if TEST_TAG in before:
        raise RuntimeError(f"record already has the tag {TEST_TAG}; remove it in DT3 first")
    adapter.set_tags(uuid, before + [TEST_TAG], batch_id=f"floor-{int(time.time())}", actor="user")
    if TEST_TAG not in adapter.read(uuid)["tags"]:
        raise RuntimeError("test tag not written")
    log(f"tag ok tags={len(before)}+1, visible in DT3 for {hold:g}s")
    time.sleep(hold)
    result = adapter.undo_last_batch()
    log(f"undo ok restored={result['restored']} conflicts={len(result['conflicts'])}")
    if adapter.read(uuid)["tags"] != before:
        raise RuntimeError("tags differ after undo")
    log("verify ok tags restored exactly")


if __name__ == "__main__":
    sys.exit(main())
