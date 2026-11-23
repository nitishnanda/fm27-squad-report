import Foundation

/// Collects a child process's output from a background queue.
final class OutputBuffer: @unchecked Sendable {
    private let lock = NSLock()
    private var data = Data()

    func append(_ chunk: Data) { lock.withLock { data.append(chunk) } }
    var text: String { lock.withLock { String(decoding: data, as: UTF8.self) } }
}

/// Holds a Process so a timeout task can stop it. Process itself isn't Sendable.
final class ProcessHandle: @unchecked Sendable {
    let process: Process
    init(_ process: Process) { self.process = process }
    func stop() { if process.isRunning { process.terminate() } }
}

struct ProcessResult: Sendable {
    let status: Int32
    let output: String
    let timedOut: Bool
    var ok: Bool { status == 0 && !timedOut }

    /// The last line worth showing someone, e.g. "ERROR: Could not find a version that satisfies…"
    var lastLine: String {
        output.split(whereSeparator: \.isNewline).map { $0.trimmingCharacters(in: .whitespaces) }
            .last { !$0.isEmpty } ?? ""
    }
}

enum ProcessRunner {
    /// Runs a program to the end (or until `timeout`) and returns its exit status and combined output.
    static func run(_ executable: URL, _ arguments: [String], in directory: URL? = nil,
                    timeout: Duration? = nil) async -> ProcessResult {
        let process = Process()
        process.executableURL = executable
        process.arguments = arguments
        process.currentDirectoryURL = directory
        var env = ProcessInfo.processInfo.environment
        env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        env["PYTHONUNBUFFERED"] = "1"
        process.environment = env
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        process.standardInput = FileHandle.nullDevice
        let buffer = OutputBuffer()
        pipe.fileHandleForReading.readabilityHandler = { handle in
            let chunk = handle.availableData
            if !chunk.isEmpty { buffer.append(chunk) }
        }
        let handle = ProcessHandle(process)
        let timer = TimeoutFlag()

        let status: Int32 = await withCheckedContinuation { continuation in
            process.terminationHandler = { finished in
                continuation.resume(returning: finished.terminationStatus)
            }
            do {
                try process.run()
            } catch {
                process.terminationHandler = nil
                buffer.append(Data(error.localizedDescription.utf8))
                continuation.resume(returning: -1)
                return
            }
            if let timeout {
                Task.detached {
                    try? await Task.sleep(for: timeout)
                    if handle.process.isRunning {
                        timer.set()
                        handle.stop()
                    }
                }
            }
        }
        pipe.fileHandleForReading.readabilityHandler = nil
        if let rest = try? pipe.fileHandleForReading.readToEnd() { buffer.append(rest) }
        return ProcessResult(status: status, output: buffer.text, timedOut: timer.value)
    }
}

final class TimeoutFlag: @unchecked Sendable {
    private let lock = NSLock()
    private var fired = false
    func set() { lock.withLock { fired = true } }
    var value: Bool { lock.withLock { fired } }
}
