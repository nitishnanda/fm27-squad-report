import Foundation

/// What `Run Squad Report.command` does before it starts the engine: find Python 3.12+, make `.venv`,
/// install `fmsave` (the save reader), and keep it current so FM27 patches keep working.
enum PythonSetup {
    enum Failure: Error, Equatable {
        case noPython
        case setupFailed(String)

        var plainWords: String {
            switch self {
            case .noPython:
                return "Couldn't find Python 3.12 or newer on this Mac. Install it from python.org, then click Try again."
            case .setupFailed(let detail):
                let why = detail.isEmpty ? "" : " (\(detail))"
                return "Setting up the save reader didn't work. Check your internet connection and click Try again.\(why)"
            }
        }
    }

    /// Progress text for the setup screen.
    typealias Progress = @MainActor @Sendable (String) -> Void

    static let lastUpgradeKey = "lastFmsaveUpgrade"

    /// Returns the venv's python once the engine can run.
    static func prepare(folder: URL, report: Progress) async throws(Failure) -> URL {
        let venvPython = folder.appending(path: ".venv/bin/python")
        let venvWorks = FileManager.default.isExecutableFile(atPath: venvPython.path)
            ? await ProcessRunner.run(venvPython, ["-c", "import fmsave"], in: folder, timeout: .seconds(30)).ok
            : false

        if venvWorks {
            await upgradeIfDue(venvPython, folder: folder, report: report)
            return venvPython
        }

        await report("First run: setting things up. This only happens once.")
        if FileManager.default.isExecutableFile(atPath: venvPython.path) {
            // .venv is there but the save reader isn't: install it into the existing one
            if await install(venvPython, folder: folder, report: report) { return venvPython }
        }
        guard let python = await findPython() else { throw .noPython }
        await report("Making a private Python setup for the app (.venv)…")
        try? FileManager.default.removeItem(at: folder.appending(path: ".venv"))
        let made = await ProcessRunner.run(python, ["-m", "venv", ".venv"], in: folder, timeout: .seconds(180))
        guard made.ok else { throw .setupFailed(made.lastLine) }
        guard await install(venvPython, folder: folder, report: report) else {
            try? FileManager.default.removeItem(at: folder.appending(path: ".venv"))
            throw .setupFailed("pip couldn't install fmsave")
        }
        return venvPython
    }

    private static func install(_ python: URL, folder: URL, report: Progress) async -> Bool {
        await report("Installing the save reader (fmsave)…")
        let result = await ProcessRunner.run(python, ["-m", "pip", "install", "--quiet", "fmsave"], in: folder,
                                             timeout: .seconds(600))
        if result.ok { UserDefaults.standard.set(Date(), forKey: lastUpgradeKey) }
        return result.ok
    }

    /// Once a day, like the .command's quiet upgrade. Skipped quietly when offline.
    private static func upgradeIfDue(_ python: URL, folder: URL, report: Progress) async {
        if let last = UserDefaults.standard.object(forKey: lastUpgradeKey) as? Date, -last.timeIntervalSinceNow < 86_400 {
            return
        }
        await report("Checking the save reader is up to date…")
        let result = await ProcessRunner.run(python, ["-m", "pip", "install", "--quiet", "--upgrade", "--timeout", "5", "fmsave"],
                                             in: folder, timeout: .seconds(90))
        if result.ok { UserDefaults.standard.set(Date(), forKey: lastUpgradeKey) }
    }

    /// Python 3.12 or newer: python.org installs first (that's what the .command found), then Homebrew,
    /// then whatever a login shell finds. A GUI app doesn't get the Terminal's PATH, hence the full paths.
    static func findPython() async -> URL? {
        var candidates: [String] = []
        for minor in stride(from: 16, through: 12, by: -1) {
            candidates.append("/Library/Frameworks/Python.framework/Versions/3.\(minor)/bin/python3")
            candidates.append("/opt/homebrew/bin/python3.\(minor)")
            candidates.append("/usr/local/bin/python3.\(minor)")
        }
        candidates += ["/opt/homebrew/bin/python3", "/usr/local/bin/python3"]
        let shell = await ProcessRunner.run(URL(filePath: "/bin/zsh"), ["-lc", "command -v python3"], timeout: .seconds(10))
        if shell.ok, !shell.lastLine.isEmpty { candidates.append(shell.lastLine) }

        let check = "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
        for path in candidates where FileManager.default.isExecutableFile(atPath: path) {
            let url = URL(filePath: path)
            if await ProcessRunner.run(url, ["-c", check], timeout: .seconds(15)).ok { return url }
        }
        return nil
    }
}
