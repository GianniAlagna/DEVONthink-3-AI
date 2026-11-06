"""Embeddings client for the knowledge index (SPEC §4.20, ADR-0011).

Talks to a second llama-server (`--embedding --pooling last`) over its OpenAI-style `/v1/embeddings`.
Vectors are cut to DIMS (Matryoshka) and L2-normalised, so cosine = dot product. Failures are short codes;
document text is never logged.
"""
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from array import array

from dt3agent import keychain
from dt3agent.ai import _direct_opener

DIMS = 512
BATCH = 16  # texts per request; chunks are ~1200 characters
# Model card: an English instruction on the query side only, documents without one.
QUERY_PREFIX = "Instruct: Given a question, find passages of business documents that answer it\nQuery:"

_OPENER = _direct_opener()  # never through a proxy (same rule as the ai-adapter)


class EmbedError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def normalise(values, dims: int = DIMS) -> array:
    """First `dims` values, scaled to length 1 (a zero vector stays zero)."""
    vec = array("f", (float(v) for v in values[:dims]))
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        for i, v in enumerate(vec):
            vec[i] = v / norm
    return vec


class EmbedClient:
    def __init__(self, url: str, *, dims: int = DIMS, timeout: float = 300.0, api_key: str | None = None):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("embed url must be http(s)://host:port")
        self.url, self.dims, self.timeout = url.rstrip("/"), dims, timeout
        self.headers = keychain.auth_headers(self.url, api_key)  # E-7: only https or private hosts; never logged

    def health(self) -> bool:
        try:
            with _OPENER.open(urllib.request.Request(self.url + "/health", headers=self.headers),
                              timeout=min(self.timeout, 5)) as r:
                return json.load(r).get("status") == "ok"
        except (OSError, ValueError):
            return False

    def embed(self, texts: list[str], *, query: bool = False) -> list[array]:
        out: list[array] = []
        for start in range(0, len(texts), BATCH):
            batch = [QUERY_PREFIX + t if query else t for t in texts[start:start + BATCH]]
            out.extend(self._request(batch))
        return out

    def _request(self, batch: list[str]) -> list[array]:
        body = json.dumps({"input": batch, "encoding_format": "float"}).encode()
        req = urllib.request.Request(self.url + "/v1/embeddings", data=body,
                                     headers={"Content-Type": "application/json", **self.headers})
        try:
            with _OPENER.open(req, timeout=self.timeout) as r:
                resp = json.load(r)
        except urllib.error.HTTPError as e:
            raise EmbedError(f"embed_http_{e.code}") from None
        except (OSError, ValueError):
            raise EmbedError("embed_unreachable") from None
        try:
            items = sorted(resp["data"], key=lambda d: d["index"])
            vectors = [item["embedding"] for item in items]
        except (KeyError, TypeError):
            raise EmbedError("embed_bad_response") from None
        if len(vectors) != len(batch) or any(
                not isinstance(v, list) or len(v) < self.dims or not all(isinstance(x, (int, float)) for x in v)
                for v in vectors):
            raise EmbedError("embed_bad_response")
        return [normalise(v, self.dims) for v in vectors]
