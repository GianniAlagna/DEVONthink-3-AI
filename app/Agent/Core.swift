// DT3 Agent menu-bar app: pure logic (no AppKit), compiled into the app and into app/Tests (SPEC §4.18, U-1).
import Foundation

/// The engine's `status` reply (SPEC §4.17). Missing fields get safe defaults; unknown fields are ignored.
struct EngineStatus: Equatable {
    var version = ""
    var dt3Version: String?
    var paused = false
    var dryRun = true
    var aiConfigured = false
    var aiOK = false
    var queue: [String: Int] = [:]
    var reviewItems = 0
    var urgentOpen = 0

    init() {}

    init(json: [String: Any]) {
        version = json["version"] as? String ?? ""
        dt3Version = json["dt3_version"] as? String
        paused = json["paused"] as? Bool ?? false
        dryRun = json["dry_run"] as? Bool ?? true
        aiConfigured = json["ai_configured"] as? Bool ?? false
        aiOK = json["ai_ok"] as? Bool ?? false
        if let q = json["queue"] as? [String: Any] {
            for (k, v) in q { if let n = v as? Int { queue[k] = n } }
        }
        reviewItems = json["review_items"] as? Int ?? 0
        urgentOpen = json["urgent_open"] as? Int ?? 0
    }

    /// Jobs still to do: waiting plus the one running now.
    var pending: Int { (queue["queued"] ?? 0) + (queue["running"] ?? 0) }
}

/// Status shown in the menu bar (brief E1). Each state has its own symbol, so color is never the only signal.
enum Health: Equatable {
    case offline        // engine not reachable
    case noAI           // AI backend missing or not answering
    case noDT3          // DT3 not running or not answering
    case paused
    case dryRun         // test mode: proposals only, nothing written
    case ready

    init(_ status: EngineStatus?) {
        guard let s = status else { self = .offline; return }
        if !s.aiConfigured || !s.aiOK { self = .noAI }
        else if s.dt3Version == nil { self = .noDT3 }
        else if s.paused { self = .paused }
        else if s.dryRun { self = .dryRun }
        else { self = .ready }
    }

    /// SF Symbol name (macOS 11+).
    var symbol: String {
        switch self {
        case .offline: return "xmark.octagon"
        case .noAI, .noDT3: return "exclamationmark.triangle"
        case .paused: return "pause.circle"
        case .dryRun: return "eye.circle"
        case .ready: return "checkmark.circle"
        }
    }

    var textKey: L10n.Key {
        switch self {
        case .offline: return .healthOffline
        case .noAI: return .healthNoAI
        case .noDT3: return .healthNoDT3
        case .paused: return .healthPaused
        case .dryRun: return .healthDryRun
        case .ready: return .healthReady
        }
    }

    var needsAttention: Bool { self == .offline || self == .noAI || self == .noDT3 }
}

/// User-facing text for an engine error code. Codes never carry document content (SPEC §4.17).
func errorText(_ code: String, _ t: L10n) -> String {
    switch code {
    case "engine_not_running", "engine_unreachable": return t[.errEngine]
    case "nothing_selected": return t[.errNothingSelected]
    case "undo_failed": return t[.errUndo]
    case "group_not_found": return t[.errGroupMissing]
    case "reminder_exists": return t[.errReminderExists]
    case "record_missing", "not_found": return t[.errRecordMissing]
    case "bad_value": return t[.errBadValue]
    case "index_unavailable": return t[.errIndex]
    case "question_invalid": return t[.errQuestion]
    case "embed_unreachable": return t[.errEmbed]
    default: return t[.errOther] + " (" + code + ")"
    }
}
