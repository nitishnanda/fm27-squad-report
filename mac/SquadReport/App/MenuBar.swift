import AppKit
import SwiftUI
import UserNotifications

/// The menu bar item: status, what's coming up, the latest news, plus Open, Reload, Settings and Quit.
struct MenuBarMenu: View {
    @Environment(AppModel.self) private var model
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        let state = MenuBarState(model: model)
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: state.symbol)
                Text(state.title).fontWeight(.semibold)
                Spacer()
            }
            if let report = model.store.report {
                Text("\(report.club.name) · \(Fmt.day(report.gameDate))").font(.callout).foregroundStyle(.secondary)
                let coming = report.news.filter { $0.kind.hasPrefix("deal") || $0.kind.hasPrefix("loan") }.prefix(3)
                let latest = report.news.filter { !$0.kind.hasPrefix("deal") && !$0.kind.hasPrefix("loan") }.prefix(3)
                if !coming.isEmpty { section("Coming up", Array(coming)) }
                if !latest.isEmpty { section("Latest", Array(latest)) }
            }
            Divider()
            HStack {
                Button("Open") { open("main") }.keyboardShortcut("o")
                Button("Matchday") { open("matchday") }
                Button("Reload") { model.store.reload() }
                if case .failed = model.engine.phase { Button("Start Again") { model.retryEngine() } }
                Spacer()
                SettingsLink { Image(systemName: "gearshape") }.help("Settings (⌘,)")
                Button { NSApp.terminate(nil) } label: { Image(systemName: "power") }.help("Quit FM27 Companion")
            }
        }
        .padding(14)
        .frame(width: 320)
    }

    private func section(_ title: String, _ items: [NewsItem]) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            ForEach(Array(items.enumerated()), id: \.offset) { _, n in
                Text(n.text).font(.callout).lineLimit(2)
            }
        }
    }

    private func open(_ id: String) {
        openWindow(id: id)
        NSApp.activate()
        model.store.markSeen()
    }
}

/// The icon in the menu bar changes with the state, so you can tell at a glance.
struct MenuBarIcon: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        Image(systemName: MenuBarState(model: model).symbol)
            .symbolEffect(.bounce, value: MenuBarState(model: model).symbol)
            .accessibilityLabel("FM27 Companion: \(MenuBarState(model: model).title)")
    }
}

/// "Up to date" / "Reading your save, step 3 of 8" / "New report ready" / "Engine problem".
struct MenuBarState {
    let title: String
    let symbol: String

    @MainActor
    init(model: AppModel) {
        let store = model.store
        if let step = store.buildStep {
            title = "Reading your save, step \(step.index + 1) of \(step.of)"
            symbol = "hourglass"
        } else if case .failed = model.engine.phase {
            title = "Engine problem: open the app to see why"
            symbol = "exclamationmark.triangle"
        } else if model.needsFolder {
            title = "Choose your FM27 Companion folder to start"
            symbol = "sportscourt"
        } else if store.unseenUpdate {
            title = "New report ready"
            symbol = "sportscourt.fill"
        } else if store.report != nil, store.reachable {
            title = "Up to date"
            symbol = "sportscourt"
        } else {
            title = "Starting…"
            symbol = "hourglass"
        }
    }
}

/// "Report updated: 22 Nov 2026" when a new save has been read while you're in FM.
enum Notifier {
    /// Asks macOS for permission whenever it hasn't decided yet (a "no" is respected: it isn't asked again).
    @MainActor
    static func askOnce() {
        Task {
            let center = UNUserNotificationCenter.current()
            if await center.notificationSettings().authorizationStatus == .notDetermined {
                _ = try? await center.requestAuthorization(options: [.alert, .sound])
            }
        }
    }

    static func reportUpdated(club: String, gameDate: String?) {
        post(title: "Report updated: \(Fmt.day(gameDate))",
             body: "\(club): your latest save has been read. Open FM27 Companion to see it.", id: "report-updated")
    }

    /// From Settings, so you can see what they look like.
    static func test(club: String?, gameDate: String?) {
        post(title: "Report updated: \(Fmt.day(gameDate))",
             body: "\(club ?? "Your club"): your latest save has been read. Open FM27 Companion to see it. (This one's a test.)", id: "test")
    }

    private static func post(title: String, body: String, id: String) {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: id, content: content, trigger: nil))
    }
}

/// Shows banners even while the app is in front (only the test button posts then).
final class NotificationPresenter: NSObject, UNUserNotificationCenterDelegate, @unchecked Sendable {
    static let shared = NotificationPresenter()
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async
        -> UNNotificationPresentationOptions { [.banner, .sound] }
}
