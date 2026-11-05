"""K-1 embeddings client against a fake llama-server (SPEC §4.20, ADR-0011)."""
import math

import pytest

from dt3agent.embed import BATCH, DIMS, QUERY_PREFIX, EmbedClient, EmbedError, normalise
from tests.fakes import FakeLlamaServer


@pytest.fixture
def server():
    s = FakeLlamaServer()
    yield s
    s.close()


def dot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_vectors_are_cut_and_normalised_in_input_order(server):
    vecs = EmbedClient(server.url).embed(["Rechnung Muster AG", "Mahnung Steueramt"])
    assert [len(v) for v in vecs] == [DIMS, DIMS]
    assert all(math.isclose(math.sqrt(dot(v, v)), 1.0, rel_tol=1e-5) for v in vecs)
    again = EmbedClient(server.url).embed(["Mahnung Steueramt"])[0]
    assert dot(vecs[1], again) > 0.999  # order follows "index", not the reply order
    req = server.requests[0]
    assert req["path"] == "/v1/embeddings" and req["body"]["encoding_format"] == "float"


def test_query_gets_the_instruction_documents_do_not(server):
    c = EmbedClient(server.url)
    c.embed(["Text"])
    c.embed(["Frage"], query=True)
    assert server.requests[0]["body"]["input"] == ["Text"]
    assert server.requests[1]["body"]["input"] == [QUERY_PREFIX + "Frage"]


def test_batches(server):
    EmbedClient(server.url).embed([f"t{i}" for i in range(BATCH + 3)])
    assert [len(r["body"]["input"]) for r in server.requests] == [BATCH, 3]


def test_http_error_is_a_short_code():
    s = FakeLlamaServer(status=500)
    try:
        with pytest.raises(EmbedError) as e:
            EmbedClient(s.url).embed(["x"])
        assert e.value.code == "embed_http_500"
    finally:
        s.close()


def test_unreachable():
    with pytest.raises(EmbedError) as e:
        EmbedClient("http://127.0.0.1:9", timeout=2).embed(["x"])
    assert e.value.code == "embed_unreachable"


def test_health(server):
    assert EmbedClient(server.url).health() is True
    assert EmbedClient("http://127.0.0.1:9", timeout=1).health() is False


def test_bad_url_refused():
    with pytest.raises(ValueError):
        EmbedClient("ftp://x")


def test_normalise_short_and_zero():
    assert list(normalise([3, 4], dims=512)) == pytest.approx([0.6, 0.8])
    assert list(normalise([0, 0])) == [0.0, 0.0]


def test_too_short_vector_is_a_bad_response(server):
    with pytest.raises(EmbedError) as e:
        EmbedClient(server.url, dims=2048).embed(["x"])  # the fake gives 1024 values
    assert e.value.code == "embed_bad_response"
