"""E-8 diagnostics (SPEC §4.22): useful for support, and nothing personal in it."""
import json
import zipfile

from dt3agent import diagnostics
from dt3agent.service import Service
from tests.fakes import FakeDT3

U = "FB2DEBBE-8F8B-4049-8F4E-CE5FD12F20D8"
SECRET_WORDS = ("Erika Beispiel", "Fall Muster", "/Recht/Fall-Muster/", "DT3Agent-T1", "Muster Treuhand", U,
                "/_Berichte/", "Rechnung")


def make(tmp_path):
    dt3 = FakeDT3({U: {"name": "Rechnung Muster Treuhand", "tags": []}})
    dt3.groups |= {"/_Berichte/"}
    svc = Service(tmp_path / "data", dt3)
    svc.handle("config_set", {"changes": {
        "identity": {"name": "Erika Beispiel"},
        "cases": [{"name": "Fall Muster", "group": "/Recht/Fall-Muster/", "words": ["Muster Treuhand AG"]}],
        "scopes": [{"database": "DT3Agent-T1", "group": "/"}],
        "jobs": {"digest": {"enabled": True, "group": "/_Berichte/"}}}})
    svc.queue.enqueue(U, "cli")
    svc.adapter.audit.write(actor="user", action="set_tags", uuid=U, fields_changed=["tags"], batch_id="b-1",
                            result="ok")
    svc.diagnostics_dir = tmp_path / "Downloads"
    return svc


def test_export_has_counts_and_no_personal_data(tmp_path):
    svc = make(tmp_path)
    out = svc.handle("diagnostics", {})
    with zipfile.ZipFile(out["path"]) as z:
        text = z.read("diagnostics.json").decode()
    data = json.loads(text)
    for word in SECRET_WORDS:
        assert word not in text, word
    assert data["queue"] == {"queued": 1} and data["audit_7d"] == {"user:set_tags:ok": 1}
    assert data["config"]["identity"]["name"] == "<set>" and data["config"]["cases"] == {"items": 1}
    assert data["config"]["jobs"]["digest"] == {"enabled": True, "day": "mon", "time": "07:30", "group": "<set>",
                                                "lang": "de"}
    assert set(data["launch_agents"]) == {"engine", "llama", "embed"}


def test_redact_is_safe_by_default():
    assert diagnostics.redact({"x": "secret", "n": 3, "b": False, "l": ["a", "b"], "e": ""}) == \
        {"x": "<set>", "n": 3, "b": False, "l": {"items": 2}, "e": ""}


def test_launch_agent_state(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics.Path, "home", lambda: tmp_path)
    (tmp_path / "Library/LaunchAgents").mkdir(parents=True)
    (tmp_path / "Library/LaunchAgents/codes.modular.dt3agent.engine.plist").write_text("x")
    assert diagnostics._launchd("codes.modular.dt3agent.engine", lambda argv: 0) == "loaded"
    assert diagnostics._launchd("codes.modular.dt3agent.engine", lambda argv: 113) == "installed_not_loaded"
    assert diagnostics._launchd("codes.modular.dt3agent.llama", lambda argv: 0) == "not_installed"
