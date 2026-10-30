// S6 - Vision framework probe for macOS 11 (Xcode 13.2 / Swift 5.5).
//   vision-probe langs
//   vision-probe ocr <file.pdf> <lang,lang,...>   prints recognised lines, top to bottom
//   vision-probe qr  <file.pdf>                   prints each QR payload as base64 (byte-exact compare)
// APIs: VNRecognizeTextRequest (macOS 10.15+, revision 2 = macOS 11), VNDetectBarcodesRequest (10.13+),
// PDFPage.draw(with:to:) (10.12+).
import Foundation
import PDFKit
import Vision

struct ProbeError: Error, CustomStringConvertible {
    let description: String
}

func renderFirstPage(_ path: String, dpi: CGFloat = 300) throws -> CGImage {
    guard let doc = PDFDocument(url: URL(fileURLWithPath: path)), let page = doc.page(at: 0) else {
        throw ProbeError(description: "cannot open PDF \(path)")
    }
    let box = page.bounds(for: .mediaBox)
    let scale = dpi / 72
    let w = Int(box.width * scale), h = Int(box.height * scale)
    guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceRGB(),
                              bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else {
        throw ProbeError(description: "cannot create bitmap context")
    }
    ctx.setFillColor(CGColor(gray: 1, alpha: 1))
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    ctx.translateBy(x: -box.origin.x, y: -box.origin.y)
    page.draw(with: .mediaBox, to: ctx)
    guard let image = ctx.makeImage() else { throw ProbeError(description: "render failed") }
    return image
}

func ms(since start: Date) -> Int { Int(Date().timeIntervalSince(start) * 1000) }

func langs() throws {
    for (name, rev) in [("revision1", VNRecognizeTextRequestRevision1), ("revision2", VNRecognizeTextRequestRevision2)] {
        let accurate = try VNRecognizeTextRequest.supportedRecognitionLanguages(for: .accurate, revision: rev)
        let fast = try VNRecognizeTextRequest.supportedRecognitionLanguages(for: .fast, revision: rev)
        print("\(name) accurate: \(accurate.joined(separator: ","))")
        print("\(name) fast:     \(fast.joined(separator: ","))")
    }
}

func ocr(_ path: String, _ languages: [String]) throws {
    let start = Date()
    let image = try renderFirstPage(path)
    let request = VNRecognizeTextRequest()
    request.revision = VNRecognizeTextRequestRevision2
    request.recognitionLevel = .accurate
    request.recognitionLanguages = languages
    request.usesLanguageCorrection = true
    try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    var lines: [(y: CGFloat, text: String)] = []
    for case let obs as VNRecognizedTextObservation in request.results ?? [] {
        if let best = obs.topCandidates(1).first { lines.append((obs.boundingBox.midY, best.string)) }
    }
    for line in lines.sorted(by: { $0.y > $1.y }) { print(line.text) }  // Vision origin is bottom-left
    FileHandle.standardError.write("ocr \(ms(since: start)) ms\n".data(using: .utf8)!)
}

func qr(_ path: String) throws {
    let start = Date()
    let image = try renderFirstPage(path)
    let request = VNDetectBarcodesRequest()
    request.symbologies = [.QR]
    try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    var found = 0
    for case let obs as VNBarcodeObservation in request.results ?? [] {
        found += 1
        print(Data((obs.payloadStringValue ?? "").utf8).base64EncodedString())
    }
    FileHandle.standardError.write("qr \(found) code(s), \(ms(since: start)) ms\n".data(using: .utf8)!)
}

let args = CommandLine.arguments
do {
    switch (args.count > 1 ? args[1] : "", args.count) {
    case ("langs", _): try langs()
    case ("ocr", 4): try ocr(args[2], args[3].split(separator: ",").map(String.init))
    case ("qr", 3): try qr(args[2])
    default:
        print("usage: vision-probe langs | ocr <pdf> <langs> | qr <pdf>")
        exit(2)
    }
} catch {
    FileHandle.standardError.write("ERROR \(error)\n".data(using: .utf8)!)
    exit(1)
}
