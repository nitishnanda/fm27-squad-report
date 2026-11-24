import SwiftUI

struct ContentView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        if model.needsFolder {
            WelcomeView()
        } else {
            NavigationSplitView {
                Sidebar()
                    .navigationSplitViewColumnWidth(min: 190, ideal: 220, max: 300)
            } detail: {
                Detail()
            }
            .toolbar {
                ToolbarItem(placement: .navigation) { ClubChip() }
                ToolbarItemGroup(placement: .primaryAction) {
                    EngineStatusPill()
                    Button {
                        model.openInBrowser()
                    } label: {
                        Label("Open in Browser", systemImage: "safari")
                    }
                    .help("Open this page in the web app (⇧⌘O)")
                }
            }
            .navigationTitle(model.route.title)
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

    var body: some View {
        if let report = model.store.report {
            page(report)
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
        if let step = model.store.buildStep {
            HStack(spacing: 10) {
                ProgressView(value: Double(step.index + 1), total: Double(step.of)).frame(width: 120)
                Text("Reading your latest save · \(step.label) (\(step.index + 1) of \(step.of))")
                Spacer()
            }
            .font(.callout)
            .padding(.horizontal, 16).padding(.vertical, 7)
            .background(.bar)
        } else if case .failed(let why) = model.engine.phase {
            HStack(spacing: 10) {
                Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Palette.verdict("amber"))
                Text("Showing your last report. \(why)").lineLimit(2)
                Spacer()
                Button("Try again") { model.engine.retry() }
            }
            .font(.callout)
            .padding(.horizontal, 16).padding(.vertical, 7)
            .background(.bar)
        } else if model.store.fromCache {
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text("Showing your last report while the engine starts…").foregroundStyle(.secondary)
                Spacer()
            }
            .font(.callout)
            .padding(.horizontal, 16).padding(.vertical, 6)
            .background(.bar)
        }
    }
}

/// The club in the toolbar: its colour and name, so you know whose save this is.
private struct ClubChip: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        if let club = model.store.report?.club {
            HStack(spacing: 6) {
                Circle().fill(Color(hex: club.kit)).frame(width: 10, height: 10)
                    .overlay(Circle().stroke(.primary.opacity(0.2)))
                Text(club.name).font(.headline)
            }
            .padding(.horizontal, 4)
            .accessibilityElement(children: .combine)
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
                ProgressView().controlSize(.mini)
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
            return ("Up to date", .green, false)
        }
    }

    private var help: String {
        switch model.engine.phase {
        case .attached: "Using the engine that's already running on this Mac"
        case .running: "The app's engine is watching your FM27 saves"
        case .failed(let why), .restarting(let why): why
        default: "Squad Report engine"
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
