// Knowledge window logic (SPEC §4.20, K-7): ask answers and summaries as plain values. Pure Foundation, tested.
// Source links are built from record UUIDs, never taken from text the model wrote.
import Foundation

struct AskSource: Identifiable, Equatable {
    let id: String      // record UUID
    let name: String
    var link: URL? { URL(string: "x-devonthink-item://" + id) }
}

struct AskAnswer: Equatable {
    let text: String
    let sources: [AskSource]
    let filtered: Int   // sentences addressed to an AI that the engine removed from the documents

    init?(json: [String: Any]) {
        guard let answer = json["answer"] as? String else { return nil }
        text = answer
        filtered = json["filtered"] as? Int ?? 0
        sources = (json["sources"] as? [[String: Any]] ?? []).compactMap { s in
            guard let uuid = s["uuid"] as? String,
                  uuid.range(of: #"^[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}$"#, options: .regularExpression) != nil
            else { return nil }
            return AskSource(id: uuid, name: (s["name"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? uuid)
        }
    }

    /// Nothing in the documents: no answer text and no source.
    var notFound: Bool { text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && sources.isEmpty }
}

struct SummaryResult: Equatable {
    let text: String
    let partial: Bool

    init?(json: [String: Any]) {
        guard let s = json["summary"] as? String else { return nil }
        text = s
        partial = json["partial"] as? Bool ?? false
    }
}

let summaryLanguages = ["de", "fr", "it", "en"]

/// The question as the engine takes it (spaces collapsed, 1-1000 characters), or nil.
func cleanQuestion(_ input: String) -> String? {
    let q = input.split(whereSeparator: { $0.isWhitespace }).joined(separator: " ")
    return q.isEmpty || q.count > 1000 ? nil : q
}
