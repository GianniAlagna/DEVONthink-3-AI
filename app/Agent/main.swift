// DT3 Agent — menu-bar app (brief §6.1, SPEC §4.18, U-1). Talks only to the engine socket; never to DT3 itself.
import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    let t = L10n()
    let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    let menu = NSMenu()
    let work = DispatchQueue(label: "codes.modular.dt3agent.rpc")  // one request at a time, like the engine
    var status: EngineStatus?
    var polling = false
    var timer: Timer?
    let setup = SetupWindow()
    let settings = SettingsWindow()

    func applicationDidFinishLaunching(_ notification: Notification) {
        menu.delegate = self
        menu.autoenablesItems = false
        statusItem.menu = menu
        render()
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 15, repeats: true) { [weak self] _ in self?.refresh() }
        if !UserDefaults.standard.bool(forKey: "setupDone") { openSetup() }  // first start (brief §6.2)
    }

    // Refresh when the user opens the menu, so the numbers are current.
    func menuWillOpen(_ menu: NSMenu) { refresh() }

    func refresh() {
        guard !polling else { return }
        polling = true
        work.async {
            let result = try? RPC.call("status", timeout: 90) as? [String: Any]
            DispatchQueue.main.async {
                self.polling = false
                self.status = result.map { EngineStatus(json: $0) }
                self.render()
            }
        }
    }

    func render() {
        let health = Health(status)
        if let button = statusItem.button {
            let image = NSImage(systemSymbolName: health.symbol, accessibilityDescription: t[health.textKey])
            image?.isTemplate = true
            button.image = image
            button.contentTintColor = health.needsAttention ? .systemRed : nil
            button.toolTip = t[.appName] + " — " + t[health.textKey]
            button.setAccessibilityLabel(t[.appName] + ", " + t[health.textKey])
        }
        menu.removeAllItems()
        menu.addItem(info(t[health.textKey]))
        menu.addItem(.separator())
        let online = status != nil
        menu.addItem(item(t[.processSelected], #selector(processSelected), enabled: online))
        menu.addItem(info(t.format(.queue, status?.pending ?? 0)))
        // The review window follows in U-4; the count is shown already.
        menu.addItem(info(t.format(.review, status?.reviewItems ?? 0)))
        if let urgent = status?.urgentOpen, urgent > 0 { menu.addItem(info(t.format(.urgent, urgent))) }
        menu.addItem(.separator())
        let paused = status?.paused ?? false
        menu.addItem(item(paused ? t[.resume] : t[.pause], #selector(togglePause), enabled: online))
        menu.addItem(item(t[.undo], #selector(undoLastBatch), enabled: online))
        menu.addItem(.separator())
        menu.addItem(item(t[.setupMenu], #selector(openSetup), enabled: true))
        menu.addItem(item(t[.settings], #selector(openSettings), enabled: true, key: ","))
        menu.addItem(item(t[.help], #selector(openHelp), enabled: true))
        menu.addItem(item(t[.quit], #selector(NSApplication.terminate(_:)), enabled: true, key: "q"))
    }

    func info(_ title: String) -> NSMenuItem {
        let i = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        i.isEnabled = false
        return i
    }

    func item(_ title: String, _ action: Selector?, enabled: Bool, key: String = "") -> NSMenuItem {
        let i = NSMenuItem(title: title, action: action, keyEquivalent: key)
        i.target = action == #selector(NSApplication.terminate(_:)) ? NSApp : self
        i.isEnabled = enabled
        return i
    }

    // MARK: actions

    @objc func processSelected() {
        call("process_selected") { result in
            let n = (result as? [String: Any])?["queued"] as? Int ?? 0
            self.notice(self.t.format(.queuedN, n))
        }
    }

    @objc func togglePause() {
        call((status?.paused ?? false) ? "resume" : "pause") { _ in }
    }

    @objc func undoLastBatch() {
        let alert = NSAlert()
        alert.messageText = t[.undoConfirmTitle]
        alert.informativeText = t[.undoConfirmText]
        alert.addButton(withTitle: t[.undoButton])
        alert.addButton(withTitle: t[.cancel])
        NSApp.activate(ignoringOtherApps: true)
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        call("undo") { result in
            let r = result as? [String: Any]
            let restored = r?["restored"] as? Int ?? 0
            let conflicts = (r?["conflicts"] as? [Any])?.count ?? 0
            self.notice(self.t.format(.undoDone, restored, conflicts))
        }
    }

    @objc func openSetup() {
        setup.show(t: t, work: work) { [weak self] in self?.refresh() }
    }

    @objc func openSettings() {
        settings.show(t: t, work: work)
    }

    @objc func openHelp() {
        if let url = URL(string: "https://github.com/GianniAlagna/DEVONthink-3-AI/blob/main/SUPPORT.md") {
            NSWorkspace.shared.open(url)
        }
    }

    /// Runs an engine method off the main thread, then refreshes the status; errors become a short message.
    func call(_ method: String, _ done: @escaping (Any?) -> Void) {
        work.async {
            do {
                let result = try RPC.call(method)
                DispatchQueue.main.async { done(result); self.refresh() }
            } catch let e as RPCError {
                DispatchQueue.main.async { self.notice(errorText(e.code, self.t)); self.refresh() }
            } catch {
                DispatchQueue.main.async { self.notice(errorText("engine_error", self.t)); self.refresh() }
            }
        }
    }

    func notice(_ text: String) {
        let alert = NSAlert()
        alert.messageText = t[.appName]
        alert.informativeText = text
        alert.addButton(withTitle: t[.ok])
        NSApp.activate(ignoringOtherApps: true)
        alert.runModal()
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)  // menu bar only, no Dock icon
app.run()
