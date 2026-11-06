import json

import pytest

from dt3agent import config


def test_missing_file_gives_safe_defaults(tmp_path):
    cfg = config.load(tmp_path / "config.json")
    assert cfg["dry_run"] is True
    assert cfg["scopes"] == []
    assert cfg["update_check"] is False
    assert cfg["logs"]["content"] is False


def test_save_is_atomic_and_keeps_backup(tmp_path):
    path = tmp_path / "config.json"
    first = config.load(path)
    config.save(path, first)
    second = dict(first, dry_run=False)
    config.save(path, second)
    assert json.loads(path.read_text(encoding="utf-8"))["dry_run"] is False
    assert json.loads((tmp_path / "config.json.bak").read_text(encoding="utf-8"))["dry_run"] is True
    assert not list(tmp_path.glob("*.tmp"))


def test_unknown_keys_are_rejected(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"schema_version": 1, "evil": True}), encoding="utf-8")
    with pytest.raises(config.ConfigError):
        config.load(path)


def test_wrong_type_is_rejected(tmp_path):
    cfg = config.load(tmp_path / "c.json")
    cfg["dry_run"] = "no"
    with pytest.raises(config.ConfigError):
        config.save(tmp_path / "c.json", cfg)


def test_import_that_drops_enabled_scopes_needs_confirmation(tmp_path):
    path = tmp_path / "config.json"
    cfg = config.load(path)
    cfg["scopes"] = [{"database": "Inbox", "group": "/"}]
    config.save(path, cfg)
    smaller = dict(cfg, scopes=[])
    with pytest.raises(config.ShrinkError):
        config.import_config(path, smaller)
    config.import_config(path, smaller, confirm_shrink=True)
    assert config.load(path)["scopes"] == []


def test_tag_vocabulary_is_checked():
    import pytest as _pytest

    from dt3agent import config as _config
    assert "Rechnung" in _config.DEFAULTS["tags"]["vocabulary"]
    for bad in (["ok", ""], ["x" * 65], "Rechnung", [1], ["a\nb"]):
        with _pytest.raises(_config.ConfigError):
            _config.validate({"tags": {"vocabulary": bad}})


def test_q1_old_default_threshold_is_raised_on_load(tmp_path):
    import json

    from dt3agent import config
    p = tmp_path / "config.json"
    p.write_text(json.dumps({"knowledge": {"min_score": 0.35}}))
    assert config.load(p)["knowledge"]["min_score"] == 0.47      # untouched old default → floor-calibrated value
    p.write_text(json.dumps({"knowledge": {"min_score": 0.5}}))
    assert config.load(p)["knowledge"]["min_score"] == 0.5       # any other value is kept
