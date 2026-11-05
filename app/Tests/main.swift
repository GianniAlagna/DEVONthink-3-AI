// Tests for the app's pure logic (app/Agent/Core.swift, L10n.swift). Built and run by tools/build-swift.sh.
import Foundation

var failures = 0
func check(_ ok: Bool, _ what: String, line: Int = #line) {
    if !ok { failures += 1; print("FAIL line \(line): \(what)") }
}

let ready: [String: Any] = ["version": "0.0.1", "dt3_version": "3.9.17", "paused": false, "dry_run": false,
                            "ai_configured": true, "ai_ok": true, "queue": ["queued": 2, "running": 1, "done": 9],
                            "review_items": 4, "urgent_open": 1]

// status decoding
let s = EngineStatus(json: ready)
check(s.dt3Version == "3.9.17" && s.reviewItems == 4 && s.urgentOpen == 1, "decodes the status reply")
check(s.pending == 3, "pending counts queued + running, not done")
let empty = EngineStatus(json: [:])
check(empty.dryRun && !empty.aiOK && empty.pending == 0, "missing fields get safe defaults (dry-run on)")

// health
func health(_ change: (inout [String: Any]) -> Void) -> Health {
    var j = ready
    change(&j)
    return Health(EngineStatus(json: j))
}
check(Health(nil) == .offline, "no reply means offline")
check(health { _ in } == .ready, "all fine means ready")
check(health { $0["ai_ok"] = false } == .noAI, "AI not answering")
check(health { $0["ai_configured"] = false } == .noAI, "AI not configured")
check(health { $0["dt3_version"] = NSNull() } == .noDT3, "DT3 not answering")
check(health { $0["paused"] = true } == .paused, "paused")
check(health { $0["dry_run"] = true } == .dryRun, "dry-run")
check(health { $0["paused"] = true; $0["ai_ok"] = false } == .noAI, "a problem outranks paused")
check(Health.offline.needsAttention && !Health.dryRun.needsAttention, "attention only for problems")
let symbols = [Health.offline, .noAI, .paused, .dryRun, .ready].map { $0.symbol }
check(Set(symbols).count == symbols.count, "each state has its own symbol (color is not the only signal)")

// texts
for lang in L10n.table.keys {
    for key in L10n.Key.allCases {
        check(L10n.table[lang]?[key]?.isEmpty == false, "\(lang) has text for \(key.rawValue)")
    }
}
check(!L10n.table["de"]!.values.contains { $0.contains("ß") }, "de-CH texts contain no ß")
check(L10n(preferred: ["de-CH", "en"]).language == "de", "de-CH picks German")
check(L10n(preferred: ["ja", "de-CH"]).language == "de", "first language with texts wins")
check(L10n(preferred: ["fr-CH", "de-CH"]).language == "fr", "fr-CH picks French")
check(L10n(preferred: ["it-CH"]).language == "it", "it-CH picks Italian")
check(Set(L10n.table.keys) == ["de", "en", "fr", "it"], "four languages")
func specs(_ s: String) -> [String] {
    var out: [String] = []
    var i = s.startIndex
    while let r = s.range(of: "%", range: i..<s.endIndex) {
        let n = s.index(after: r.lowerBound)
        guard n < s.endIndex else { break }
        if "d@%".contains(s[n]) { out.append(String(s[r.lowerBound...n])) }
        i = s.index(after: n)
    }
    return out
}
for lang in L10n.table.keys {
    for key in L10n.Key.allCases {
        check(specs(L10n.table[lang]?[key] ?? "") == specs(L10n.table["en"]![key]!),
              "\(lang) \(key.rawValue) has the same format fields as en")
    }
}
check(L10n(preferred: ["ja"]).language == "en", "unknown language falls back to English")
check(L10n(preferred: ["de"]).format(.undoDone, 3, 1) == "3 wiederhergestellt, 1 Konflikte", "format with numbers")
let en = L10n(preferred: ["en"])
check(errorText("nothing_selected", en) == "Nothing is selected in DT3.", "known code gets a sentence")
check(errorText("weird_code", en) == "Error (weird_code)", "unknown code is shown as is")

// rpc reply decoding
check((try? RPC.decode(Data(#"{"ok": true, "result": {"paused": true}}"#.utf8)) as? [String: Any])?["paused"] as? Bool == true,
      "ok reply returns the result")
do { _ = try RPC.decode(Data(#"{"ok": false, "error": "bad_uuid"}"#.utf8)); check(false, "error reply throws") }
catch let e as RPCError { check(e.code == "bad_uuid", "error code is passed on") } catch { check(false, "error type") }
do { _ = try RPC.decode(Data("not json".utf8)); check(false, "garbage throws") }
catch let e as RPCError { check(e.code == "bad_reply", "garbage is bad_reply") } catch { check(false, "error type") }

// rpc against a missing socket
do { _ = try RPC.call("status", timeout: 1, path: NSTemporaryDirectory() + "dt3agent-no-such.sock"); check(false, "no socket throws") }
catch let e as RPCError { check(e.code == "engine_not_running", "missing socket is engine_not_running") } catch { check(false, "error type") }

// onboarding
check(SetupStep.welcome.previous == nil && SetupStep.finish.next == nil, "steps have ends")
check(SetupStep.allCases.count == 7, "seven steps")
check(AIHost("http://127.0.0.1:8080") == .thisMac && AIHost("http://localhost:11434") == .thisMac, "this Mac")
check(AIHost("http://192.168.1.20:8080") == .localNetwork && AIHost("http://10.0.0.5") == .localNetwork, "LAN")
check(AIHost("http://172.20.1.1") == .localNetwork && AIHost("http://nas.local:8080") == .localNetwork, "LAN 2")
check(AIHost("http://172.32.1.1") == .internet && AIHost("https://api.example.com") == .internet, "internet")
check(AIHost("ftp://127.0.0.1") == .invalid && AIHost("") == .invalid && AIHost("127.0.0.1") == .invalid, "invalid")
check(SystemFacts(macOS: (11, 7), ramGB: 8, appleSilicon: false).macOSSupported, "macOS 11 supported")
check(!SystemFacts(macOS: (10, 15), ramGB: 8, appleSilicon: false).macOSSupported, "macOS 10.15 not")
check(!SystemFacts(macOS: (12, 0), ramGB: 4, appleSilicon: true).ramEnough, "4 GB is too little")
check(cleanName("  Erika Beispiel ") == "Erika Beispiel" && cleanName("") == "", "names are trimmed")
check(cleanName("a\u{0007}b") == nil && cleanName(String(repeating: "x", count: 201)) == nil, "bad names refused")

// settings
check(lines(" a \n\n b\n") == ["a", "b"], "lines drops blanks and spaces")
check(parseMap("invoice = /Finanzen/Rechnungen/\n receipt=/Belege/ ") == ["invoice": "/Finanzen/Rechnungen/", "receipt": "/Belege/"],
      "map lines")
check(parseMap("no equals sign") == nil && parseMap("x = ") == nil, "bad map lines refused")
check(parseMap("") == [:], "empty map is fine")
check(formatMap(["b": "/B/", "a": "/A/"]) == "a = /A/\nb = /B/", "map is written sorted")
let cases = parseCases("Fall Muster | /Recht/Fall-Muster/ | Muster Treuhand AG, Az 123")
check(cases == [CaseFolder(name: "Fall Muster", group: "/Recht/Fall-Muster/", words: ["Muster Treuhand AG", "Az 123"])],
      "case line")
check(parseCases("only | two") == nil && parseCases("x | /G/ | ") == nil, "bad case lines refused")
check(formatCases(cases ?? []) == "Fall Muster | /Recht/Fall-Muster/ | Muster Treuhand AG, Az 123", "case round trip")
let cfg: [String: Any] = ["dry_run": false, "identity": ["name": "Erika Beispiel"],
                          "ai": ["url": "http://127.0.0.1:8080", "context": 8192],
                          "tags": ["vocabulary": ["Rechnung", "Steuern"]],
                          "filing": ["enabled": true, "groups": ["invoice": "/R/"], "review_group": "/_AI-Review/"],
                          "duplicates": ["near_threshold": 0.8, "group": "/_Duplicates/"],
                          "thresholds": ["apply": 0.85], "vision": ["helper": "/x"]]
var sv = SettingsValues(config: cfg)
check(!sv.dryRun && sv.name == "Erika Beispiel" && sv.vocabulary == "Rechnung\nSteuern" && sv.filingGroups == "invoice = /R/",
      "settings read from config")
check(sv.problems.isEmpty, "valid settings have no problems")
let ch = sv.changes
check(ch["vision"] == nil && ch["schema_version"] == nil, "locked settings are never sent")
check((ch["tags"] as? [String: Any])?["vocabulary"] as? [String] == ["Rechnung", "Steuern"], "vocabulary sent as a list")
check((ch["identity"] as? [String: Any])?["name"] as? String == "Erika Beispiel", "name sent")
sv.name = ""
check((sv.changes["identity"] as? [String: Any])?["name"] is NSNull, "empty name is sent as null")
sv.filingGroups = "broken"
sv.applyThreshold = 0.2
check(sv.problems.contains(.setFilingGroups) && sv.problems.contains(.setThresholds), "problems are named")
check(importChanges(["vision": ["helper": "/evil"], "dry_run": true]).map { $0["vision"] == nil } == true,
      "import drops locked keys")
check(importChanges(["vision": [:]]) == nil && importChanges("x") == nil, "nothing to import")

// review queue
let de = L10n(preferred: ["de"])
let nameItem = ReviewItem(json: ["id": 3, "uuid": "AB4B045D-7D33-44B0-B97F-991CCD829D09", "kind": "field",
                                 "field": "name", "after": "20260417_Muster-Treuhand-AG", "before": "scan01",
                                 "confidence": 0.7, "record_name": "scan01", "record_missing": false,
                                 "actions": ["accept", "edit", "reject"]])!
check(nameItem.title(de) == "Name" && nameItem.before == "scan01" && nameItem.after == "20260417_Muster-Treuhand-AG",
      "field item before/after")
check(nameItem.editValue("  neuer Name ") as? String == "neuer Name" && nameItem.editValue("  ") == nil, "field edit")
check(nameItem.link?.absoluteString == "x-devonthink-item://AB4B045D-7D33-44B0-B97F-991CCD829D09", "link to DT3")
let tagItem = ReviewItem(json: ["id": 4, "uuid": "U", "kind": "planned", "tags_add": ["Rechnung", "Steuern"],
                                "before": ["Steuern"], "actions": ["accept", "edit", "reject"]])!
check(tagItem.before == "Steuern" && tagItem.after == "Steuern, Rechnung", "tags after = old + new, no doubles")
check(tagItem.editStart == "Rechnung, Steuern", "tag edit starts with the proposed tags")
check(tagItem.editValue("A, B ,") as? [String] == ["A", "B"], "tag edit is a list")
let deadline = ReviewItem(json: ["id": 5, "uuid": "U", "kind": "deadline", "date": "2026-12-17",
                                 "title": "Frist: Muster Verwaltung AG", "actions": ["accept", "edit", "reject"]])!
check(deadline.after == "2026-12-17 – Frist: Muster Verwaltung AG" && deadline.editStart == "2026-12-17", "deadline")
check(deadline.editValue("2026-12-20") as? String == "2026-12-20" && deadline.editValue("20.12.2026") == nil,
      "deadline edit is a date")
let caseItem = ReviewItem(json: ["id": 6, "uuid": "U", "kind": "case", "case": "Fall Muster", "group": "/Recht/Fall-Muster/",
                                 "actions": ["accept", "edit", "reject"]])!
check(caseItem.title(de) == "Fall: Fall Muster" && caseItem.editStart == "replicate /Recht/Fall-Muster/", "case item")
check(caseItem.editValue("copy /X/") as? String == "copy /X/" && caseItem.editValue("delete /X/") == nil,
      "case edit: only replicate, copy or link")
let urgentItem = ReviewItem(json: ["id": 7, "uuid": "U", "kind": "urgent", "group": "/_Urgent/",
                                   "hints": ["SchKG Art. 74"], "actions": ["accept", "reject"]])!
check(!urgentItem.canEdit && urgentItem.hints == ["SchKG Art. 74"] && urgentItem.editValue("x") == nil, "urgent")
let gone = ReviewItem(json: ["id": 8, "uuid": "U", "kind": "field", "field": "comment", "record_missing": true,
                             "record_name": NSNull(), "before": NSNull(), "actions": ["reject"]])!
check(gone.missing && gone.recordName == nil && gone.before == "" && gone.actions == ["reject"], "missing record")
check(ReviewItem(json: ["kind": "field"]) == nil, "item without id is skipped")
check(errorText("reminder_exists", en) == "The document already has a reminder. Nothing was changed.", "decide errors")

// installer
let ip = InstallPaths(home: URL(fileURLWithPath: "/Users/erika"), bundle: URL(fileURLWithPath: "/Applications/DT3 Agent.app"))
check(ip.enginePlist.path == "/Users/erika/Library/LaunchAgents/codes.modular.dt3agent.engine.plist", "engine plist path")
check(ip.script.path == "/Users/erika/Library/Application Scripts/com.devon-technologies.think3/Smart Rules/DT3 Agent Enqueue.scpt",
      "smart rule script path")
check(ip.model.path == "/Users/erika/Library/Application Support/DT3 Agent/models/Qwen3-1.7B-Q4_K_M.gguf", "model path")
let ep = ip.enginePlistContent()
check(ep["Label"] as? String == "codes.modular.dt3agent.engine" && ep["KeepAlive"] as? Bool == true, "engine plist")
check((ep["ProgramArguments"] as? [String])?.first ==
      "/Applications/DT3 Agent.app/Contents/Helpers/DT3 Agent Engine.app/Contents/MacOS/DT3AgentEngine",
      "the signed host is the program (ADR-0005)")
check((ep["ProgramArguments"] as? [String])?.contains("/Applications/DT3 Agent.app/Contents/Resources/engine") == true,
      "engine dir inside the app")
let lp = ip.llamaPlistContent(threads: 4)
let largs = lp["ProgramArguments"] as? [String] ?? []
check(largs.contains("127.0.0.1") && largs.contains("--no-webui") && largs.contains("8192") && !largs.contains("0.0.0.0"),
      "llama-server: this Mac only, no web UI, 8192 context")
let zeroArgs = ip.llamaPlistContent(threads: 0)["ProgramArguments"] as? [String] ?? []
if let ti = zeroArgs.firstIndex(of: "-t") { check(zeroArgs[ti + 1] == "1", "at least one thread") } else {
    check(false, "threads argument")
}
let patched = patchConfig(["ai": ["url": NSNull(), "context": 8192], "identity": ["name": "Erika"]],
                          visionHelper: "/x/dt3agent-vision", aiURL: "http://127.0.0.1:8080")
check((patched["vision"] as? [String: Any])?["helper"] as? String == "/x/dt3agent-vision", "vision helper set")
check((patched["ai"] as? [String: Any])?["url"] as? String == "http://127.0.0.1:8080", "AI address set when empty")
check((patched["identity"] as? [String: Any])?["name"] as? String == "Erika", "other settings stay")
let kept = patchConfig(["ai": ["url": "http://192.168.1.5:11434"]], visionHelper: "/v", aiURL: "http://127.0.0.1:8080")
check((kept["ai"] as? [String: Any])?["url"] as? String == "http://192.168.1.5:11434", "a set AI address is kept")
check(hex([0, 15, 255]) == "000fff", "hex")
check(DefaultModel.sha256.count == 64 && DefaultModel.url.scheme == "https", "model pinned by https and SHA-256")
let items = installItems(ip) { $0.hasSuffix(".plist") }
check(items.count == 7 && items.filter { $0.present }.count == 3, "items with what is there")
let embArgs = ip.embedPlistContent(threads: 4)["ProgramArguments"] as? [String] ?? []
check(embArgs.contains("--embedding") && embArgs.contains("last") && embArgs.contains("8081") && embArgs.contains("127.0.0.1")
      && embArgs.contains(ip.embedModel.path) && !embArgs.contains("0.0.0.0"), "index server: embeddings, this Mac only, 8081")
check(EmbedModel.sha256.count == 64 && EmbedModel.url.scheme == "https", "index model pinned by https and SHA-256")
let withEmbed = patchConfig(["ai": ["url": NSNull()]], visionHelper: "/v", aiURL: nil, embedURL: "http://127.0.0.1:8081")
check((withEmbed["ai"] as? [String: Any])?["embed_url"] as? String == "http://127.0.0.1:8081", "index address set when empty")

// knowledge window (K-7)
let good = "AB4B045D-7D33-44B0-B97F-991CCD829D09"
let ans = AskAnswer(json: ["answer": "CHF 1957.04", "sources": [
    ["uuid": good, "name": "Rechnung", "link": "x-devonthink-item://EVIL"],
    ["uuid": "not-a-uuid", "name": "x"], ["uuid": good.lowercased(), "name": "y"]]])!
check(ans.text == "CHF 1957.04" && ans.sources.map(\.id) == [good], "only real record UUIDs become sources")
check(ans.sources[0].link?.absoluteString == "x-devonthink-item://" + good, "link built from the UUID, never from the reply")
check(AskAnswer(json: ["answer": "", "sources": []])!.notFound, "empty answer means not found")
check(AskAnswer(json: ["sources": []]) == nil, "an answer needs text")
check(AskAnswer(json: ["answer": "x", "sources": [["uuid": good, "name": ""]]])!.sources[0].name == good,
      "a source without a name shows its UUID")
check(SummaryResult(json: ["summary": "Kurz", "partial": true]) == SummaryResult(json: ["summary": "Kurz", "partial": true])
      && SummaryResult(json: ["summary": "Kurz", "partial": true])!.partial, "summary with partial flag")
check(cleanQuestion("  Wie   hoch\nist die Rechnung? ") == "Wie hoch ist die Rechnung?", "question spaces collapsed")
check(cleanQuestion("   ") == nil && cleanQuestion(String(repeating: "x", count: 1001)) == nil, "bad questions refused")
check(summaryLanguages == ["de", "fr", "it", "en"], "four summary languages")
check(errorText("index_unavailable", de) == de[.errIndex], "index error text")

if failures > 0 { print("\(failures) failed"); exit(1) }
print("app tests ok")
