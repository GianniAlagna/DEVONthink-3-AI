// dt3agent-vision — OCR and QR reading with Apple Vision (ADR-0006, SPEC §4.15). macOS 11+.
//   dt3agent-vision ocr <file> <lang,lang,...> [max-pages]   -> {"pages": n, "text": "...", "ms": n}
//   dt3agent-vision qr  <file> [max-pages]                   -> {"payloads": ["<base64>", ...], "ms": n}
// Files: PDF (each page rendered at 300 dpi) or an image (JPEG, PNG, TIFF, HEIC). Read-only: the original is
// never changed (brief A1). Output is one JSON line on stdout; errors are a short code on stderr, exit 1.
// Measured in Phase 0 (S6): revision 2, accurate; de 0.997 · fr 0.966 · it 1.000 · en 1.000; 1.7–5.9 s/page.
import Foundation
import ImageIO
import PDFKit
import Vision

struct VisionError: Error { let code: String }

func pageImages(_ path: String, maxPages: Int) throws -> [CGImage] {
    let url = URL(fileURLWithPath: path)
    if let doc = PDFDocument(url: url) {
        return try (0..<min(doc.pageCount, maxPages)).compactMap { i in
            guard let page = doc.page(at: i) else { return nil }
            return try render(page)
        }
    }
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil) else { throw VisionError(code: "unreadable") }
    let count = min(CGImageSourceGetCount(source), maxPages)
    let images = (0..<count).compactMap { CGImageSourceCreateImageAtIndex(source, $0, nil) }
    if images.isEmpty { throw VisionError(code: "unreadable") }
    return images
}

func render(_ page: PDFPage, dpi: CGFloat = 300) throws -> CGImage {
    let box = page.bounds(for: .mediaBox)
    let scale = dpi / 72
    let w = Int(box.width * scale), h = Int(box.height * scale)
    guard w > 0, h > 0, w * h < 200_000_000,
          let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                              space: CGColorSpaceCreateDeviceRGB(),
                              bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else {
        throw VisionError(code: "render_failed")
    }
    ctx.setFillColor(CGColor(gray: 1, alpha: 1))
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    ctx.translateBy(x: -box.origin.x, y: -box.origin.y)
    page.draw(with: .mediaBox, to: ctx)
    guard let image = ctx.makeImage() else { throw VisionError(code: "render_failed") }
    return image
}

func ocr(_ images: [CGImage], _ languages: [String]) throws -> String {
    var pages: [String] = []
    for image in images {
        let request = VNRecognizeTextRequest()
        request.revision = VNRecognizeTextRequestRevision2
        request.recognitionLevel = .accurate
        request.recognitionLanguages = languages
        request.usesLanguageCorrection = true
        try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
        let lines = (request.results ?? []).compactMap { obs -> (CGFloat, String)? in
            guard let o = obs as? VNRecognizedTextObservation, let best = o.topCandidates(1).first else { return nil }
            return (o.boundingBox.midY, best.string)
        }
        pages.append(lines.sorted { $0.0 > $1.0 }.map { $0.1 }.joined(separator: "\n"))  // origin bottom-left
    }
    return pages.joined(separator: "\n\u{000C}\n")  // form feed between pages
}

func qr(_ images: [CGImage]) throws -> [String] {
    var payloads: [String] = []
    for image in images {
        let request = VNDetectBarcodesRequest()
        request.symbologies = [.QR]
        try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
        for case let obs as VNBarcodeObservation in request.results ?? [] {
            payloads.append(Data((obs.payloadStringValue ?? "").utf8).base64EncodedString())
        }
    }
    return payloads
}

func emit(_ object: [String: Any]) {
    let data = try! JSONSerialization.data(withJSONObject: object)
    FileHandle.standardOutput.write(data + Data("\n".utf8))
}

let args = Array(CommandLine.arguments.dropFirst())
let start = Date()
do {
    switch (args.first ?? "", args.count) {
    case ("ocr", 3), ("ocr", 4):
        let maxPages = args.count == 4 ? max(1, Int(args[3]) ?? 5) : 5
        let images = try pageImages(args[1], maxPages: maxPages)
        let text = try ocr(images, args[2].split(separator: ",").map(String.init))
        emit(["pages": images.count, "text": text, "ms": Int(Date().timeIntervalSince(start) * 1000)])
    case ("qr", 2), ("qr", 3):
        let maxPages = args.count == 3 ? max(1, Int(args[2]) ?? 5) : 5
        emit(["payloads": try qr(try pageImages(args[1], maxPages: maxPages)),
              "ms": Int(Date().timeIntervalSince(start) * 1000)])
    default:
        FileHandle.standardError.write("usage\n".data(using: .utf8)!)
        exit(2)
    }
} catch let e as VisionError {
    FileHandle.standardError.write("\(e.code)\n".data(using: .utf8)!)
    exit(1)
} catch {
    FileHandle.standardError.write("vision_failed\n".data(using: .utf8)!)
    exit(1)
}
