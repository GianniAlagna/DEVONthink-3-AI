"""Settings over rpc (Phase 5, for onboarding U-2 and settings U-3): read, change, validate, apply at once."""
import pytest

from dt3agent import config
from dt3agent.rpc import RPCError
from tests.unit.test_service import A, env  # noqa: F401  (fixture)


def test_config_get_returns_the_settings(env):  # noqa: F811
    svc, _, _ = env
    cfg = svc.handle("config_get", {})
    assert cfg["dry_run"] is True and "naming" in cfg and "tags" in cfg
    cfg["naming"]["template"] = "changed"  # a copy: the caller cannot change the engine's settings
    assert svc.handle("config_get", {})["naming"]["template"] != "changed"


def test_config_set_merges_saves_and_applies(env):  # noqa: F811
    svc, _, tmp = env
    out = svc.handle("config_set", {"changes": {"identity": {"name": "Erika Beispiel"},
                                                "tags": {"vocabulary": ["Rechnung", "Steuern"]}}})
    assert out["identity"]["name"] == "Erika Beispiel" and out["tags"]["vocabulary"] == ["Rechnung", "Steuern"]
    saved = config.load(tmp / "config.json")
    assert saved["identity"]["name"] == "Erika Beispiel"
    assert saved["naming"] == config.DEFAULTS["naming"]  # untouched sections stay
    assert svc.pipeline.settings["identity"]["name"] == "Erika Beispiel"  # in effect without a restart
    assert svc.pipeline.vocabulary == ["Rechnung", "Steuern"]


def test_live_after_config_set_keeps_the_new_settings(env):  # noqa: F811
    """Floor 2026-11-05: a stale copy in memory was written back. Every save starts from the current settings."""
    svc, _, tmp = env
    svc.handle("config_set", {"changes": {"keywords": {"urgent": ["Steueramt"]}}})
    svc.handle("live", {"on": True})
    saved = config.load(tmp / "config.json")
    assert saved["keywords"]["urgent"] == ["Steueramt"] and saved["dry_run"] is False


def test_config_set_reloads_a_file_changed_outside(env):  # noqa: F811
    svc, _, tmp = env
    cfg = config.load(tmp / "config.json")
    cfg["identity"]["name"] = "Von aussen"
    config.save(tmp / "config.json", cfg)
    svc.handle("config_set", {"changes": {"summary": {"target": "comment"}}})
    assert svc.handle("config_get", {})["identity"]["name"] == "Von aussen"


@pytest.mark.parametrize("changes", [
    {"vision": {"helper": "/tmp/evil"}},          # the helper path is set by the installer only
    {"schema_version": 2},
    {"nope": {}},
    {"tags": {"vocabulary": "not a list"}},
    {"scopes": [{"database": ""}]},
    {"ai": {"url": "file:///etc/passwd"}},
    {"ai": {"url": "ftp://x"}},
    {"identity": {"name": 5}},
    {"naming": {"template": ""}},
])
def test_config_set_refuses_bad_changes_and_keeps_the_file(env, changes):  # noqa: F811
    svc, _, tmp = env
    before = (tmp / "config.json").read_bytes()
    with pytest.raises(RPCError) as e:
        svc.handle("config_set", {"changes": changes})
    assert str(e.value) in ("config_invalid", "config_forbidden")
    assert (tmp / "config.json").read_bytes() == before
    assert svc.handle("config_get", {})["tags"]["vocabulary"] == config.DEFAULTS["tags"]["vocabulary"]


def test_config_set_needs_a_changes_object(env):  # noqa: F811
    svc, _, _ = env
    for params in ({}, {"changes": []}, {"changes": {}, "x": 1}):
        with pytest.raises(RPCError):
            svc.handle("config_set", params)


def test_config_set_can_switch_the_ai_url(env):  # noqa: F811
    svc, _, _ = env
    svc.handle("config_set", {"changes": {"ai": {"url": None}}})
    assert svc.ai is None and svc.handle("status", {})["ai_configured"] is False
    svc.handle("config_set", {"changes": {"ai": {"url": "http://127.0.0.1:9"}}})
    assert svc.ai is not None
