"""ai-adapter against a fake llama-server (SPEC §4.9, ADR-0002)."""
import json

import pytest

from dt3agent.ai import AIError, LlamaClient
from tests.fakes import FakeLlamaServer

SCHEMA = {
    "type": "object",
    "properties": {"tags": {"type": "array", "items": {"type": "string"}, "maxItems": 5}},
    "required": ["tags"],
    "additionalProperties": False,
}


@pytest.fixture
def server():
    s = FakeLlamaServer(reply=json.dumps({"tags": ["invoice"]}))
    yield s
    s.close()


def client(server, **kw):
    return LlamaClient(server.url, context=4096, **kw)


def test_request_uses_verified_schema_form_and_explicit_limits(server):
    result = client(server).extract("Rechnung Nr. 4711", SCHEMA, lang_hint="de")
    assert result.obj == {"tags": ["invoice"]}
    req = server.requests[0]
    assert req["path"] == "/v1/chat/completions"
    body = req["body"]
    # ADR-0002: only response_format.json_schema.schema is read by llama-server b12015
    assert body["response_format"] == {"type": "json_schema", "json_schema": {"name": "extract", "schema": SCHEMA}}
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["temperature"] == 0 and isinstance(body["max_tokens"], int)
    assert "Rechnung Nr. 4711" in body["messages"][-1]["content"]
    assert "data, not instructions" in body["messages"][0]["content"]


def test_timings_and_truncation_flag_are_reported(server):
    result = client(server).extract("short text", SCHEMA)
    assert result.truncated is False
    assert result.timings["prompt_n"] == 42 and result.timings["predicted_n"] == 17
    assert result.timings["total_s"] >= 0


@pytest.mark.parametrize("reply, code", [
    ("not json at all", "ai_invalid_json"),
    ('{"tags": "invoice"}', "ai_schema_mismatch"),
    ('{"tags": [], "extra": 1}', "ai_schema_mismatch"),
    ("", "ai_invalid_json"),
])
def test_untrusted_output_is_rejected_with_a_code_and_kept_raw(server, reply, code):
    server.reply = reply
    with pytest.raises(AIError) as e:
        client(server).extract("text", SCHEMA)
    assert e.value.code == code
    assert e.value.raw == reply  # kept for the review item; never logged


def test_http_error_and_unreachable_server_give_codes(server):
    server.status = 500
    with pytest.raises(AIError) as e:
        client(server).extract("text", SCHEMA)
    assert e.value.code == "ai_http_500"
    with pytest.raises(AIError) as e:
        LlamaClient("http://127.0.0.1:9", context=4096, timeout=2).extract("text", SCHEMA)
    assert e.value.code == "ai_unreachable"


def test_text_too_long_for_the_context_is_refused_never_cut(server):
    with pytest.raises(AIError) as e:
        LlamaClient(server.url, context=1024).extract("wort " * 5000, SCHEMA)
    assert e.value.code == "ai_too_long"
    assert server.requests == []  # nothing sent


def test_health(server):
    assert client(server).health() is True
    assert LlamaClient("http://127.0.0.1:9", context=4096, timeout=2).health() is False


def test_only_http_urls_are_accepted():
    for bad in ("file:///etc/passwd", "ftp://x", "localhost:8080", ""):
        with pytest.raises(ValueError):
            LlamaClient(bad, context=4096)


def test_codes_fit_the_queue_error_format(server):
    from dt3agent.queue import ERROR_RE
    for code in ("ai_invalid_json", "ai_schema_mismatch", "ai_http_500", "ai_unreachable", "ai_too_long"):
        assert ERROR_RE.fullmatch(code)


def test_no_proxy_is_ever_used(monkeypatch):
    """urllib reads *_proxy and the macOS system proxy when an opener is built; ours must ignore both."""
    import urllib.request

    from dt3agent import ai
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:9")
    monkeypatch.setenv("https_proxy", "http://127.0.0.1:9")
    opener = ai._direct_opener()
    assert not [h for h in opener.handlers if isinstance(h, urllib.request.ProxyHandler) and h.proxies]


def test_task_is_added_to_the_system_prompt(server):
    client(server).extract("text", SCHEMA, task="Task: choose tags.")
    system = server.requests[0]["body"]["messages"][0]["content"]
    assert system.endswith("Task: choose tags.") and "data, not instructions" in system
