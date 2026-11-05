# Phase 3 retest 4 — fix two groups, then the last open points (about 15 minutes)

Retest 3 found the cause of `group_not_found`: the test database has **one** group named `Recht/Fall-Muster`
(with a slash in the name). DT3 Agent needs a group `Fall-Muster` **inside** a group `Recht`.
The same applies to `Finanzen/Rechnungen`. Nothing is deleted: you only rename and move groups.

Copy **one grey box at a time** into Terminal. Never copy text outside the boxes.

## A. Fix the two groups in DT3 (by hand, test database `DT3Agent-T1`)

1. Rename group `Recht/Fall-Muster` to `Fall-Muster`.
2. Create a new group `Recht` at the top level. Drag `Fall-Muster` into `Recht`.
3. Rename group `Finanzen/Rechnungen` to `Rechnungen`.
4. Create a new group `Finanzen` at the top level. Drag `Rechnungen` into `Finanzen`.

## B. Start

```bash
cd ~/dt3agent-dev-kit && bash tools/dev-agent.sh llama && bash tools/dev-agent.sh install osakit
```

```bash
tools/dt3agent live on
```

5. In DT3 click any document of the test database. Then:

```bash
osascript -l JavaScript -e 'const a=Application("DEVONthink 3"); const d=a.selectedRecords()[0].database(); JSON.stringify(["/Recht/Fall-Muster","/Finanzen/Rechnungen"].map(p => { const g=a.getRecordAt(p,{in:d}); return [p, g ? g.type() : null]; }))'
```

   Expected: `group` twice (not `null`).

## C. Case folder

```bash
tools/dt3agent decide 27 accept
```

   Expected: `"applied": true`. The invoice also appears in `Recht > Fall-Muster` → **screenshot**.

## D. Metadata and filing

```bash
tools/dt3agent decide 30 accept
```

```bash
tools/dt3agent decide 34 accept
```

6. In DT3 open the Info pane (Cmd+Shift+I) of that invoice → **screenshot** of the custom metadata and the location.

## E. Scan (OCR)

7. In DT3 click **ocr-de** (the PDF in the test database). Then:

```bash
tools/dt3agent process
```

8. Wait 90 seconds. Then:

```bash
tools/dt3agent review
```

   Expected: new items for the scan (name or comment), **no** `no_text` for it.

## F. Smart Rule on import

9. Drag `~/dt3agent-dev-kit/samples/Zahlungsbefehl-Muster.txt` into the test database **once more**.
   Do **not** click it, do **not** run process. Wait 60 seconds. Then:

```bash
bash tools/dev-agent.sh status
```

   Expected: one more `engine job …` line than before.

## G. Send and clean up

10. Send the whole Terminal output and the screenshots from C and step 6. Then:

```bash
tools/dt3agent live off
```

```bash
bash tools/dev-agent.sh uninstall
```

If a step fails, stop and send the full output of that step.
