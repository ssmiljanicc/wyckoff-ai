import Foundation
import Vision
import CoreGraphics
import ImageIO

struct TextObservation: Codable {
    let text: String
    let confidence: Double
    let x: Double
    let y: Double
    let w: Double
    let h: Double
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(2)
}

let arguments = Array(CommandLine.arguments.dropFirst())
guard arguments.count == 1 else { fail("usage: fraser_header_vision <image>") }

let imagePath = arguments[0]
guard let source = CGImageSourceCreateWithURL(
    URL(fileURLWithPath: imagePath) as CFURL,
    nil
), let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
    fail("cannot decode image: \(imagePath)")
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.recognitionLanguages = ["en-US"]
request.minimumTextHeight = 0.0

do {
    try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
} catch {
    fail("Vision OCR failed: \(error)")
}

let observations = (request.results ?? []).compactMap { observation -> TextObservation? in
    guard let candidate = observation.topCandidates(1).first else { return nil }
    return TextObservation(
        text: candidate.string,
        confidence: Double(candidate.confidence),
        x: observation.boundingBox.origin.x,
        y: observation.boundingBox.origin.y,
        w: observation.boundingBox.size.width,
        h: observation.boundingBox.size.height
    )
}.sorted {
    if $0.y != $1.y { return $0.y > $1.y }
    if $0.x != $1.x { return $0.x < $1.x }
    return $0.text < $1.text
}

let encoder = JSONEncoder()
encoder.outputFormatting = [.sortedKeys]
do {
    FileHandle.standardOutput.write(try encoder.encode(observations))
    FileHandle.standardOutput.write(Data("\n".utf8))
} catch {
    fail("cannot encode OCR observations: \(error)")
}
