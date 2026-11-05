// Installer window (SPEC §4.19, U-5): shows what will be installed and asks first; uninstall removes all of it.
// launchctl gets its arguments as a list (no shell). Nothing in DT3 databases is ever touched.
import AppKit
import CryptoKit
import SwiftUI

final class InstallerModel: ObservableObject {
    let t: L10n
    let paths: InstallPaths
    var onChange: () -> Void = {}
    @Published var items: [InstallItem] = []
    @Published var downloadModel = true
    @Published var removeModel = true
    @Published var removeData = false
    @Published var busy = false
    @Published var progress: Double?
    @Published var log: [String] = []
    private var observation: NSKeyValueObservation?
    private let fm = FileManager.default

    init(t: L10n) {
        self.t = t
        paths = InstallPaths(home: fm.homeDirectoryForCurrentUser, bundle: Bundle.main.bundleURL)
        refresh()
    }

    var llamaBundled: Bool { fm.isExecutableFile(atPath: paths.llamaServer.path) }
    var pythonBundled: Bool { fm.isExecutableFile(atPath: paths.python.path) }
    var dt3Running: Bool {
        !NSRunningApplication.runningApplications(withBundleIdentifier: "com.devon-technologies.think3").isEmpty
    }

    func refresh() {
        items = installItems(paths) { fm.fileExists(atPath: $0) }
    }

    func say(_ line: String) { DispatchQueue.main.async { self.log.append(line); announce(line) } }

    // MARK: install

    func install() {
        guard pythonBundled else { log = [t[.instNoPython]]; return }
        busy = true
        log = []
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                try self.makeFolders()
                self.stopAgents()
                self.installScript()
                if self.downloadModel && self.llamaBundled && !self.fm.fileExists(atPath: self.paths.model.path) {
                    try self.download()
                }
                let llama = self.llamaBundled && self.fm.fileExists(atPath: self.paths.model.path)
                try self.writeConfig(aiURL: llama ? InstallPaths.aiURL : nil)
                if llama {
                    try self.startAgent(self.paths.llamaPlist,
                                        self.paths.llamaPlistContent(threads: ProcessInfo.processInfo.activeProcessorCount))
                    self.say(self.t[.instLlamaStarted])
                } else {
                    self.say(self.t[.instNoLlama])
                }
                try self.startAgent(self.paths.enginePlist, self.paths.enginePlistContent())
                self.say(self.t[.instDone])
            } catch {
                self.say(self.t[.instFailed] + ": " + error.localizedDescription)
            }
            DispatchQueue.main.async {
                self.busy = false
                self.progress = nil
                self.refresh()
                self.onChange()
            }
        }
    }

    private func makeFolders() throws {
        for dir in [paths.data, paths.models, paths.logs, paths.launchAgents] {
            try fm.createDirectory(at: dir, withIntermediateDirectories: true)
        }
        try fm.setAttributes([.posixPermissions: 0o700], ofItemAtPath: paths.data.path)
    }

    /// Stops our agents, including the developer ones (tools/dev-agent.sh), so only one engine uses the data folder.
    private func stopAgents() {
        for label in [InstallPaths.engineLabel, InstallPaths.llamaLabel,
                      InstallPaths.engineLabel + ".dev", "codes.modular.dt3agent.llama.dev"] {
            launchctl(["bootout", "gui/\(getuid())/\(label)"])
        }
    }

    private func installScript() {
        guard fm.fileExists(atPath: paths.bundledScript.path) else { return }
        if dt3Running {
            say(t[.instQuitDT3])  // DT3 reads external scripts only at start (Phase 2 T1)
            return
        }
        do {
            try fm.createDirectory(at: paths.smartRules, withIntermediateDirectories: true)
            if fm.fileExists(atPath: paths.script.path) { try fm.removeItem(at: paths.script) }
            try fm.copyItem(at: paths.bundledScript, to: paths.script)
            say(t[.instScript])
        } catch {
            say(t[.instFailed] + ": " + error.localizedDescription)
        }
    }

    private func writeConfig(aiURL: String?) throws {
        var cfg: [String: Any] = [:]
        if let data = try? Data(contentsOf: paths.config),
           let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] { cfg = obj }
        let patched = patchConfig(cfg, visionHelper: paths.vision.path, aiURL: aiURL)
        let data = try JSONSerialization.data(withJSONObject: patched, options: [.prettyPrinted, .sortedKeys])
        try data.write(to: paths.config, options: .atomic)
    }

    private func startAgent(_ plist: URL, _ content: [String: Any]) throws {
        let data = try PropertyListSerialization.data(fromPropertyList: content, format: .xml, options: 0)
        try data.write(to: plist, options: .atomic)
        launchctl(["bootstrap", "gui/\(getuid())", plist.path])
    }

    @discardableResult
    private func launchctl(_ args: [String]) -> Int32 {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        p.arguments = args
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        do { try p.run() } catch { return -1 }
        p.waitUntilExit()
        return p.terminationStatus
    }

    // MARK: model download (consent given by the checkbox; pinned URL and SHA-256, ADR-0003)

    private func download() throws {
        say(t[.instDownloading])
        let done = DispatchSemaphore(value: 0)
        var tempURL: URL?
        var failure: Error?
        let task = URLSession.shared.downloadTask(with: DefaultModel.url) { url, response, error in
            if let url = url, (response as? HTTPURLResponse)?.statusCode == 200 {
                let keep = self.paths.models.appendingPathComponent(DefaultModel.name + ".part")
                try? self.fm.removeItem(at: keep)
                do { try self.fm.moveItem(at: url, to: keep); tempURL = keep } catch { failure = error }
            } else {
                failure = error ?? NSError(domain: "download", code: (response as? HTTPURLResponse)?.statusCode ?? 0)
            }
            done.signal()
        }
        observation = task.progress.observe(\.fractionCompleted) { p, _ in
            DispatchQueue.main.async { self.progress = p.fractionCompleted }
        }
        task.resume()
        done.wait()
        observation = nil
        if let e = failure { throw e }
        guard let file = tempURL else { throw NSError(domain: "download", code: 0) }
        guard try sha256(of: file) == DefaultModel.sha256 else {
            try? fm.removeItem(at: file)
            throw NSError(domain: "download", code: 1, userInfo: [NSLocalizedDescriptionKey: t[.instChecksum]])
        }
        try fm.moveItem(at: file, to: paths.model)
        say(t[.instModel])
    }

    private func sha256(of file: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: file)
        defer { try? handle.close() }
        var hasher = SHA256()
        while true {
            let chunk = handle.readData(ofLength: 4 * 1024 * 1024)
            if chunk.isEmpty { break }
            hasher.update(data: chunk)
        }
        return hex(Array(hasher.finalize()))
    }

    // MARK: uninstall

    func uninstall() {
        busy = true
        log = []
        DispatchQueue.global(qos: .userInitiated).async {
            self.stopAgents()
            var targets = [self.paths.enginePlist, self.paths.llamaPlist, self.paths.script]
            if self.removeModel { targets.append(self.paths.model) }
            if self.removeData { targets.append(self.paths.data) }
            for url in targets where self.fm.fileExists(atPath: url.path) {
                do { try self.fm.removeItem(at: url); self.say(self.t[.instRemoved] + " " + url.path) } catch {
                    self.say(self.t[.instFailed] + ": " + url.path)
                }
            }
            UserDefaults.standard.removeObject(forKey: "setupDone")
            self.say(self.t[.instUninstalled])
            DispatchQueue.main.async {
                self.busy = false
                self.refresh()
                self.onChange()
            }
        }
    }
}

struct InstallerView: View {
    @ObservedObject var m: InstallerModel
    var t: L10n { m.t }

    func label(_ kind: InstallItem.Kind) -> String {
        switch kind {
        case .engine: return t[.instItemEngine]
        case .llama: return t[.instItemLlama]
        case .script: return t[.instItemScript]
        case .model: return t[.instItemModel]
        case .data: return t[.instItemData]
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(t[.instTitle]).font(.title)
            Text(t[.instText]).fixedSize(horizontal: false, vertical: true)
            ForEach(m.items, id: \.path) { item in
                VStack(alignment: .leading, spacing: 2) {
                    CheckRow(ok: item.present, text: label(item.kind))
                    Text(item.path).font(.caption).foregroundColor(.secondary).lineLimit(1).truncationMode(.middle)
                }
            }
            if m.llamaBundled {
                Toggle(t[.instDownloadModel], isOn: $m.downloadModel)
            }
            if let p = m.progress { ProgressView(value: p).accessibilityLabel(t[.instDownloading]) }
            ForEach(Array(m.log.enumerated()), id: \.offset) { _, line in
                Text(line).font(.callout).fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
            Divider()
            Toggle(t[.instRemoveModel], isOn: $m.removeModel)
            Toggle(t[.instRemoveData], isOn: $m.removeData)
            HStack {
                Button(t[.instUninstall]) { m.uninstall() }.disabled(m.busy)
                Spacer()
                Button(t[.instInstall]) { m.install() }.keyboardShortcut(.defaultAction).disabled(m.busy)
            }
        }
        .padding(20)
        .frame(width: 600, height: 560)
    }
}

final class InstallerWindow {
    private var window: NSWindow?

    func show(t: L10n, onChange: @escaping () -> Void) {
        if let w = window { w.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true); return }
        let m = InstallerModel(t: t)
        m.onChange = onChange
        let w = NSWindow(contentViewController: NSHostingController(rootView: InstallerView(m: m)))
        w.title = t[.instTitle]
        w.styleMask = [.titled, .closable]
        w.isReleasedWhenClosed = false
        window = w
        w.center()
        w.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}
