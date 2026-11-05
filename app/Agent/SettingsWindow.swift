// Settings window (brief §6.3, U-3). Tabs for what the engine supports today; every save goes through
// config_set, so the engine checks it. Schedules and power settings come with their features (Phase 6/7).
import AppKit
import SwiftUI

final class SettingsModel: ObservableObject {
    let t: L10n
    let work: DispatchQueue
    @Published var v = SettingsValues()
    @Published var loaded = SettingsValues()
    @Published var message: String?
    @Published var messageIsError = false
    @Published var preview: String?
    @Published var aiTest: Bool?
    var raw: [String: Any] = [:]

    init(t: L10n, work: DispatchQueue) {
        self.t = t
        self.work = work
    }

    var dirty: Bool { v != loaded }

    func load() {
        rpc("config_get", [:]) { result in
            guard let c = result as? [String: Any] else { return }
            self.raw = c
            self.v = SettingsValues(config: c)
            self.loaded = self.v
            self.updatePreview()
        }
    }

    func save() {
        let problems = v.problems
        guard problems.isEmpty else {
            show(t.format(.setFix, problems.map { t[$0] }.joined(separator: "; ")), error: true)
            return
        }
        rpc("config_set", ["changes": v.changes]) { result in
            if let c = result as? [String: Any] {
                self.raw = c
                self.v = SettingsValues(config: c)
                self.loaded = self.v
            }
            self.show(self.t[.saved], error: false)
        }
    }

    func revert() {
        v = loaded
        message = nil
    }

    func updatePreview() {
        let tpl = v.template
        rpc("naming_preview", ["template": tpl], quiet: true) { result in
            guard tpl == self.v.template else { return }
            self.preview = (result as? [String: Any])?["name"] as? String
        }
    }

    func testAI() {
        aiTest = nil
        let url = v.aiURL.trimmingCharacters(in: .whitespaces)
        guard AIHost(url) != .invalid else { return }
        rpc("config_set", ["changes": ["ai": ["url": url]]]) { _ in
            self.loaded.aiURL = url
            self.rpc("status", [:]) { result in self.aiTest = (result as? [String: Any])?["ai_ok"] as? Bool ?? false }
        }
    }

    func exportSettings() {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "DT3-Agent-settings.json"
        NSApp.activate(ignoringOtherApps: true)
        guard panel.runModal() == .OK, let url = panel.url,
              let data = try? JSONSerialization.data(withJSONObject: raw, options: [.prettyPrinted, .sortedKeys])
        else { return }
        do { try data.write(to: url, options: .atomic) } catch { show(t[.saveFailed], error: true) }
    }

    func importSettings() {
        let panel = NSOpenPanel()
        panel.allowedFileTypes = ["json"]
        NSApp.activate(ignoringOtherApps: true)
        guard panel.runModal() == .OK, let url = panel.url, let data = try? Data(contentsOf: url),
              let json = try? JSONSerialization.jsonObject(with: data), let changes = importChanges(json) else { return }
        rpc("config_set", ["changes": changes]) { _ in
            self.load()
            self.show(self.t[.setImported], error: false)
        }
    }

    func show(_ text: String, error: Bool) {
        message = text
        messageIsError = error
    }

    func rpc(_ method: String, _ params: [String: Any], quiet: Bool = false, _ done: @escaping (Any?) -> Void) {
        work.async {
            do {
                let result = try RPC.call(method, params)
                DispatchQueue.main.async { done(result) }
            } catch {
                let code = (error as? RPCError)?.code ?? "engine_error"
                DispatchQueue.main.async {
                    if quiet { done(nil) } else { self.show(self.t[.saveFailed] + ": " + errorText(code, self.t), error: true) }
                }
            }
        }
    }
}

/// A labelled multi-line text field (VoiceOver reads the label).
struct LinesField: View {
    let label: String
    @Binding var text: String
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).fixedSize(horizontal: false, vertical: true)
            TextEditor(text: $text)
                .font(.system(.body, design: .monospaced))
                .frame(minHeight: 120)
                .border(Color.secondary.opacity(0.4))
                .accessibilityLabel(label)
        }
    }
}

struct LabeledField: View {
    let label: String
    @Binding var text: String
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
            TextField(label, text: $text).accessibilityLabel(label)
        }
    }
}

struct SettingsView: View {
    @ObservedObject var m: SettingsModel
    var t: L10n { m.t }

    var body: some View {
        VStack(spacing: 12) {
            TabView {
                general.tabItem { Text(t[.tabGeneral]) }
                ai.tabItem { Text(t[.tabAI]) }
                naming.tabItem { Text(t[.tabNaming]) }
                LinesField(label: t[.setVocabulary], text: $m.v.vocabulary).padding()
                    .tabItem { Text(t[.tabTags]) }
                filing.tabItem { Text(t[.tabFiling]) }
                swiss.tabItem { Text(t[.tabSwiss]) }
                duplicates.tabItem { Text(t[.tabDuplicates]) }
                privacy.tabItem { Text(t[.tabPrivacy]) }
                advanced.tabItem { Text(t[.tabAdvanced]) }
            }
            HStack {
                if let msg = m.message {
                    if m.messageIsError {
                        ErrorLine(text: msg).id(msg)
                    } else {
                        Text(msg).foregroundColor(.secondary).fixedSize(horizontal: false, vertical: true)
                            .onAppear { announce(msg) }.id(msg)
                    }
                }
                Spacer()
                Button(t[.revert]) { m.revert() }.disabled(!m.dirty)
                Button(t[.save]) { m.save() }
                    .keyboardShortcut("s", modifiers: .command)
                    .disabled(!m.dirty)
            }
        }
        .padding(16)
        .frame(width: 640, height: 480)
    }

    var general: some View {
        VStack(alignment: .leading, spacing: 12) {
            Toggle(t[.setTestMode], isOn: $m.v.dryRun)
            LabeledField(label: t[.identityName], text: $m.v.name)
            HStack {
                Button(t[.setExport]) { m.exportSettings() }
                Button(t[.setImport]) { m.importSettings() }
            }
            Spacer()
        }.padding()
    }

    var ai: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(t[.aiText]).fixedSize(horizontal: false, vertical: true)
            HStack {
                TextField(t[.aiURL], text: $m.v.aiURL)
                    .accessibilityLabel(t[.aiURL])
                    .onChange(of: m.v.aiURL) { _ in m.aiTest = nil }
                Button(t[.test]) { m.testAI() }.disabled(AIHost(m.v.aiURL) == .invalid)
            }
            switch AIHost(m.v.aiURL) {
            case .invalid: CheckRow(ok: false, text: t[.aiInvalid])
            case .thisMac: CheckRow(ok: true, text: t[.aiThisMac])
            case .localNetwork: CheckRow(ok: false, text: t[.aiLAN])
            case .internet: CheckRow(ok: false, text: t[.aiInternet])
            }
            if let ok = m.aiTest { CheckRow(ok: ok, text: ok ? t[.aiOK] : t[.aiFail]) }
            Spacer()
        }.padding()
    }

    var naming: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(t[.namingText]).fixedSize(horizontal: false, vertical: true)
            HStack {
                TextField(t[.namingTemplate], text: $m.v.template)
                    .accessibilityLabel(t[.namingTemplate])
                    .onChange(of: m.v.template) { _ in m.updatePreview() }
                Button(t[.namingReset]) { m.v.template = defaultTemplate }
            }
            if let p = m.preview {
                Text(t.format(.namingPreview, p)).font(.system(.body, design: .monospaced))
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                CheckRow(ok: false, text: t[.namingInvalid])
            }
            Spacer()
        }.padding()
    }

    var filing: some View {
        VStack(alignment: .leading, spacing: 12) {
            Toggle(t[.setFilingEnabled], isOn: $m.v.filingEnabled)
            LinesField(label: t[.setFilingGroups], text: $m.v.filingGroups)
            LabeledField(label: t[.setReviewGroup], text: $m.v.reviewGroup)
            Text(t[.setGroupNote]).font(.callout).foregroundColor(.secondary)
        }.padding()
    }

    var swiss: some View {
        VStack(alignment: .leading, spacing: 12) {
            LinesField(label: t[.setUrgentWords], text: $m.v.urgentWords)
            LabeledField(label: t[.setUrgentGroup], text: $m.v.urgentGroup)
            Toggle(t[.setRetention], isOn: $m.v.retentionEnabled)
        }.padding()
    }

    var duplicates: some View {
        VStack(alignment: .leading, spacing: 12) {
            LabeledField(label: t[.setDuplicatesGroup], text: $m.v.duplicatesGroup)
            Text(t.format(.setNear, Int((m.v.nearThreshold * 100).rounded())))
            Slider(value: $m.v.nearThreshold, in: 0.5...1.0, step: 0.05)
                .accessibilityLabel(t.format(.setNear, Int((m.v.nearThreshold * 100).rounded())))
            LinesField(label: t[.setCases], text: $m.v.cases)
        }.padding()
    }

    var privacy: some View {
        VStack(alignment: .leading, spacing: 12) {
            Toggle(t[.setLogContent], isOn: $m.v.logContent)
            Text(t[.setLogWarning]).font(.callout).foregroundColor(.secondary).fixedSize(horizontal: false, vertical: true)
            Spacer()
        }.padding()
    }

    var advanced: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(t.format(.setApply, Int((m.v.applyThreshold * 100).rounded())))
            Slider(value: $m.v.applyThreshold, in: 0.5...1.0, step: 0.05)
                .accessibilityLabel(t.format(.setApply, Int((m.v.applyThreshold * 100).rounded())))
            Text(t[.setApplyNote]).font(.callout).foregroundColor(.secondary)
            Spacer()
        }.padding()
    }
}

final class SettingsWindow {
    private var window: NSWindow?

    func show(t: L10n, work: DispatchQueue) {
        if let w = window { w.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true); return }
        let model = SettingsModel(t: t, work: work)
        let w = NSWindow(contentViewController: NSHostingController(rootView: SettingsView(m: model)))
        w.title = t[.setTitle]
        w.styleMask = [.titled, .closable]
        w.isReleasedWhenClosed = false
        window = w
        model.load()
        w.center()
        w.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}
