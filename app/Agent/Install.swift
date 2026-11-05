// Installer logic (SPEC §4.19, U-5): what gets installed where, as plain values. Pure Foundation, tested in app/Tests.
// The installer shows this list and asks first; uninstall removes exactly these items (never anything in DT3).
import Foundation

/// The default model (ADR-0003): pinned by revision and SHA-256, never bundled, downloaded only after consent.
enum DefaultModel {
    static let name = "Qwen3-1.7B-Q4_K_M.gguf"
    static let license = "Apache-2.0"
    static let url = URL(string: "https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/daeb8e2d528a760970442092f6bf1e55c3b659eb/Qwen3-1.7B-Q4_K_M.gguf")!
    static let sha256 = "d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5"
}

struct InstallPaths {
    let home: URL
    let bundle: URL      // DT3 Agent.app

    static let engineLabel = "codes.modular.dt3agent.engine"
    static let llamaLabel = "codes.modular.dt3agent.llama"
    static let aiURL = "http://127.0.0.1:8080"

    var launchAgents: URL { home.appendingPathComponent("Library/LaunchAgents") }
    var enginePlist: URL { launchAgents.appendingPathComponent(InstallPaths.engineLabel + ".plist") }
    var llamaPlist: URL { launchAgents.appendingPathComponent(InstallPaths.llamaLabel + ".plist") }
    var data: URL { home.appendingPathComponent("Library/Application Support/DT3 Agent") }
    var config: URL { data.appendingPathComponent("config.json") }
    var models: URL { data.appendingPathComponent("models") }
    var model: URL { models.appendingPathComponent(DefaultModel.name) }
    var logs: URL { home.appendingPathComponent("Library/Logs/DT3 Agent") }
    var smartRules: URL {
        home.appendingPathComponent("Library/Application Scripts/com.devon-technologies.think3/Smart Rules")
    }
    var script: URL { smartRules.appendingPathComponent("DT3 Agent Enqueue.scpt") }

    // inside the app bundle (assembled by tools/build-swift.sh; Python and llama-server are added for a release)
    var resources: URL { bundle.appendingPathComponent("Contents/Resources") }
    var engineHost: URL {
        bundle.appendingPathComponent("Contents/Helpers/DT3 Agent Engine.app/Contents/MacOS/DT3AgentEngine")
    }
    var vision: URL {
        bundle.appendingPathComponent("Contents/Helpers/DT3 Agent Engine.app/Contents/MacOS/dt3agent-vision")
    }
    var engineDir: URL { resources.appendingPathComponent("engine") }
    var python: URL { resources.appendingPathComponent("python/bin/python3") }
    var llamaServer: URL { resources.appendingPathComponent("llama/llama-server") }
    var bundledScript: URL { resources.appendingPathComponent("DT3 Agent Enqueue.scpt") }

    /// LaunchAgent for the engine host (ADR-0005): the signed host is the program, so the Automation permission
    /// carries its name. Arguments are a list, never a shell string.
    func enginePlistContent() -> [String: Any] {
        let log = logs.appendingPathComponent("engine.log").path
        return ["Label": InstallPaths.engineLabel,
                "ProgramArguments": [engineHost.path, "--python", python.path, "--engine-dir", engineDir.path,
                                     "--mode", "osakit", "--"],
                "RunAtLoad": true, "KeepAlive": true, "StandardOutPath": log, "StandardErrorPath": log]
    }

    /// LaunchAgent for llama-server: this Mac only, no web UI, 8192 context (SPEC §4.9), thinking off.
    func llamaPlistContent(threads: Int) -> [String: Any] {
        let log = logs.appendingPathComponent("llama.log").path
        return ["Label": InstallPaths.llamaLabel,
                "ProgramArguments": [llamaServer.path, "-m", model.path, "-c", "8192", "-t", String(max(1, threads)),
                                     "-np", "1", "--host", "127.0.0.1", "--port", "8080", "--no-webui",
                                     "--reasoning-budget", "0"],
                "RunAtLoad": true, "KeepAlive": true, "StandardOutPath": log, "StandardErrorPath": log]
    }
}

/// Settings only the installer may write (the vision helper is locked over rpc): set the helper of this build,
/// and the local AI address if none is set yet. Everything else in config.json stays as it is.
func patchConfig(_ cfg: [String: Any], visionHelper: String, aiURL: String?) -> [String: Any] {
    var c = cfg
    var vision = c["vision"] as? [String: Any] ?? [:]
    vision["helper"] = visionHelper
    c["vision"] = vision
    if let url = aiURL {
        var ai = c["ai"] as? [String: Any] ?? [:]
        if ai["url"] == nil || ai["url"] is NSNull { ai["url"] = url }
        c["ai"] = ai
    }
    return c
}

/// Lowercase hex, as SHA-256 sums are written.
func hex(_ bytes: [UInt8]) -> String {
    bytes.map { String(format: "%02x", $0) }.joined()
}

/// One line of the "what will be installed" list.
struct InstallItem: Equatable {
    enum Kind: Equatable { case engine, llama, script, model, data }
    let kind: Kind
    let path: String
    let present: Bool
}

/// What install would create and what uninstall would remove, with what is there now.
func installItems(_ p: InstallPaths, exists: (String) -> Bool) -> [InstallItem] {
    [InstallItem(kind: .engine, path: p.enginePlist.path, present: exists(p.enginePlist.path)),
     InstallItem(kind: .llama, path: p.llamaPlist.path, present: exists(p.llamaPlist.path)),
     InstallItem(kind: .script, path: p.script.path, present: exists(p.script.path)),
     InstallItem(kind: .model, path: p.model.path, present: exists(p.model.path)),
     InstallItem(kind: .data, path: p.data.path, present: exists(p.data.path))]
}
