# Phase 4 retest — tax office letter (MacBook Pro 2014, macOS 11.7, DT3 3.9.17)

Passed on 2026-11-05: C (deadline), D (urgent), B-2 (QR values read back: IBAN, total, reference).
Still open: **B-6 tax office**. Cause found: the running engine kept its old settings in memory, and
`live on` wrote them back over the new ones from `testconfig`. `testconfig` now restarts the engine.

Copy **one grey box at a time** into Terminal.

## A. Start

```bash
cd ~/dt3agent-dev-kit && bash tools/dev-agent.sh llama && bash tools/dev-agent.sh install osakit
```

```bash
bash tools/dev-agent.sh testconfig "Erika Beispiel" && tools/dt3agent live on
```

Check (read only): expected a number of 1 or more.

```bash
grep -c Steueramt ~/Library/Application\ Support/DT3\ Agent/config.json
```

## B. Tax office letter (B-6)

1. In DT3 click the `ocr-de` document (Steueramt, already in the test database). Then:

```bash
tools/dt3agent process
```

2. After 1–2 minutes:

```bash
tools/dt3agent review urgent
```

   Expected: an item with `"words": ["Steueramt"]` and `"hints": []` (no deadline is ever computed).
   Type its `"id"` in place of 8:

```bash
tools/dt3agent decide 8 accept
```

   Expected: `{"applied": true}`, the letter is in `_Urgent`.

## C. End

```bash
tools/dt3agent live off && bash tools/dev-agent.sh uninstall
```

Send me the outputs. Then I write the Phase 4 report.
