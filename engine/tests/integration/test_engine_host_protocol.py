"""Plays the Swift host: starts the engine exactly as app/EngineHost/main.swift does and answers its requests."""
import json
import subprocess
import sys
import threading
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parents[2]
UUID = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"
# Same launch line as the host (runEngine in main.swift).
LAUNCH = ("import runpy, sys; sys.path.insert(0, sys.argv[1]); del sys.argv[1]; "
          "runpy.run_module('dt3agent.engine', run_name='__main__', alter_sys=True)")


def start(*engine_args):
    return subprocess.Popen([sys.executable, "-I", "-c", LAUNCH, str(ENGINE_DIR), *engine_args],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def answer(proc, reply):
    request = json.loads(proc.stdout.readline())
    proc.stdin.write(json.dumps({"id": request["id"], **reply}) + "\n")
    proc.stdin.flush()
    return request


def test_engine_asks_info_then_reads_record_and_logs_no_content():
    proc = start("--read", UUID, "--heartbeat", "0.05")
    try:
        assert answer(proc, {"ok": True, "result": {"version": "3.9.17", "databases": ["Inbox"]}})["verb"] == "info"
        req = answer(proc, {"ok": True, "result": {"uuid": UUID, "name": "SECRET-NAME-4711", "tags": []}})
        assert req == {"id": 2, "verb": "read", "args": {"uuid": UUID}}
        lines = []
        while not any("read ok" in x for x in lines):  # wait for the log line, then stop (no race)
            lines.append(proc.stderr.readline())
    finally:
        proc.terminate()
        _, rest = proc.communicate(timeout=5)
    err = "".join(lines) + rest
    assert "dt3 version=3.9.17" in err and "read ok" in err
    assert "SECRET-NAME-4711" not in err


def test_engine_exits_with_error_when_host_reports_failure():
    proc = start()
    answer(proc, {"ok": False, "error": "dt3_error_1743"})
    assert proc.wait(timeout=5) == 1
    assert "bridge error=dt3_error_1743" in proc.stderr.read()


class Host:
    """A fake DT3 behind the real pipe protocol: answers every request from the engine until it stops."""

    def __init__(self, proc, tags):
        self.proc, self.tags, self.verbs = proc, list(tags), []

    def serve(self):
        for line in self.proc.stdout:
            req = json.loads(line)
            self.verbs.append(req["verb"])
            if req["verb"] == "info":
                result = {"version": "3.9.17", "databases": ["Test"]}
            elif req["verb"] == "set_tags":
                self.tags = req["args"]["tags"]
                result = {"uuid": UUID, "tags": self.tags}
            else:
                result = {"uuid": UUID, "name": "SECRET-NAME-4711", "tags": self.tags}
            self.proc.stdin.write(json.dumps({"id": req["id"], "ok": True, "result": result}) + "\n")
            self.proc.stdin.flush()


def test_tag_undo_floor_check_writes_test_tag_then_restores_exactly(tmp_path):
    proc = start("--tag-undo", UUID, "--hold", "0", "--data", str(tmp_path), "--heartbeat", "0.05")
    host = Host(proc, ["inbox"])
    threading.Thread(target=host.serve, daemon=True).start()
    lines = []
    try:
        while not any("verify ok" in x or "error" in x for x in lines):
            lines.append(proc.stderr.readline())
    finally:
        proc.terminate()
        proc.wait(timeout=5)
    err = "".join(lines)
    assert "tag ok" in err and "undo ok restored=1 conflicts=0" in err and "verify ok" in err
    assert host.tags == ["inbox"]
    assert host.verbs.count("set_tags") == 2
    assert "SECRET-NAME-4711" not in err
    assert (tmp_path / "undo.db").exists()


def test_service_mode_answers_the_cli_over_its_socket(tmp_path_factory):
    from dt3agent import rpc
    data = tmp_path_factory.mktemp("d")
    proc = start("--data", str(data))
    threading.Thread(target=Host(proc, []).serve, daemon=True).start()
    try:
        line = ""
        while "service ready" not in line:
            line = proc.stderr.readline()
            assert line, "engine exited"
        status = rpc.call(data / "engine.sock", "status", {})
        assert status["dt3_version"] == "3.9.17" and status["dry_run"] is True
        assert rpc.call(data / "engine.sock", "process", {"uuid": UUID}) == {"queued": True}
        assert rpc.call(data / "engine.sock", "status", {})["queue"] == {"queued": 1}  # no AI set: waits
    finally:
        proc.terminate()
        proc.wait(timeout=5)
