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
    metadata: r.customMetaData() || {} });
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
  // UNVERIFIED on the floor: getRecordAt (move itself verified in Phase 0, S4).
  const r = rec(uuid);
  const g = dt3().getRecordAt(location, { in: r.database() });
  if (!g || g.type() !== 'group') throw new Error('group_not_found');
  dt3().move({ record: r, to: g });
  return JSON.stringify({ uuid: uuid, location: r.location() });
}
function setTags(uuid, tagsJson) {
  const r = rec(uuid);
  r.tags = JSON.parse(tagsJson);
  return JSON.stringify({ uuid: r.uuid(), tags: r.tags() });
}
function run(argv) {
  const verbs = { info: info, selected: selected, read: read, readText: readText, readPath: readPath, setTags: setTags,
    setName: setName, setComment: setComment, setMetadata: setMetadata, move: move };
  const f = verbs[argv[0]];
  if (!f) throw new Error('unknown_verb');
  return f.apply(null, argv.slice(1));
}
"""

/// Runs the DT3 handlers either in-process via OSAKit or via /usr/bin/osascript as a child of this host.
/// Verified on macOS 11 (Phase 2 T5): OSAKit (default) passes parameters and keeps the Automation entry on this app;
/// osascript is the fallback.
final class DT3Bridge {
    enum Mode: String { case osakit, osascript }
    let mode: Mode
    private var script: OSAScript?
    private let scriptFile: URL
    private var checkedVersion = false

    init(mode: Mode) throws {
        self.mode = mode
        scriptFile = FileManager.default.temporaryDirectory.appendingPathComponent("dt3agent-bridge.js")
        try jxaSource.write(to: scriptFile, atomically: true, encoding: .utf8)
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
    case "move":
        guard args.count == 2, let l = args["location"] as? String, l.hasPrefix("/"), l.count <= 500,
              !l.split(separator: "/").contains("..") else { throw HostError(code: "bad_args") }
        try bridge.requireDT3()
        text = try bridge.call("move", [try uuid(), l])
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
