# Fehler `group_not_found` eingrenzen — Schritt für Schritt (ca. 10 Minuten)

Ziel: herausfinden, **warum** `tools/dt3agent decide 27 accept` mit `group_not_found` endet.
Es wird **nichts gelöscht**. Schritte 1–4 lesen nur. Erst Schritt 6 schreibt (Replikat in den Fall-Ordner).
Immer nur **einen grauen Kasten** kopieren. Nach jedem Schritt: Ausgabe mit der Tabelle vergleichen.

## 1. Richtiges Kit?

```bash
shasum -a 256 ~/Downloads/dt3agent-dev-kit.zip | cut -c1-16
```

| Ausgabe | Bedeutung | Weiter |
|---|---|---|
| gleiche Zahl wie in meiner Nachricht | richtiges Kit | Schritt 2 |
| andere Zahl | altes Kit | neues Kit laden, dann nochmals Schritt 1 |

```bash
rm -rf ~/dt3agent-dev-kit && ditto -x -k ~/Downloads/dt3agent-dev-kit.zip ~ && cd ~/dt3agent-dev-kit
```

## 2. Welche Datenbank ist ausgewählt?

In DT3 **ein Dokument der Testdatenbank** anklicken. Dann:

```bash
osascript -l JavaScript -e 'const r=Application("DEVONthink 3").selectedRecords()[0]; JSON.stringify({db:r.database().name(), name:r.name()})'
```

| Ausgabe | Bedeutung | Weiter |
|---|---|---|
| `"db":"DT3Agent-T1"` | Testdatenbank | Schritt 3 |
| anderer Name oder Fehler | falsches Dokument angeklickt | Dokument in `DT3Agent-T1` anklicken, Schritt 2 wiederholen |

## 3. Wie sehen die Gruppen aus? (nur Namen, kein Inhalt)

```bash
osascript -l JavaScript -e 'const d=Application("DEVONthink 3").selectedRecords()[0].database(); JSON.stringify(d.root().children().filter(c => c.type()==="group").map(c => [c.name(), c.children().filter(k => k.type()==="group").map(k => k.name())]))'
```

| Ausgabe enthält | Bedeutung | Weiter |
|---|---|---|
| `["Recht",["Fall-Muster"]]` | richtig verschachtelt | Schritt 4 |
| `["Recht/Fall-Muster",[]]` | **eine** Gruppe mit `/` im Namen | Schritt 4 (das neue Kit findet auch diese Form) |
| weder noch | Gruppe fehlt | in DT3 Gruppe `Recht` anlegen, darin `Fall-Muster`; Schritt 3 wiederholen |

## 4. Liegt das Dokument von Eintrag 27 in derselben Datenbank?

```bash
osascript -l JavaScript -e 'const r=Application("DEVONthink 3").getRecordWithUuid("AAE51938-EA82-42B0-BBAA-68A75343F353"); JSON.stringify(r ? {db:r.database().name(), location:r.location()} : null)'
```

| Ausgabe | Bedeutung | Weiter |
|---|---|---|
| `"db":"DT3Agent-T1"` | gleiche Datenbank wie die Gruppe | Schritt 5 |
| andere Datenbank | Fall-Ordner fehlt dort | Ursache gefunden → Ausgabe an mich |
| `null` | Dokument existiert nicht mehr | Ursache gefunden → Ausgabe an mich |

## 5. Engine starten

```bash
cd ~/dt3agent-dev-kit && bash tools/dev-agent.sh llama && bash tools/dev-agent.sh install osakit
```

```bash
tools/dt3agent live on
```

## 6. Der eigentliche Test

```bash
tools/dt3agent decide 27 accept
```

| Ausgabe | Bedeutung |
|---|---|
| `"applied": true` | **gelöst.** In DT3 liegt die Rechnung jetzt zusätzlich in `Fall-Muster` → Screenshot |
| `group_not_found` | Gruppe wird trotz Schritt 3 nicht gefunden → Ausgaben von 2–4 und 6 an mich |
| `no_open_item` | Eintrag 27 ist schon erledigt → `tools/dt3agent review` ausführen, die Nummer eines anderen `"kind": "case"` nehmen, Schritt 6 wiederholen |
| anderer Fehler | → Ausgabe an mich |

## 7. Aufräumen

```bash
tools/dt3agent live off
```

```bash
bash tools/dev-agent.sh uninstall
```

Schick mir die Ausgaben der Schritte 1–4 und 6 (alles in einem Stück reicht).
