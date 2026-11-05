# Phase 4 gate — floor test (MacBook Pro 2014, macOS 11.7, DT3 3.9.17)

Goal: Swiss features on the **test database**. Nothing is ever deleted.
Copy **one grey box at a time** into Terminal. Where a command needs a number, the step says which.

## A. Start (every time)

```bash
cd ~/dt3agent-dev-kit && bash tools/dev-agent.sh llama && bash tools/dev-agent.sh install osakit
```

```bash
bash tools/dev-agent.sh testconfig "Erika Beispiel" && tools/dt3agent live on
```

In DT3 create the group **`_Urgent`** in the test database (top level), if it is not there yet.

## B. QR-bill (B-1, B-2, B-3, B-4)

1. Drag `~/dt3agent-dev-kit/samples/qrbill-qrr.pdf` into the test database. Click it. Then:

```bash
tools/dt3agent process
```

2. Wait until `tools/dt3agent status` shows no `"queued"` (each document takes 1–2 minutes). Info pane (Cmd+Shift+I) → **screenshot**.
   Expected: `dt3agenttotal CHF 1957.04`, `dt3agentiban CH4431999123000889012`,
   `dt3agentreference 210000000003139471430009017`.

```bash
tools/dt3agent review field
```

   Expected: items `dt3agentretention` (`2036-12-31`) and `dt3agentretentionbasis`; maybe `dt3agentuid`.
   Copy the whole output to me.

## C. Deadline → calendar event + DT3 reminder (B-5)

The `Frist-Muster` from the last run is still in the test database and carries the **test reminder** you set by hand.
First check that the agent never overwrites it, then let it create its own.

3. List the deadline items:

```bash
tools/dt3agent review deadline
```

   Note the `"id"` of the item with `"date": "2026-12-17"`. Type it in place of 7:

```bash
tools/dt3agent decide 7 accept
```

   Expected: `dt3agent: reminder_exists` (the document already has your test reminder; nothing is changed).

4. In DT3 remove the test reminder: click `Frist-Muster`, Info pane (Cmd+Shift+I) → reminder → **none**. Then again (same number):

```bash
tools/dt3agent decide 7 accept
```

   Expected: `{"applied": true}`. Next to the document a new record `Frist Muster Verwaltung AG … 2026-12-17.ics`;
   the document has a reminder (bell) for 17.12.2026, 09:00. Double-click the `.ics` → macOS Calendar shows the
   event on 17.12.2026 → **screenshots**. If an error appears, copy it exactly.

## D. Urgent letter (B-6)

5. List the urgent letters:

```bash
tools/dt3agent review urgent
```

   Pick one from the Zahlungsbefehl sample. Expected: `"hints"` with "SchKG Art. 74 … bitte prüfen".
   Type its number in place of 8:

```bash
tools/dt3agent decide 8 accept
```

   Expected: the letter moves to `_Urgent`.

```bash
tools/dt3agent status
```

   Expected: `"urgent_open"` is one less than before.

## E. Missing document (B-0) — optional

6. Only if an old review item points to a document that no longer exists (as on 2026-11-05). Run:

```bash
tools/dt3agent review
```

   Expected: that item shows `"record_missing": true` and `"actions": ["reject"]`.

## F. End

```bash
tools/dt3agent live off && bash tools/dev-agent.sh uninstall
```

Send me all outputs and screenshots. Then I write the Phase 4 report.
