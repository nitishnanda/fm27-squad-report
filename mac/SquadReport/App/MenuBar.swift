import AppKit
import SwiftUI
import UserNotifications

/// The menu bar item: how the engine is doing, in a word, plus Open, Reload, Settings and Quit.
struct MenuBarMenu: View {
    @Environment(AppModel.self) private var model
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Text(MenuBarState(model: model).title)
        if let report = model.store.report {
            Text("\(report.club.name) · \(Fmt.day(report.gameDate))")
        }
        Divider()
        Button("Open Squad Report") {
            openWindow(id: "main")
            NSApp.activate()
            model.store.markSeen()
        }
        .keyboardShortcut("o")
        Button("Reload Report") { model.store.reload() }
        if case .failed = model.engine.phase {
            Button("Start the Engine Again") { model.engine.retry() }
        }
        Divider()
        SettingsLink { Text("Settings…") }
            .keyboardShortcut(",")
        Button("Quit Squad Report") { NSApp.terminate(nil) }
            .keyboardShortcut("q")
    }
}

/// The icon in the menu bar changes with the state, so you can tell at a glance.
struct MenuBarIcon: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        Image(systemName: MenuBarState(model: model).symbol)
            .accessibilityLabel("Squad Report: \(MenuBarState(model: model).title)")
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
            title = "Choose your Squad Report folder to start"
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
             body: "\(club): your latest save has been read. Open Squad Report to see it.", id: "report-updated")
    }

    /// From Settings, so you can see what they look like.
    static func test(club: String?, gameDate: String?) {
        post(title: "Report updated: \(Fmt.day(gameDate))",
             body: "\(club ?? "Your club"): your latest save has been read. Open Squad Report to see it. (This one's a test.)", id: "test")
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
