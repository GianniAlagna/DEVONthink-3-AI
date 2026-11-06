// Settings window (brief §6.3, U-3). Tabs for what the engine supports today; every save goes through
// config_set, so the engine checks it. Phase 7 adds the schedule tab (scopes, jobs, reports, power).
import AppKit
import Security
import SwiftUI

/// E-7: the remote AI key in the login Keychain. Only this app and /usr/bin/security (the engine reads the key
/// with `security find-generic-password -w`) are trusted to read it. The key is never written anywhere else.
/// UNVERIFIED on macOS 11 until the floor check: that the engine's read needs no extra Keychain prompt.
enum AIKey {
    static let service = "codes.modular.dt3agent.ai"
    static let account = "dt3agent"

    static var stored: Bool {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                kSecReturnAttributes as String: true]
        return SecItemCopyMatching(q as CFDictionary, nil) == errSecSuccess
    }

    static func save(_ key: String) -> Bool {
        remove()
        var apps: [SecTrustedApplication] = []
        for path in [nil, "/usr/bin/security"] as [String?] {
            var app: SecTrustedApplication?
            if SecTrustedApplicationCreateFromPath(path, &app) == errSecSuccess, let a = app { apps.append(a) }
        }
        var access: SecAccess?
        guard SecAccessCreate("DT3 Agent AI key" as CFString, apps as CFArray, &access) == errSecSuccess,
              let acc = access else { return false }
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service,
                                kSecAttrAccount as String: account, kSecValueData as String: Data(key.utf8),
                                kSecAttrAccess as String: acc]
        return SecItemAdd(q as CFDictionary, nil) == errSecSuccess
    }

    static func remove() {
        let q: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service]
        SecItemDelete(q as CFDictionary)
    }
}

final class SettingsModel: ObservableObject {
    let t: L10n
    let work: DispatchQueue
    @Published var v = SettingsValues()
    @Published var loaded = SettingsValues()
    @Published var message: String?
    @Published var messageIsError = false
    @Published var preview: String?
    @Published var aiTest: Bool?
    @Published var keyInput = ""
    @Published var keyStored = AIKey.stored
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

    func saveKey() {
        guard let key = cleanKey(keyInput) else { show(t[.setKeyBad], error: true); return }
        keyInput = ""  // never kept in the window
        guard AIKey.save(key) else { show(t[.saveFailed], error: true); return }
        keyStored = true
        v.useKey = true
        save()  // the engine reads the key again when its settings change
    }

    func removeKey() {
        AIKey.remove()
        keyStored = false
        v.useKey = false
        save()
    }

    func exportDiagnostics() {
        rpc("diagnostics", [:]) { result in
            guard let path = (result as? [String: Any])?["path"] as? String else { return }
            self.show(self.t[.setDiagnosticsDone], error: false)
            NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
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
                jobs.tabItem { Text(t[.tabJobs]) }  // 10 tabs: the ViewBuilder limit on the floor's Swift 5.5
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
        .frame(width: 900, height: 540)  // floor 2026-11-05: tab names were cut at 640; 10 tabs since Phase 7
    }

    var general: some View {
        VStack(alignment: .leading, spacing: 12) {
            Toggle(t[.setTestMode], isOn: $m.v.dryRun)
            LabeledField(label: t[.identityName], text: $m.v.name)
            HStack {
                Button(t[.setExport]) { m.exportSettings() }
                Button(t[.setImport]) { m.importSettings() }
                Button(t[.setDiagnostics]) { m.exportDiagnostics() }
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
            keyBox
            Spacer()
        }.padding()
    }

    var keyBox: some View {
        VStack(alignment: .leading, spacing: 8) {
            Divider()
            Text(t[.setKeyNote]).font(.callout).foregroundColor(.secondary).fixedSize(horizontal: false, vertical: true)
            HStack {
                SecureField(t[.setKey], text: $m.keyInput).accessibilityLabel(t[.setKey])
                Button(t[.setKeySave]) { m.saveKey() }.disabled(m.keyInput.isEmpty)
                Button(t[.setKeyRemove]) { m.removeKey() }.disabled(!m.keyStored)
            }
            CheckRow(ok: m.keyStored, text: m.keyStored ? t[.setKeyStored] : t[.setKeyNone])
            Toggle(t[.setUseKey], isOn: $m.v.useKey).disabled(!m.keyStored)
        }
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

    // Phase 7 (SPEC §4.21/4.22): scopes, nightly run, reports, power mode. Groups keep each stack ≤ 10 views.
    var jobs: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                LinesField(label: t[.setScopes], text: $m.v.scopes)
                Text(t[.setScopesNote]).font(.callout).foregroundColor(.secondary).fixedSize(horizontal: false, vertical: true)
                HStack {
                    Toggle(t[.setNightly], isOn: $m.v.nightlyOn)
                    TextField("02:30", text: $m.v.nightlyTime).frame(width: 70).accessibilityLabel(t[.setTime])
                }
                Divider()
                report(t[.setDigest], on: $m.v.digestOn, day: $m.v.digestDay, time: $m.v.digestTime,
                       group: $m.v.digestGroup, lang: $m.v.digestLang)
                Divider()
                report(t[.setHygiene], on: $m.v.hygieneOn, day: $m.v.hygieneDay, time: $m.v.hygieneTime,
                       group: $m.v.hygieneGroup, lang: $m.v.hygieneLang)
                hygieneExtras
                Divider()
                power
            }.padding()
        }
    }

    var hygieneExtras: some View {
        VStack(alignment: .leading, spacing: 8) {
            LabeledField(label: t[.setInbox], text: $m.v.hygieneInbox)
            Stepper(t.format(.setInboxDays, m.v.hygieneDays), value: $m.v.hygieneDays, in: 1...365)
                .accessibilityLabel(t.format(.setInboxDays, m.v.hygieneDays))
            Toggle(t[.setTagHygiene], isOn: $m.v.hygieneTags)
        }
    }

    var power: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(t[.setPower]).font(.headline)
            Toggle(t[.setPauseBattery], isOn: $m.v.pauseOnBattery)
            Toggle(t[.setPauseMemory], isOn: $m.v.pauseOnMemory)
        }
    }

    func report(_ title: String, on: Binding<Bool>, day: Binding<String>, time: Binding<String>,
                group: Binding<String>, lang: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Toggle(title, isOn: on)
            HStack {
                Picker(t[.setDay], selection: day) {
                    ForEach(jobDays, id: \.self) { d in Text(weekdayName(d, language: t.language)).tag(d) }
                }.frame(width: 220)
                TextField("07:30", text: time).frame(width: 70).accessibilityLabel(t[.setTime])
                Picker(t[.setLang], selection: lang) {
                    ForEach(reportLanguages, id: \.self) { l in Text(l.uppercased()).tag(l) }
                }.frame(width: 160)
            }
            LabeledField(label: t[.setReportGroup], text: group)
        }
    }

    var advanced: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(t.format(.setApply, Int((m.v.applyThreshold * 100).rounded())))
            Slider(value: $m.v.applyThreshold, in: 0.5...1.0, step: 0.05)
                .accessibilityLabel(t.format(.setApply, Int((m.v.applyThreshold * 100).rounded())))
            Text(t[.setApplyNote]).font(.callout).foregroundColor(.secondary)
            Divider()
            VStack(alignment: .leading, spacing: 8) {
                Toggle(t[.setEntities], isOn: $m.v.entities)
                LabeledField(label: t[.setEntityGroup], text: $m.v.entityGroup)
                Text(t[.setEntitiesNote]).font(.callout).foregroundColor(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
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
