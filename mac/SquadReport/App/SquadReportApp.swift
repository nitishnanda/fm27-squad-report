import AppKit
import SwiftUI
import UniformTypeIdentifiers
import UserNotifications

@main
struct SquadReportApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate

    init() {
        Fonts.register()   // before any window: SwiftUI looks the fonts up once
    }

    var body: some Scene {
        // One main window. Closing it keeps the app in the Dock and the menu bar, still watching your saves.
        Window("Squad Report", id: "main") {
            ContentView()
                .environment(delegate.model)
                .themed()
                .frame(minWidth: 900, minHeight: 600)
        }
        .defaultSize(width: 1320, height: 860)
        .commands { AppCommands(model: delegate.model) }

        MenuBarExtra {
            MenuBarMenu().environment(delegate.model)
        } label: {
            MenuBarIcon().environment(delegate.model)
        }

        Settings {
            SettingsView().environment(delegate.model).themed()
        }
    }
}

/// Owns the model so the engine can be stopped when the app quits.
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let model = AppModel()

    func applicationDidFinishLaunching(_ notification: Notification) {
        UNUserNotificationCenter.current().delegate = NotificationPresenter.shared
        Notifier.askOnce()
    }

    func applicationDidBecomeActive(_ notification: Notification) {
        model.store.markSeen()
    }

    func applicationWillTerminate(_ notification: Notification) {
        model.engine.stop()
    }

    /// Clicking the Dock icon with no window open brings the window back.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { NSApp.windows.first { $0.identifier?.rawValue == "main" || $0.title == "Squad Report" }?.makeKeyAndOrderFront(nil) }
        return true
    }
}

struct AppCommands: Commands {
    let model: AppModel

    var body: some Commands {
        // one window is enough: File › New becomes picking the project folder
        CommandGroup(replacing: .newItem) {
            Button("Choose Project Folder…") { chooseProjectFolder(model) }
        }
        CommandGroup(after: .toolbar) {
            Button("Reload Report") { model.store.reload() }
                .keyboardShortcut("r")
            Button("Open in Browser") { model.openInBrowser() }
                .keyboardShortcut("o", modifiers: [.command, .shift])
            Divider()
        }
        CommandMenu("Go") {
            ForEach(AppSection.allCases) { section in
                Button(section.title) { model.go(section) }
                    .keyboardShortcut(KeyEquivalent(Character("\(section.rawValue + 1)")), modifiers: .command)
            }
            Divider()
            Button("Previous Page in Section") { model.step(-1) }
                .keyboardShortcut("[", modifiers: .command)
            Button("Next Page in Section") { model.step(1) }
                .keyboardShortcut("]", modifiers: .command)
        }
    }
}

@MainActor
func chooseProjectFolder(_ model: AppModel) {
    let panel = NSOpenPanel()
    panel.canChooseDirectories = true
    panel.canChooseFiles = false
    panel.allowsMultipleSelection = false
    panel.prompt = "Use This Folder"
    panel.message = "Pick the folder with Run Squad Report.command and fm27_squad_report.py in it."
    if panel.runModal() == .OK, let url = panel.url { model.choose(folder: url) }
}
