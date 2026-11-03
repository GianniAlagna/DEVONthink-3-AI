# ADR-0005: Who sends Apple events to DT3

Status: **Accepted** (2026-10-31, Phase 0 approved by Gianni).

## Context
A LaunchAgent running the bundled interpreter got the Automation grant listed as **"python3.12"** (S5). Users would not recognise it, and interpreter updates may reset it.

## Decision
A small Swift helper inside the app bundle, **"DT3 Agent Bridge"**, signed with the project certificate (ADR-0010), executes the DT3 scripts. The engine calls it with arguments via argv/stdin only. The Automation entry then shows the product name and survives updates.

## Evidence (floor machine, see `docs/spike/phase0-report.md`)
S5: grant on python3.12 survived agent restarts and a Mac restart. S8: Apple events from a signed Swift app work; grant identity follows the signature (ADR-0010).

## Consequences
- One extra small binary to build and sign.
- Engine keeps no AppleScript/JXA permission of its own.
- **macOS attributes Apple events to the *responsible* process.** For a launchd job that is the job's program. If Python launches the bridge, the grant may again land on "python3.12". So the LaunchAgent program must be the signed Swift binary ("DT3 Agent Engine"); it starts the Python engine as its child and sends the Apple events itself. UNVERIFIED — Phase 2 task T5 verifies this on the floor machine.
