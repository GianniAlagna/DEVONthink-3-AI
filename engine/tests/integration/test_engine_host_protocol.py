"""Plays the Swift host: starts the engine exactly as app/EngineHost/main.swift does and answers its requests."""
import json
import subprocess
import sys
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
    finally:
        proc.terminate()
        _, err = proc.communicate(timeout=5)
    assert "dt3 version=3.9.17" in err and "read ok" in err
    assert "SECRET-NAME-4711" not in err


def test_engine_exits_with_error_when_host_reports_failure():
    proc = start()
    answer(proc, {"ok": False, "error": "dt3_error_1743"})
    assert proc.wait(timeout=5) == 1
    assert "bridge error=dt3_error_1743" in proc.stderr.read()
