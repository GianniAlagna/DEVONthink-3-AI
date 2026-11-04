"""Local JSON-RPC over a private Unix socket (SPEC §4.17, ADR-0007): one JSON line in, one JSON line out.

The socket file is created with mode 0600 inside a 0700 folder, so only this macOS user can talk to the engine.
Errors travel as short codes; no document content is ever part of a request or an error.
"""
import json
import os
import select
import socket
import stat
from pathlib import Path

MAX_PATH = 103  # sockaddr_un.sun_path on macOS (104 bytes incl. NUL)
MAX_LINE = 64 * 1024


class RPCError(RuntimeError):
    pass


def _check_path(path: Path) -> None:
    if len(os.fsencode(str(path))) > MAX_PATH:
        raise RPCError("socket_path_too_long")


class Server:
    def __init__(self, path: Path):
        self.path = Path(path)
        _check_path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.exists() or self.path.is_symlink():
            if not stat.S_ISSOCK(os.lstat(self.path).st_mode):
                raise RPCError("socket_path_occupied")  # never delete a file we did not create
            self.path.unlink()
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        old = os.umask(0o177)  # no window in which the socket is readable by others
        try:
            self.sock.bind(str(self.path))
        finally:
            os.umask(old)
        os.chmod(self.path, 0o600)
        self.sock.listen(4)

    def poll(self, handler, timeout: float) -> bool:
        """Serve at most one request. handler(method, params) -> result; raise RPCError for a coded error."""
        ready, _, _ = select.select([self.sock], [], [], timeout)
        if not ready:
            return False
        conn, _ = self.sock.accept()
        with conn:
            conn.settimeout(5)
            try:
                reply = self._answer(self._read_line(conn), handler)
            except (OSError, RPCError):
                return True
            try:
                conn.sendall(json.dumps(reply).encode() + b"\n")
            except OSError:
                pass
        return True

    @staticmethod
    def _read_line(conn) -> bytes:
        data = b""
        while b"\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if len(data) > MAX_LINE:
                raise RPCError("request_too_long")
        return data.split(b"\n", 1)[0]

    @staticmethod
    def _answer(line: bytes, handler) -> dict:
        try:
            req = json.loads(line)
            method, params = req["method"], req.get("params", {})
            if not isinstance(method, str) or not isinstance(params, dict):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            return {"ok": False, "error": "bad_request"}
        try:
            return {"ok": True, "result": handler(method, params)}
        except RPCError as e:
            return {"ok": False, "error": str(e)}
        except Exception:  # never leak internals (or content) to the client
            return {"ok": False, "error": "engine_error"}

    def close(self) -> None:
        self.sock.close()
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def call(path: Path, method: str, params: dict, timeout: float = 120.0):
    _check_path(Path(path))
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(str(path))
            s.sendall(json.dumps({"method": method, "params": params}).encode() + b"\n")
            line = Server._read_line(s)
    except (FileNotFoundError, ConnectionRefusedError):
        raise RPCError("engine_not_running") from None
    except OSError:
        raise RPCError("engine_unreachable") from None
    try:
        reply = json.loads(line)
    except ValueError:
        raise RPCError("bad_reply") from None
    if not reply.get("ok"):
        raise RPCError(str(reply.get("error", "unknown_error")))
    return reply.get("result")
