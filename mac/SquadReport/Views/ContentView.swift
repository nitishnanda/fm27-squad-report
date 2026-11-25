import SwiftUI

struct ContentView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.openWindow) private var openWindow

    /// "Liverpool · 31 Dec 2026" under the page name, so the toolbar needn't repeat the club.
    private var subtitle: String {
        guard let report = model.store.report else { return "" }
        return "\(report.club.name) · \(Fmt.day(report.gameDate))"
    }

    var body: some View {
        @Bindable var model = model
        if model.needsFolder {
            WelcomeView()
        } else {
            NavigationSplitView {
                Sidebar()
                    .navigationSplitViewColumnWidth(min: 190, ideal: 220, max: 300)
            } detail: {
                Detail()
            }
            .inspector(isPresented: $model.showInspector) {
                InspectorPanel()
                    .inspectorColumnWidth(min: 300, ideal: 330, max: 420)
            }
            .sheet(isPresented: $model.showQuickOpen) { QuickOpen() }
            .toolbar {
                ToolbarItemGroup(placement: .navigation) {
                    ControlGroup {
                        Button { model.goBack() } label: { Label("Back", systemImage: "chevron.left") }
                            .disabled(!model.canGoBack)
                            .help("Back (⌘[)")
                        Button { model.goForward() } label: { Label("Forward", systemImage: "chevron.right") }
                            .disabled(!model.canGoForward)
                            .help("Forward (⌘])")
                    }
                    .controlGroupStyle(.navigation)
                }
                ToolbarItemGroup(placement: .primaryAction) {
                    EngineStatusPill()
                    Button { model.showQuickOpen = true } label: { Label("Quick Open", systemImage: "magnifyingglass") }
                        .help("Search pages, players and actions (⌘K)")
                    Button { openWindow(id: "matchday") } label: { Label("Matchday", systemImage: "pin") }
                        .labelStyle(.titleAndIcon)
                        .help("A small window that floats over FM (⇧⌘M)")
                    SettingsLink { Label("Settings", systemImage: "gearshape") }
                        .help("Look, folder, notifications, phone access (⌘,)")
                }
            }
            .navigationTitle(model.route.title)
            .navigationSubtitle(subtitle)
        }
    }
}

/// The side panel: the player you picked from ⌘K, a right-click menu or a double-click in the Squad list.
private struct InspectorPanel: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        if let report = model.store.report, let player = report.player(model.inspected) {
            VStack(spacing: 0) {
                HStack {
                    Spacer()
                    Button { model.showInspector = false } label: { Image(systemName: "xmark.circle.fill") }
                        .buttonStyle(.plain).foregroundStyle(.secondary).help("Close the side panel (⌥⌘I)")
                }
                .padding(.horizontal, 12).padding(.top, 8)
                ScrollView { PlayerCard(player: player, report: report, fixedWidth: false) }
            }
        } else {
            ContentUnavailableView("Pick a player", systemImage: "person",
                                   description: Text("Press ⌘K, right-click a player, or double-click one in the Squad list."))
        }
    }
}

private struct Sidebar: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        @Bindable var model = model
        List(selection: Binding(get: { model.route }, set: { if let r = $0 { model.go(r) } })) {
            row(.home)
            Section("Team") { ForEach(AppSection.team.pages) { row($0) } }
            Section("Tactics") { ForEach(AppSection.tactics.pages) { row($0) } }
            Section("Club") {
                row(.sandbox)
                row(.transfers)
                row(.stats)
            }
        }
        .listStyle(.sidebar)
        .tint(Palette.brand)     // the app's own green for the selection, white text on it, like a system accent
    }

    @ViewBuilder
    private func row(_ route: Route) -> some View {
        Label(route.title, systemImage: route.symbol)
            .badge(badge(for: route))
            .tag(route)
    }

    /// The same counts as the web app's navbar: positions that need work, the squad, moves coming up.
    private func badge(for route: Route) -> Int {
        guard let report = model.store.report else { return 0 }
        switch route {
        case .home: return report.verdicts.filter(\.needsWork).count
        case .squad: return report.players.filter { $0.location == "squad" && !$0.youth }.count
        case .transfers: return report.players.filter { !$0.status.moves.isEmpty }.count
        default: return 0
        }
    }
}

private struct Detail: View {
    @Environment(AppModel.self) private var model
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    /// The club panel that slides away when the first report arrives.
    @State private var wipe: Club?
    /// `-demoLoader YES` with a demo report: play the loader's eight steps, then the wipe (for checking the motion).
    @State private var demoStep: Int? = UserDefaults.standard.bool(forKey: "demoLoader") && ReportStore.demoPath != nil ? -1 : nil

    var body: some View {
        content
            .overlay { if let club = wipe { ClubWipe(club: club) { wipe = nil } } }
            .onChange(of: model.store.report == nil) { wasEmpty, isEmpty in
                if wasEmpty, !isEmpty, !reduceMotion, let club = model.store.report?.club { wipe = club }
            }
            .task {
                if UserDefaults.standard.bool(forKey: "demoWipe"), let club = model.store.report?.club { wipe = club; return }
                guard demoStep != nil else { return }
                for i in -1..<ReportStore.defaultSteps.count {
                    demoStep = i
                    try? await Task.sleep(for: .seconds(1.1 * Motion.slow))
                }
                demoStep = nil
                if !reduceMotion, let club = model.store.report?.club { wipe = club }
            }
    }

    @ViewBuilder
    private var content: some View {
        if let step = demoStep {
            LoaderBody(steps: ReportStore.defaultSteps, current: step)
        } else if let report = model.store.report {
            page(report)
                .modifier(PageEntrance())
                .id(model.route)            // a fresh page (and a fresh entrance) per route; the old one goes at once
                .safeAreaInset(edge: .top, spacing: 0) { Banner() }
                .pageBackground()
        } else if let problem = model.store.problem {
            ProblemView(title: "Can't show the report", message: problem)
        } else {
            EngineGate()
        }
    }

    @ViewBuilder
    private func page(_ report: Report) -> some View {
        switch model.route {
        case .home: HomeView(report: report)
        case .xis: BestXIsView(report: report)
        case .positions: PositionsView(report: report)
        case .squad: SquadListView(report: report)
        case .fit: TacticalFitView(report: report)
        case .training: TrainingView(report: report)
        case .transfers: TransfersView(report: report)
        case .stats: StatsView(report: report)
        case .sandbox: SandboxView(report: report)
        }
    }
}

/// A thin strip over the page while a newer save is being read, or when the engine has a problem.
private struct Banner: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        if case .failed(let why) = model.engine.phase {
            HStack(spacing: 10) {
                Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Palette.verdict("amber"))
                Text("Showing your last report. \(why)").lineLimit(2)
                Spacer()
                Button("Try again") { model.retryEngine() }
            }
            .font(.callout)
            .padding(.horizontal, 16).padding(.vertical, 7)
            .background(.bar)
        }
    }
}

/// Up to date / Reading your save, step 3 of 8 / Engine problem.
struct EngineStatusPill: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        let (text, color, busy) = state
        HStack(spacing: 6) {
            if busy {
                PulseDot(color: .orange)      // the web's .ah-live.busy: an amber dot that pulses while a save is read
            } else {
                Circle().fill(color).frame(width: 8, height: 8)
            }
            Text(text).font(.callout).foregroundStyle(.secondary)
        }
        .padding(.horizontal, 6)
        .help(help)
        .accessibilityElement(children: .combine)
    }

    private var state: (String, Color, Bool) {
        if ReportStore.demoPath != nil { return ("Demo report", .blue, false) }
        if let step = model.store.buildStep { return ("Reading save · \(step.index + 1) of \(step.of)", .orange, true) }
        switch model.engine.phase {
        case .preparing: return ("Setting up", .orange, true)
        case .starting, .idle: return ("Starting", .orange, true)
        case .restarting: return ("Restarting", .orange, true)
        case .failed: return ("Engine problem", .red, false)
        case .stopped: return ("Stopped", .secondary, false)
        case .running, .attached:
            if !model.store.reachable { return ("Reconnecting", .orange, true) }
            if model.store.fromCache { return ("Opening your last report", .orange, true) }
            return ("Up to date", .green, false)
        }
    }

    private var help: String {
        switch model.engine.phase {
        case .attached: "Using the engine that's already running on this Mac"
        case .running: "The app's engine is watching your FM27 saves"
        case .failed(let why), .restarting(let why): why
        default: "FM27 Companion engine"
        }
    }
}

struct ProblemView: View {
    let title: String
    let message: String
    var action: (title: String, run: () -> Void)?

    var body: some View {
        ContentUnavailableView {
            Label(title, systemImage: "exclamationmark.triangle")
        } description: {
            Text(message).textSelection(.enabled)
        } actions: {
            if let action { Button(action.title, action: action.run).buttonStyle(.borderedProminent) }
        }
    }
}

/// A dot with a ring that grows and fades, over and over (the web's `lpulse`). Still with Reduce Motion on.
struct PulseDot: View {
    let color: Color
    @State private var out = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        Circle().fill(color).frame(width: 8, height: 8)
            .background {
                if !reduceMotion {
                    Circle().stroke(color, lineWidth: 2)
                        .scaleEffect(out ? 2.4 : 1)
                        .opacity(out ? 0 : 0.7)
                }
            }
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeOut(duration: 1.4 * Motion.slow).repeatForever(autoreverses: false)) { out = true }
            }
            .accessibilityHidden(true)
    }
}
