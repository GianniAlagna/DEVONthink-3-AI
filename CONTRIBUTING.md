# Contributing to DT3 Agent

Thank you for helping! This project brings private, offline AI to DEVONthink 3 users on macOS. Contributions of any size are welcome: tests on old Macs, code, Swiss domain knowledge, translations, docs.

## Before you start

1. Read [`docs/SPEC.md`](docs/SPEC.md) (what we build) and the ADRs in [`docs/adr/`](docs/adr/) (why).
2. Check the open tasks in [`fsd/todo.md`](fsd/todo.md) and the [issues](../../issues).
3. For anything bigger than a small fix, open an issue first so we can agree on the approach.

## Ground rules (non-negotiable)

| Rule | Why |
|---|---|
| Engine runtime = **Python standard library only** | Offline install, no compiled dependencies on old Macs |
| Works on **macOS 11 Big Sur, Intel** | That is the floor; newer APIs only behind a version check |
| **Never delete** anything in DEVONthink | No delete action exists in the engine |
| No string-built shell or scripts; arguments via argv/stdin | Injection safety |
| AI output is untrusted: parse → schema → allowlist → act | Prompt injection in documents |
| No telemetry, no cloud calls | Privacy promise |
| **Synthetic test data only** — never real personal documents | revDSG/GDPR |
| Never use "DEVONthink" in a product name | Trademark; describe compatibility only |

## Workflow

- Tests first for non-trivial logic (red → green → refactor); bugs get a failing test first.
- One concern per pull request; describe problem, change, verification, limitations.
- [Conventional Commits](https://www.conventionalcommits.org/): `feat(rules): validate QR reference (mod 10 recursive)`.
- New dependencies (even dev-only) need agreement in an issue first.

## Development setup (from Phase 2)

```bash
python3 -m pytest engine/tests -q
```
```bash
python3 -m ruff check engine
```
Swift parts build with Command Line Tools for Xcode 13.2 (`tools/build-swift.sh`, added in Phase 2).

## Floor testing

If you have an old Intel Mac with macOS 11/12 and DEVONthink 3, your test runs are extremely valuable. The Phase 0 test kit in [`spike/`](spike/) shows the style: scripts that measure and write logs, never touching real data.

## License

By contributing you agree that your contribution is licensed under the [Apache License 2.0](LICENSE).
