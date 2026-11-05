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

if failures > 0 { print("\(failures) failed"); exit(1) }
print("app tests ok")
