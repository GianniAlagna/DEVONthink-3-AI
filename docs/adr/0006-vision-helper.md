# ADR-0006: Vision helper

Status: **Accepted** (2026-10-31, Phase 0 approved by Gianni).

## Context
DT3 OCR is not usable from scripts (ADR-0004); QR-bill decode needs a reliable reader.

## Decision
Swift CLI (universal, target 11.0): PDFKit render at 300 dpi → `VNRecognizeTextRequest` revision 2, accurate, language list from settings; `VNDetectBarcodesRequest` for QR; payload returned byte-exact.

## Evidence (floor machine, see `docs/spike/phase0-report.md`)
S6: languages en, fr, it, de (+ es, pt, zh); char similarity de 0.997 / fr 0.966 / it 1.000 / en 1.000; 1.7–5.9 s per page; QR-bill QRR + SCOR byte-exact in 0.3–0.8 s.

## Consequences
- OCR text is for analysis only; originals stay untouched (A1).
- French logs a missing language-model asset on this macOS install; accuracy still 0.966.
