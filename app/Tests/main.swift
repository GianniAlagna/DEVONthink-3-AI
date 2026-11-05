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
check(L10n(preferred: ["fr-CH", "de-CH"]).language == "de", "first language with texts wins")
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

if failures > 0 { print("\(failures) failed"); exit(1) }
print("app tests ok")
