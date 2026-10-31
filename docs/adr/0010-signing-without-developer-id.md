# ADR-0010: Signing without an Apple Developer ID

Status: **Proposed** (Phase 0, 2026-10-31) — accepted when Gianni approves the spike report.

## Context
Owner decision Q7: no Apple Developer Program. Ad-hoc signatures change identity with every build.

## Decision
Sign app and helpers with a **project self-signed code-signing certificate** (key owned by Gianni, kept as a CI secret, never on the floor machine). No notarization. Distribute as DMG with first-launch instructions (right-click → Open on macOS 11–14; System Settings → Open Anyway on 15+) and offer build-from-source.

## Evidence (floor machine, see `docs/spike/phase0-report.md`)
S8: ad-hoc build 2 → macOS **asked again** for the DT3 permission (designated requirement = cdhash). Self-signed build 2 → **no new prompt**; designated requirement = identifier + certificate leaf hash, identical across builds.

## Consequences
- Users see a Gatekeeper warning once per download.
- Losing the certificate key = every user re-grants permissions → back up the key (owner).
- Build machines: keychain "Always Allow" for codesign avoids the password dialog.
