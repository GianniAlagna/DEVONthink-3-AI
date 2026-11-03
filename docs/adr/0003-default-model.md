# ADR-0003: Default model

Status: **Accepted** (2026-10-31, Phase 0 approved by Gianni).

## Context
8 GB floor, ≤ 3B parameters, permissive license only (owner decision Q3), de/fr/it/en.

## Decision
Default: **Qwen3-1.7B Q4_K_M** (Apache-2.0, ggml-org GGUF, pinned revision + SHA-256). Thinking off (`chat_template_kwargs.enable_thinking=false`, `--reasoning-budget 0`), temperature 0, JSON schema enforced. Granite-4.0-micro 3B (Apache-2.0) as optional larger model. SmolLM3 rejected (no German).

## Evidence (floor machine, see `docs/spike/phase0-report.md`)
S3 run 4: 20/20 schema-valid; median 19.9 s per 1-page document; field accuracy 78.6 %; peak memory footprint 1.92 GB; no slowdown under memory pressure. Granite 3B: ~45 s, 2.41 GB (unconstrained run).

## Consequences
- Language, amounts, dates are wrong in deterministic ways → ADR-0009 (rules first).
- Download only after consent, license shown (brief §8.4).
