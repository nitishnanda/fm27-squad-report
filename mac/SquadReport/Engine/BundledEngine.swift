import Foundation

/// The engine that ships inside the app (Contents/Resources/Engine): Python 3.13 with fmsave, plus
/// fm27_squad_report.py and its assets. No project folder, no Python install, no first-run setup.
/// It writes to ~/Library/Application Support/Squad Report: star history, club, phone key, scouting list, saved reports.
enum BundledEngine {
    /// Nil when this build doesn't carry the engine (a dev build without mac/build/vendor/python).
    static var root: URL? {
        guard let root = Bundle.main.resourceURL?.appending(path: "Engine", directoryHint: .isDirectory),
              FileManager.default.isExecutableFile(atPath: root.appending(path: "python/bin/python3").path),
              FileManager.default.fileExists(atPath: root.appending(path: "engine/fm27_squad_report.py").path)
        else { return nil }
        return root
    }

    static var isAvailable: Bool { root != nil }

    static var home: URL {
        URL.applicationSupportDirectory.appending(path: "Squad Report", directoryHint: .isDirectory)
    }

    /// A newer fmsave than the one in the app, put here by the daily check. Comes first on the import path.
    static var packages: URL { home.appending(path: "python-packages", directoryHint: .isDirectory) }

    static func python(_ root: URL) -> URL { root.appending(path: "python/bin/python3") }
    static func script(_ root: URL) -> URL { root.appending(path: "engine/fm27_squad_report.py") }

    /// A clean environment: nothing from a Python the user installed leaks in, and nothing is written into the app.
    static func environment(packages overlay: URL? = packages) -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        for key in ["PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "VIRTUAL_ENV", "PYTHONEXECUTABLE", "__PYVENV_LAUNCHER__"] {
            env[key] = nil
        }
        env["SQUAD_REPORT_HOME"] = home.path(percentEncoded: false)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONNOUSERSITE"] = "1"
        if let overlay, FileManager.default.fileExists(atPath: overlay.path) {
            env["PYTHONPATH"] = overlay.path(percentEncoded: false)
        }
        return env
    }

    /// Ready to run: the home folder exists, your history came over from the project folder, and fmsave is current.
    static func prepare(root: URL, importFrom folder: URL?, report: PythonSetup.Progress) async -> URL {
        try? FileManager.default.createDirectory(at: home, withIntermediateDirectories: true)
        importOnce(from: folder)
        let python = python(root)
        // a newer fmsave that won't import (half an update, say) is dropped: the app's own one still works
        if FileManager.default.fileExists(atPath: packages.path),
           await !ProcessRunner.run(python, ["-c", "import fmsave"], environment: environment(), timeout: .seconds(30)).ok {
            try? FileManager.default.removeItem(at: packages)
        }
        await upgradeIfDue(python, report: report)
        return python
    }

    // MARK: - bringing your files over

    static let importedKey = "importedProjectFiles"

    /// Once: the star history (trends), last club, phone key (so the iPhone's Home Screen link keeps working) and
    /// scouting list, copied from the project folder the app used before. Never overwrites, never deletes the originals.
    static func importOnce(from folder: URL?) {
        guard let folder, !UserDefaults.standard.bool(forKey: importedKey) else { return }
        let fm = FileManager.default
        for path in ["data/history.json", "data/club.json", "data/phone.json", "scouting.txt"] {
            let from = folder.appending(path: path), to = home.appending(path: path)
            guard fm.fileExists(atPath: from.path), !fm.fileExists(atPath: to.path) else { continue }
            try? fm.createDirectory(at: to.deletingLastPathComponent(), withIntermediateDirectories: true)
            try? fm.copyItem(at: from, to: to)
            if path == "data/phone.json" { try? fm.setAttributes([.posixPermissions: 0o600], ofItemAtPath: to.path) }
        }
        UserDefaults.standard.set(true, forKey: importedKey)
    }

    // MARK: - keeping fmsave current

    static let lastCheckKey = "lastBundledFmsaveCheck"

    /// Once a day: if PyPI has a newer fmsave (FM patches can need one), install it next to the app's copy.
    /// Offline or slow: skipped quietly, the app's own fmsave keeps working.
    static func upgradeIfDue(_ python: URL, report: PythonSetup.Progress) async {
        if let last = UserDefaults.standard.object(forKey: lastCheckKey) as? Date, -last.timeIntervalSinceNow < 86_400 { return }
        await report("Checking the save reader is up to date…")
        guard let latest = await latestOnPyPI() else { return }
        UserDefaults.standard.set(Date(), forKey: lastCheckKey)
        let now = await ProcessRunner.run(python, ["-c", "import importlib.metadata as m; print(m.version('fmsave'))"],
                                          environment: environment(), timeout: .seconds(30))
        guard now.ok, isNewer(latest, than: now.lastLine) else { return }

        await report("Updating the save reader to fmsave \(latest)…")
        let fresh = home.appending(path: "python-packages.new", directoryHint: .isDirectory)
        try? FileManager.default.removeItem(at: fresh)
        let installed = await ProcessRunner.run(python, ["-m", "pip", "install", "--quiet", "--timeout", "10",
                                                         "--target", fresh.path(percentEncoded: false), "fmsave==\(latest)"],
                                                environment: environment(packages: nil), timeout: .seconds(240))
        let works = installed.ok
            ? await ProcessRunner.run(python, ["-c", "import fmsave"], environment: environment(packages: fresh), timeout: .seconds(30)).ok
            : false
        if works {
            try? FileManager.default.removeItem(at: packages)
            try? FileManager.default.moveItem(at: fresh, to: packages)
        } else {
            try? FileManager.default.removeItem(at: fresh)
            UserDefaults.standard.removeObject(forKey: lastCheckKey)   // try again next start
        }
    }

    private struct PyPI: Decodable {
        struct Info: Decodable { let version: String }
        let info: Info
    }

    static func latestOnPyPI() async -> String? {
        var request = URLRequest(url: URL(string: "https://pypi.org/pypi/fmsave/json")!)
        request.timeoutInterval = 6
        guard let (data, response) = try? await URLSession.shared.data(for: request),
              (response as? HTTPURLResponse)?.statusCode == 200,
              let pypi = try? JSONDecoder().decode(PyPI.self, from: data) else { return nil }
        return pypi.info.version
    }

    /// "0.15.0" vs "0.14.3", number by number.
    static func isNewer(_ a: String, than b: String) -> Bool {
        a.compare(b, options: .numeric) == .orderedDescending
    }
}
