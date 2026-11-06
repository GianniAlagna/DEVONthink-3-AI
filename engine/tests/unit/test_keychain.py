"""E-7 remote AI key (SPEC §4.22): Keychain only, sent only where it is safe, never stored or reported."""
import json

import pytest

from dt3agent import config, keychain
from dt3agent.ai import LlamaClient
from dt3agent.embed import EmbedClient
from tests.fakes import FakeLlamaServer

KEY = "sk-test-0123456789"


def test_read_key_uses_argv_and_returns_the_key():
    seen = []
    assert keychain.read_key(lambda argv: seen.append(argv) or (0, KEY + "\n")) == KEY
    assert seen == [["/usr/bin/security", "find-generic-password", "-s", "codes.modular.dt3agent.ai", "-w"]]


@pytest.mark.parametrize("reply", [(44, ""), (0, ""), (0, "two words"), (0, "x" * 600), (0, "bad\x00")])
def test_missing_or_odd_keys_are_not_used(reply):
    assert keychain.read_key(lambda argv: reply) is None


def test_no_security_tool_means_no_key():
    def boom(argv):
        raise OSError("no such file")
    assert keychain.read_key(boom) is None


@pytest.mark.parametrize("url,ok", [
    ("https://ai.example.com", True), ("http://127.0.0.1:8080", True), ("http://localhost:8080", True),
    ("http://192.168.1.20:8080", True), ("http://10.0.0.5", True), ("http://mac-mini.local:8080", True),
    ("http://ai.example.com", False), ("http://8.8.8.8:8080", False),
])
def test_key_only_over_https_or_to_private_hosts(url, ok):
    assert bool(keychain.auth_headers(url, KEY)) is ok


def test_clients_send_the_key_to_their_own_host():
    srv = FakeLlamaServer(reply=json.dumps({"tags": []}))
    try:
        EmbedClient(srv.url, api_key=KEY).embed(["a"])
        LlamaClient(srv.url, context=4096, api_key=KEY).extract("Text", {"type": "object"})
        EmbedClient(srv.url).embed(["b"])
        assert [r["auth"] for r in srv.requests] == [f"Bearer {KEY}", f"Bearer {KEY}", None]
    finally:
        srv.close()


def test_config_never_holds_the_key():
    with pytest.raises(config.ConfigError):
        config.merge(config.DEFAULTS, {"ai": {"api_key": KEY}})
    assert config.merge(config.DEFAULTS, {"ai": {"use_key": True}})["ai"]["use_key"] is True


def test_status_and_diagnostics_never_show_the_key(tmp_path, monkeypatch):
    import zipfile

    from dt3agent.service import Service
    from tests.fakes import FakeDT3
    monkeypatch.setattr(keychain, "_run", lambda argv: (0, KEY))
    svc = Service(tmp_path / "d", FakeDT3())
    svc.handle("config_set", {"changes": {"ai": {"use_key": True, "url": "http://127.0.0.1:9"}}})
    st = svc.handle("status", {})
    assert st["ai_key_found"] is True and KEY not in json.dumps(st)
    svc.diagnostics_dir = tmp_path / "dl"
    with zipfile.ZipFile(svc.handle("diagnostics", {})["path"]) as z:
        assert KEY not in z.read("diagnostics.json").decode()
