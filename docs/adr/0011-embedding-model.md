# ADR-0011: Embedding model for the knowledge index

Status: **Accepted** (2026-11-05, Gianni chose "second small model" for Phase 6).

## Context
Brief C1 asks for embeddings from the active AI backend. The default chat model (ADR-0003, Qwen3-1.7B) is not
trained for embeddings. Options: a second small embedding model, or keyword search (SQLite FTS5) plus DT3's own
"related" function without embeddings (deviates from C1).

## Decision
**Qwen3-Embedding-0.6B, Q8_0 GGUF** (Apache-2.0), served by a second llama-server (`--embedding --pooling last`).

- Source: `https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF/resolve/370f27d7550e0def9b39c1f16d3fbaa13aa67728/Qwen3-Embedding-0.6B-Q8_0.gguf`
- Size 639 150 592 bytes, SHA-256 `06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`
  (Hugging Face LFS metadata, read 2026-11-05).
- 100+ languages incl. de/fr/it/en; 1024 dimensions with MRL → we keep 512 (half the storage, small quality loss).
- Query instruction in English, as the model card advises; documents without instruction.

## Consequences
- Downloaded only after consent, size and license shown, SHA-256 checked (as ADR-0003). Never bundled.
- About 0.7–1 GB more memory while the embedding server runs (UNVERIFIED on the floor machine); it is idle
  between jobs. Phase 7 power mode may stop it on battery or memory pressure.
- llama.cpp b12015 support for this model and `--pooling last` is UNVERIFIED until the K-1 floor check.
- The index is rebuildable: changing the model means re-embedding (stored with the model name).
