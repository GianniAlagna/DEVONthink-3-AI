# Phase 4 retest — two open points (MacBook Pro 2014, macOS 11.7, DT3 3.9.17)

Parts C (deadline) and D (urgent) passed on 2026-11-05. Two points are still open:

| Point | Why open |
|---|---|
| B-2 QR-bill | The QR values were applied directly (confidence 0.95), so they never showed in `review` |
| B-6 tax office | `ocr-de.pdf` (Steueramt) was not flagged: the saved test config still held the urgent words from Phase 3. `testconfig` now refreshes them |

Copy **one grey box at a time** into Terminal.

## A. Start

```bash
cd ~/dt3agent-dev-kit && bash tools/dev-agent.sh llama && bash tools/dev-agent.sh install osakit
```

```bash
bash tools/dev-agent.sh testconfig "Erika Beispiel" && tools/dt3agent live on
```

## B. QR-bill values (B-2) — read only, changes nothing

```bash
osascript -l JavaScript -e 'const r=Application("DEVONthink 3").getRecordWithUuid("2BA1C95E-05D6-4FBC-9900-9B87CAF6712B"); JSON.stringify(r ? r.customMetaData() : null)'
```

Expected: `dt3agentiban` `CH4431999123000889012`, `dt3agenttotal` `CHF 1957.04`,
`dt3agentreference` `210000000003139471430009017`. If it prints `null`: drag `samples/qrbill-qrr.pdf` into the
test database again, click it, run `tools/dt3agent process`, wait 2 minutes, then use the new document's ID
(Edit > Copy Item Link) in place of `2BA1C95E-…`.

## C. Tax office letter (B-6)

1. Drag `~/dt3agent-dev-kit/samples/ocr-de.pdf` into the test database. Click it. Then:

```bash
tools/dt3agent process
```

2. After 1–2 minutes:

```bash
tools/dt3agent review urgent
```

   Expected: a new item with `"words": ["Steueramt"]` and `"hints": []` (no deadline is ever computed).
   Type its `"id"` in place of 8:

```bash
tools/dt3agent decide 8 accept
```

   Expected: `{"applied": true}`, the letter is in `_Urgent`.

## D. Calendar (optional) — screenshot

Open the group of a `Frist-Muster` copy: the `.ics` record lies next to it and the document shows the bell
(17.12.2026, 09:00). Double-click the `.ics` → macOS Calendar → **screenshot**.

## E. End

```bash
tools/dt3agent live off && bash tools/dev-agent.sh uninstall
```

Send me the outputs. Then I write the Phase 4 report.
