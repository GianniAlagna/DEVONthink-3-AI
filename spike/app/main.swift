// S8 - menu-bar smoke test: NSStatusItem + NSPopover hosting SwiftUI at macOS 11 API level.
// No MenuBarExtra / SMAppService (macOS 13). One button sends an AppleEvent to DT3 (TCC test).
import AppKit
import SwiftUI

final class Model: ObservableObject {
    @Published var status = "Idle"

    func askDT3() {
        // Constant script text, nothing interpolated. Run 4: "version" is answered locally by AppleScript
        // without an Apple event (no Automation entry appeared), so ask for something only DT3 can answer.
        let source = "tell application id \"com.devon-technologies.think3\" to return (count of databases) as text"
        var error: NSDictionary?
        if let result = NSAppleScript(source: source)?.executeAndReturnError(&error), let v = result.stringValue {
            status = "DT3 open databases: \(v)"
        } else {
            let code = error?[NSAppleScript.errorNumber] ?? "?"
            let text = error?[NSAppleScript.errorMessage] ?? ""
            status = "Error \(code): \(text)"
        }
        NSLog("SpikeMenu askDT3: %@", status)
    }
}

struct PopoverView: View {
    @ObservedObject var model: Model

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("DT3 Agent Spike").font(.headline)
            Text(model.status)
                .font(.callout)
                .accessibilityLabel(Text("Status: \(model.status)"))
            Button("Ask DEVONthink 3 for its databases") { model.askDT3() }
                .keyboardShortcut("r")
            Button("Quit") { NSApp.terminate(nil) }
                .keyboardShortcut("q")
        }
        .padding(16)
        .frame(width: 300)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    let model = Model()
    let popover = NSPopover()
    var item: NSStatusItem!

    func applicationDidFinishLaunching(_ notification: Notification) {
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = item.button {
            button.image = NSImage(systemSymbolName: "doc.text.magnifyingglass", accessibilityDescription: "DT3 Agent Spike")
            if button.image == nil { button.title = "DT3" }
            button.target = self
            button.action = #selector(toggle)
        }
        popover.behavior = .transient
        popover.contentViewController = NSHostingController(rootView: PopoverView(model: model))
    }

    @objc func toggle() {
        if popover.isShown {
            popover.performClose(nil)
        } else if let button = item.button {
            popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
            NSApp.activate(ignoringOtherApps: true)
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()
