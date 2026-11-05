"""K-2 knowledge index (SPEC §4.20): chunking, incremental update, hybrid search, related records."""
import pytest

from dt3agent.embed import normalise
from dt3agent.index import CHUNK, Index, chunks
from tests.fakes import fake_vector


class FakeEmbedder:
    def __init__(self):
        self.calls = []

    def embed(self, texts, query=False):
        self.calls.append((list(texts), query))
        return [normalise(fake_vector(t)) for t in texts]


@pytest.fixture
def idx(tmp_path):
    return Index(tmp_path / "index.db", FakeEmbedder(), model="test-model")


def test_short_text_is_one_chunk():
    assert chunks("  Rechnung Nr. 1  ") == ["Rechnung Nr. 1"]
    assert chunks("") == []


def test_long_text_is_cut_at_sentence_ends_with_overlap():
    text = " ".join(f"Satz Nummer {i} endet hier." for i in range(300))
    parts = chunks(text)
    assert len(parts) > 1
    assert all(len(p) <= CHUNK for p in parts)
    assert all(p.endswith(".") for p in parts[:-1])          # cut after a sentence, not inside a word
    assert parts[0][-60:] in text and parts[1][:20] in parts[0]  # pieces overlap


def test_unchanged_text_is_not_embedded_again(idx):
    assert idx.update("U1", "DB", "Rechnung Muster AG") is True
    assert idx.update("U1", "DB", "Rechnung Muster AG") is False
    assert len(idx.embedder.calls) == 1
    assert idx.update("U1", "DB", "Rechnung Muster AG korrigiert") is True
    assert idx.count() == 1


def test_search_finds_the_matching_record_and_uses_the_query_instruction(idx):
    idx.update("INV", "DB", "Rechnung von Muster Treuhand AG über CHF 1957.04")
    idx.update("DOG", "DB", "Der Hund schläft im Garten unter dem Baum")
    hits = idx.search("Rechnung Muster Treuhand")
    assert hits[0].uuid == "INV"
    assert idx.embedder.calls[-1] == (["Rechnung Muster Treuhand"], True)


def test_search_respects_the_database_scope(idx):
    idx.update("A", "Privat", "Rechnung Zahnarzt")
    idx.update("B", "Firma", "Rechnung Treuhand")
    assert {h.uuid for h in idx.search("Rechnung", databases=["Firma"])} == {"B"}
    assert idx.search("Rechnung", databases=[]) == []


def test_keyword_query_cannot_inject_fts_syntax(idx):
    idx.update("A", "DB", "Rechnung Muster")
    hits = idx.search('Rechnung" OR uuid:* NEAR(')  # FTS5 syntax in the question must not raise
    assert [h.uuid for h in hits] == ["A"]


def test_remove(idx):
    idx.update("A", "DB", "Rechnung Muster")
    idx.remove("A")
    assert idx.count() == 0 and idx.search("Rechnung") == []


def test_other_model_clears_the_index(tmp_path):
    Index(tmp_path / "i.db", FakeEmbedder(), model="m1").update("A", "DB", "Text")
    assert Index(tmp_path / "i.db", FakeEmbedder(), model="m2").count() == 0


def test_related_records(idx):
    idx.update("A", "DB", "Mängelrüge Getriebedefekt Ford Puma Garantie")
    idx.update("B", "DB", "Antwort Mängelrüge Getriebedefekt Ford Puma Garantie Werkstatt")
    idx.update("C", "DB", "Der Hund schläft im Garten")
    related = idx.related("A", min_score=0.5)
    assert [u for u, _ in related] == ["B"]
    assert idx.related("missing") == []
