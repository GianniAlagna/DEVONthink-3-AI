// Onboarding logic (brief §6.2, U-2): steps, checks and input rules. Pure Foundation, tested in app/Tests.
import Foundation

enum SetupStep: Int, CaseIterable {
    case welcome, system, ai, identity, naming, smartRule, finish

    var next: SetupStep? { SetupStep(rawValue: rawValue + 1) }
    var previous: SetupStep? { SetupStep(rawValue: rawValue - 1) }
}

/// Where an AI server address points. Brief E7: warn when it is not on this Mac or the local network.
enum AIHost: Equatable {
    case invalid, thisMac, localNetwork, internet

    init(_ text: String) {
        let s = text.trimmingCharacters(in: .whitespaces)
        guard let url = URL(string: s), let scheme = url.scheme?.lowercased(), scheme == "http" || scheme == "https",
              let host = url.host?.lowercased(), !host.isEmpty, s.count <= 300 else { self = .invalid; return }
        if host == "localhost" || host == "::1" || host.hasPrefix("127.") { self = .thisMac; return }
        let parts = host.split(separator: ".").compactMap { Int($0) }
        if parts.count == 4 {
            let (a, b) = (parts[0], parts[1])
            if a == 10 || (a == 192 && b == 168) || (a == 172 && (16...31).contains(b)) { self = .localNetwork; return }
        }
        if host.hasSuffix(".local") { self = .localNetwork; return }
        self = .internet
    }
}

/// System facts for step 2. RAM in GB, macOS as (major, minor).
struct SystemFacts {
    var macOS: (Int, Int)
    var ramGB: Int
    var appleSilicon: Bool

    static var current: SystemFacts {
        let v = ProcessInfo.processInfo.operatingSystemVersion
        var arm = false
        #if arch(arm64)
        arm = true
        #endif
        return SystemFacts(macOS: (v.majorVersion, v.minorVersion),
                           ramGB: Int(ProcessInfo.processInfo.physicalMemory / 1_073_741_824), appleSilicon: arm)
    }

    var macOSSupported: Bool { macOS.0 >= 11 }
    /// The default model (ADR-0003, Qwen3-1.7B Q4_K_M) was measured on 8 GB; less works only slowly.
    var ramEnough: Bool { ramGB >= 8 }
}

/// Identity name (brief §6.2 step 5): optional, printable, at most 200 characters (same rule as the engine).
func cleanName(_ text: String) -> String? {
    let s = text.trimmingCharacters(in: .whitespacesAndNewlines)
    guard s.count <= 200, !s.unicodeScalars.contains(where: { CharacterSet.controlCharacters.contains($0) }) else {
        return nil
    }
    return s
}

let defaultTemplate = "{datetime}_{sender}_{receiver}_{subject}"
let defaultAIURL = "http://127.0.0.1:8080"
