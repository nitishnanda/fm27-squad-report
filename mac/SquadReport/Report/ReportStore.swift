import AppKit
import Foundation
import Observation

/// Follows the engine: polls /api/status, fetches /api/report when a new build is ready, and keeps the last good
/// report on disk so the app opens instantly next time.
@MainActor @Observable
final class ReportStore {
    private(set) var report: Report?
    private(set) var status: EngineStatus?
    private(set) var reachable = false
    /// True while the report on screen is the cached one from last time, before the engine has a fresh one.
    private(set) var fromCache = false
    /// A report the app can't read (a newer feed, or a broken file), in plain words.
    private(set) var problem: String?
    /// A newer save was read while you weren't looking (the menu bar says "New report ready").
    private(set) var unseenUpdate = false

    func markSeen() {
        unseenUpdate = false
        NSApp.dockTile.badgeLabel = nil
    }

    /// The save behind each report is the first part of the engine's version ("<save time>-<script time>-<n>"),
    /// so a restart or an app update doesn't count as a new report.
    private static let lastSaveKey = "lastSaveStamp"

    private var loadedVersion: String?
    private var failures = 0
    private var polling: Task<Void, Never>?
    private var engine: Engine?

    private static var cacheURL: URL {
        let dir = URL.applicationSupportDirectory.appending(path: "Squad Report", directoryHint: .isDirectory)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appending(path: "last-report.json")
    }

    init() {
        if Self.demoPath == nil { Task { await loadCache() } }
    }

    /// `open "FM27 Companion.app" --args -demoReport /path/report.json` shows that file and leaves the engine alone.
    /// Handy for checking screens with the demo save (mac/Fixtures/report.json), which has injuries, bans and every move.
    static var demoPath: String? { UserDefaults.standard.string(forKey: "demoReport") }

    /// Demo mode has no engine, so "last checked" is when the demo file was opened.
    var demoLoaded: Date?

    func showDemo(_ path: String) {
        demoLoaded = .now
        guard let data = FileManager.default.contents(atPath: path) else {
            problem = "Couldn't open the demo report at \(path)."
            return
        }
        if use(data) { reachable = true }
    }

    /// Building right now, with the step being worked on (0-based) out of how many.
    var buildStep: (index: Int, of: Int, label: String)? {
        guard let status, status.building, status.step >= 0 else { return nil }
        let steps = status.steps.isEmpty ? Self.defaultSteps : status.steps
        let i = min(status.step, steps.count - 1)
        return (i, steps.count, steps[i])
    }

    static let defaultSteps = ["Opening your save", "Players and contracts", "Injuries and season stats",
                               "Positions played this season", "This season's matches", "Rating the squad",
                               "Best XIs and verdicts", "Writing the report"]

    func follow(_ engine: Engine) {
        self.engine = engine
        polling?.cancel()
        polling = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                await self.poll()
                let quick = !self.reachable || self.status?.building == true || self.status?.ready != true
                try? await Task.sleep(for: quick ? .seconds(1) : .seconds(3))
            }
        }
    }

    /// ⌘R: ask again now, and fetch the report even if the version hasn't changed.
    func reload() {
        loadedVersion = nil
        Task { await poll() }
    }

    private func poll() async {
        guard let engine else { return }
        do {
            let s = try await engine.client.status()
            status = s
            reachable = true
            failures = 0
            if let schema = s.schema, schema > Report.supportedSchema {
                problem = "Your engine is newer than this app. Rebuild the app (mac/build.sh) to read this report."
                return
            }
            if s.ready, s.version != loadedVersion { await fetch(version: s.version, client: engine.client) }
        } catch {
            reachable = false
            failures += 1
            if failures >= 5 { engine.lostContact() }
        }
    }

    private func fetch(version: String, client: EngineClient) async {
        guard let data = try? await client.reportData() else { return }
        if use(data) {
            loadedVersion = version
            fromCache = false
            let stamp = String(version.split(separator: "-").first ?? "")
            let last = UserDefaults.standard.string(forKey: Self.lastSaveKey)
            if let last, !stamp.isEmpty, stamp != last, let report {
                if !NSApplication.shared.isActive {
                    unseenUpdate = true
                    NSApp.dockTile.badgeLabel = "New"
                    NSApp.requestUserAttention(.informationalRequest)
                    Notifier.reportUpdated(club: report.club.name, gameDate: report.gameDate)
                }
            }
            if !stamp.isEmpty { UserDefaults.standard.set(stamp, forKey: Self.lastSaveKey) }
            let url = Self.cacheURL
            Task.detached(priority: .utility) { try? data.write(to: url, options: .atomic) }
        }
    }

    /// Decodes and shows a report. Returns false (and says why) if it can't be read.
    @discardableResult
    private func use(_ data: Data) -> Bool {
        if let schema = Report.schema(of: data), schema > Report.supportedSchema {
            problem = "This report comes from a newer engine than the app understands. Rebuild the app (mac/build.sh)."
            return false
        }
        do {
            report = try Report.decode(data)
            problem = nil
            return true
        } catch {
            problem = "Couldn't read the report: \(Self.describe(error))"
            return false
        }
    }

    private func loadCache() async {
        let url = Self.cacheURL
        guard report == nil,
              let data = await Task.detached(priority: .userInitiated, operation: { try? Data(contentsOf: url) }).value
        else { return }
        if report == nil, use(data) { fromCache = true }
    }

    private static func describe(_ error: Error) -> String {
        switch error {
        case DecodingError.keyNotFound(let key, let ctx):
            return "missing \(key.stringValue) at \(ctx.codingPath.map(\.stringValue).joined(separator: "."))"
        case DecodingError.typeMismatch(_, let ctx), DecodingError.valueNotFound(_, let ctx):
            return "unexpected value at \(ctx.codingPath.map(\.stringValue).joined(separator: "."))"
        default:
            return error.localizedDescription
        }
    }
}
