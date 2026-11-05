# Phase 5 gate — floor test (MacBook Pro 2014, macOS 11.7, DT3 3.9.17)

Goal: the menu-bar app as a user sees it. Installer, setup, menu, Review Queue, settings, languages, VoiceOver,
removal. Use the **test database** only. Nothing is ever deleted in DT3.
Copy **one grey box at a time** into Terminal. Take a **screenshot** wherever it says so.

## A. Prepare (Terminal)

1. Remove the developer agents (from Phase 2–4), then build the app with Python and the AI server inside
   (about 3 minutes):

```bash
cd ~/dt3agent-dev-kit && bash tools/dev-agent.sh uninstall && bash tools/dev-agent.sh bundle
```

   Expected last line: `Built: ~/Applications/DT3 Agent.app (…)`. No line with `Warning`.

2. Copy the AI model you already have, so the installer does not download 1 GB again:

```bash
mkdir -p ~/Library/Application\ Support/DT3\ Agent/models && cp ~/dt3agent-dev/models/Qwen3-1.7B-Q4_K_M.gguf ~/Library/Application\ Support/DT3\ Agent/models/
```

3. **Quit DT3** (Cmd+Q). The installer copies the Smart Rule script only while DT3 is closed.

## B. Installer (U-5)

4. Open the app:

```bash
open ~/Applications/DT3\ Agent.app
```

   Expected: a new icon in the menu bar (top right). The window **Installation** opens by itself.
   List: AI model is green (copied in step 2). The others are orange. → **screenshot**

5. Click **Installieren**. Wait about 30 seconds. → **screenshot** of the lines at the bottom.
   Expected lines: `Smart-Rule-Skript installiert.`, `KI-Server gestartet.`, `Fertig. Die Engine läuft. …`.
   All five rows are now green.

6. Check (read only):

```bash
launchctl list | grep dt3agent; ls ~/Library/Application\ Scripts/com.devon-technologies.think3/Smart\ Rules/
```

   Expected: `codes.modular.dt3agent.engine` and `codes.modular.dt3agent.llama` (no `.dev`), and the file
   `DT3 Agent Enqueue.scpt`. Copy the output to me.

7. Close the installer window. Open DT3.

## C. Setup (U-2)

8. Menu-bar icon → **Einrichtung …**. Go through all 7 steps with **Weiter**:
   - **Systemprüfung**: if DT3 shows orange, click **Erneut prüfen**. If macOS asks whether “DT3 Agent Engine” may
     control DEVONthink 3: **OK**. → **screenshot** of the system check.
   - **KI**: click **Testen**. Expected: `Die KI antwortet.`
   - **Deine Angaben**: type `Erika Beispiel`.
   - **Dokumentnamen**: the example line changes while you type. Type `{foo}` at the end: expected
     `Diese Vorlage enthält unbekannte Felder.` Then click **Standard**.
   - **Smart Rule in DT3**: → **screenshot** (it lists your open databases).
   - **Bereit**: leave **Testmodus beibehalten (empfohlen)** on. Click **Fertig**.

## D. Smart Rule in DT3 (optional, 2 minutes)

9. In DT3: Tools → New Smart Rule. Event menu → **screenshot** of the event list (I need the exact German name
   of “On Import”). Action menu → “Execute Script” → the list must show **DT3 Agent Enqueue** → **screenshot**.
   Cancel; do not save the rule.

## E. Menu and Review Queue (U-1, U-4)

10. In DT3 select 2 documents in the test database. Menu-bar icon → **Ausgewählte Dokumente verarbeiten**.
    The menu shows the queue. Wait until it is empty (1–2 minutes per document). → **screenshot** of the open menu.
    Expected icon: an eye (test mode).

11. Menu → **Prüfliste (n)**. → **screenshot**. Each item shows the document name, `Vorher` / `Vorschlag` and
    `Sicherheit: … %`.
    - **In DT3 zeigen** on one item: DT3 shows that document.
    - **Ändern** on a tags item: change the text, press **Return**. Expected: the item disappears; DT3 shows the tags.
    - **Ändern** on another item, press **Escape**. Expected: the edit closes, nothing changes.
    - **Ändern** on a deadline item (if there is one), type `morgen`, press **Return**.
      Expected: warning `Diese Eingabe passt nicht.`
    - **Ablehnen** on one item: it disappears; nothing changes in DT3.

## F. Settings (U-3)

12. Menu → **Einstellungen …** (or Cmd+,). Click through all tabs → **screenshot** of **Schweiz**.
    - Change **Gruppe für dringende Briefe** to `/_Urgent2/`. Press **Cmd+S**. Expected: `Gesichert.`
    - Close and open Settings again: the value is still `/_Urgent2/`. Set it back to `/_Urgent/`, Cmd+S.
    - **Einstellungen exportieren …** → save on the Desktop. Open the file with TextEdit: settings, no document text.

## G. Languages (U-6)

13. French:

```bash
defaults write codes.modular.dt3agent.app AppleLanguages '("fr-CH")' && osascript -e 'quit app "DT3 Agent"'; sleep 2; open ~/Applications/DT3\ Agent.app
```

    Menu, **Réglages …** and **Liste de contrôle** in French → **screenshots**.

14. Italian (same as 13 with `it-CH`), then back to German:

```bash
defaults write codes.modular.dt3agent.app AppleLanguages '("it-CH")' && osascript -e 'quit app "DT3 Agent"'; sleep 2; open ~/Applications/DT3\ Agent.app
```

```bash
defaults delete codes.modular.dt3agent.app AppleLanguages; osascript -e 'quit app "DT3 Agent"'; sleep 2; open ~/Applications/DT3\ Agent.app
```

    Tell me any text that is cut off or reads wrong.

## H. VoiceOver and keyboard (U-6)

15. Turn VoiceOver on: **Cmd+F5**. Then:
    - Menu-bar icon (VoiceOver: press Ctrl+Option+M twice, then move with Ctrl+Option+arrow keys): it reads `DT3 Agent, Testmodus: nur Vorschläge`.
    - **Einrichtung …** → system check: each line starts with `In Ordnung` or `Achtung`.
    - Review Queue: the buttons read e.g. `Annehmen: Tags`.
    - Settings, tab **KI**: type `abc` as address, click **Testen**: nothing breaks.
    Turn VoiceOver off: **Cmd+F5**. Tell me what was read wrong or not at all.

16. Keyboard: System Preferences → Keyboard → Shortcuts → tick **Use keyboard navigation to move focus between
    controls**. In Settings move with **Tab**, switch toggles with **Space**, save with **Cmd+S**. Tell me where Tab
    gets stuck.

## I. Remove (U-5)

17. Menu → **Installation …**. Leave **Beim Entfernen auch das KI-Modell löschen** on and
    **… Einstellungen, Prüfliste und Protokolle löschen** off. Click **Entfernen**. → **screenshot**.

```bash
launchctl list | grep dt3agent; ls ~/Library/Application\ Support/DT3\ Agent/
```

    Expected: no `dt3agent` line. The folder still has `config.json` (settings kept); the folder `models` is empty.
    Your DT3 databases are unchanged.

18. Quit the app (menu → **DT3 Agent beenden**), then:

```bash
rm -rf ~/Applications/DT3\ Agent.app
```

Send me all outputs and screenshots. Then I write the Phase 5 report.
