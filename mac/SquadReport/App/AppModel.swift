import AppKit
import Foundation
import Observation

/// Everything the window and the menus share: the engine (and where it comes from), the report and where you are.
@MainActor @Observable
final class AppModel {
    let engine = Engine()
    let store = ReportStore()

    private(set) var folder: URL?
    var folderProblem: String?
    var route: Route = .home
    /// The status key popover (toolbar button, Help › Status Key).
    var showKey = false
    /// ⌘K Quick Open, and the player panel on the right (⌥⌘I).
    var showQuickOpen = false
    var showInspector = false
    var inspected: Int?
    /// A name for the Squad list to search for when you jump there from a player's menu.
    var squadSearch: String?
    /// The last page you opened in each section, so ⌘2 goes back to the Team page you were on.
    private var lastPage: [AppSection: Route] = [:]

    private static let bookmarkKey = "projectFolderBookmark"
    static let folderEngineKey = "useProjectFolderEngine"

    /// The engine inside the app, unless this build has none or you asked for a project folder's (Settings › General).
    private(set) var usesBundledEngine: Bool

    /// The welcome screen: only when the engine has to come from a project folder and none is chosen.
    var needsFolder: Bool { !usesBundledEngine && folder == nil }

    init() {
        folder = Self.restoreFolder()
        usesBundledEngine = BundledEngine.isAvailable && !UserDefaults.standard.bool(forKey: Self.folderEngineKey)
        if let demo = ReportStore.demoPath {
            folder = folder ?? URL(filePath: demo).deletingLastPathComponent()
            store.showDemo(demo)
            return
        }
        store.follow(engine)
        if let source = engineSource { engine.start(source) }
    }

    private var engineSource: Engine.Source? {
        if usesBundledEngine { return .bundled(importFrom: folder) }
        return folder.map { .folder($0) }
    }

    /// Settings: run the engine from a project folder (to work on the script) or the one inside the app.
    func useFolderEngine(_ on: Bool) {
        UserDefaults.standard.set(on, forKey: Self.folderEngineKey)
        usesBundledEngine = BundledEngine.isAvailable && !on
        refreshFolder()
        if let source = engineSource { engine.switchSource(to: source) }
    }

    /// "Try again": looks for a moved project folder first.
    func retryEngine() {
        refreshFolder()
        if let source = engineSource { engine.retry(with: source) } else { engine.retry() }
    }

    /// The folder was moved or renamed since launch: follow the bookmark to where it is now.
    func refreshFolder() {
        if let folder, FileManager.default.fileExists(atPath: folder.appending(path: "fm27_squad_report.py").path) { return }
        folder = Self.restoreFolder()
    }

    // MARK: - navigation

    /// Pages you've been on, for Back and Forward (like Finder or Safari).
    private(set) var backStack: [Route] = []
    private(set) var forwardStack: [Route] = []

    func go(_ route: Route) {
        lastPage[route.section] = route
        guard route != self.route else { return }
        backStack.append(self.route)
        if backStack.count > 50 { backStack.removeFirst() }
        forwardStack.removeAll()
        self.route = route
    }

    var canGoBack: Bool { !backStack.isEmpty }
    var canGoForward: Bool { !forwardStack.isEmpty }

    func goBack() {
        guard let previous = backStack.popLast() else { return }
        forwardStack.append(route)
        lastPage[previous.section] = previous
        route = previous
    }

    func goForward() {
        guard let next = forwardStack.popLast() else { return }
        backStack.append(route)
        lastPage[next.section] = next
        route = next
    }

    /// Shows a player in the side panel.
    func inspect(_ uid: Int) {
        inspected = uid
        showInspector = true
    }

    func showInSquad(_ player: Player) {
        squadSearch = player.name
        go(.squad)
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
    /// so it's still found if the folder is moved or renamed. With the engine inside the app it's only used once,
    /// to copy your star history, phone key and scouting list over.
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
        guard !usesBundledEngine else { return }   // the app's own engine doesn't need it
        if changed { engine.switchSource(to: .folder(url)) } else { engine.start(.folder(url)) }
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
