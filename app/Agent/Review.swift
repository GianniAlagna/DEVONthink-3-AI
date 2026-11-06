// Review Queue logic (brief §6.4, U-4): one engine review item as display text, and edit input → decide value.
// Pure Foundation, tested in app/Tests. The engine checks every decision again (SPEC §4.15).
import Foundation

struct ReviewItem: Identifiable, Equatable {
    let id: Int
    let uuid: String
    let kind: String
    let code: String?
    let recordName: String?
    let missing: Bool
    let actions: [String]
    let field: String?
    let key: String?
    let before: String
    let after: String
    let confidence: Double?
    let hints: [String]
    let caseName: String?
    let tagsAdd: [String]
    let preview: String  // J-4 report: the first lines of the note (the engine keeps the full text)

    init?(json j: [String: Any]) {
        guard let id = j["id"] as? Int, let uuid = j["uuid"] as? String, let kind = j["kind"] as? String else {
            return nil
        }
        self.id = id
        self.uuid = uuid
        self.kind = kind
        code = j["code"] as? String
        recordName = j["record_name"] as? String
        missing = j["record_missing"] as? Bool ?? false
        actions = j["actions"] as? [String] ?? ["reject"]
        field = j["field"] as? String
        key = j["key"] as? String
        confidence = (j["confidence"] as? NSNumber)?.doubleValue
        hints = j["hints"] as? [String] ?? []
        caseName = j["case"] as? String
        tagsAdd = j["tags_add"] as? [String] ?? []
        preview = kind == "report" ? (j["preview"] as? String ?? "") : ""
        let beforeValue = j["before"]
        switch kind {
        case "planned":
            let old = beforeValue as? [String] ?? []
            let add = j["tags_add"] as? [String] ?? []
            before = old.joined(separator: ", ")
            after = (old + add.filter { !old.contains($0) }).joined(separator: ", ")
        case "field":
            before = ReviewItem.text(beforeValue)
            after = ReviewItem.text(j["after"])
        case "duplicate":
            before = ""
            after = "x-devonthink-item://" + (j["other"] as? String ?? "")
        case "case", "urgent", "report":
            before = ""
            after = j["group"] as? String ?? ""
        case "deadline":
            before = ""
            after = [j["date"] as? String, j["title"] as? String].compactMap { $0 }.joined(separator: " – ")
        default:
            before = ""
            after = ""
        }
    }

    private static func text(_ v: Any?) -> String {
        switch v {
        case let s as String: return s
        case let n as NSNumber: return n.stringValue
        case let a as [Any]: return a.map { text($0) }.joined(separator: ", ")
        default: return ""
        }
    }

    /// Short heading of the proposal, e.g. "Name", "Tags", "Fall: Fall Muster".
    func title(_ t: L10n) -> String {
        switch kind {
        case "planned": return t[.kindTags]
        case "field":
            switch field {
            case "name": return t[.kindName]
            case "comment": return t[.kindComment]
            case "location": return t[.kindLocation]
            default: return t.format(.kindMetadata, key ?? "")
            }
        case "duplicate": return t[.kindDuplicate]
        case "case": return t.format(.kindCase, caseName ?? "")
        case "deadline": return t[.kindDeadline]
        case "urgent": return t[.kindUrgent]
        case "report": return t[.kindReport]
        default: return t.format(.kindError, code ?? "")
        }
    }

    /// What the edit field expects, as a hint under it.
    func editHint(_ t: L10n) -> String {
        switch kind {
        case "planned": return t[.editHintTags]
        case "deadline": return t[.editHintDate]
        case "duplicate", "case": return t[.editHintGroup]
        default: return ""
        }
    }

    var canEdit: Bool { actions.contains("edit") }
    var link: URL? { kind == "report" ? nil : URL(string: "x-devonthink-item://" + uuid) }  // a report has no record

    /// What the edit field starts with.
    var editStart: String {
        switch kind {
        case "planned": return tagsAdd.joined(separator: ", ")
        case "field": return after
        case "deadline": return String(after.prefix(10))
        case "duplicate": return "replicate /_Duplicates/"
        case "case": return "replicate " + after
        default: return ""
        }
    }

    /// The `value` for decide(edit), or nil when the input cannot be right (the engine checks it again).
    func editValue(_ input: String) -> Any? {
        let s = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !s.isEmpty else { return nil }
        switch kind {
        case "planned":
            let tags = s.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
            return tags.isEmpty ? nil : tags
        case "field":
            return s
        case "deadline":
            return s.range(of: #"^\d{4}-\d{2}-\d{2}$"#, options: .regularExpression) != nil ? s : nil
        case "duplicate", "case":
            return s.range(of: #"^(replicate|copy|link) /\S.*$"#, options: .regularExpression) != nil ? s : nil
        default:
            return nil
        }
    }
}
