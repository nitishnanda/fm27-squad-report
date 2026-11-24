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
        } else if model.folder == nil {
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
    private static let askedKey = "askedForNotifications"

    @MainActor
    static func askOnce() {
        guard !UserDefaults.standard.bool(forKey: askedKey) else { return }
        UserDefaults.standard.set(true, forKey: askedKey)
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in }
    }

    static func reportUpdated(club: String, gameDate: String?) {
        let content = UNMutableNotificationContent()
        content.title = "Report updated: \(Fmt.day(gameDate))"
        content.body = "\(club): your latest save has been read. Open Squad Report to see it."
        let request = UNNotificationRequest(identifier: "report-updated", content: content, trigger: nil)
        UNUserNotificationCenter.current().add(request)
    }
}
