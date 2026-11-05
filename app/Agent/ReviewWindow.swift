// Review Queue window (brief §6.4, U-4): open proposals with before/after, confidence and Accept · Edit · Reject.
// Decisions go to the engine (decide), which checks them again and writes to DT3 only on accept or edit.
import AppKit
import SwiftUI

final class ReviewModel: ObservableObject {
    let t: L10n
    let work: DispatchQueue
    var onChange: () -> Void = {}
    @Published var items: [ReviewItem] = []
    @Published var editing: Int?
    @Published var editText = ""
    @Published var message: String?
    @Published var busy = false

    init(t: L10n, work: DispatchQueue) {
        self.t = t
        self.work = work
    }

    func load() {
        rpc("review", [:]) { result in
            self.items = (result as? [[String: Any]] ?? []).compactMap { ReviewItem(json: $0) }
            if let e = self.editing, !self.items.contains(where: { $0.id == e }) { self.editing = nil }
        }
    }

    func startEdit(_ item: ReviewItem) {
        editing = item.id
        editText = item.editStart
        message = nil
    }

    func decide(_ item: ReviewItem, _ decision: String) {
        var params: [String: Any] = ["id": item.id, "decision": decision]
        if decision == "edit" {
            guard let value = item.editValue(editText) else { message = t[.editInvalid]; return }
            params["value"] = value
        }
        busy = true
        rpc("decide", params) { _ in
            self.editing = nil
            self.message = nil
            self.load()
            self.onChange()
        }
    }

    func rpc(_ method: String, _ params: [String: Any], _ done: @escaping (Any?) -> Void) {
        work.async {
            do {
                let result = try RPC.call(method, params)
                DispatchQueue.main.async { self.busy = false; done(result) }
            } catch {
                let code = (error as? RPCError)?.code ?? "engine_error"
                DispatchQueue.main.async {
                    self.busy = false
                    self.message = errorText(code, self.t)
                    self.load()  // e.g. a record that disappeared is now marked
                }
            }
        }
    }
}

struct ReviewRow: View {
    @ObservedObject var m: ReviewModel
    let item: ReviewItem
    var t: L10n { m.t }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(item.title(t)).font(.headline)
                if let name = item.recordName {
                    Text(name).foregroundColor(.secondary).lineLimit(1).truncationMode(.middle)
                }
                Spacer()
                if !item.missing, let link = item.link {
                    Button(t[.openInDT3]) { NSWorkspace.shared.open(link) }
                }
            }
            if item.missing {
                CheckRow(ok: false, text: t[.missingRecord])
            }
            if !item.before.isEmpty {
                Text(t[.before] + ": " + item.before).foregroundColor(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            if !item.after.isEmpty {
                Text(t[.after] + ": " + item.after).fixedSize(horizontal: false, vertical: true)
            }
            if let c = item.confidence {
                Text(t.format(.confidenceN, Int((c * 100).rounded()))).font(.caption).foregroundColor(.secondary)
            }
            ForEach(item.hints, id: \.self) { hint in CheckRow(ok: false, text: hint) }
            if m.editing == item.id {
                TextField(t[.edit], text: $m.editText).accessibilityLabel(t[.edit])
                if !item.editHint(t).isEmpty {
                    Text(item.editHint(t)).font(.caption).foregroundColor(.secondary)
                }
                HStack {
                    Button(t[.cancel]) { m.editing = nil }
                    Button(t[.save]) { m.decide(item, "edit") }.disabled(m.busy)
                }
            } else {
                HStack {
                    if item.actions.contains("accept") { Button(t[.accept]) { m.decide(item, "accept") } }
                    if item.canEdit { Button(t[.edit]) { m.startEdit(item) } }
                    if item.actions.contains("reject") { Button(t[.reject]) { m.decide(item, "reject") } }
                }.disabled(m.busy)
            }
        }
        .padding(.vertical, 6)
    }
}

struct ReviewView: View {
    @ObservedObject var m: ReviewModel
    var t: L10n { m.t }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(t.format(.review, m.items.count)).font(.title2)
                Spacer()
                Button(t[.refresh]) { m.load() }.keyboardShortcut("r", modifiers: .command)
            }
            if let msg = m.message {
                Text(msg).foregroundColor(.red).fixedSize(horizontal: false, vertical: true)
            }
            if m.items.isEmpty {
                Spacer()
                Text(t[.reviewEmpty]).foregroundColor(.secondary).frame(maxWidth: .infinity)
                Spacer()
            } else {
                List(m.items) { item in ReviewRow(m: m, item: item) }
            }
        }
        .padding(16)
        .frame(minWidth: 620, minHeight: 460)
    }
}

final class ReviewWindow {
    private var window: NSWindow?
    private var model: ReviewModel?

    func show(t: L10n, work: DispatchQueue, onChange: @escaping () -> Void) {
        if let w = window {
            model?.load()
            w.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            return
        }
        let m = ReviewModel(t: t, work: work)
        m.onChange = onChange
        let w = NSWindow(contentViewController: NSHostingController(rootView: ReviewView(m: m)))
        w.title = t[.reviewTitle]
        w.styleMask = [.titled, .closable, .resizable]
        w.isReleasedWhenClosed = false
        window = w
        model = m
        m.load()
        w.center()
        w.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}
