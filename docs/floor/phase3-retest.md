# Phase 3 retest 2 — only the open points (about 15 minutes)

Run 1 and 2 already verified: name, comment, duplicate, urgent letter, case match, re-check.
Copy **one grey box at a time** into Terminal. Never copy text outside the boxes.

## A. Start

```bash
cd ~/dt3agent-dev-kit && bash tools/dev-agent.sh llama && bash tools/dev-agent.sh install osakit
```

If macOS asks about "DT3 Agent Engine": **OK**.

## B. Dry-run (nothing is written)

1. Drag `~/dt3agent-dev-kit/samples/Rechnung-Muster-Treuhand.txt` into the test database and click the **new** copy.
   Live mode stays **off**. Then:

```bash
tools/dt3agent process
```

2. Wait 60 seconds. Then:

```bash
bash tools/dev-agent.sh status
```

   Expected: last line `engine job planned` or `engine job review`; the new copy in DT3 keeps its name, tags and place.

## C. Groups check

3. In the **test database** check that these groups exist (create the missing ones):
   `Recht` → `Fall-Muster`, `_Duplicates`, `_AI-Review`, `Finanzen` → `Rechnungen`.
4. Keep one document of the test database selected. Then:

```bash
osascript -l JavaScript -e 'const a=Application("DEVONthink 3"); const d=a.selectedRecords()[0].database(); JSON.stringify(["/Recht/Fall-Muster/","/Recht/Fall-Muster"].map(p => { const g=a.getRecordAt(p,{in:d}); return [p, g ? g.type() : null]; }))'
```

   Send me the output. It tells me which path form DT3 accepts.

## D. Case folder and duplicate (after the fix)

```bash
tools/dt3agent live on
```

```bash
tools/dt3agent review
```

5. Find an item with `"kind": "case"`. Type its number in place of 21:

```bash
tools/dt3agent decide 21 accept
```

   Expected: `"applied": true`. The document also appears in `Recht/Fall-Muster` → **screenshot**.
6. Find an item with `"kind": "duplicate"`. Type its number in place of 20:

```bash
tools/dt3agent decide 20 accept
```

   Expected: tag `duplicate`, document in `_Duplicates`.

## E. Metadata and filing

7. In DT3 click **Rechnung-Muster-Treuhand**, then:

```bash
tools/dt3agent process
```

8. Wait 60 seconds. Open the Info pane (Cmd+Shift+I) → **screenshot** of the custom metadata and the location.

## F. Scan (OCR)

9. Drag `~/dt3agent-dev-kit/samples/ocr-de.pdf` into the test database and click it. Then:

```bash
tools/dt3agent process
```

10. Wait 90 seconds. Then:

```bash
bash tools/dev-agent.sh status
```

   Expected: last line `engine job applied` or `engine job review`, **not** an error. If macOS asks for access: **OK**.

## G. Smart Rule on import

11. Drag `~/dt3agent-dev-kit/samples/Zahlungsbefehl-Muster.txt` in **once more**. Do **not** click it, do **not** run process.
    Wait 60 seconds. Then:

```bash
bash tools/dev-agent.sh status
```

   Expected: one more `engine job …` line than in step 10.

## H. Send and clean up

12. Send the whole Terminal output and the screenshots from steps 5 and 8. Then:

```bash
tools/dt3agent live off
```

```bash
bash tools/dev-agent.sh uninstall
```

If a step fails, stop and send the full output of that step.
