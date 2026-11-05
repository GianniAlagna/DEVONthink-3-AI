// Client for the engine's private Unix socket (SPEC §4.17, ADR-0007): one JSON line out, one JSON line in.
import Foundation

struct RPCError: Error { let code: String }

enum RPC {
    static let maxLine = 64 * 1024

    static var socketPath: String {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        return base.appendingPathComponent("DT3 Agent/engine.sock").path
    }

    /// Blocking call; run it off the main thread. Throws RPCError with a short code.
    static func call(_ method: String, _ params: [String: Any] = [:], timeout: Int = 120,
                     path: String = RPC.socketPath) throws -> Any? {
        let request = try JSONSerialization.data(withJSONObject: ["method": method, "params": params])
        let reply = try exchange(request + Data([0x0A]), path: path, timeout: timeout)
        return try decode(reply)
    }

    /// Parses one reply line: {"ok": true, "result": …} or {"ok": false, "error": "code"}.
    static func decode(_ line: Data) throws -> Any? {
        guard let obj = (try? JSONSerialization.jsonObject(with: line)) as? [String: Any] else {
            throw RPCError(code: "bad_reply")
        }
        if obj["ok"] as? Bool == true { return obj["result"] }
        throw RPCError(code: obj["error"] as? String ?? "unknown_error")
    }

    private static func exchange(_ request: Data, path: String, timeout: Int) throws -> Data {
        var addr = sockaddr_un()
        addr.sun_family = sa_family_t(AF_UNIX)
        let pathBytes = Array(path.utf8)
        let capacity = MemoryLayout.size(ofValue: addr.sun_path)
        guard pathBytes.count < capacity else { throw RPCError(code: "socket_path_too_long") }
        withUnsafeMutableBytes(of: &addr.sun_path) { raw in
            raw.copyBytes(from: pathBytes)
            raw[pathBytes.count] = 0
        }
        let fd = socket(AF_UNIX, SOCK_STREAM, 0)
        guard fd >= 0 else { throw RPCError(code: "engine_unreachable") }
        defer { close(fd) }
        var tv = timeval(tv_sec: timeout, tv_usec: 0)
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, socklen_t(MemoryLayout<timeval>.size))
        setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, socklen_t(MemoryLayout<timeval>.size))
        var noSigPipe: Int32 = 1
        setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &noSigPipe, socklen_t(MemoryLayout<Int32>.size))
        let connected = withUnsafePointer(to: &addr) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                connect(fd, $0, socklen_t(MemoryLayout<sockaddr_un>.size))
            }
        }
        guard connected == 0 else {
            throw RPCError(code: errno == ENOENT || errno == ECONNREFUSED ? "engine_not_running" : "engine_unreachable")
        }
        let sent = request.withUnsafeBytes { send(fd, $0.baseAddress, request.count, 0) }
        guard sent == request.count else { throw RPCError(code: "engine_unreachable") }
        var reply = Data()
        var buffer = [UInt8](repeating: 0, count: 4096)
        while !reply.contains(0x0A) {
            let n = recv(fd, &buffer, buffer.count, 0)
            if n <= 0 { break }
            reply.append(contentsOf: buffer[0..<n])
            if reply.count > maxLine { throw RPCError(code: "reply_too_long") }
        }
        guard let end = reply.firstIndex(of: 0x0A) else { throw RPCError(code: "engine_unreachable") }
        return reply.prefix(upTo: end)
    }
}
