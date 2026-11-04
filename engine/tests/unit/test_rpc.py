import os
import socket
import stat
import threading

import pytest

from dt3agent import rpc


@pytest.fixture
def sock_path(tmp_path_factory):
    # AF_UNIX paths are limited to 103 bytes on macOS: keep test paths short
    d = tmp_path_factory.mktemp("s")
    return d / "e.sock"


def serve_one(server, handler):
    t = threading.Thread(target=lambda: server.poll(handler, timeout=5), daemon=True)
    t.start()
    return t


def test_socket_is_private_and_round_trips(sock_path):
    server = rpc.Server(sock_path)
    try:
        assert stat.S_IMODE(os.stat(sock_path).st_mode) == 0o600
        t = serve_one(server, lambda method, params: {"echo": method, "params": params})
        assert rpc.call(sock_path, "status", {"x": 1}) == {"echo": "status", "params": {"x": 1}}
        t.join(5)
    finally:
        server.close()
    assert not sock_path.exists()


def test_handler_errors_come_back_as_codes(sock_path):
    server = rpc.Server(sock_path)

    def boom(method, params):
        raise rpc.RPCError("unknown_method")
    try:
        serve_one(server, boom)
        with pytest.raises(rpc.RPCError) as e:
            rpc.call(sock_path, "nope", {})
        assert str(e.value) == "unknown_method"
    finally:
        server.close()


def test_bad_request_is_refused(sock_path):
    server = rpc.Server(sock_path)
    try:
        serve_one(server, lambda m, p: {})
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(str(sock_path))
            s.sendall(b"not json\n")
            assert b"bad_request" in s.recv(1000)
    finally:
        server.close()


def test_poll_without_client_returns_quickly(sock_path):
    server = rpc.Server(sock_path)
    try:
        assert server.poll(lambda m, p: {}, timeout=0.01) is False
    finally:
        server.close()


def test_too_long_path_is_refused(tmp_path):
    with pytest.raises(rpc.RPCError):
        rpc.Server(tmp_path / ("x" * 120) / "e.sock")


def test_engine_not_running(sock_path):
    with pytest.raises(rpc.RPCError) as e:
        rpc.call(sock_path, "status", {})
    assert str(e.value) == "engine_not_running"
