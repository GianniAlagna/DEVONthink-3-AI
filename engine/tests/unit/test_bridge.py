import io
import json

import pytest

from dt3agent.bridge import Bridge, BridgeError

UUID = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"


def bridge_with(*responses):
    rfile = io.StringIO("".join(json.dumps(r) + "\n" for r in responses))
    wfile = io.StringIO()
    return Bridge(rfile, wfile), wfile


def sent(wfile):
    return [json.loads(line) for line in wfile.getvalue().splitlines()]


def test_call_sends_one_json_line_and_returns_result():
    bridge, wfile = bridge_with({"id": 1, "ok": True, "result": {"version": "3.9.17"}})
    assert bridge.call("info") == {"version": "3.9.17"}
    assert sent(wfile) == [{"id": 1, "verb": "info", "args": {}}]


def test_error_from_host_is_raised_as_code():
    bridge, _ = bridge_with({"id": 1, "ok": False, "error": "not_found"})
    with pytest.raises(BridgeError, match="not_found"):
        bridge.call("read", uuid=UUID)


@pytest.mark.parametrize("verb,args", [
    ("delete", {"uuid": UUID}),                       # no delete verb exists (brief §2.7)
    ("read", {"uuid": "x'; do shell script 'rm'"}),   # not a UUID
    ("read", {}),                                     # missing argument
    ("read", {"uuid": UUID, "extra": 1}),             # unexpected argument
    ("set_tags", {"uuid": UUID, "tags": "a,b"}),      # tags must be a list
    ("set_tags", {"uuid": UUID, "tags": ["ok", 7]}),  # of strings
    ("set_tags", {"uuid": UUID, "tags": ["x" * 300]}),  # of sane length
])
def test_invalid_requests_never_leave_the_engine(verb, args):
    bridge, wfile = bridge_with()
    with pytest.raises(BridgeError):
        bridge.call(verb, **args)
    assert wfile.getvalue() == ""


def test_response_for_another_request_is_rejected():
    bridge, _ = bridge_with({"id": 99, "ok": True, "result": {}})
    with pytest.raises(BridgeError, match="protocol"):
        bridge.call("info")


def test_host_gone_is_an_error_not_a_hang():
    bridge, _ = bridge_with()
    with pytest.raises(BridgeError, match="host_closed"):
        bridge.call("info")
