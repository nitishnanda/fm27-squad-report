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
            // Laid out from his Figma Make design (StatsView.tsx); the leader tiles keep his separate Figma (top rule).
            VStack(alignment: .leading, spacing: 24) {
                Leaders(rows: first)
                if !first.isEmpty {
                    HStack(alignment: .top, spacing: 16) {
                        ContributionsChart(rows: first)
                        RatingsChart(rows: first)
                    }
                }
                HStack {
                    SectionTitle(team == .first ? "First team statistics" : "Youth team statistics",
                                 sub: team == .first ? "All competitions this season · click a column header to sort" : "Appearances for your U21 and U18 sides")
                    Spacer()
                    PillPicker(options: Team.allCases.map { ($0.rawValue, $0) }, selection: $team)
                }
                StatsTable(rows: team == .first ? first : StatRow.youth(report), showTeam: team == .youth)
                    .scrollContentBackground(.hidden)
                    .frame(minHeight: 420)
                    .hubCard()
            }
            .frame(maxWidth: 1172, alignment: .leading)
            .padding(.horizontal, 24).padding(.vertical, 20)
            .frame(maxWidth: .infinity)
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
        VStack(alignment: .leading, spacing: 12) {
            SectionTitle("Season leaders", sub: "First team, all competitions", page: true)
            if rows.isEmpty {
                Text("No first-team appearances yet this season.").foregroundStyle(.secondary)
            } else {
                ViewThatFits(in: .horizontal) { cards(5); cards(3) }
            }
        }
    }

    /// One row of five at full width; three per row when the window is narrow.
    private func cards(_ perRow: Int) -> some View {
        let floor = max(3, Int((Double(rows.map(\.apps).max() ?? 0) / 3).rounded()))
        return LazyVGrid(columns: Array(repeating: GridItem(.flexible(minimum: 180), spacing: DS.Space.grid, alignment: .top), count: perRow),
                         alignment: .leading, spacing: DS.Space.l) {
            card("Goals", rows) { Double($0.goals) }
            card("Assists", rows) { Double($0.assists) }
            card("Average rating · \(floor)+ apps", rows.filter { $0.avg >= 0 && $0.apps >= floor }, decimals: true) { $0.avg }
            card("Appearances", rows) { Double($0.apps) }
            card("Clean sheets · keepers", rows.filter(\.keeper)) { Double(max(0, $0.cleanSheets)) }
        }
    }

    private func card(_ label: String, _ pool: [StatRow], decimals: Bool = false, _ value: (StatRow) -> Double) -> some View {
        // His Figma: one leader by name, then the next two with their numbers, even when they're level with the leader
        // (no "A & B" or "+10 more"). Level players are ordered by games played, then name, so it doesn't jump around.
        let ranked = pool.sorted { (value($0), $0.apps, $1.name) > (value($1), $1.apps, $0.name) }
        let top = ranked.first.map(value) ?? 0
        let next = ranked.dropFirst().filter { value($0) > 0 }.prefix(2)
        let fmt: (Double) -> String = { decimals ? String(format: "%.2f", $0) : String(Int($0)) }
        // Every size and gap here is measured off his Figma (pt from the top rule: label cap 17, value cap 41, name cap
        // 80, sub 99), so a few (14, 6, 4) sit off the DESIGN.md scale on purpose.
        return VStack(alignment: .leading, spacing: 0) {
            Text(label).font(.system(size: 13)).foregroundStyle(.secondary).lineLimit(1)
            NumberText(top > 0 ? fmt(top) : "–", size: 34)
                .padding(.top, DS.Space.xxs)
            Text(top > 0 ? ranked[0].name : "Nobody yet")
                .font(.system(size: 13, weight: .bold)).lineLimit(1)
                .padding(.top, 6)
            Text(next.isEmpty || top == 0 ? " " : "then " + next.map { "\(surname($0.name)) \(fmt(value($0)))" }.joined(separator: " · "))
                .font(.system(size: 11)).foregroundStyle(.secondary).lineLimit(1)
                .padding(.top, 6)
        }
        .padding(.horizontal, 14).padding(.top, DS.Space.m).padding(.bottom, DS.Space.m)
        .frame(maxWidth: .infinity, alignment: .leading)
        // The Figma's rule is bright (#BFBFB9 on #131312), not a hairline: that is #EDEDE6 at 80 % (the programme print rule); primary at 80 % gives it on the dark looks
        // and a matching dark rule on the light ones.
        .overlay(alignment: .top) { Rectangle().fill(Color.primary.opacity(0.8)).frame(height: 1) }
        .accessibilityElement(children: .combine)
    }
}

// MARK: - charts

/// Goals and assists for everyone who's got one: the design's stacked bars, one line per player. The table below has
/// every number too.
private struct ContributionsChart: View {
    let rows: [StatRow]

    var body: some View {
        let top = rows.filter { $0.contributions > 0 }.sorted { ($0.contributions, $0.goals) > ($1.contributions, $1.goals) }.prefix(10)
        let most = Double(top.first?.contributions ?? 1)
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Goal contributions").font(.system(size: 14.5, weight: .semibold))
                    Text("Goals and assists, all competitions").font(.system(size: 11.5)).foregroundStyle(.secondary)
                }
                Spacer()
                legend("Goals", Palette.brandHigh)
                legend("Assists", Palette.loanIn)
            }
            if top.isEmpty {
                Text("No goals or assists yet this season.").font(.system(size: 12)).foregroundStyle(.secondary).frame(height: 160)
            }
            VStack(spacing: 10) {
                ForEach(Array(top)) { r in
                    VStack(spacing: 4) {
                        HStack {
                            Text(surname(r.name)).font(.system(size: 11.5, weight: .medium))
                            Spacer()
                            (Text("\(r.goals)G + \(r.assists)A = ").foregroundStyle(.secondary) + Text("\(r.contributions)").fontWeight(.bold))
                                .font(.system(size: 11.5)).monospacedDigit()
                        }
                        GeometryReader { geo in
                            HStack(spacing: 0) {
                                Rectangle().fill(Palette.brandHigh).frame(width: geo.size.width * Double(r.goals) / most)
                                Rectangle().fill(Palette.loanIn).frame(width: geo.size.width * Double(r.assists) / most)
                                Spacer(minLength: 0)
                            }
                            .background(Color.primary.opacity(0.04))
                            .clipShape(RoundedRectangle(cornerRadius: 4, style: .continuous))
                        }
                        .frame(height: 10)
                    }
                    .contentShape(Rectangle())
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("\(r.name): \(r.goals) goals, \(r.assists) assists")
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .hubCard()
    }

    private func legend(_ text: String, _ color: Color) -> some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(text)
        }
        .font(.system(size: 11)).foregroundStyle(.secondary)
    }
}

/// Average match rating for regulars: the design's dot plot, one line per player. Dots, not bars: bars must start at
/// 0, and from 0 every rating looks the same. 7.20+ green, under 6.85 amber (the web app's bands).
private struct RatingsChart: View {
    let rows: [StatRow]

    var body: some View {
        let most = rows.map(\.apps).max() ?? 0
        let floor = max(3, Int((Double(most) / 3).rounded()))
        let rated = rows.filter { $0.avg >= 0 && $0.apps >= floor }.sorted { $0.avg > $1.avg }.prefix(10)
        let lo = min(6.6, (rated.map(\.avg).min() ?? 6.6) - 0.05)
        let hi = max(7.6, (rated.map(\.avg).max() ?? 7.6) + 0.05)
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Average match rating").font(.system(size: 14.5, weight: .semibold))
                Text("\(floor)+ appearances · 7.20+ green, under 6.85 amber · scale \(String(format: "%.1f", lo))–\(String(format: "%.1f", hi))")
                    .font(.system(size: 11.5)).foregroundStyle(.secondary)
            }
            if rated.isEmpty {
                Text("Nobody has enough games yet.").font(.system(size: 12)).foregroundStyle(.secondary).frame(height: 160)
            }
            VStack(spacing: 10) {
                ForEach(Array(rated)) { r in
                    let c = r.avg >= StatRow.high ? DS.Delta.up : r.avg < StatRow.low ? DS.Delta.warn : Palette.loanIn
                    HStack(spacing: 12) {
                        Text(surname(r.name)).font(.system(size: 11.5)).foregroundStyle(.secondary).lineLimit(1)
                            .frame(width: 96, alignment: .leading)
                        GeometryReader { geo in
                            let x = geo.size.width * max(0.04, min(0.96, (r.avg - lo) / (hi - lo)))
                            ZStack(alignment: .leading) {
                                Rectangle().fill(Color.primary.opacity(0.06)).frame(height: 1)
                                Circle().fill(c).frame(width: 10, height: 10)
                                    .overlay(Circle().strokeBorder(Color.black.opacity(0.6), lineWidth: 2))
                                    .offset(x: x - 5)
                            }
                            .frame(maxHeight: .infinity)
                        }
                        .frame(height: 16)
                        Text(String(format: "%.2f", r.avg)).font(.system(size: 11.5, weight: .semibold)).monospacedDigit()
                            .frame(width: 36, alignment: .trailing)
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityLabel("\(r.name): \(String(format: "%.2f", r.avg))")
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .hubCard()
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
