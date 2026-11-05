# Phase 3 retest 3 — only the open points (about 15 minutes)

Already verified: name, comment, duplicate found, urgent letter, case match, re-check, dry-run, metadata values.
Copy **one grey box at a time** into Terminal. Never copy text outside the boxes.

## A. Start

```bash
cd ~/dt3agent-dev-kit && bash tools/dev-agent.sh llama && bash tools/dev-agent.sh install osakit
```

```bash
tools/dt3agent live on
```

## B. Groups check

1. In DT3 click any document of the **test database**. Then:

```bash
osascript -l JavaScript -e 'const a=Application("DEVONthink 3"); const d=a.selectedRecords()[0].database(); JSON.stringify({db:d.name(), top:d.root().children().map(c => [c.name(), c.type()])})'
```

   Send me the output. It shows only database and group names, no content.
2. If `Recht`, `_Duplicates` or `_AI-Review` is missing in that list: create it in the test database
   (and `Fall-Muster` inside `Recht`).

## C. Case folder and duplicate

```bash
tools/dt3agent review
```

3. Find an item with `"kind": "case"`. Type its number in place of 27:

```bash
tools/dt3agent decide 27 accept
```

   Expected: `"applied": true`. The document also appears in `Recht/Fall-Muster` → **screenshot**.
4. Find an item with `"kind": "duplicate"`. Type its number in place of 26:

```bash
tools/dt3agent decide 26 accept
```

   Expected: tag `duplicate`, document in `_Duplicates`.

## D. Metadata and filing

5. In the review list find the items with `"key": "dt3agentdate"` and `"field": "location"` (from the dry-run).
   Type their numbers in place of 30 and 34:

```bash
tools/dt3agent decide 30 accept
```

```bash
tools/dt3agent decide 34 accept
```

6. In DT3 open the Info pane (Cmd+Shift+I) of that document → **screenshot** of the custom metadata and the location.

## E. Scan (OCR)

7. Drag `~/dt3agent-dev-kit/samples/ocr-de.pdf` into the test database and click it. Then:

```bash
tools/dt3agent process
```

8. Wait 90 seconds. Then:

```bash
bash tools/dev-agent.sh status
```

   Expected: last line `engine job applied` or `engine job review`. If macOS asks for access: **OK**.

## F. Smart Rule on import

9. Drag `~/dt3agent-dev-kit/samples/Zahlungsbefehl-Muster.txt` in **once more**. Do **not** click it, do **not** run process.
   Wait 60 seconds. Then:

```bash
bash tools/dev-agent.sh status
```

   Expected: one more `engine job …` line than in step 8.

## G. Send and clean up

10. Send the whole Terminal output and the screenshots from steps 3 and 6. Then:

```bash
tools/dt3agent live off
```

```bash
bash tools/dev-agent.sh uninstall
```

If a step fails, stop and send the full output of that step.
