// DT3 Agent Engine — the LaunchAgent program (ADR-0005, SPEC §4.4).
//
// macOS charges Apple events to the responsible process, which for a launchd job is the job's program.
// So this signed app is the program, starts the Python engine as its child, and is the only process that
// sends Apple events to DEVONthink 3. The Automation permission then carries the name "DT3 Agent Engine".
//
// Protocol with the engine: the engine's stdout carries one JSON request per line
// {"id": n, "verb": "...", "args": {...}}; the host answers on the engine's stdin with
// {"id": n, "ok": true, "result": {...}} or {"id": n, "ok": false, "error": "code"}.
// Arguments reach DT3 as Apple-event parameters of pre-written handlers, never by building script text.
//
// Usage: DT3AgentEngine --python <python3> --engine-dir <dir> [--mode osakit|osascript] [-- engine args]
import Foundation
import OSAKit

let dt3BundleID = "com.devon-technologies.think3"
let maxLine = 64 * 1024
let uuidRegex = try! NSRegularExpression(pattern: "^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$")

var currentEngine: Process?  // the running Python engine, stopped on SIGTERM

func log(_ message: String) {
    FileHandle.standardError.write("\(ISO8601DateFormatter().string(from: Date())) host \(message)\n".data(using: .utf8)!)
}

struct HostError: Error { let code: String }

// MARK: - DT3 scripts (fixed text; data only as handler arguments)

let jxaSource = """
function dt3() { return Application('\(dt3BundleID)'); }
function selected() {
  // DT3 3.9 application property "selected records" (verified on the floor, Phase 2 gate)
  return JSON.stringify({ uuids: dt3().selectedRecords().slice(0, 100).map(function (r) { return r.uuid(); }) });
}
function rec(uuid) { const r = dt3().getRecordWithUuid(uuid); if (!r) throw new Error('not_found'); return r; }
function info() {
  const a = dt3();
  return JSON.stringify({ version: a.version(), databases: a.databases().map(function (d) { return d.name(); }) });
}
function read(uuid) {
  const r = rec(uuid);
  return JSON.stringify({ uuid: r.uuid(), name: r.name(), tags: r.tags(), comment: r.comment(), kind: r.kind(),
    wordCount: r.wordCount(), contentHash: r.contentHash(), location: r.location(), database: r.database().name(),
    metadata: r.customMetaData() || {}, created: r.creationDate().toISOString() });
}
function readText(uuid) {
  const t = rec(uuid).plainText() || '';
  return JSON.stringify({ uuid: uuid, text: t.slice(0, 200000), length: t.length });
}
function readPath(uuid) {
  return JSON.stringify({ uuid: uuid, path: rec(uuid).path() || '' });
}
function setName(uuid, name) { const r = rec(uuid); r.name = name; return JSON.stringify({ uuid: uuid, name: r.name() }); }
function setComment(uuid, c) { const r = rec(uuid); r.comment = c; return JSON.stringify({ uuid: uuid }); }
function setMetadata(uuid, key, value) {
  dt3().addCustomMetaData(value, { for: key, to: rec(uuid) });  // verified Phase 0 (S4); DT3 stores it as "md" + key
  return JSON.stringify({ uuid: uuid });
}
function move(uuid, location) {
  // Only into an existing group of the same database; the host never creates groups.
  // move itself verified in Phase 0 (S4).
  const r = rec(uuid);
  dt3().move({ record: r, to: group(location, r) });
  return JSON.stringify({ uuid: uuid, location: r.location() });
}
function isGroup(g) {
  // UNVERIFIED: the floor showed type() returning display text ("PDF document"), so accept any "group" spelling.
  return !!g && String(g.type()).toLowerCase().indexOf('group') >= 0;
}
function walk(db, location) {
  // Fallback without getRecordAt: follow the path name by name from the database root. Read-only.
  let g = db.root();
  const parts = location.split('/').filter(function (p) { return p.length > 0; });
  // A group whose own name holds the rest of the path ("Recht/Fall-Muster" as one name) also counts:
  // floor 2026-11-05 showed users create groups that way. Read-only; nothing is created or renamed.
  let i = 0;
  while (i < parts.length) {
    const kids = g.children();
    let next = null, used = 0;
    for (let n = parts.length - i; n >= 1 && !next; n--) {
      const want = parts.slice(i, i + n).join('/');
      for (let k = 0; k < kids.length; k++) {
        if (kids[k].name() === want && isGroup(kids[k])) { next = kids[k]; used = n; break; }
      }
    }
    if (!next) return null;
    g = next;
    i += used;
  }
  return g;
}
function group(location, r) {
  // Floor 2026-11-05: getRecordAt returned nothing for "/Recht/Fall-Muster/" and "/Recht/Fall-Muster".
  // Try getRecordAt with and without the trailing "/", then walk the path from the database root.
  const db = r ? r.database() : null;
  const paths = [location];
  if (location.length > 1 && location.endsWith('/')) paths.push(location.replace(/\\/+$/, ''));
  for (let i = 0; i < paths.length; i++) {
    const g = dt3().getRecordAt(paths[i], db ? { in: db } : {});
    if (isGroup(g)) return g;
  }
  const w = db ? walk(db, location) : null;
  if (isGroup(w)) return w;
  throw new Error('group_not_found');
}
function duplicatesOf(uuid) {
  return JSON.stringify({ uuids: (rec(uuid).duplicates() || []).slice(0, 20).map(function (d) { return d.uuid(); }) });
}
function replicateTo(uuid, location) { const r = rec(uuid); dt3().replicate({ record: r, to: group(location, r) }); return JSON.stringify({ uuid: uuid }); }
function duplicateTo(uuid, location) { const r = rec(uuid); const d = dt3().duplicate({ record: r, to: group(location, r) }); return JSON.stringify({ uuid: d.uuid() }); }
function createMarkdown(location, name, text) {
  // content, not plainText (ADR-0004, F7)
  const n = dt3().createRecordWith({ name: name, type: 'markdown', content: text }, { in: group(location, null) });
  return JSON.stringify({ uuid: n.uuid() });
}
function setTags(uuid, tagsJson) {
  const r = rec(uuid);
  r.tags = JSON.parse(tagsJson);
  return JSON.stringify({ uuid: r.uuid(), tags: r.tags() });
}
function run(argv) {
  const verbs = { info: info, selected: selected, read: read, readText: readText, readPath: readPath, setTags: setTags,
    setName: setName, setComment: setComment, setMetadata: setMetadata, move: move,
    duplicatesOf: duplicatesOf, replicateTo: replicateTo, duplicateTo: duplicateTo, createMarkdown: createMarkdown };
  const f = verbs[argv[0]];
  if (!f) throw new Error('unknown_verb');
  return f.apply(null, argv.slice(1));
}
"""

// B-5 calendar event + DT3 reminder. AppleScript, because DT3 3.9 refuses or crashes on reminders made from JXA
// (DEVONtechnologies forum "JS: make reminder syntax", 2021). UNVERIFIED on the floor until the Phase 4 gate:
// `get record with uuid`, `parent 1 of`, `import … to`, `make new reminder … at`.
// Never overwrites a reminder; nothing is deleted. Arguments arrive only as handler parameters.
let appleScriptSource = """
on addevent(theUUID, icsPath, y, m, d)
	tell application id "\(dt3BundleID)"
		set r to get record with uuid theUUID
		if r is missing value then error "not_found"
		if reminder of r is not missing value then error "reminder_exists"
		set g to parent 1 of r
		set theDate to current date
		set day of theDate to 1
		set year of theDate to (y as integer)
		set month of theDate to (m as integer)
		set day of theDate to (d as integer)
		set time of theDate to (9 * hours)
		set n to import icsPath to g
		make new reminder with properties {schedule:once, alarm:notification, due date:theDate} at r
		return "{\\"uuid\\":\\"" & (uuid of n) & "\\"}"
	end tell
end addevent
on run argv
	if (count of argv) is 6 and item 1 of argv is "addevent" then
		return addevent(item 2 of argv, item 3 of argv, item 4 of argv, item 5 of argv, item 6 of argv)
	end if
	error "unknown_verb"
end run
"""

/// Runs the DT3 handlers either in-process via OSAKit or via /usr/bin/osascript as a child of this host.
/// Verified on macOS 11 (Phase 2 T5): OSAKit (default) passes parameters and keeps the Automation entry on this app;
/// osascript is the fallback.
final class DT3Bridge {
    enum Mode: String { case osakit, osascript }
    let mode: Mode
    private var script: OSAScript?
    private let scriptFile: URL
    private var appleScript: OSAScript?  // compiled on first use: it needs DT3's dictionary, CI has no DT3
    private let appleScriptFile: URL
    private var checkedVersion = false

    init(mode: Mode) throws {
        self.mode = mode
        scriptFile = FileManager.default.temporaryDirectory.appendingPathComponent("dt3agent-bridge.js")
        try jxaSource.write(to: scriptFile, atomically: true, encoding: .utf8)
        appleScriptFile = FileManager.default.temporaryDirectory.appendingPathComponent("dt3agent-bridge.applescript")
        try appleScriptSource.write(to: appleScriptFile, atomically: true, encoding: .utf8)
        if mode == .osakit {
            guard let language = OSALanguage(forName: "JavaScript") else { throw HostError(code: "no_jxa") }
            let s = OSAScript(source: jxaSource, language: language)
            var error: NSDictionary?
            guard s.compileAndReturnError(&error) else { throw HostError(code: "compile_failed") }
            script = s
        }
    }

    func call(_ handler: String, _ args: [String]) throws -> String {
        switch mode {
        case .osakit:
            var error: NSDictionary?
            let descriptors = args.map { NSAppleEventDescriptor(string: $0) }
            guard let result = script!.executeHandler(withName: handler, arguments: descriptors, error: &error),
                  let text = result.stringValue else {
                throw HostError(code: errorCode(error))
            }
            return text
        case .osascript:
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
            p.arguments = ["-l", "JavaScript", scriptFile.path, handler] + args
            let out = Pipe(), err = Pipe()
            p.standardOutput = out
            p.standardError = err
            try p.run()
            p.waitUntilExit()
            let text = String(data: out.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            guard p.terminationStatus == 0 else {
                let message = String(data: err.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                throw HostError(code: message.contains("group_not_found") ? "group_not_found"
                                : message.contains("not_found") ? "not_found" : "dt3_error")
            }
            return text.trimmingCharacters(in: .whitespacesAndNewlines)
        }
    }

    /// AppleScript handlers (B-5). Same two modes as `call`.
    func callAppleScript(_ handler: String, _ args: [String]) throws -> String {
        switch mode {
        case .osakit:
            if appleScript == nil {
                guard let language = OSALanguage(forName: "AppleScript") else { throw HostError(code: "no_applescript") }
                let s = OSAScript(source: appleScriptSource, language: language)
                var error: NSDictionary?
                guard s.compileAndReturnError(&error) else { throw HostError(code: "compile_failed") }
                appleScript = s
            }
            var error: NSDictionary?
            let descriptors = args.map { NSAppleEventDescriptor(string: $0) }
            guard let result = appleScript!.executeHandler(withName: handler, arguments: descriptors, error: &error),
                  let text = result.stringValue else {
                throw HostError(code: errorCode(error))
            }
            return text
        case .osascript:
            let p = Process()
            p.executableURL = URL(fileURLWithPath: "/usr/bin/osascript")
            p.arguments = [appleScriptFile.path, handler] + args
            let out = Pipe(), err = Pipe()
            p.standardOutput = out
            p.standardError = err
            try p.run()
            p.waitUntilExit()
            let text = String(data: out.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            guard p.terminationStatus == 0 else {
                let message = String(data: err.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                throw HostError(code: message.contains("reminder_exists") ? "reminder_exists"
                                : message.contains("not_found") ? "not_found" : "dt3_error")
            }
            return text.trimmingCharacters(in: .whitespacesAndNewlines)
        }
    }

    /// Refuses write verbs unless the target answers as DEVONthink 3 (DT4 also answers to scripts).
    func requireDT3() throws {
        if checkedVersion { return }
        let info = try JSONSerialization.jsonObject(with: Data(try call("info", []).utf8)) as? [String: Any]
        guard let version = info?["version"] as? String, version.hasPrefix("3.") else { throw HostError(code: "not_dt3") }
        checkedVersion = true
    }

    private func errorCode(_ error: NSDictionary?) -> String {
        let text = error?.allValues.compactMap { $0 as? String }.joined(separator: " ") ?? ""
        if text.contains("group_not_found") { return "group_not_found" }
        if text.contains("reminder_exists") { return "reminder_exists" }
        if text.contains("not_found") { return "not_found" }
        if let number = error?.allValues.compactMap({ $0 as? Int }).first { return "dt3_error_\(abs(number))" }
        return "dt3_error"
    }
}

// MARK: - Request validation (the engine validates too; this is the second fence)

func isUUID(_ s: String) -> Bool {
    uuidRegex.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil
}

func handle(_ request: [String: Any], bridge: DT3Bridge) throws -> Any {
    guard let verb = request["verb"] as? String, let args = request["args"] as? [String: Any] else {
        throw HostError(code: "bad_request")
    }
    func uuid() throws -> String {
        guard let u = args["uuid"] as? String, isUUID(u) else { throw HostError(code: "bad_uuid") }
        return u
    }
    let text: String
    switch verb {
    case "info":
        guard args.isEmpty else { throw HostError(code: "bad_args") }
        text = try bridge.call("info", [])
    case "selected":
        guard args.isEmpty else { throw HostError(code: "bad_args") }
        text = try bridge.call("selected", [])
    case "read":
        guard args.count == 1 else { throw HostError(code: "bad_args") }
        text = try bridge.call("read", [try uuid()])
    case "read_text":
        guard args.count == 1 else { throw HostError(code: "bad_args") }
        text = try bridge.call("readText", [try uuid()])
    case "read_path":
        guard args.count == 1 else { throw HostError(code: "bad_args") }
        text = try bridge.call("readPath", [try uuid()])
    case "set_tags":
        guard args.count == 2, let tags = args["tags"] as? [String], tags.count <= 100,
              tags.allSatisfy({ !$0.isEmpty && $0.count <= 255 }) else { throw HostError(code: "bad_args") }
        try bridge.requireDT3()
        let tagsJSON = String(data: try JSONSerialization.data(withJSONObject: tags), encoding: .utf8)!
        text = try bridge.call("setTags", [try uuid(), tagsJSON])
    case "set_name":
        guard args.count == 2, let n = args["name"] as? String, !n.isEmpty, n.count <= 255 else { throw HostError(code: "bad_args") }
        try bridge.requireDT3()
        text = try bridge.call("setName", [try uuid(), n])
    case "set_comment":
        guard args.count == 2, let c = args["comment"] as? String, c.count <= 4000 else { throw HostError(code: "bad_args") }
        try bridge.requireDT3()
        text = try bridge.call("setComment", [try uuid(), c])
    case "set_metadata":
        guard args.count == 3, let k = args["key"] as? String, let v = args["value"] as? String, v.count <= 1000,
              k.range(of: "^[a-z][a-z0-9]{0,39}$", options: .regularExpression) != nil else { throw HostError(code: "bad_args") }
        try bridge.requireDT3()
        text = try bridge.call("setMetadata", [try uuid(), k, v])
    case "duplicates":
        guard args.count == 1 else { throw HostError(code: "bad_args") }
        text = try bridge.call("duplicatesOf", [try uuid()])
    case "replicate", "duplicate":
        guard args.count == 2, let l = args["location"] as? String, l.hasPrefix("/"), l.count <= 500,
              !l.split(separator: "/").contains("..") else { throw HostError(code: "bad_args") }
        try bridge.requireDT3()
        text = try bridge.call(verb == "replicate" ? "replicateTo" : "duplicateTo", [try uuid(), l])
    case "create_markdown":
        guard args.count == 3, let l = args["location"] as? String, l.hasPrefix("/"), l.count <= 500,
              !l.split(separator: "/").contains(".."), let n = args["name"] as? String, !n.isEmpty, n.count <= 255,
              let t = args["text"] as? String, t.count <= 2000 else { throw HostError(code: "bad_args") }
        try bridge.requireDT3()
        text = try bridge.call("createMarkdown", [l, n, t])
    case "move":
        guard args.count == 2, let l = args["location"] as? String, l.hasPrefix("/"), l.count <= 500,
              !l.split(separator: "/").contains("..") else { throw HostError(code: "bad_args") }
        try bridge.requireDT3()
        text = try bridge.call("move", [try uuid(), l])
    case "add_event":
        // B-5: the .ics goes to a private temp folder under its final name (DT3 names the record after the file),
        // DT3 imports it next to the record, then the folder is removed. Same limits as the engine.
        guard args.count == 4, let n = args["name"] as? String, n.hasSuffix(".ics"), n.count <= 120,
              n.range(of: "^[^/:\\u0000-\\u001f]+$", options: .regularExpression) != nil,
              let ics = args["ics"] as? String, ics.hasPrefix("BEGIN:VCALENDAR"), ics.count <= 8000,
              let d = args["date"] as? String, d.range(of: "^\\d{4}-\\d{2}-\\d{2}$", options: .regularExpression) != nil
        else { throw HostError(code: "bad_args") }
        try bridge.requireDT3()
        let ymd = d.split(separator: "-").map(String.init)
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("dt3agent-event-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: false,
                                                attributes: [.posixPermissions: 0o700])
        defer { try? FileManager.default.removeItem(at: dir) }
        let file = dir.appendingPathComponent(n)
        try ics.write(to: file, atomically: true, encoding: .utf8)
        text = try bridge.callAppleScript("addevent", [try uuid(), file.path, ymd[0], ymd[1], ymd[2]])
    default:
        throw HostError(code: "verb_not_allowed")  // there is no delete verb (brief §2.7)
    }
    return try JSONSerialization.jsonObject(with: Data(text.utf8))
}

// MARK: - Engine child process

struct Options {
    var python = ""
    var engineDir = ""
    var mode = DT3Bridge.Mode.osakit
    var engineArgs: [String] = []
}

func parseOptions() -> Options {
    var o = Options()
    var it = CommandLine.arguments.dropFirst().makeIterator()
    while let a = it.next() {
        switch a {
        case "--python": o.python = it.next() ?? ""
        case "--engine-dir": o.engineDir = it.next() ?? ""
        case "--mode": o.mode = DT3Bridge.Mode(rawValue: it.next() ?? "") ?? .osakit
        case "--": while let rest = it.next() { o.engineArgs.append(rest) }
        default: log("ignoring unknown option \(a)")
        }
    }
    return o
}

func runEngine(_ o: Options, bridge: DT3Bridge) -> Int32 {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: o.python)
    // -I: isolated mode (no env vars, no user site). The engine dir arrives as argv[1], not as code text.
    p.arguments = ["-I", "-c",
                   "import runpy, sys; sys.path.insert(0, sys.argv[1]); del sys.argv[1]; "
                   + "runpy.run_module('dt3agent.engine', run_name='__main__', alter_sys=True)",
                   o.engineDir] + o.engineArgs
    let toEngine = Pipe(), fromEngine = Pipe()
    p.standardInput = toEngine
    p.standardOutput = fromEngine
    p.standardError = FileHandle.standardError
    do { try p.run() } catch { log("cannot start engine: \(error)"); return 127 }
    currentEngine = p
    log("engine started pid=\(p.processIdentifier) mode=\(bridge.mode.rawValue)")

    var buffer = Data()
    let reader = fromEngine.fileHandleForReading
    while true {
        let chunk = reader.availableData
        if chunk.isEmpty { break }  // engine closed stdout / exited
        buffer.append(chunk)
        if buffer.count > maxLine && buffer.firstIndex(of: 0x0A) == nil {
            log("request too long, stopping engine")
            p.terminate()
            break
        }
        while let nl = buffer.firstIndex(of: 0x0A) {
            let line = buffer[buffer.startIndex..<nl]
            buffer.removeSubrange(buffer.startIndex...nl)
            var reply: [String: Any] = ["id": NSNull(), "ok": false, "error": "bad_request"]
            if let request = (try? JSONSerialization.jsonObject(with: line)) as? [String: Any] {
                reply["id"] = request["id"] ?? NSNull()
                do {
                    reply = ["id": reply["id"]!, "ok": true, "result": try handle(request, bridge: bridge)]
                } catch let e as HostError {
                    reply["error"] = e.code
                } catch {
                    reply["error"] = "host_error"
                }
            }
            var data = (try? JSONSerialization.data(withJSONObject: reply)) ?? Data()
            data.append(0x0A)
            toEngine.fileHandleForWriting.write(data)
        }
    }
    p.waitUntilExit()
    return p.terminationStatus
}

// MARK: - Main: run the engine, restart it with back-off, stop on SIGTERM
// The engine loop runs on the main thread: OSA scripting expects it. The signal handler uses its own queue.

signal(SIGTERM, SIG_IGN)
let term = DispatchSource.makeSignalSource(signal: SIGTERM, queue: DispatchQueue(label: "signals"))
term.setEventHandler {
    log("SIGTERM, stopping engine")
    currentEngine?.terminate()
    exit(0)
}
term.resume()

let options = parseOptions()
guard !options.python.isEmpty, !options.engineDir.isEmpty else {
    log("usage: DT3AgentEngine --python <python3> --engine-dir <dir> [--mode osakit|osascript] [-- engine args]")
    exit(64)
}
let bridge: DT3Bridge
do { bridge = try DT3Bridge(mode: options.mode) } catch {
    log("bridge setup failed: \((error as? HostError)?.code ?? "\(error)")")
    exit(70)
}

var delay: UInt32 = 1
while true {
    let status = runEngine(options, bridge: bridge)
    log("engine exited status=\(status), restart in \(delay)s")
    sleep(delay)
    delay = min(delay * 2, 300)
}
