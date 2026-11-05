// Settings window logic (brief §6.3, U-3): the editable part of config.json as plain values, and back.
// Pure Foundation, tested in app/Tests. The engine validates every save (config_set); this only shapes the data.
import Foundation

/// One line per entry; blank lines and surrounding spaces are dropped.
func lines(_ text: String) -> [String] {
    text.split(whereSeparator: \.isNewline).map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
}

/// "type = /Group/" per line → map. Returns nil when a line has no "=".
func parseMap(_ text: String) -> [String: String]? {
    var out: [String: String] = [:]
    for line in lines(text) {
        guard let eq = line.firstIndex(of: "=") else { return nil }
        let key = line[..<eq].trimmingCharacters(in: .whitespaces)
        let value = line[line.index(after: eq)...].trimmingCharacters(in: .whitespaces)
        guard !key.isEmpty, !value.isEmpty else { return nil }
        out[key] = value
    }
    return out
}

func formatMap(_ map: [String: String]) -> String {
    map.keys.sorted().map { "\($0) = \(map[$0]!)" }.joined(separator: "\n")
}

/// Case folder line: "Name | /Group/ | word one, word two" (brief A11).
struct CaseFolder: Equatable {
    var name: String
    var group: String
    var words: [String]

    var json: [String: Any] { ["name": name, "group": group, "words": words] }
}

func parseCases(_ text: String) -> [CaseFolder]? {
    var out: [CaseFolder] = []
    for line in lines(text) {
        let parts = line.split(separator: "|", omittingEmptySubsequences: false)
            .map { $0.trimmingCharacters(in: .whitespaces) }
        guard parts.count == 3, !parts[0].isEmpty, !parts[1].isEmpty else { return nil }
        let words = parts[2].split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
        guard !words.isEmpty else { return nil }
        out.append(CaseFolder(name: parts[0], group: parts[1], words: words))
    }
    return out
}

func formatCases(_ cases: [CaseFolder]) -> String {
    cases.map { "\($0.name) | \($0.group) | \($0.words.joined(separator: ", "))" }.joined(separator: "\n")
}

/// The values the settings window edits. Unknown or locked settings (vision, schema_version, …) are not touched.
struct SettingsValues: Equatable {
    var dryRun = true
    var name = ""
    var aiURL = ""
    var context = 8192
    var template = defaultTemplate
    var vocabulary = ""          // one tag per line
    var filingEnabled = false
    var filingGroups = ""        // "type = /Group/" per line
    var reviewGroup = "/_AI-Review/"
    var urgentWords = ""         // one word per line
    var urgentGroup = "/_Urgent/"
    var retentionEnabled = true
    var duplicatesGroup = "/_Duplicates/"
    var nearThreshold = 0.8
    var cases = ""               // "Name | /Group/ | words" per line
    var applyThreshold = 0.85
    var logContent = false

    init() {}

    init(config c: [String: Any]) {
        func section(_ k: String) -> [String: Any] { c[k] as? [String: Any] ?? [:] }
        dryRun = c["dry_run"] as? Bool ?? true
        name = section("identity")["name"] as? String ?? ""
        aiURL = section("ai")["url"] as? String ?? ""
        context = section("ai")["context"] as? Int ?? 8192
        template = section("naming")["template"] as? String ?? defaultTemplate
        vocabulary = (section("tags")["vocabulary"] as? [String] ?? []).joined(separator: "\n")
        filingEnabled = section("filing")["enabled"] as? Bool ?? false
        filingGroups = formatMap(section("filing")["groups"] as? [String: String] ?? [:])
        reviewGroup = section("filing")["review_group"] as? String ?? "/_AI-Review/"
        urgentWords = (section("keywords")["urgent"] as? [String] ?? []).joined(separator: "\n")
        urgentGroup = section("urgent")["group"] as? String ?? "/_Urgent/"
        retentionEnabled = section("retention")["enabled"] as? Bool ?? true
        duplicatesGroup = section("duplicates")["group"] as? String ?? "/_Duplicates/"
        nearThreshold = (section("duplicates")["near_threshold"] as? NSNumber)?.doubleValue ?? 0.8
        let caseList = (c["cases"] as? [[String: Any]] ?? []).compactMap { d -> CaseFolder? in
            guard let n = d["name"] as? String, let g = d["group"] as? String, let w = d["words"] as? [String] else {
                return nil
            }
            return CaseFolder(name: n, group: g, words: w)
        }
        cases = formatCases(caseList)
        applyThreshold = (section("thresholds")["apply"] as? NSNumber)?.doubleValue ?? 0.85
        logContent = section("logs")["content"] as? Bool ?? false
    }

    /// Which field has bad input, by key; empty when all can be sent to the engine.
    var problems: [L10n.Key] {
        var p: [L10n.Key] = []
        if cleanName(name) == nil { p.append(.identityName) }
        if !aiURL.trimmingCharacters(in: .whitespaces).isEmpty && AIHost(aiURL) == .invalid { p.append(.aiURL) }
        if parseMap(filingGroups) == nil { p.append(.setFilingGroups) }
        if parseCases(cases) == nil { p.append(.setCases) }
        if !(0.5...1.0).contains(nearThreshold) || !(0.5...1.0).contains(applyThreshold) { p.append(.setThresholds) }
        return p
    }

    /// The config_set changes for everything this window edits (only call when `problems` is empty).
    var changes: [String: Any] {
        let n = cleanName(name) ?? ""
        let url = aiURL.trimmingCharacters(in: .whitespaces)
        let out: [String: Any] = [
            "dry_run": dryRun,
            "identity": ["name": n.isEmpty ? NSNull() as Any : n as Any] as [String: Any],
            "ai": ["url": url.isEmpty ? NSNull() as Any : url as Any, "context": context] as [String: Any],
            "naming": ["template": template],
            "tags": ["vocabulary": lines(vocabulary)],
            "filing": ["enabled": filingEnabled, "groups": parseMap(filingGroups) ?? [:],
                       "review_group": reviewGroup] as [String: Any],
            "keywords": ["urgent": lines(urgentWords)],
            "urgent": ["group": urgentGroup],
            "retention": ["enabled": retentionEnabled],
            "duplicates": ["group": duplicatesGroup, "near_threshold": nearThreshold] as [String: Any],
            "cases": (parseCases(cases) ?? []).map { $0.json },
            "thresholds": ["apply": applyThreshold],
            "logs": ["content": logContent],
        ]
        return out
    }
}

/// Settings import (brief E5): everything but the keys the engine locks; the engine validates the rest.
func importChanges(_ json: Any) -> [String: Any]? {
    guard var d = json as? [String: Any] else { return nil }
    d.removeValue(forKey: "vision")
    d.removeValue(forKey: "schema_version")
    return d.isEmpty ? nil : d
}
