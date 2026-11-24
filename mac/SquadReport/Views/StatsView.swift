import Charts
import SwiftUI

/// Stats: season leaders, two charts (goal contributions and average ratings) and sortable tables for the first team
/// and the youth teams. All from the game's own match records.
struct StatsView: View {
    let report: Report

    enum Team: String, CaseIterable, Identifiable {
        case first = "First team", youth = "Youth teams"
        var id: String { rawValue }
    }
    @State private var team: Team = .first

    var body: some View {
        let first = StatRow.firstTeam(report)
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                Leaders(rows: first)
                if !first.isEmpty {
                    HStack(alignment: .top, spacing: 16) {
                        ContributionsChart(rows: first)
                        RatingsChart(rows: first)
                    }
                }
                HStack {
                    SectionTitle(team == .first ? "First team" : "Youth teams",
                                 sub: team == .first ? "all competitions this season · click a column to sort" : "appearances for your U21 and U18 sides")
                    Spacer()
                    Picker("Team", selection: $team) { ForEach(Team.allCases) { Text($0.rawValue).tag($0) } }
                        .pickerStyle(.segmented).labelsHidden().fixedSize()
                }
                StatsTable(rows: team == .first ? first : StatRow.youth(report), showTeam: team == .youth)
                    .frame(minHeight: 420)
            }
            .padding(24)
        }
    }
}

// MARK: - rows

struct StatRow: Identifiable, Sendable {
    let id: String
    let name: String
    let team: String
    let pos: String
    let age: Int
    let apps: Int
    let goals: Int
    let assists: Int
    let avg: Double          // -1 when there's no rating
    let cleanSheets: Int     // -1 when it doesn't apply (not a keeper or defender)
    let yellows: Int
    let reds: Int
    let keeper: Bool
    var contributions: Int { goals + assists }

    static let high = 7.20, low = 6.85   // the web app's colouring

    private init(_ p: Player, _ s: Player.SeasonStats, team: String, id: String) {
        self.id = id
        name = p.name
        self.team = team
        pos = p.best?.slot ?? "–"
        age = p.age ?? 0
        apps = s.apps
        goals = s.g
        assists = s.a
        avg = s.avg ?? -1
        cleanSheets = ["GK", "LB", "CB", "RB"].contains(p.best?.slot ?? "") ? (s.cs ?? 0) : -1
        yellows = s.y ?? 0
        reds = s.r ?? 0
        keeper = p.best?.slot == "GK"
    }

    static func firstTeam(_ report: Report) -> [StatRow] {
        report.players.compactMap { p in
            p.stats.flatMap { $0.apps > 0 ? StatRow(p, $0, team: "First team", id: "\(p.uid)") : nil }
        }
        .sorted { $0.apps > $1.apps }
    }

    static func youth(_ report: Report) -> [StatRow] {
        report.players.flatMap { p in
            (p.youthStats ?? []).enumerated().compactMap { i, s in
                guard s.apps > 0 else { return nil }
                let team = s.team.flatMap { report.teamNames?[String($0)] } ?? "Youth"
                return StatRow(p, s, team: team, id: "\(p.uid)-\(i)")
            }
        }
        .sorted { ($0.team, -$0.apps) < ($1.team, -$1.apps) }
    }
}

// MARK: - leaders

private struct Leaders: View {
    let rows: [StatRow]

    var body: some View {
        let most = rows.map(\.apps).max() ?? 0
        let floor = max(3, Int((Double(most) / 3).rounded()))
        VStack(alignment: .leading, spacing: 12) {
            SectionTitle("Season leaders", sub: "first team, all competitions")
            if rows.isEmpty {
                Text("No first-team appearances yet this season.").foregroundStyle(.secondary)
            } else {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 200), spacing: 10)], spacing: 10) {
                    card("Goals", rows) { Double($0.goals) }
                    card("Assists", rows) { Double($0.assists) }
                    card("Average rating · \(floor)+ apps", rows.filter { $0.avg >= 0 && $0.apps >= floor }, decimals: true) { $0.avg }
                    card("Appearances", rows) { Double($0.apps) }
                    card("Clean sheets · keepers", rows.filter(\.keeper)) { Double(max(0, $0.cleanSheets)) }
                }
            }
        }
    }

    private func card(_ label: String, _ pool: [StatRow], decimals: Bool = false, _ value: (StatRow) -> Double) -> some View {
        let ranked = pool.sorted { value($0) > value($1) }
        let top = ranked.first.map(value) ?? 0
        let leaders = ranked.filter { value($0) == top }
        let next = ranked.filter { value($0) != top }.prefix(2)
        let fmt: (Double) -> String = { decimals ? String(format: "%.2f", $0) : String(Int($0)) }
        return VStack(alignment: .leading, spacing: 4) {
            Text(label).font(.callout).foregroundStyle(.secondary)
            Text(top > 0 ? fmt(top) : "–").numberFont(34)
            Text(top > 0 ? (leaders.count == 2 ? "\(surname(leaders[0].name)) & \(surname(leaders[1].name))"
                            : leaders.count > 2 ? "\(leaders[0].name) +\(leaders.count - 1) more" : leaders.first?.name ?? "")
                         : "Nobody yet")
                .fontWeight(.bold).lineLimit(1)
            Text(next.isEmpty || top == 0 ? " " : "then " + next.map { "\(surname($0.name)) \(fmt(value($0)))" }.joined(separator: " · "))
                .font(.caption).foregroundStyle(.secondary).lineLimit(1)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .panel(10)
        .accessibilityElement(children: .combine)
    }
}

// MARK: - charts

/// Goals and assists, stacked, for everyone who's got one. The table below has every number too.
private struct ContributionsChart: View {
    let rows: [StatRow]

    var body: some View {
        let top = rows.filter { $0.contributions > 0 }.sorted { ($0.contributions, $0.goals) > ($1.contributions, $1.goals) }.prefix(12)
        VStack(alignment: .leading, spacing: 8) {
            Text("Goal contributions").font(.headline)
            Text("Goals and assists, all competitions").font(.caption).foregroundStyle(.secondary)
            if top.isEmpty {
                Text("No goals or assists yet this season.").foregroundStyle(.secondary).frame(height: 200)
            } else {
                Chart {
                    ForEach(Array(top)) { r in
                        BarMark(x: .value("Goals", r.goals), y: .value("Player", surname(r.name)), height: .ratio(0.5))
                            .foregroundStyle(by: .value("Type", "Goals"))
                            .annotation(position: .top, alignment: .leading, spacing: 2) {
                                Text("\(surname(r.name))  \(r.goals) + \(r.assists)").font(.caption).foregroundStyle(.secondary)
                            }
                        BarMark(x: .value("Assists", r.assists), y: .value("Player", surname(r.name)), height: .ratio(0.5))
                            .foregroundStyle(by: .value("Type", "Assists"))
                    }
                }
                .chartForegroundStyleScale(["Goals": Palette.brandHigh, "Assists": Palette.loanIn])
                .chartYAxis(.hidden)
                .chartLegend(position: .bottom)
                .chartXAxisLabel("Goals + assists")
                .frame(height: CGFloat(max(160, top.count * 36)))
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .panel(10)
    }
}

/// Average match rating for regulars, with the web app's colour bands: 7.20+ green, under 6.85 amber.
private struct RatingsChart: View {
    let rows: [StatRow]

    var body: some View {
        let most = rows.map(\.apps).max() ?? 0
        let floor = max(3, Int((Double(most) / 3).rounded()))
        let rated = rows.filter { $0.avg >= 0 && $0.apps >= floor }.sorted { $0.avg > $1.avg }.prefix(14)
        VStack(alignment: .leading, spacing: 8) {
            Text("Average rating").font(.headline)
            Text("Players with \(floor)+ apps · 7.20+ green, under 6.85 amber (the dashed lines)").font(.caption).foregroundStyle(.secondary)
            if rated.isEmpty {
                Text("Nobody has enough games yet.").foregroundStyle(.secondary).frame(height: 200)
            } else {
                // dots, not bars: bars must start at 0, and from 0 every rating looks the same
                let lo = min(6.0, (rated.map(\.avg).min() ?? 6.0) - 0.1)
                let hi = max(7.5, (rated.map(\.avg).max() ?? 7.5) + 0.1)
                Chart {
                    RuleMark(x: .value("Amber below", StatRow.low))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 3])).foregroundStyle(Palette.verdict("amber").opacity(0.6))
                    RuleMark(x: .value("Green from", StatRow.high))
                        .lineStyle(StrokeStyle(lineWidth: 1, dash: [3, 3])).foregroundStyle(Palette.transferIn.opacity(0.6))
                    ForEach(Array(rated)) { r in
                        RuleMark(xStart: .value("From", lo), xEnd: .value("Average rating", r.avg), y: .value("Player", surname(r.name)))
                            .lineStyle(StrokeStyle(lineWidth: 1)).foregroundStyle(Color.secondary.opacity(0.25))
                        PointMark(x: .value("Average rating", r.avg), y: .value("Player", surname(r.name)))
                            .symbolSize(90)
                            .foregroundStyle(r.avg >= StatRow.high ? Palette.transferIn : r.avg < StatRow.low ? Palette.verdict("amber") : Color.secondary)
                            .annotation(position: .trailing, spacing: 6) {
                                Text(String(format: "%.2f", r.avg)).font(.caption2).monospacedDigit().foregroundStyle(.secondary)
                            }
                            .annotation(position: .top, alignment: .leading, spacing: 4) {
                                Text(surname(r.name)).font(.caption).foregroundStyle(.secondary)
                            }
                    }
                }
                .chartXScale(domain: lo...hi)
                .chartYAxis(.hidden)
                .chartXAxisLabel("Average match rating (zoomed in: \(String(format: "%.1f", lo))–\(String(format: "%.1f", hi)))")
                .frame(height: CGFloat(max(160, rated.count * 36)))
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .panel(10)
    }
}

// MARK: - table

private struct StatsTable: View {
    let rows: [StatRow]
    let showTeam: Bool
    @State private var sortOrder = [KeyPathComparator(\StatRow.apps, order: .reverse)]

    var body: some View {
        if rows.isEmpty {
            ContentUnavailableView(showTeam ? "No youth-team appearances yet" : "No first-team appearances yet",
                                   systemImage: "list.number", description: Text("They show up here once games are played."))
        } else {
            Table(rows.sorted(using: sortOrder), sortOrder: $sortOrder) {
                TableColumn("Player", value: \.name) { r in
                    HStack(spacing: 6) {
                        Text(r.name).fontWeight(.semibold)
                        if showTeam { Text(r.team).font(.caption.weight(.bold)).foregroundStyle(.secondary) }
                    }
                }
                .width(min: 150, ideal: 210)
                TableColumn("Pos", value: \.pos) { Text($0.pos) }.width(40)
                TableColumn("Age", value: \.age) { Text("\($0.age)").monospacedDigit() }.width(36)
                TableColumn("Apps", value: \.apps) { Text("\($0.apps)").monospacedDigit() }.width(44)
                TableColumn("G", value: \.goals) { Text("\($0.goals)").monospacedDigit() }.width(34)
                TableColumn("A", value: \.assists) { Text("\($0.assists)").monospacedDigit() }.width(34)
                TableColumn("Avg", value: \.avg) { r in
                    Text(r.avg < 0 ? "–" : String(format: "%.2f", r.avg)).monospacedDigit()
                        .foregroundStyle(r.avg >= StatRow.high ? Palette.transferIn : r.avg >= 0 && r.avg < StatRow.low ? Palette.verdict("amber") : .primary)
                }
                .width(46)
                TableColumn("CS", value: \.cleanSheets) { r in Text(r.cleanSheets < 0 ? "–" : "\(r.cleanSheets)").monospacedDigit() }.width(36)
                TableColumn("Y / R", value: \.yellows) { r in Text("\(r.yellows) / \(r.reds)").monospacedDigit() }.width(50)
            }
        }
    }
}
