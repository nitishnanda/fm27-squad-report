import AppKit
import SwiftUI
import UniformTypeIdentifiers

@main
struct SquadReportApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate

    var body: some Scene {
        WindowGroup("Squad Report") {
            ContentView()
                .environment(delegate.model)
                .frame(minWidth: 900, minHeight: 600)
        }
        .defaultSize(width: 1320, height: 860)
        .commands { AppCommands(model: delegate.model) }
    }
}

/// Owns the model so the engine can be stopped when the app quits.
@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let model = AppModel()

    func applicationWillTerminate(_ notification: Notification) {
        model.engine.stop()
    }
}

struct AppCommands: Commands {
    let model: AppModel

    var body: some Commands {
        // one window is enough: File › New becomes picking the project folder
        CommandGroup(replacing: .newItem) {
            Button("Choose Project Folder…") { chooseFolder() }
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

    private func chooseFolder() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        panel.prompt = "Use This Folder"
        panel.message = "Pick the folder with Run Squad Report.command and fm27_squad_report.py in it."
        if panel.runModal() == .OK, let url = panel.url { model.choose(folder: url) }
    }
}
