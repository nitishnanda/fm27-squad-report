import SwiftUI

/// One row of the squad table, with plain sort keys (missing values sort last).
struct SquadRow: Identifiable, Hashable, Sendable {
    let id: Int
    let name: String
    let natural: String
    let accomplished: String
    let age: Int
    let system: Double
    let bestSlot: String
    let trend: Double
    let ability: Double
    let potential: Double
    let value: Double
    let wage: Double
    let contract: String
    let contractEnd: String?
    let expiring: Bool
    let statuses: [PlayerStatus]
    let tokens: [String]
    let youth: Bool
    let group: Int

    init(_ p: Player, group: Int, today: String? = nil) {
        id = p.uid
        name = p.name
        natural = p.positions.natural.joined(separator: " ")
        accomplished = p.positions.accomplished.joined(separator: " ")
        age = p.age ?? 99
        system = p.best?.stars ?? -1
        bestSlot = p.best?.slot ?? ""
        trend = p.trend ?? 0
        ability = p.abilityBest ?? -1
        potential = p.potential ?? -1
        value = p.value ?? -1
        wage = p.wage ?? -1
        contract = p.contractEnd ?? "9999"
        contractEnd = p.contractEnd
        expiring = p.expiring
        statuses = PlayerStatus.of(p, today: today)
        tokens = p.status.tokens
        youth = p.youth
        self.group = group
    }

    static func == (a: SquadRow, b: SquadRow) -> Bool { a.id == b.id }
    func hash(into h: inout Hasher) { h.combine(id) }
}

/// The squad grouped like the web app: by position, then arriving, out on loan, youth teams.
enum SquadGroups {
    static let titles = ["Goalkeepers", "Defenders", "Midfielders", "Attackers", "Other",
                         "Arriving (transfers & loans arranged)", "Out on loan", "Youth teams"]

    /// His main FM position decides the group (GK / D / M / A), falling back to his best slot.
    static func positionGroup(_ p: Player) -> Int {
        let byLabel: [String: Int] = ["GK": 0, "SW": 1, "LB": 1, "CB": 1, "RB": 1, "LWB": 1, "RWB": 1,
                                      "DM": 2, "CM": 2, "LM": 2, "RM": 2, "AM": 2, "LW": 3, "RW": 3, "ST": 3]
        if let first = p.positions.natural.first, let g = byLabel[first] { return g }
        if let slot = p.best?.slot, let g = byLabel[slot] { return g }
        return 4
    }

    static func group(_ p: Player) -> Int? {
        switch p.location {
        case "incoming": return 5
        case "loan_out": return 6
        case "squad": return p.youth ? 7 : positionGroup(p)
        default: return nil   // scouting targets live in the Sandbox
        }
    }

    static func rows(_ report: Report) -> [SquadRow] {
        report.players.compactMap { p in group(p).map { SquadRow(p, group: $0, today: report.gameDate) } }
    }
}

struct SquadListView: View {
    let report: Report

    enum Show: String, CaseIterable, Identifiable {
        case all = "All", loan = "On loan", injured = "Injured", suspended = "Suspended"
        case arranged = "Arranged moves", expiring = "Contract ending"
        var id: String { rawValue }
        var token: String? {
            switch self {
            case .all: nil
            case .loan: "loan"
            case .injured: "injured"
            case .suspended: "suspended"
            case .arranged: "arranged"
            case .expiring: "expiring"
            }
        }
    }

    @State private var search = ""
    @AppStorage("showPotential") private var showPotential = true
    @State private var show: Show = .all
    @State private var youth = false
    @State private var sortOrder = [KeyPathComparator(\SquadRow.system, order: .reverse)]
    @State private var selection: Set<SquadRow.ID> = []
    /// Groups you've folded away. "Out on loan" starts folded; a filter or search opens whatever it finds.
    @State private var folded: Set<Int> = [6]
    /// Column widths, order and which ones are hidden (right-click a header), kept between launches.
    @AppStorage("squadColumns") private var savedColumns = Data()
    @State private var columns = TableColumnCustomization<SquadRow>()

    private var showPicker: some View {
        Picker("Show", selection: $show) {
            ForEach(Show.allCases) { Text($0.rawValue).tag($0) }
        }
        .labelsHidden()
    }

    var body: some View {
        let all = SquadGroups.rows(report)
        let shown = filtered(all)
        VStack(spacing: 0) {
            Summary(report: report, rows: all, show: $show)
                .padding(.horizontal, 20).padding(.top, 16).padding(.bottom, 10)
            HStack(spacing: 12) {
                ViewThatFits(in: .horizontal) {
                    showPicker.pickerStyle(.segmented).fixedSize()
                    showPicker.pickerStyle(.menu).fixedSize()      // narrow window: a pop-up instead of six segments
                }
                Toggle("Youth teams", isOn: $youth)
                Spacer()
                let filtering = show != .all || !search.trimmingCharacters(in: .whitespaces).isEmpty
                let away = filtering ? 0 : shown.filter { folded.contains($0.group) }.count
                Text("\(shown.count) player\(shown.count == 1 ? "" : "s")" + (away > 0 ? " · \(away) folded away" : ""))
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
                    .accessibilityLabel("\(shown.count) players" + (away > 0 ? ", \(away) in folded groups" : ""))
            }
            .padding(.horizontal, 20).padding(.bottom, 10)
            if shown.isEmpty {
                ContentUnavailableView {
                    Label("No players match", systemImage: "magnifyingglass")
                } description: {
                    Text(search.isEmpty ? "Nobody fits “\(show.rawValue)” right now." : "Nobody called “\(search)”\(show == .all ? "" : " with “\(show.rawValue)”").")
                        + Text(!youth ? " Youth-team players only show with “Youth teams” on." : "")
                } actions: {
                    Button("Clear filters") { search = ""; show = .all }
                }
            } else {
                table(shown)
            }
        }
        .searchable(text: $search, placement: .toolbar, prompt: "Search the squad")
        .onAppear {
            if let saved = try? JSONDecoder().decode(TableColumnCustomization<SquadRow>.self, from: savedColumns) { columns = saved }
        }
        .onChange(of: columns) { _, now in
            if let data = try? JSONEncoder().encode(now) { savedColumns = data }
        }
    }

    private func filtered(_ rows: [SquadRow]) -> [SquadRow] {
        let q = fold(search.trimmingCharacters(in: .whitespaces))
        return rows.filter { row in
            (youth || !row.youth)
                && (show.token.map { row.tokens.contains($0) } ?? true)
                && (q.isEmpty || fold(row.name).contains(q))
        }
    }

    /// Accent-insensitive, so "pecsi" finds Pécsi.
    private func fold(_ s: String) -> String {
        s.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .current)
    }

    private func table(_ rows: [SquadRow]) -> some View {
        let groups = Dictionary(grouping: rows, by: \.group)
        let filtering = show != .all || !search.trimmingCharacters(in: .whitespaces).isEmpty
        return Table(of: SquadRow.self, selection: $selection, sortOrder: $sortOrder, columnCustomization: $columns) {
            TableColumn("Player", value: \.name) { row in
                Text(row.name).fontWeight(.semibold)
            }
            .width(min: 130, ideal: 160)
            .customizationID("player")
            .disabledCustomizationBehavior(.visibility)
            TableColumn("FM positions", value: \.natural) { row in
                (Text(row.natural) + Text(row.accomplished.isEmpty ? "" : "  \(row.accomplished)").foregroundStyle(.secondary))
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .contentShape(Rectangle())
                    .help("Natural: \(row.natural)\(row.accomplished.isEmpty ? "" : " · accomplished (grey): \(row.accomplished)")")
            }
            .width(min: 110, ideal: 150)
            .customizationID("positions")
            TableColumn("Age", value: \.age) { row in
                Text(row.age == 99 ? "" : "\(row.age)").monospacedDigit()
            }
            .width(34)
            .customizationID("age")
            TableColumn("System ★", value: \.system) { row in
                if row.system >= 0 {
                    HStack(spacing: 5) {
                        StarsView(value: row.system)
                        Text(row.bestSlot).font(.caption2.weight(.bold)).foregroundStyle(.secondary)
                        if row.trend != 0 {
                            Text("\(row.trend > 0 ? "▲" : "▼") \(Fmt.stars(abs(row.trend)))")
                                .font(.caption2.weight(.bold))
                                .foregroundStyle(row.trend > 0 ? Palette.verdict("green") : Palette.verdict("red"))
                                .help("Since your last report")
                        }
                    }
                } else {
                    Text("–").foregroundStyle(.secondary)
                }
            }
            .width(min: 110, ideal: 128)
            .customizationID("system")
            TableColumn("Ability ★", value: \.ability) { row in
                if row.ability >= 0 { StarsView(value: row.ability) } else { Text("–").foregroundStyle(.secondary) }
            }
            .width(min: 70, ideal: 76)
            .customizationID("ability")
            TableColumn("Potential ★", value: \.potential) { row in
                if showPotential && row.potential >= 0 {
                    StarsView(value: row.potential, tint: Palette.potential)
                        .help("Potential, from FM's hidden potential (players 23 and under)")
                } else {
                    Text("–").foregroundStyle(.secondary)
                }
            }
            .width(min: 70, ideal: 76)
            .customizationID("potential")
            TableColumn("Value", value: \.value) { row in
                Text(Fmt.money(row.value < 0 ? nil : row.value)).monospacedDigit()
                    .frame(maxWidth: .infinity, alignment: .trailing)
            }
            .width(min: 50, ideal: 58)
            .customizationID("value")
            TableColumn("Wage p/w", value: \.wage) { row in
                Text(Fmt.wage(row.wage < 0 ? nil : row.wage)).monospacedDigit()
                    .frame(maxWidth: .infinity, alignment: .trailing)
            }
            .width(min: 72, ideal: 78)
            .customizationID("wage")
            TableColumn("Contract", value: \.contract) { row in
                Text(Fmt.month(row.contractEnd))
                    .underline(row.expiring, pattern: .dash)
                    .foregroundStyle(row.expiring ? .primary : .secondary)
                    .help(row.expiring ? "Ends within a year" : "")
            }
            .width(min: 64, ideal: 72)
            .customizationID("contract")
            TableColumn("Status") { row in
                HStack(spacing: 4) {
                    ForEach(row.statuses) { StatusBadge(status: $0) }
                }
            }
            .width(min: 110, ideal: 200)
            .customizationID("status")
        } rows: {
            ForEach(SquadGroups.titles.indices, id: \.self) { g in
                if let members = groups[g], !members.isEmpty {
                    let open = filtering || !folded.contains(g)
                    Section {
                        ForEach(open ? members.sorted(using: sortOrder) : []) { TableRow($0) }
                    } header: {
                        Button {
                            if folded.contains(g) { folded.remove(g) } else { folded.insert(g) }
                        } label: {
                            HStack(spacing: 6) {
                                Image(systemName: "chevron.right")
                                    .font(.caption.weight(.bold))
                                    .rotationEffect(.degrees(open ? 90 : 0))
                                Text(SquadGroups.titles[g])
                                Text("\(members.count)").foregroundStyle(.secondary)
                            }
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .disabled(filtering)
                        .help(filtering ? "Filters and search show every match" : (open ? "Fold this group" : "Show this group"))
                        .accessibilityLabel("\(SquadGroups.titles[g]), \(members.count) players")
                        .accessibilityValue(open ? "expanded" : "collapsed")
                    }
                }
            }
        }
    }
}

/// Key figures over the list. The last three filter the table to the players behind them.
private struct Summary: View {
    let report: Report
    let rows: [SquadRow]
    @Binding var show: SquadListView.Show

    var body: some View {
        let first = report.players.filter { $0.location == "squad" && !$0.youth }
        let ages = first.compactMap(\.age)
        let youthCount = report.players.filter { $0.location == "squad" && $0.youth }.count
        let worth = first.compactMap(\.value).reduce(0, +)
        let seniors = rows.filter { !$0.youth }
        let count: (String) -> Int = { token in seniors.filter { $0.tokens.contains(token) }.count }
        let out = report.players.filter { p in p.status.moves.contains { $0.kind == "loan_out" } }.count
        let inn = report.players.filter { p in p.status.moves.contains { $0.kind == "loan_in" } }.count
        let coming = report.players.filter { p in p.status.moves.contains { ["deal_in", "loan_in_arr"].contains($0.kind) } }.count
        let going = report.players.filter { p in p.status.moves.contains { ["deal_out", "loan_out_arr"].contains($0.kind) } }.count

        // five across on a wide window, wrapping to rows of three or two on a narrow one
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 190), spacing: 10, alignment: .top)], spacing: 10) {
            figure("First team", "\(first.count)", unit: "players",
                   sub: "avg age \(ages.isEmpty ? "–" : String(format: "%.1f", Double(ages.reduce(0, +)) / Double(ages.count))) · \(youthCount) in the youth teams")
            figure("First-team value", Fmt.money(Double(worth)), sub: "FM's transfer values")
            filter("Contracts ending", count("expiring"), sub: "within 12 months", .expiring)
            filter("On loan", count("loan"), sub: "\(out) out · \(inn) in", .loan)
            filter("Arranged moves", count("arranged"), sub: "\(coming) coming · \(going) going", .arranged)
        }
    }

    private func figure(_ label: String, _ value: String, unit: String? = nil, sub: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(.callout).foregroundStyle(.secondary)
            HStack(alignment: .firstTextBaseline, spacing: 5) {
                NumberText(value, size: 28)
                if let unit { Text(unit).foregroundStyle(.secondary) }
            }
            Text(sub).font(.caption).foregroundStyle(.secondary).lineLimit(1).minimumScaleFactor(0.85)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .panel(10)
        .accessibilityElement(children: .combine)
    }

    private func filter(_ label: String, _ n: Int, sub: String, _ target: SquadListView.Show) -> some View {
        let on = show == target
        return Button {
            show = on ? .all : target
        } label: {
            figure(label, "\(n)", sub: sub)
                .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .strokeBorder(on ? Palette.brandHigh : .clear, lineWidth: 2))
                .overlay(alignment: .topTrailing) {
                    Text(on ? "Showing" : "Filter")
                        .font(.caption2.weight(.bold))
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .overlay(Capsule().stroke(.secondary.opacity(0.5)))
                        .foregroundStyle(.secondary)
                        .padding(10)
                }
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .help(on ? "Show everyone again" : "Show only these players")
        .accessibilityAddTraits(on ? .isSelected : [])
    }
}
