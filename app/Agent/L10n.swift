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
