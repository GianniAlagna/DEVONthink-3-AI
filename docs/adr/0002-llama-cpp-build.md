# ADR-0002: llama.cpp build

Status: **Proposed** (Phase 0, 2026-10-31) — accepted when Gianni approves the spike report.

## Context
Official llama.cpp macOS x64 release binaries target macOS 13.3 (verified in `.github/workflows/release.yml`, tag b12015) and cannot run on the floor.

## Decision
Build `llama-server` from source, **latest release tag**, in CI per architecture with `CMAKE_OSX_DEPLOYMENT_TARGET=11.0`, `BUILD_SHARED_LIBS=OFF`, `GGML_METAL=OFF` (Intel), `GGML_ACCELERATE=OFF`, `GGML_BLAS=OFF`, `GGML_OPENMP=OFF`, `LLAMA_OPENSSL=OFF`. Apple Silicon build may enable Metal (to verify in CI).

## Evidence (floor machine, see `docs/spike/phase0-report.md`)
S2: b12015 built on the floor in 353 s with AppleClang 12.0.5 and 13.0.0; `minos 11.0`; links only libSystem and libc++.

## Consequences
- No need to pin an old llama.cpp release.
- Accelerate is off because its new LAPACK interface needs the macOS 13.3 SDK; CPU speed measured without it is acceptable (ADR-0003).
- Structured output must use `response_format.json_schema.schema` (the README form is ignored, `tools/server/server-common.cpp:1392-1394`).
