import Foundation
import Observation

/// Starts and stops the Python engine (`fm27_squad_report.py --headless`) with the app, restarts it if it crashes,
/// and says what went wrong in plain words. The engine normally ships inside the app (`BundledEngine`); for working
/// on the script it can run from a project folder instead, with that folder's .venv, like the .command.
/// If an engine is already running (the .command in Terminal, or one left over from before), the app uses that one
/// instead of starting a second.
@MainActor @Observable
final class Engine {
    enum Phase: Equatable {
        case idle
        case preparing(String)      // first-run setup / save-reader update, with progress text
        case starting
        case running                // ours
        case attached               // someone else's, e.g. Run Squad Report.command
        case restarting(String)     // it crashed; why, while we start it again
        case failed(String)
        case stopped
    }

    /// Where the engine comes from.
    enum Source: Equatable {
        case bundled(importFrom: URL?)   // inside the app; the folder is only where your old files get copied from
        case folder(URL)
    }

    private(set) var phase: Phase = .idle
    private(set) var recentOutput: [String] = []
    let client = EngineClient()

    private(set) var source: Source?
    private var process: Process?
    private var pipe: Pipe?
    private var partialLine = ""
    private var crashes: [Date] = []
    private var quitting = false
    private var launching = false
    private var sawAlreadyRunning = false
    private var startAfterExit = false

    var isUp: Bool { phase == .running || phase == .attached }

    func start(_ source: Source) {
        self.source = source
        quitting = false
        Task { await launch() }
    }

    /// Another source (or another project folder): stop the engine we started (if any), then start the new one.
    func switchSource(to source: Source) {
        self.source = source
        if let process, process.isRunning {
            startAfterExit = true
            quitting = true
            process.terminate()
        } else {
            start(source)
        }
    }

    func retry() {
        crashes.removeAll()
        if case .failed = phase { phase = .idle }
        if let source { start(source) }
    }

    /// Try again, possibly from somewhere new (the project folder moved, say).
    func retry(with source: Source) {
        crashes.removeAll()
        if case .failed = phase { phase = .idle }
        if source != self.source { switchSource(to: source) } else { start(source) }
    }

    /// Start ours again (a setting it reads at start changed). Someone else's engine is left alone.
    func restart() {
        guard source != nil, let process, process.isRunning else { return }
        startAfterExit = true
        quitting = true
        process.terminate()
    }

    /// The store couldn't reach the engine for a while. If it was someone else's, start our own.
    func lostContact() {
        guard phase == .attached, !quitting else { return }
        phase = .idle
        Task { await launch() }
    }

    /// When the app quits. An engine we only attached to keeps running: it isn't ours to stop.
    func stop() {
        quitting = true
        if let process, process.isRunning { process.terminate() }
    }

    // MARK: - starting

    private func launch() async {
        guard let source, !launching, process?.isRunning != true else { return }
        launching = true
        await launch(source)
        launching = false
        // switched in Settings while that one was still getting ready: start the new one now
        if self.source != source, process?.isRunning != true, !quitting { await launch() }
    }

    private func launch(_ source: Source) async {
        if (try? await client.status(timeout: 1.5)) != nil {
            phase = .attached
            return
        }
        phase = .preparing("Getting ready…")
        let progress: PythonSetup.Progress = { [weak self] text in self?.phase = .preparing(text) }
        switch source {
        case .bundled(let importFrom):
            guard let root = BundledEngine.root else {
                phase = .failed("This copy of the app doesn't have the engine inside it. Rebuild it with mac/build.sh, or choose a project folder in Settings.")
                return
            }
            let python = await BundledEngine.prepare(root: root, importFrom: importFrom, report: progress)
            guard self.source == source else { return }   // switched while getting ready
            spawn(python: python, script: BundledEngine.script(root), directory: BundledEngine.home,
                  environment: BundledEngine.environment())
        case .folder(let folder):
            let python: URL
            do {
                python = try await PythonSetup.prepare(folder: folder, report: progress)
            } catch {
                phase = .failed(error.plainWords)
                return
            }
            guard self.source == source else { return }   // switched while getting ready
            let script = folder.appending(path: "fm27_squad_report.py")
            guard FileManager.default.fileExists(atPath: script.path) else {
                phase = .failed("fm27_squad_report.py isn't in \(folder.lastPathComponent) any more. Choose the folder again (File › Choose Project Folder…).")
                return
            }
            spawn(python: python, script: script, directory: folder, environment: ProcessInfo.processInfo.environment)
        }
    }

    private func spawn(python: URL, script: URL, directory: URL, environment: [String: String]) {
        let process = Process()
        process.executableURL = python
        // phone access off: the engine only listens to this Mac
        let phone = UserDefaults.standard.object(forKey: "phoneAccess") as? Bool ?? true
        process.arguments = [script.path(percentEncoded: false), "--headless"] + (phone ? [] : ["--mac-only"])
        process.currentDirectoryURL = directory
        var env = environment
        env["PYTHONUNBUFFERED"] = "1"
        env["FM27_NO_OPEN"] = "1"
        process.environment = env
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        process.standardInput = FileHandle.nullDevice

        let engine: Engine? = self
        pipe.fileHandleForReading.readabilityHandler = { handle in
            let chunk = handle.availableData
            guard !chunk.isEmpty else { return }
            Task { @MainActor in engine?.take(chunk) }
        }
        process.terminationHandler = { finished in
            let status = finished.terminationStatus
            Task { @MainActor in engine?.ended(status: status) }
        }
        sawAlreadyRunning = false
        do {
            try process.run()
        } catch {
            pipe.fileHandleForReading.readabilityHandler = nil
            phase = .failed("Couldn't start the engine: \(error.localizedDescription)")
            return
        }
        self.process = process
        self.pipe = pipe
        phase = .starting
        Task { await waitUntilUp() }
    }

    private func waitUntilUp() async {
        for _ in 0..<240 {   // a first start imports a lot; give it up to two minutes
            try? await Task.sleep(for: .milliseconds(500))
            guard phase == .starting, process?.isRunning == true else { return }
            if (try? await client.status(timeout: 1)) != nil {
                phase = .running
                return
            }
        }
    }

    // MARK: - output and exits

    private func take(_ chunk: Data) {
        partialLine += String(decoding: chunk, as: UTF8.self)
        var lines = partialLine.components(separatedBy: "\n")
        partialLine = lines.removeLast()
        for line in lines where !line.trimmingCharacters(in: .whitespaces).isEmpty {
            if line.contains("already running") { sawAlreadyRunning = true }
            recentOutput.append(line)
        }
        if recentOutput.count > 80 { recentOutput.removeFirst(recentOutput.count - 80) }
    }

    private func ended(status: Int32) {
        pipe?.fileHandleForReading.readabilityHandler = nil
        pipe = nil
        process = nil
        if quitting {
            if startAfterExit {
                startAfterExit = false
                quitting = false
                phase = .idle
                Task { await launch() }
            } else {
                phase = .stopped
            }
            return
        }
        if sawAlreadyRunning {
            // another engine holds the port: use it if it speaks the app's language
            Task {
                if (try? await client.status()) != nil {
                    phase = .attached
                } else {
                    phase = .failed("An older Squad Report is still running in a Terminal window, and it can't talk to the app. "
                                    + "Close that window, then click Try again.")
                }
            }
            return
        }
        crashes.append(Date())
        crashes.removeAll { -$0.timeIntervalSinceNow > 120 }
        let why = plainWords(status: status)
        if crashes.count >= 3 {
            phase = .failed(why)
            return
        }
        phase = .restarting(why)
        Task {
            try? await Task.sleep(for: .seconds(2))
            await launch()
        }
    }

    /// The last thing the engine said, turned into something a person can act on.
    private func plainWords(status: Int32) -> String {
        let all = recentOutput.joined(separator: "\n")
        if all.contains("No module named 'fmsave'") {
            UserDefaults.standard.removeObject(forKey: PythonSetup.lastUpgradeKey)
            return "The save reader (fmsave) is missing. Click Try again and the app will install it."
        }
        if all.contains("Address already in use") {
            return "Something else on this Mac is using port \(EngineClient.port), so the engine can't start. Quit it, then click Try again."
        }
        if all.contains("SyntaxError") || all.contains("IndentationError") {
            return "fm27_squad_report.py has a mistake in it, so the engine won't start. Fix the file (or git pull), then click Try again."
        }
        let last = recentOutput.last { !$0.hasPrefix(" ") || $0.contains("Error") } ?? recentOutput.last ?? ""
        let detail = last.trimmingCharacters(in: .whitespaces)
        return detail.isEmpty ? "The engine stopped (exit code \(status))." : "The engine stopped: \(detail)"
    }
}
