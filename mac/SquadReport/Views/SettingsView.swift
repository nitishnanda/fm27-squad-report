import CoreImage.CIFilterBuiltins
import ServiceManagement
import SwiftUI
import UserNotifications

/// Settings: where the engine runs from, open at login, the look, potential stars, and phone access with QR codes.
struct SettingsView: View {
    var body: some View {
        TabView {
            GeneralSettings().tabItem { Label("General", systemImage: "gearshape") }
            LookSettings().tabItem { Label("Look", systemImage: "paintpalette") }
            PhoneSettings().tabItem { Label("Phone", systemImage: "iphone") }
        }
        .frame(width: 560, height: 560)
        .scenePadding()
    }
}

// MARK: - general

private struct GeneralSettings: View {
    @Environment(AppModel.self) private var model
    @AppStorage("showPotential") private var showPotential = true
    @State private var loginItem = SMAppService.mainApp.status == .enabled
    @State private var loginProblem: String?
    @State private var notifications = "Checking…"

    var body: some View {
        Form {
            Section("Engine") {
                if BundledEngine.isAvailable {
                    LabeledContent("Runs from", value: model.usesBundledEngine ? "Inside the app" : "Your project folder")
                    Text(model.usesBundledEngine
                         ? "Python and the save reader come with the app. Your star history, phone key and scouting list are kept in Application Support."
                         : "Uses fm27_squad_report.py and .venv from the folder below, like Run Squad Report.command. Handy when you're changing the script.")
                        .font(.caption).foregroundStyle(.secondary)
                    if model.usesBundledEngine {
                        Button("Show the App's Files in Finder") {
                            NSWorkspace.shared.activateFileViewerSelecting([BundledEngine.home])
                        }
                    }
                    Toggle("Run the engine from a project folder instead", isOn: Binding(
                        get: { !model.usesBundledEngine },
                        set: { model.useFolderEngine($0) }))
                }
                if !model.usesBundledEngine {
                    LabeledContent("Folder") {
                        Text(model.folder?.path(percentEncoded: false) ?? "Not chosen yet").lineLimit(2).truncationMode(.middle)
                            .textSelection(.enabled)
                    }
                    Button("Choose Another Folder…") { chooseProjectFolder(model) }
                }
            }
            Section("Starting up") {
                Toggle("Open Squad Report when you log in", isOn: $loginItem)
                    .onChange(of: loginItem) { _, on in setLogin(on) }
                if let loginProblem {
                    Text(loginProblem).font(.caption).foregroundStyle(Palette.verdict("amber"))
                }
                LabeledContent("Notifications", value: notifications)
                Text("You get one when a new save has been read while you're in FM.").font(.caption).foregroundStyle(.secondary)
                if notifications == "Not asked yet" {
                    Button("Turn On Notifications…") {
                        Task {
                            _ = try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound])
                            await refreshNotifications()
                        }
                    }
                } else if notifications.hasPrefix("Off") {
                    Button("Open Notification Settings…") {
                        let id = Bundle.main.bundleIdentifier ?? "com.squadreport.mac"
                        if let url = URL(string: "x-apple.systempreferences:com.apple.Notifications-Settings.extension?id=\(id)") {
                            NSWorkspace.shared.open(url)
                        }
                    }
                } else if notifications == "On" {
                    Button("Send Test Notification") {
                        Notifier.test(club: model.store.report?.club.name, gameDate: model.store.report?.gameDate)
                    }
                }
            }
            Section("Ratings") {
                Toggle("Show potential stars", isOn: $showPotential)
                Text("Potential comes from FM's hidden potential: the only hidden number this app uses, and only for players 23 and under who could grow by a star or more. Turn it off for no spoilers at all.")
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
        .formStyle(.grouped)
        .onAppear { model.refreshFolder() }
        .task { await refreshNotifications() }
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.didBecomeActiveNotification)) { _ in
            Task { await refreshNotifications() }   // back from System Settings
        }
    }

    private func refreshNotifications() async {
        let s = await UNUserNotificationCenter.current().notificationSettings()
        notifications = switch s.authorizationStatus {
        case .authorized, .provisional: "On"
        case .denied: "Off (turn them on in System Settings › Notifications)"
        default: "Not asked yet"
        }
    }

    private func setLogin(_ on: Bool) {
        do {
            if on { try SMAppService.mainApp.register() } else { try SMAppService.mainApp.unregister() }
            loginProblem = nil
        } catch {
            loginProblem = "macOS didn't allow it: \(error.localizedDescription). Moving the app into Applications usually fixes this."
            loginItem = SMAppService.mainApp.status == .enabled
        }
    }
}

// MARK: - look

private struct LookSettings: View {
    @AppStorage("look") private var lookName = Look.original.rawValue

    var body: some View {
        Form {
            Picker("Look", selection: $lookName) {
                ForEach(Look.allCases) { look in
                    VStack(alignment: .leading, spacing: 2) {
                        Text(look.title)
                        Text(look.note).font(.caption).foregroundStyle(.secondary)
                    }
                    .tag(look.rawValue)
                }
            }
            .pickerStyle(.radioGroup)
            Text("The web app's other looks stay in the web app. Glass + scoreboard is always dark.")
                .font(.caption).foregroundStyle(.secondary)
        }
        .formStyle(.grouped)
    }
}

// MARK: - phone

private struct PhoneSettings: View {
    @Environment(AppModel.self) private var model
    @AppStorage("phoneAccess") private var phoneAccess = true
    @State private var links: [PhoneLink] = []
    @State private var loading = true

    var body: some View {
        Form {
            Section {
                Toggle("Let my iPhone open the report over home Wi-Fi", isOn: $phoneAccess)
                    .onChange(of: phoneAccess) { _, _ in
                        model.engine.restart()
                        Task { try? await Task.sleep(for: .seconds(6)); await load() }
                    }
                Text(phoneAccess
                     ? "Only devices with the link's key get in, and the Mac app's data feed never leaves this Mac."
                     : "The report stays on this Mac only.")
                    .font(.caption).foregroundStyle(.secondary)
                if model.engine.phase == .attached {
                    Text("The engine was started outside the app (Run Squad Report.command), so this applies the next time the app starts it.")
                        .font(.caption).foregroundStyle(Palette.verdict("amber"))
                }
            }
            if phoneAccess {
                Section("Scan with your iPhone's camera") {
                    if loading {
                        ProgressView().frame(maxWidth: .infinity)
                    } else if links.isEmpty {
                        Text("No phone links yet: the engine needs to be running with phone access on.").foregroundStyle(.secondary)
                    } else {
                        HStack(alignment: .top, spacing: 24) {
                            ForEach(links) { link in
                                VStack(spacing: 6) {
                                    QRCode(text: link.url).frame(width: 160, height: 160)
                                    Text(link.kind == "name" ? "Works on any Wi-Fi this Mac joins" : "This network's address")
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                            }
                        }
                        .frame(maxWidth: .infinity)
                        Text("Then Share › Add to Home Screen on the iPhone to keep it as an app.").font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }
        .formStyle(.grouped)
        .task { await load() }
    }

    private func load() async {
        loading = true
        links = (try? await model.engine.client.phone().links) ?? []
        loading = false
    }
}

/// A QR code drawn with Core Image, crisp at any size.
private struct QRCode: View {
    let text: String

    var body: some View {
        if let image = Self.make(text) {
            Image(nsImage: image).interpolation(.none).resizable().scaledToFit()
                .padding(8).background(.white, in: RoundedRectangle(cornerRadius: 8))
                .accessibilityLabel("QR code for the phone link")
        }
    }

    static func make(_ text: String) -> NSImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(text.utf8)
        filter.correctionLevel = "M"
        guard let output = filter.outputImage?.transformed(by: CGAffineTransform(scaleX: 8, y: 8)),
              let cg = CIContext().createCGImage(output, from: output.extent) else { return nil }
        return NSImage(cgImage: cg, size: NSSize(width: output.extent.width, height: output.extent.height))
    }
}
