# DT3 Agent – Anleitung (Deutsch)

DT3 Agent ergänzt DEVONthink 3 um eine KI, die nur auf deinem Mac läuft. Er benennt, taggt und legt Dokumente ab,
liest Schweizer QR-Rechnungen, erkennt Fristen und Duplikate und beantwortet Fragen zu deinen Dokumenten mit
Quellen. **Er löscht nie etwas in DT3**, und jede Änderung lässt sich rückgängig machen.

*DT3 Agent ist ein unabhängiges Open-Source-Projekt und nicht mit DEVONtechnologies verbunden.*

## 1. Voraussetzungen

| | |
|---|---|
| macOS | 11 Big Sur oder neuer, Intel oder Apple Silicon |
| DEVONthink | 3.9.x (DEVONthink 4 wird nicht unterstützt) |
| Arbeitsspeicher | 16 GB empfohlen; mit 8 GB einen KI-Server im eigenen Netz verwenden |
| Speicherplatz | etwa 2.5 GB für App und KI-Modelle |

## 2. Installieren

1. DMG öffnen und **DT3 Agent** in den Ordner **Programme** ziehen.
2. Erster Start: Die App ist selbst signiert (keine Apple-Entwickler-ID).
   - macOS 11–14: Rechtsklick auf die App → **Öffnen** → **Öffnen**.
   - macOS 15 und neuer: App öffnen, dann **Systemeinstellungen → Datenschutz & Sicherheit → Trotzdem öffnen**.
3. **DT3 beenden** (Cmd+Q). Das Smart-Rule-Skript lässt sich nur bei geschlossenem DT3 kopieren.
4. Menüleisten-Symbol → **Installation …**. Die beiden Haken für die KI-Modelle setzen (Download von
   huggingface.co, etwa 1.9 GB, Prüfsumme wird kontrolliert) → **Installieren** → warten bis `Fertig.`
5. DT3 wieder öffnen. Bei der ersten Aktion fragt macOS, ob «DT3 Agent Engine» DEVONthink steuern darf: **OK**.

## 3. Einrichten

Menüleisten-Symbol → **Einrichtung …**, dann Schritt für Schritt mit **Weiter**:

1. **Systemprüfung** – alles grün? Sonst **Erneut prüfen**.
2. **KI** – **Testen** → `Die KI antwortet.`
3. **Deine Angaben** – dein Name (wird bei Briefen an dich als Empfänger verwendet und nie als Kontakt vorgeschlagen).
4. **Dokumentnamen** – Vorlage für Namen, mit Vorschau.
5. **Smart Rule in DT3** – in DT3: **Tools → New Smart Rule**, Ereignis **On Import**, Aktion
   **Apply Script › External › DT3 Agent Enqueue**. Nur Gruppen, für die du so eine Regel anlegst, werden bearbeitet.
6. **Bereit** – **Testmodus beibehalten (empfohlen)** lassen.

### Testmodus

Im Testmodus (Symbol: Auge) schreibt DT3 Agent **nichts** in DT3. Alle Vorschläge landen in der **Prüfliste**.
Erst wenn du die Vorschläge eine Weile für gut befindest: **Einstellungen → Allgemein → Testmodus** aus. Danach
werden sichere Vorschläge direkt angewendet, unsichere kommen weiterhin in die Prüfliste.

## 4. Täglich arbeiten

| Was | Wie |
|---|---|
| Neue Dokumente | kommen über die Smart Rule automatisch in die Warteschlange |
| Einzelne Dokumente | in DT3 auswählen → Menüleiste → **Ausgewählte Dokumente verarbeiten** |
| Vorschläge prüfen | Menüleiste → **Prüfliste** → **Annehmen**, **Ändern** oder **Ablehnen** |
| Etwas zurücknehmen | Menüleiste → **Letzten Durchgang rückgängig machen …** (deine eigenen Änderungen bleiben) |
| Kurz anhalten | Menüleiste → **Pausieren** |

Die Prüfliste zeigt bei jedem Vorschlag **Vorher** und **Vorschlag** sowie die **Sicherheit** in Prozent.
**In DT3 zeigen** öffnet das Dokument.

### Schweizer Briefe

- **QR-Rechnungen**: Betrag, Währung, Referenz und Gläubiger werden aus dem QR-Code gelesen und geprüft.
- **Fristen**: «zahlbar bis …» wird ein Vorschlag für einen Kalendereintrag mit DT3-Erinnerung – nur nach deinem OK.
- **Dringende Briefe** (Betreibung, Gericht, Steueramt): Hinweis in der Prüfliste, auf Wunsch in eine eigene Gruppe.

## 5. Fragen und Zusammenfassen

Menüleiste → **Fragen …**

- Frage eintippen, Return. Die Antwort nennt ihre **Quellen**; ein Klick öffnet das Dokument in DT3.
- Gibt es kein passendes Dokument, sagt DT3 Agent das – ohne zu raten.
- **Zusammenfassen**: In DT3 ein Dokument auswählen, Sprache wählen (DE, FR, IT, EN) → **Zusammenfassen**.
- Fragen kann nie etwas in DT3 ändern. Anweisungen an eine KI, die in Dokumenten stehen, werden vorher entfernt.

Hinweis: Das mitgelieferte Modell ist klein. Prüfe wichtige Antworten immer in der Quelle.

## 6. Zeitplan (Einstellungen → Ablauf)

| Auftrag | Standard | Wirkung |
|---|---|---|
| **Bereiche** | leer | Datenbanken und Gruppen, die der Nachtlauf lesen darf, eine Zeile pro Bereich: `Datenbank \| /Gruppe/` |
| **Nachtlauf** | ein, 02:30 | geänderte Dokumente der Bereiche in die Warteschlange |
| **Wochenübersicht** | aus | Montag 07:30: neue Dokumente, offene Fristen – als Notiz-Vorschlag |
| **Aufräum-Bericht** | aus | Sonntag 03:30: Dokumente ohne Tags, alte Einträge in der Eingangsgruppe, ähnliche Tags |
| **Feeds und Mails** | aus | täglich 06:30: Zusammenfassung neuer RSS-, Web- und Mail-Einträge |
| **Sparmodus** | ein | pausiert mit Akku und bei knappem Arbeitsspeicher |

Berichte brauchen eine **Gruppe, die in DT3 schon besteht**. DT3 Agent legt nie Gruppen an. Jeder Bericht kommt
zuerst in die Prüfliste; erst **Annehmen** schreibt ihn als Notiz.

Unter **Erweitert** kannst du **Notizen zu Personen und Firmen** einschalten: Ab zwei Dokumenten derselben Firma
schlägt DT3 Agent eine Notiz mit Links vor.

## 7. Menüleisten-Symbol

| Symbol | Bedeutung | Was tun |
|---|---|---|
| ✓ | Bereit | – |
| Auge | Testmodus | normal; nur Vorschläge |
| Pause | Pausiert | Menü → Fortsetzen |
| Blitz durchgestrichen | Wartet: Akku oder Speicher knapp | Netzteil anschliessen |
| ⚠︎ rot | KI, KI-Index oder DT3 nicht erreichbar | DT3 öffnen; Menü → Installation … → Installieren |
| Sanduhr rot | Warteschlange hängt seit über 2 Stunden | Menü → Einstellungen → Allgemein → Diagnose exportieren …, an den Support |
| ⛔ rot | Engine läuft nicht | Menü → Installation … → Installieren |

## 8. Einstellungen in Kürze

**Allgemein** (Testmodus, Name, Export/Import, Diagnose) · **KI** (Adresse des KI-Servers, optional API-Schlüssel im
Schlüsselbund) · **Namen** · **Tags** (dein Vokabular) · **Ablage** (Gruppen pro Dokumenttyp) · **Schweiz**
(dringende Briefe, Aufbewahrung) · **Duplikate & Fälle** · **Datenschutz** · **Erweitert** (Schwelle,
Personen und Firmen) · **Ablauf** (siehe 6). **Cmd+S** sichert.

## 9. Entfernen

Menüleiste → **Installation …** → **Entfernen**. Haken setzen, wenn auch die KI-Modelle bzw. Einstellungen,
Prüfliste und Protokolle gelöscht werden sollen. Deine DT3-Datenbanken bleiben unverändert. Danach die App aus
**Programme** in den Papierkorb ziehen.

## 10. Datenschutz und Hilfe

- Alles bleibt auf deinem Mac. Details: [PRIVACY.md](../../PRIVACY.md).
- Fehler melden: GitHub-Issues. Sicherheitsprobleme: **Security → Report a vulnerability**.
- Support für Firmen: [SUPPORT.md](../../SUPPORT.md).
