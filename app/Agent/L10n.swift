// Texts of the menu-bar app. de-CH and en now; fr-CH and it-CH follow in U-6 (until then they fall back to en).
// de-CH: "ss", never "ß" (a test checks it).
import Foundation

struct L10n {
    enum Key: String, CaseIterable {
        case appName
        case healthOffline, healthNoAI, healthNoDT3, healthPaused, healthDryRun, healthReady
        case processSelected, queuedN, queue, review, urgent
        case pause, resume
        case undo, undoConfirmTitle, undoConfirmText, undoButton, cancel, undoDone
        case settings, help, quit, ok
        case errEngine, errNothingSelected, errUndo, errOther
        // onboarding (U-2)
        case setupMenu, setupTitle, back, next, done, checkAgain, test
        case welcomeTitle, welcomeText
        case systemTitle, sysMacOS, sysChip, sysRAM, sysEngine, sysDT3, sysDT3Missing, sysAutomation, sysRAMLow
        case aiTitle, aiText, aiURL, aiThisMac, aiLAN, aiInternet, aiInvalid, aiOK, aiFail, aiModel
        case identityTitle, identityText, identityName
        case namingTitle, namingText, namingTemplate, namingPreview, namingInvalid, namingReset
        case ruleTitle, ruleText, ruleDatabases
        case finishTitle, finishText, keepTestMode
        case saveFailed
    }

    static let table: [String: [Key: String]] = [
        "de": [
            .appName: "DT3 Agent",
            .healthOffline: "Engine nicht erreichbar",
            .healthNoAI: "KI nicht erreichbar",
            .healthNoDT3: "DT3 ist nicht geöffnet",
            .healthPaused: "Pausiert",
            .healthDryRun: "Testmodus: nur Vorschläge",
            .healthReady: "Bereit",
            .processSelected: "Ausgewählte Dokumente verarbeiten",
            .queuedN: "%d Dokumente in der Warteschlange",
            .queue: "Warteschlange: %d",
            .review: "Prüfliste (%d)",
            .urgent: "Dringende Briefe: %d",
            .pause: "Pausieren",
            .resume: "Fortsetzen",
            .undo: "Letzten Durchgang rückgängig machen …",
            .undoConfirmTitle: "Letzten Durchgang rückgängig machen?",
            .undoConfirmText: "Die letzten Änderungen des Agenten werden zurückgesetzt. Was du seither selbst geändert hast, bleibt unverändert.",
            .undoButton: "Rückgängig machen",
            .cancel: "Abbrechen",
            .undoDone: "%d wiederhergestellt, %d Konflikte",
            .settings: "Einstellungen …",
            .help: "Hilfe & Support",
            .quit: "DT3 Agent beenden",
            .ok: "OK",
            .errEngine: "Die Engine läuft nicht. Starte DT3 Agent neu.",
            .errNothingSelected: "In DT3 ist nichts ausgewählt.",
            .errUndo: "Rückgängig machen ist fehlgeschlagen.",
            .errOther: "Fehler",
            .setupMenu: "Einrichtung …",
            .setupTitle: "DT3 Agent einrichten",
            .back: "Zurück",
            .next: "Weiter",
            .done: "Fertig",
            .checkAgain: "Erneut prüfen",
            .test: "Testen",
            .welcomeTitle: "Willkommen bei DT3 Agent",
            .welcomeText: "DT3 Agent ordnet Dokumente in DT3: Namen, Tags, Metadaten, Fristen. Alles läuft auf diesem Mac, nichts geht ins Internet. Es wird nie etwas gelöscht. Zu Beginn macht DT3 Agent nur Vorschläge (Testmodus); du entscheidest.",
            .systemTitle: "Systemprüfung",
            .sysMacOS: "macOS %@",
            .sysChip: "Prozessor: %@",
            .sysRAM: "Arbeitsspeicher: %d GB",
            .sysRAMLow: "Weniger als 8 GB: die KI wird langsam sein.",
            .sysEngine: "Engine läuft",
            .sysDT3: "DT3 %@ antwortet",
            .sysDT3Missing: "DT3 antwortet nicht. Öffne DT3 und klicke auf «Erneut prüfen».",
            .sysAutomation: "Fragt macOS, ob «DT3 Agent Engine» DEVONthink 3 steuern darf: auf «OK» klicken. Später änderbar unter Systemeinstellungen > Sicherheit > Datenschutz > Automation.",
            .aiTitle: "KI",
            .aiText: "Adresse des KI-Servers (llama.cpp, Ollama oder kompatibel). Standard: llama.cpp auf diesem Mac.",
            .aiURL: "Adresse",
            .aiThisMac: "Auf diesem Mac",
            .aiLAN: "Im lokalen Netz: Dokumenttexte gehen an diesen Rechner.",
            .aiInternet: "Achtung: Adresse im Internet. Dokumenttexte würden diesen Mac verlassen.",
            .aiInvalid: "Bitte eine Adresse mit http:// oder https:// eingeben.",
            .aiOK: "Die KI antwortet.",
            .aiFail: "Die KI antwortet nicht. Läuft der Server?",
            .aiModel: "Empfohlenes Modell für diesen Mac: Qwen3 1.7B (Q4_K_M, Apache-2.0). Es wird nie mitgeliefert, nur nach deiner Zustimmung geladen.",
            .identityTitle: "Deine Angaben",
            .identityText: "Briefe an diesen Namen erkennt DT3 Agent als Post an dich (Empfänger im Dokumentnamen). Leer lassen ist möglich.",
            .identityName: "Name oder Firma",
            .namingTitle: "Dokumentnamen",
            .namingText: "Vorlage für neue Namen. Felder: {datetime} {date} {sender} {receiver} {subject} {type} {lang} {amount} {reference}",
            .namingTemplate: "Vorlage",
            .namingPreview: "Beispiel: %@",
            .namingInvalid: "Diese Vorlage enthält unbekannte Felder.",
            .namingReset: "Standard",
            .ruleTitle: "Smart Rule in DT3",
            .ruleText: "DT3 Agent arbeitet nur in Gruppen, die du freigibst: Lege in DT3 eine Smart Rule an (Ereignis «Beim Importieren», Aktion «Skript ausführen: DT3 Agent Enqueue»). Ohne Smart Rule verarbeitest du Dokumente über das Menü «Ausgewählte Dokumente verarbeiten».",
            .ruleDatabases: "Offene Datenbanken: %@",
            .finishTitle: "Bereit",
            .finishText: "Im Testmodus schreibt DT3 Agent nichts in DT3. Alle Vorschläge erscheinen in der Prüfliste. Den Testmodus kannst du jederzeit in den Einstellungen ausschalten.",
            .keepTestMode: "Testmodus beibehalten (empfohlen)",
            .saveFailed: "Speichern fehlgeschlagen",
        ],
        "en": [
            .appName: "DT3 Agent",
            .healthOffline: "Engine not reachable",
            .healthNoAI: "AI not reachable",
            .healthNoDT3: "DT3 is not open",
            .healthPaused: "Paused",
            .healthDryRun: "Test mode: proposals only",
            .healthReady: "Ready",
            .processSelected: "Process selected records",
            .queuedN: "%d records queued",
            .queue: "Queue: %d",
            .review: "Review Queue (%d)",
            .urgent: "Urgent letters: %d",
            .pause: "Pause",
            .resume: "Resume",
            .undo: "Undo last batch …",
            .undoConfirmTitle: "Undo the last batch?",
            .undoConfirmText: "The agent's last changes are reset. What you changed yourself since then stays as it is.",
            .undoButton: "Undo",
            .cancel: "Cancel",
            .undoDone: "%d restored, %d conflicts",
            .settings: "Settings …",
            .help: "Help & Support",
            .quit: "Quit DT3 Agent",
            .ok: "OK",
            .errEngine: "The engine is not running. Restart DT3 Agent.",
            .errNothingSelected: "Nothing is selected in DT3.",
            .errUndo: "Undo failed.",
            .errOther: "Error",
            .setupMenu: "Setup …",
            .setupTitle: "Set up DT3 Agent",
            .back: "Back",
            .next: "Continue",
            .done: "Done",
            .checkAgain: "Check again",
            .test: "Test",
            .welcomeTitle: "Welcome to DT3 Agent",
            .welcomeText: "DT3 Agent organises documents in DT3: names, tags, metadata, deadlines. Everything runs on this Mac; nothing goes to the internet. Nothing is ever deleted. At first DT3 Agent only makes proposals (test mode); you decide.",
            .systemTitle: "System check",
            .sysMacOS: "macOS %@",
            .sysChip: "Processor: %@",
            .sysRAM: "Memory: %d GB",
            .sysRAMLow: "Less than 8 GB: the AI will be slow.",
            .sysEngine: "Engine is running",
            .sysDT3: "DT3 %@ answers",
            .sysDT3Missing: "DT3 does not answer. Open DT3 and click “Check again”.",
            .sysAutomation: "If macOS asks whether “DT3 Agent Engine” may control DEVONthink 3: click “OK”. You can change it later in System Preferences > Security & Privacy > Privacy > Automation.",
            .aiTitle: "AI",
            .aiText: "Address of the AI server (llama.cpp, Ollama or compatible). Default: llama.cpp on this Mac.",
            .aiURL: "Address",
            .aiThisMac: "On this Mac",
            .aiLAN: "On the local network: document text goes to that computer.",
            .aiInternet: "Warning: an internet address. Document text would leave this Mac.",
            .aiInvalid: "Please enter an address starting with http:// or https://.",
            .aiOK: "The AI answers.",
            .aiFail: "The AI does not answer. Is the server running?",
            .aiModel: "Recommended model for this Mac: Qwen3 1.7B (Q4_K_M, Apache-2.0). It is never bundled; it is downloaded only with your consent.",
            .identityTitle: "About you",
            .identityText: "Letters addressed to this name are recognised as mail to you (receiver in the document name). You may leave it empty.",
            .identityName: "Name or company",
            .namingTitle: "Document names",
            .namingText: "Template for new names. Fields: {datetime} {date} {sender} {receiver} {subject} {type} {lang} {amount} {reference}",
            .namingTemplate: "Template",
            .namingPreview: "Example: %@",
            .namingInvalid: "This template contains unknown fields.",
            .namingReset: "Default",
            .ruleTitle: "Smart Rule in DT3",
            .ruleText: "DT3 Agent works only in groups you enable: in DT3, create a Smart Rule (event “On Import”, action “Execute Script: DT3 Agent Enqueue”). Without a Smart Rule, process documents with the menu item “Process selected records”.",
            .ruleDatabases: "Open databases: %@",
            .finishTitle: "Ready",
            .finishText: "In test mode DT3 Agent writes nothing to DT3. All proposals appear in the Review Queue. You can switch test mode off at any time in Settings.",
            .keepTestMode: "Keep test mode (recommended)",
            .saveFailed: "Saving failed",
        ],
    ]

    let language: String

    /// First preferred language we have texts for; English otherwise.
    init(preferred: [String] = Locale.preferredLanguages) {
        let codes = preferred.map { String($0.prefix(2)).lowercased() }
        language = codes.first { L10n.table[$0] != nil } ?? "en"
    }

    subscript(_ key: Key) -> String {
        L10n.table[language]?[key] ?? L10n.table["en"]![key]!
    }

    func format(_ key: Key, _ args: CVarArg...) -> String {
        String(format: self[key], arguments: args)
    }
}
