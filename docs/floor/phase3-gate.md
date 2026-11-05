# Phase 3 gate — floor test (MacBook Pro 2014, macOS 11.7, DT3 3.9.17)

Goal: the full inbox pipeline on the **test database**. Nothing is ever deleted.
Copy **one grey box at a time** into Terminal. Never copy text outside the boxes.
Where a command needs a number, the step says which number to type.

## A. Start (every time)

```bash
cd ~/dt3agent-dev-kit && bash tools/dev-agent.sh llama && bash tools/dev-agent.sh install osakit
```

Expected: `llama-server running …` and `Started (osakit, service)`. If macOS asks about "DT3 Agent Engine": **OK**.

```bash
tools/dt3agent live on
```

## B. Invoice: metadata, filing, name (already partly done)

1. In DT3 click **Rechnung-Muster-Treuhand** (the one from Phase 2) so it is selected. Then:

```bash
tools/dt3agent process
```

2. Wait 60 seconds. In DT3 open the Info pane (Cmd+Shift+I) of that document → **screenshot**.
   Expected: custom metadata `dt3agentdate 2026-04-17`, `dt3agenttotal CHF 1957.04`, `dt3agentiban …`; the document is now in group `_AI-Review`.

## C. Duplicate

3. Drag `~/dt3agent-dev-kit/samples/Rechnung-Muster-Treuhand.txt` into the test database again. Click the **new** copy. Then:

```bash
tools/dt3agent process
```

4. Wait 60 seconds, then:

```bash
tools/dt3agent review
```

   Expected: an item with `"kind": "duplicate"`. Note its `"id"` number (for example 9) and type it in place of 9 here:

```bash
tools/dt3agent decide 9 accept
```

   Expected: the new copy gets the tag `duplicate` and moves to `_Duplicates`.

## D. Case folder

5. In the list from step 4 find an item with `"kind": "case"`. Type its number in place of 5:

```bash
tools/dt3agent decide 5 accept
```

   Expected: the invoice also appears in group `Recht/Fall-Muster` → **screenshot**.

## E. Scan (OCR)

6. In DT3 click the scan **PRT10.scan133209** (or drag in `~/dt3agent-dev-kit/samples/ocr-de.pdf` and click it). Then:

```bash
tools/dt3agent process
```

7. Wait 90 seconds, then `tools/dt3agent review`. Expected: items for the scan, **no** `no_text`. If macOS asks for access to a folder: **OK**.

## F. Urgent letter

8. Drag `~/dt3agent-dev-kit/samples/Zahlungsbefehl-Muster.txt` into the test database, click it, then:

```bash
tools/dt3agent process
```

9. Wait 60 seconds, then `tools/dt3agent review`. Expected: an item `"kind": "urgent"` with `Zahlungsbefehl`.

## G. Smart Rule on import

10. Drag `~/dt3agent-dev-kit/samples/Zahlungsbefehl-Muster.txt` in **once more**. Do **not** click it, do **not** run process. Wait 60 seconds, then:

```bash
bash tools/dev-agent.sh status
```

   Expected: one more `engine job …` line than before → the Smart Rule works on import.

## H. Send and clean up

11. Send the output of these two commands and the screenshots from steps 2 and 5:

```bash
tools/dt3agent review
```

```bash
bash tools/dev-agent.sh status
```

12. Clean up:

```bash
tools/dt3agent live off
```

```bash
bash tools/dev-agent.sh uninstall
```

If a step fails, stop and send the full output of that step.
