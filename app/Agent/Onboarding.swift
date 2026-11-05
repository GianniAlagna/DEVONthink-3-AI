// Onboarding wizard (brief §6.2, U-2). One decision per screen; every step can be changed later in Settings.
// Talks only to the engine socket. Settings are saved step by step with config_set (validated by the engine).
import AppKit
import SwiftUI

final class SetupModel: ObservableObject {
    let t: L10n
    let facts = SystemFacts.current
    let work: DispatchQueue
    var onFinish: () -> Void = {}

    @Published var step = SetupStep.welcome
    @Published var engineOK = false
    @Published var dt3Version: String?
    @Published var databases: [String] = []
    @Published var checking = false
    @Published var aiURL = defaultAIURL
    @Published var aiTest: Bool?          // nil: not tested yet
    @Published var name = ""
    @Published var template = defaultTemplate
    @Published var preview: String?
    @Published var templateOK = true
    @Published var keepTestMode = true
    @Published var error: String?

    init(t: L10n, work: DispatchQueue) {
        self.t = t
        self.work = work
    }

    func start() {
        load()
        check()
    }

    /// Current settings from the engine, so a second run of the wizard starts from what is saved.
    func load() {
        rpc("config_get") { result in
            guard let cfg = result as? [String: Any] else { return }
            if let url = (cfg["ai"] as? [String: Any])?["url"] as? String { self.aiURL = url }
            if let n = (cfg["identity"] as? [String: Any])?["name"] as? String { self.name = n }
            if let tpl = (cfg["naming"] as? [String: Any])?["template"] as? String { self.template = tpl }
            self.keepTestMode = cfg["dry_run"] as? Bool ?? true
            self.updatePreview()
        }
    }

    func check() {
        checking = true
        work.async {
            let status = try? RPC.call("status", timeout: 90) as? [String: Any]
            let info = try? RPC.call("dt3_info", timeout: 30) as? [String: Any]
            DispatchQueue.main.async {
                self.checking = false
                self.engineOK = status != nil
                self.dt3Version = info?["version"] as? String
                self.databases = info?["databases"] as? [String] ?? []
            }
        }
    }

    func testAI() {
        aiTest = nil
        guard AIHost(aiURL) != .invalid else { return }
        save(["ai": ["url": aiURL.trimmingCharacters(in: .whitespaces)]]) {
            self.rpc("status") { result in
                self.aiTest = (result as? [String: Any])?["ai_ok"] as? Bool ?? false
            }
        }
    }

    func updatePreview() {
        let tpl = template
        rpc("naming_preview", ["template": tpl], quiet: true) { result in
            guard tpl == self.template else { return }  // an older answer
            self.preview = (result as? [String: Any])?["name"] as? String
            self.templateOK = self.preview != nil
        }
    }

    var canContinue: Bool {
        switch step {
        case .ai: return AIHost(aiURL) != .invalid
        case .identity: return cleanName(name) != nil
        case .naming: return templateOK
        default: return true
        }
    }

    /// Saves what this step changed, then moves on.
    func forward() {
        let go = { if let n = self.step.next { self.step = n } else { self.finish() } }
        switch step {
        case .ai: save(["ai": ["url": aiURL.trimmingCharacters(in: .whitespaces)]], then: go)
        case .identity:
            let n = cleanName(name) ?? ""
            let value: Any = n.isEmpty ? NSNull() as Any : n as Any
            save(["identity": ["name": value]], then: go)
        case .naming: save(["naming": ["template": template]], then: go)
        case .finish: rpc("live", ["on": !keepTestMode]) { _ in go() }
        default: go()
        }
    }

    func back() { if let p = step.previous { step = p } }

    func finish() {
        UserDefaults.standard.set(true, forKey: "setupDone")
        onFinish()
    }

    func save(_ changes: [String: Any], then done: @escaping () -> Void) {
        rpc("config_set", ["changes": changes]) { _ in done() }
    }

    /// Engine call off the main thread; the answer comes back on the main thread. Errors show in the window.
    func rpc(_ method: String, _ params: [String: Any] = [:], quiet: Bool = false,
             _ done: @escaping (Any?) -> Void) {
        work.async {
            do {
                let result = try RPC.call(method, params)
                DispatchQueue.main.async { self.error = nil; done(result) }
            } catch {
                let code = (error as? RPCError)?.code ?? "engine_error"
                DispatchQueue.main.async {
                    if quiet { done(nil) } else { self.error = self.t[.saveFailed] + ": " + errorText(code, self.t) }
                }
            }
        }
    }
}

struct CheckRow: View {
    let ok: Bool
    let text: String
    var body: some View {
        HStack(alignment: .top) {
            Image(systemName: ok ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                .foregroundColor(ok ? .green : .orange)
                .accessibilityHidden(true)
            Text(text).fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityElement(children: .combine)
    }
}

struct SetupView: View {
    @ObservedObject var m: SetupModel
    var t: L10n { m.t }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("\(m.step.rawValue + 1) / \(SetupStep.allCases.count)")
                .font(.caption).foregroundColor(.secondary)
            content
            Spacer(minLength: 0)
            if let e = m.error { Text(e).foregroundColor(.red).fixedSize(horizontal: false, vertical: true) }
            HStack {
                if m.step.previous != nil { Button(t[.back]) { m.back() } }
                Spacer()
                Button(m.step == .finish ? t[.done] : t[.next]) { m.forward() }
                    .keyboardShortcut(.defaultAction)
                    .disabled(!m.canContinue)
            }
        }
        .padding(24)
        .frame(width: 560, height: 420)
    }

    @ViewBuilder var content: some View {
        switch m.step {
        case .welcome:
            Text(t[.welcomeTitle]).font(.title)
            Text(t[.welcomeText]).fixedSize(horizontal: false, vertical: true)
        case .system:
            Text(t[.systemTitle]).font(.title)
            let f = m.facts
            CheckRow(ok: f.macOSSupported, text: t.format(.sysMacOS, "\(f.macOS.0).\(f.macOS.1)"))
            CheckRow(ok: true, text: t.format(.sysChip, f.appleSilicon ? "Apple Silicon" : "Intel"))
            CheckRow(ok: f.ramEnough, text: t.format(.sysRAM, f.ramGB) + (f.ramEnough ? "" : " " + t[.sysRAMLow]))
            CheckRow(ok: m.engineOK, text: m.engineOK ? t[.sysEngine] : t[.errEngine])
            if let v = m.dt3Version {
                CheckRow(ok: true, text: t.format(.sysDT3, v))
            } else {
                CheckRow(ok: false, text: t[.sysDT3Missing])
            }
            Text(t[.sysAutomation]).font(.callout).foregroundColor(.secondary).fixedSize(horizontal: false, vertical: true)
            Button(t[.checkAgain]) { m.check() }.disabled(m.checking)
        case .ai:
            Text(t[.aiTitle]).font(.title)
            Text(t[.aiText]).fixedSize(horizontal: false, vertical: true)
            HStack {
                TextField(t[.aiURL], text: $m.aiURL)
                    .accessibilityLabel(t[.aiURL])
                    .onChange(of: m.aiURL) { _ in m.aiTest = nil }
                Button(t[.test]) { m.testAI() }.disabled(AIHost(m.aiURL) == .invalid)
            }
            switch AIHost(m.aiURL) {
            case .invalid: CheckRow(ok: false, text: t[.aiInvalid])
            case .thisMac: CheckRow(ok: true, text: t[.aiThisMac])
            case .localNetwork: CheckRow(ok: false, text: t[.aiLAN])
            case .internet: CheckRow(ok: false, text: t[.aiInternet])
            }
            if let ok = m.aiTest { CheckRow(ok: ok, text: ok ? t[.aiOK] : t[.aiFail]) }
            Text(t[.aiModel]).font(.callout).foregroundColor(.secondary).fixedSize(horizontal: false, vertical: true)
        case .identity:
            Text(t[.identityTitle]).font(.title)
            Text(t[.identityText]).fixedSize(horizontal: false, vertical: true)
            TextField(t[.identityName], text: $m.name).accessibilityLabel(t[.identityName])
        case .naming:
            Text(t[.namingTitle]).font(.title)
            Text(t[.namingText]).fixedSize(horizontal: false, vertical: true)
            HStack {
                TextField(t[.namingTemplate], text: $m.template)
                    .accessibilityLabel(t[.namingTemplate])
                    .onChange(of: m.template) { _ in m.updatePreview() }
                Button(t[.namingReset]) { m.template = defaultTemplate }
            }
            if m.templateOK, let p = m.preview {
                Text(t.format(.namingPreview, p)).font(.system(.body, design: .monospaced))
                    .fixedSize(horizontal: false, vertical: true)
            } else if !m.templateOK {
                CheckRow(ok: false, text: t[.namingInvalid])
            }
        case .smartRule:
            Text(t[.ruleTitle]).font(.title)
            Text(t[.ruleText]).fixedSize(horizontal: false, vertical: true)
            if !m.databases.isEmpty { Text(t.format(.ruleDatabases, m.databases.joined(separator: ", "))) }
        case .finish:
            Text(t[.finishTitle]).font(.title)
            Text(t[.finishText]).fixedSize(horizontal: false, vertical: true)
            Toggle(t[.keepTestMode], isOn: $m.keepTestMode)
        }
    }
}

/// The wizard window. Closing it is fine: it opens again at the next start until "Done".
final class SetupWindow {
    private var window: NSWindow?

    func show(t: L10n, work: DispatchQueue, onFinish: @escaping () -> Void) {
        if let w = window { w.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true); return }
        let model = SetupModel(t: t, work: work)
        let w = NSWindow(contentViewController: NSHostingController(rootView: SetupView(m: model)))
        w.title = t[.setupTitle]
        w.styleMask = [.titled, .closable]
        w.isReleasedWhenClosed = false
        model.onFinish = { [weak self] in
            self?.window?.close()
            self?.window = nil
            onFinish()
        }
        window = w
        model.start()
        w.center()
        w.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}
