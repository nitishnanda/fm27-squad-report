import Foundation

/// The six sections and their pages, the same as the web app's navbar (and its #hash routes).
enum AppSection: Int, CaseIterable, Identifiable, Sendable {
    case home, team, tactics, sandbox, transfers, stats
    var id: Int { rawValue }

    var title: String {
        switch self {
        case .home: "Home"
        case .team: "Team"
        case .tactics: "Tactics"
        case .sandbox: "Sandbox"
        case .transfers: "Transfers"
        case .stats: "Stats"
        }
    }

    var pages: [Route] {
        switch self {
        case .home: [.home]
        case .team: [.xis, .positions, .squad]
        case .tactics: [.fit, .training]
        case .sandbox: [.sandbox]
        case .transfers: [.transfers]
        case .stats: [.stats]
        }
    }
}

enum Route: String, CaseIterable, Identifiable, Hashable, Sendable {
    case home, xis, positions, squad, fit, training, sandbox, transfers, stats
    var id: String { rawValue }

    var title: String {
        switch self {
        case .home: "Home"
        case .xis: "Best XIs"
        case .positions: "Positions"
        case .squad: "Squad list"
        case .fit: "Tactical fit"
        case .training: "Training"
        case .sandbox: "Sandbox"
        case .transfers: "Transfers"
        case .stats: "Stats"
        }
    }

    var symbol: String {
        switch self {
        case .home: "house"
        case .xis: "sportscourt"
        case .positions: "square.grid.3x3"
        case .squad: "person.3"
        case .fit: "chart.bar.xaxis"
        case .training: "figure.run"
        case .sandbox: "slider.horizontal.3"
        case .transfers: "arrow.left.arrow.right"
        case .stats: "list.number"
        }
    }

    var section: AppSection { AppSection.allCases.first { $0.pages.contains(self) } ?? .home }

    /// The web app's address for this page, e.g. "team/squad".
    var webHash: String {
        switch self {
        case .home: "home"
        case .xis: "team/xis"
        case .positions: "team/positions"
        case .squad: "team/squad"
        case .fit: "tactics/fit"
        case .training: "tactics/training"
        case .sandbox: "sandbox"
        case .transfers: "transfers"
        case .stats: "stats"
        }
    }

    /// The web app's news items carry a route like "team/squad".
    init?(webHash: String) {
        guard let match = Route.allCases.first(where: { $0.webHash == webHash }) else { return nil }
        self = match
    }

    /// Pages drawn natively so far; the others open in the web app until their phase lands.
    var isNative: Bool { [.home, .xis, .positions, .squad].contains(self) }
}
