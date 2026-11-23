import AppKit
import Foundation
import Observation

/// Everything the window and the menus share: the project folder, the engine, the report and where you are.
@MainActor @Observable
final class AppModel {
    let engine = Engine()
    let store = ReportStore()

    private(set) var folder: URL?
    var folderProblem: String?
    var route: Route = .home
    /// The last page you opened in each section, so ⌘2 goes back to the Team page you were on.
    private var lastPage: [AppSection: Route] = [:]

    private static let bookmarkKey = "projectFolderBookmark"

    init() {
        folder = Self.restoreFolder()
        store.follow(engine)
        if let folder { engine.start(folder: folder) }
    }

    // MARK: - navigation

    func go(_ route: Route) {
        lastPage[route.section] = route
        self.route = route
    }

    func go(_ section: AppSection) {
        go(lastPage[section] ?? section.pages[0])
    }

    /// ⌘[ and ⌘]: the page before or after this one in the same section.
    func step(_ delta: Int) {
        let pages = route.section.pages
        guard pages.count > 1, let i = pages.firstIndex(of: route) else { return }
        go(pages[(i + delta + pages.count) % pages.count])
    }

    func openInBrowser(_ route: Route? = nil) {
        NSWorkspace.shared.open(engine.client.webURL(route: (route ?? self.route).webHash))
    }

    // MARK: - project folder

    /// The folder with fm27_squad_report.py in it (where Run Squad Report.command lives). Kept as a bookmark,
    /// so it's still found if the folder is moved or renamed.
    func choose(folder url: URL) {
        guard FileManager.default.fileExists(atPath: url.appending(path: "fm27_squad_report.py").path) else {
            folderProblem = "That folder doesn't have fm27_squad_report.py in it. Pick the one with Run Squad Report.command."
            return
        }
        folderProblem = nil
        if let data = try? url.bookmarkData(options: [], includingResourceValuesForKeys: nil, relativeTo: nil) {
            UserDefaults.standard.set(data, forKey: Self.bookmarkKey)
        }
        let changed = folder != url
        folder = url
        if changed { engine.switchFolder(to: url) } else { engine.start(folder: url) }
    }

    private static func restoreFolder() -> URL? {
        guard let data = UserDefaults.standard.data(forKey: bookmarkKey) else { return nil }
        var stale = false
        guard let url = try? URL(resolvingBookmarkData: data, options: [], relativeTo: nil, bookmarkDataIsStale: &stale),
              FileManager.default.fileExists(atPath: url.appending(path: "fm27_squad_report.py").path)
        else { return nil }
        if stale, let fresh = try? url.bookmarkData(options: [], includingResourceValuesForKeys: nil, relativeTo: nil) {
            UserDefaults.standard.set(fresh, forKey: bookmarkKey)
        }
        return url
    }
}
