// Knowledge window (brief C2/C5, K-7): ask about the documents (answer + sources) and summarise the record
// selected in DT3. Read-only: the engine has no write path from here.
import AppKit
import SwiftUI

final class KnowledgeModel: ObservableObject {
    let t: L10n
    let work: DispatchQueue
    @Published var question = ""
    @Published var answer: AskAnswer?
    @Published var summary: SummaryResult?
    @Published var lang: String
    @Published var busy = false
    @Published var message: String?

    init(t: L10n, work: DispatchQueue) {
        self.t = t
        self.work = work
        lang = summaryLanguages.contains(t.language) ? t.language : "en"
    }

    func ask() {
        guard let q = cleanQuestion(question) else { message = t[.errQuestion]; return }
        answer = nil  // floor 2026-11-06: an old answer stayed visible under a new error message
        run("ask", ["question": q]) { self.answer = ($0 as? [String: Any]).flatMap(AskAnswer.init(json:)) }
    }

    func summarise() {
        run("selected", [:]) { result in
            guard let uuid = ((result as? [String: Any])?["uuids"] as? [String])?.first else {
                self.message = self.t[.errNothingSelected]
                return
            }
            self.run("summary", ["uuid": uuid, "lang": self.lang]) {
                self.summary = ($0 as? [String: Any]).flatMap(SummaryResult.init(json:))
            }
        }
    }

    /// Engine call off the main thread (answers can take a minute on an older Mac).
    func run(_ method: String, _ params: [String: Any], _ done: @escaping (Any?) -> Void) {
        busy = true
        message = nil
        work.async {
            do {
                let result = try RPC.call(method, params, timeout: 600)
                DispatchQueue.main.async { self.busy = false; done(result) }
            } catch {
                let code = (error as? RPCError)?.code ?? "engine_error"
                DispatchQueue.main.async { self.busy = false; self.message = errorText(code, self.t) }
            }
        }
    }
}

struct KnowledgeView: View {
    @ObservedObject var m: KnowledgeModel
    var t: L10n { m.t }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(t[.askTitle]).font(.title2)
            HStack {
                TextField(t[.askQuestion], text: $m.question, onCommit: { m.ask() })
                    .accessibilityLabel(t[.askQuestion])
                Button(t[.askButton]) { m.ask() }.keyboardShortcut(.defaultAction).disabled(m.busy)
            }
            if m.busy { ProgressView().accessibilityLabel(t[.askWorking]) }
            if let msg = m.message { ErrorLine(text: msg).id(msg) }
            answer
            Divider()
            summaryPart
            Spacer(minLength: 0)
        }
        .padding(16)
        .frame(minWidth: 560, minHeight: 480)
    }

    @ViewBuilder var answer: some View {
        if let a = m.answer {
            if a.notFound {
                Text(t[.askNotFound]).foregroundColor(.secondary)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(a.text).fixedSize(horizontal: false, vertical: true)
                        if a.filtered > 0 { CheckRow(ok: false, text: t[.askFiltered]) }
                        if !a.sources.isEmpty { Text(t[.askSources]).font(.headline) }
                        ForEach(a.sources) { s in
                            Button(s.name) { if let l = s.link { NSWorkspace.shared.open(l) } }
                                .accessibilityLabel(t[.askSources] + ": " + s.name)
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder var summaryPart: some View {
        HStack {
            Text(t[.summaryTitle]).font(.headline)
            Picker(t[.summaryLanguage], selection: $m.lang) {
                ForEach(summaryLanguages, id: \.self) { Text($0.uppercased()).tag($0) }
            }
            .frame(width: 180)
            Button(t[.summaryButton]) { m.summarise() }.disabled(m.busy)
        }
        if let s = m.summary {
            Text(s.text).fixedSize(horizontal: false, vertical: true)
            if s.partial { CheckRow(ok: false, text: t[.summaryPartial]) }
        }
    }
}

final class KnowledgeWindow {
    private var window: NSWindow?

    func show(t: L10n, work: DispatchQueue) {
        if let w = window { w.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true); return }
        let m = KnowledgeModel(t: t, work: work)
        let w = NSWindow(contentViewController: NSHostingController(rootView: KnowledgeView(m: m)))
        w.title = t[.askTitle]
        w.styleMask = [.titled, .closable, .resizable]
        w.isReleasedWhenClosed = false
        window = w
        w.center()
        w.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}
