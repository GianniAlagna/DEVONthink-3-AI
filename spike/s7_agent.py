"""S7/S5 - minimal LaunchAgent engine: Unix socket (0600) with a JSON-RPC ping, heartbeat log,
optional DT3 AppleEvent probe at start (for the S5 permission test). Stdlib only."""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time

MAX_MSG = 4096


def log(msg: str) -> None:
    print(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} pid={os.getpid()} {msg}", flush=True)


def dt3_probe(probe_js: str) -> None:
    try:
        r = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", probe_js, "info"],
                           capture_output=True, text=True, timeout=120)
        log(f"dt3 probe rc={r.returncode} stdout={r.stdout.strip()[:300]!r} stderr={r.stderr.strip()[:300]!r}")
    except subprocess.TimeoutExpired:
        log("dt3 probe TIMEOUT (permission prompt waiting?)")


def handle(conn: socket.socket) -> None:
    conn.settimeout(5)
    data = conn.recv(MAX_MSG)
    try:
        msg = json.loads(data.decode("utf-8"))
        ok = (isinstance(msg, dict) and msg.get("jsonrpc") == "2.0" and msg.get("method") == "ping"
              and isinstance(msg.get("id"), int) and set(msg) <= {"jsonrpc", "method", "id", "params"})
    except (ValueError, UnicodeDecodeError):
        msg, ok = {}, False
    if ok:
        reply = {"jsonrpc": "2.0", "id": msg["id"], "result": {"pong": True, "pid": os.getpid()}}
    else:  # schema violation: reject, never act on it
        reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}
    conn.sendall(json.dumps(reply).encode("utf-8"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sock", required=True)
    ap.add_argument("--probe-js")
    a = ap.parse_args()

    log(f"start uid={os.getuid()} exe={sys.executable}")
    if a.probe_js:  # in a thread: a waiting permission prompt must not block the socket
        threading.Thread(target=dt3_probe, args=(a.probe_js,), daemon=True).start()

    os.makedirs(os.path.dirname(a.sock), mode=0o700, exist_ok=True)
    if os.path.exists(a.sock):
        os.unlink(a.sock)
    old = os.umask(0o177)  # socket is created 0600, no window with wider permissions
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(a.sock)
    os.umask(old)
    srv.listen(4)
    srv.settimeout(60)
    log(f"listening {a.sock} mode={oct(os.stat(a.sock).st_mode & 0o777)} pathlen={len(a.sock.encode())}")

    def stop(*_):
        log("SIGTERM - cleaning up")
        srv.close()
        if os.path.exists(a.sock):
            os.unlink(a.sock)
        sys.exit(0)
    signal.signal(signal.SIGTERM, stop)

    while True:
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            log("heartbeat")
            continue
        with conn:
            try:
                handle(conn)
            except OSError as e:
                log(f"client error {e!r}")


if __name__ == "__main__":
    main()
