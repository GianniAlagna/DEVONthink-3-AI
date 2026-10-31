# ADR-0009: Rules first, AI second

Status: **Proposed** (Phase 0, 2026-10-31) — accepted when Gianni approves the spike report.

## Context
Brief §3.2-1. S3 showed deterministic AI errors on language, amount and date.

## Decision
Language detection, amounts (total line, QR-bill), dates, IBAN/QR-IBAN, references and UID by **rules** (pure Python). The AI fills document type, sender/receiver, subject and summary, always with confidence; below threshold → Review Queue.

## Evidence (floor machine, see `docs/spike/phase0-report.md`)
S3 run 4: language always `de`; EN amount took the net value; FR date off by two days; DE type `receipt` instead of `invoice`. Sender, due date, currency correct.

## Consequences
- Each rule extractor gets table-driven tests (Phase 3/4).
- AI values never overwrite rule values.
