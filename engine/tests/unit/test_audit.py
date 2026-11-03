import json

import pytest

from dt3agent import audit

UUID = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"
SENTINEL = "SECRET-DOCUMENT-TEXT-4711"


def read_all(tmp_path):
    return [json.loads(line) for f in sorted(tmp_path.glob("audit-*.jsonl")) for line in f.read_text().splitlines()]


def test_writes_one_json_line_per_event(tmp_path):
    log = audit.AuditLog(tmp_path)
    log.write(actor="ai", action="set_tags", uuid=UUID, fields_changed=["tags"], batch_id="b1", result="ok")
    (event,) = read_all(tmp_path)
    assert event["uuid"] == UUID and event["fields_changed"] == ["tags"] and event["ts"].endswith("Z")


@pytest.mark.parametrize("kwargs", [
    {"text": SENTINEL},                                   # unknown key
    {"result": SENTINEL},                                 # not an allowed result
    {"fields_changed": [SENTINEL]},                       # not a field name
    {"uuid": SENTINEL},                                   # not a UUID
    {"action": SENTINEL},                                 # not an allowed action
])
def test_document_content_can_never_reach_the_log(tmp_path, kwargs):
    log = audit.AuditLog(tmp_path)
    base = dict(actor="ai", action="set_tags", uuid=UUID, fields_changed=["tags"], batch_id="b1", result="ok")
    with pytest.raises((TypeError, ValueError)):  # unknown keys fail at the keyword-only signature
        log.write(**{**base, **kwargs})
    assert SENTINEL not in "".join(f.read_text() for f in tmp_path.glob("*"))
