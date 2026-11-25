import AppKit
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
    /// Natural or accomplished: what the web's "Can play" chips filter on.
    let canPlay: Set<String>
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
        canPlay = Set(p.positions.natural + p.positions.accomplished)
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
    /// "Can play" chips, the same positions in the same order as the web app (`FILTER_POS`).
    nonisolated static let filterPositions = ["GK", "LB", "LWB", "CB", "RB", "RWB", "DM", "CM", "LM", "RM", "AM", "LW", "RW", "ST"]
    @State private var positions: Set<String> = []
    @State private var allPositions = false     // "all of these" instead of "any of these"
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(AppModel.self) private var app

    /// Changes whenever any filter does, so the table animates rows in and out instead of jumping.
    private var filterSignature: String {
        "\(show.rawValue)|\(positions.sorted())|\(allPositions)|\(youth)|\(search)"
    }
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
        // Laid out from his Figma Make design (SquadListView.tsx): KPI cards, status pills + search, "Can play" chips,
        // then the table in a card. The table stays the native one (sorting, saved columns, folding groups).
        VStack(alignment: .leading, spacing: 16) {
            Summary(report: report, rows: all, show: $show)
            HStack(spacing: 12) {
                statusPills
                Toggle("Youth teams", isOn: $youth).toggleStyle(.checkbox).font(.system(size: 11.5))
                Spacer(minLength: 8)
                let away = isFiltering ? 0 : shown.filter { folded.contains($0.group) }.count
                Text("\(shown.count) player\(shown.count == 1 ? "" : "s")" + (away > 0 ? " · \(away) folded away" : ""))
                    .font(.system(size: 11.5)).foregroundStyle(.tertiary).monospacedDigit()
                    .accessibilityLabel("\(shown.count) players" + (away > 0 ? ", \(away) in folded groups" : ""))
                searchField
            }
            positionFilter
            if shown.isEmpty {
                ContentUnavailableView {
                    Label("No players match", systemImage: "magnifyingglass")
                } description: {
                    Text(emptyMessage)
                        + Text(!youth ? " Youth-team players only show with “Youth teams” on." : "")
                } actions: {
                    Button("Clear filters") { clearFilters() }
                }
                .frame(maxHeight: .infinity)
            } else {
                table(shown)
                    .scrollContentBackground(.hidden)
                    .hubCard()
                    .animation(reduceMotion ? nil : Motion.filter, value: filterSignature)
            }
        }
        .padding(.horizontal, 24).padding(.vertical, 20)
        .onAppear {
            if let name = app.squadSearch { search = name; app.squadSearch = nil }
            if let saved = try? JSONDecoder().decode(TableColumnCustomization<SquadRow>.self, from: savedColumns) { columns = saved }
        }
        .onChange(of: columns) { _, now in
            if !app.showInspector, let data = try? JSONEncoder().encode(now) { savedColumns = data }
        }
        .onChange(of: app.showInspector) { _, open in
            // the side panel takes a third of the width: the three least-needed columns step aside, and come back after
            if open {
                for id in ["ability", "potential", "wage"] { columns[visibility: id] = .hidden }
            } else if let saved = try? JSONDecoder().decode(TableColumnCustomization<SquadRow>.self, from: savedColumns) {
                columns = saved
            } else {
                for id in ["ability", "potential", "wage"] { columns[visibility: id] = .automatic }
            }
        }
    }

    private func filtered(_ rows: [SquadRow]) -> [SquadRow] {
        let q = fold(search.trimmingCharacters(in: .whitespaces))
        return rows.filter { row in
            (youth || !row.youth)
                && (show.token.map { row.tokens.contains($0) } ?? true)
                && (q.isEmpty || fold(row.name).contains(q))
                && Self.matches(row.canPlay, positions, all: allPositions)
        }
    }

    /// Any (or all) of the chosen positions among the ones he can play. No chips chosen: everyone.
    nonisolated static func matches(_ canPlay: Set<String>, _ chosen: Set<String>, all: Bool) -> Bool {
        chosen.isEmpty || (all ? chosen.isSubset(of: canPlay) : !chosen.isDisjoint(with: canPlay))
    }

    /// A filter, a position or a search: groups open up to show what they found.
    private var isFiltering: Bool {
        show != .all || !positions.isEmpty || !search.trimmingCharacters(in: .whitespaces).isEmpty
    }

    private func clearFilters() {
        search = ""
        show = .all
        positions = []
        allPositions = false
    }

    private var emptyMessage: String {
        var bits: [String] = []
        if show != .all { bits.append("“\(show.rawValue)”") }
        if !positions.isEmpty {
            let list = Self.filterPositions.filter(positions.contains).joined(separator: allPositions ? " and " : " or ")
            bits.append("who can play \(list)")
        }
        let q = search.trimmingCharacters(in: .whitespaces)
        if !q.isEmpty { return "Nobody called “\(q)”" + (bits.isEmpty ? "." : " " + bits.joined(separator: ", ") + ".") }
        return bits.isEmpty ? "Nobody here right now." : "Nobody fits " + bits.joined(separator: ", ") + " right now."
    }

    /// The design's status pills: the picked one in signal green. Narrow windows get a pop-up instead.
    private var statusPills: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 0) {
                ForEach(Show.allCases) { option in
                    let on = show == option
                    Button { show = option } label: {
                        Text(option.rawValue).font(.system(size: 11.5, weight: .medium))
                            .foregroundStyle(on ? Palette.brandHigh : .secondary)
                            .padding(.horizontal, 12).padding(.vertical, 4)
                            .background(on ? Palette.brandHigh.opacity(0.2) : .clear, in: Capsule())
                            .overlay(Capsule().strokeBorder(on ? Palette.brandHigh.opacity(0.3) : .clear))
                            .contentShape(Capsule())
                    }
                    .buttonStyle(.plain)
                    .accessibilityAddTraits(on ? .isSelected : [])
                }
            }
            .padding(2)
            .background(Color.primary.opacity(0.03), in: Capsule())
            .overlay(Capsule().strokeBorder(Color.primary.opacity(0.08)))
            .fixedSize()
            showPicker.pickerStyle(.menu).fixedSize()      // narrow window: a pop-up instead of six pills
        }
        .animation(.easeOut(duration: 0.14), value: show)
    }

    /// The design's search: a 32 pt capsule with a magnifying glass, in the page instead of the toolbar.
    private var searchField: some View {
        HStack(spacing: 6) {
            Image(systemName: "magnifyingglass").font(.system(size: 11)).foregroundStyle(.tertiary)
            TextField("Filter players…", text: $search).textFieldStyle(.plain).font(.system(size: 12))
            if !search.isEmpty {
                Button { search = "" } label: { Image(systemName: "xmark.circle.fill").foregroundStyle(.tertiary) }
                    .buttonStyle(.plain).accessibilityLabel("Clear search")
            }
        }
        .padding(.horizontal, 12).frame(width: 240, height: 32)
        .background(Color.primary.opacity(0.03), in: Capsule())
        .overlay(Capsule().strokeBorder(Color.primary.opacity(search.isEmpty ? 0.08 : 0.22)))
    }

    /// "Can play" chips (toggle any number), "any / all of these", and Clear filters when something is on.
    private var positionFilter: some View {
        HStack(alignment: .center, spacing: 10) {
            Text("Can play:").font(.system(size: 11)).foregroundStyle(.tertiary).fixedSize()
            FlowRow(spacing: 6) {
                ForEach(Self.filterPositions, id: \.self) { pos in
                    let on = positions.contains(pos)
                    Button {
                        if on { positions.remove(pos) } else { positions.insert(pos) }
                    } label: {
                        Text(pos).font(.system(size: 11, weight: .medium))
                            .padding(.horizontal, 8).padding(.vertical, 2)
                            .background(Color.primary.opacity(on ? 0.08 : 0.03), in: RoundedRectangle(cornerRadius: 5, style: .continuous))
                            .overlay(RoundedRectangle(cornerRadius: 5, style: .continuous).strokeBorder(Color.primary.opacity(on ? 0.22 : 0.07)))
                            .foregroundStyle(on ? .primary : .secondary)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Can play \(pos)")
                    .accessibilityAddTraits(on ? .isSelected : [])
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            PillPicker(options: [("any of these", false), ("all of these", true)], selection: $allPositions)
                .disabled(positions.count < 2)
                .opacity(positions.count < 2 ? 0.5 : 1)
            .help("With two or more positions chosen: players who can play any of them, or all of them")
            if isFiltering {
                Button("Clear filters") { clearFilters() }
            }
        }
    }

    /// Accent-insensitive, so "pecsi" finds Pécsi.
    private func fold(_ s: String) -> String {
        s.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .current)
    }

    private func table(_ rows: [SquadRow]) -> some View {
        let groups = Dictionary(grouping: rows, by: \.group)
        let filtering = isFiltering
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
        .contextMenu(forSelectionType: SquadRow.ID.self) { ids in
            if let uid = ids.first, let player = report.player(uid) {
                Button("Show in Side Panel") { app.inspect(uid) }
                Button("Copy Name") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(player.name, forType: .string)
                }
            }
        } primaryAction: { ids in
            if let uid = ids.first { app.inspect(uid) }   // double-click
        }
        .alternatingRowBackgrounds(.disabled)   // rows guide by alignment, not banding (DESIGN.md › Don'ts)
    }
}

/// Key figures over the list. The last three filter the table to the players behind them.
private struct Summary: View {
    let report: Report
    let rows: [SquadRow]
    @Binding var show: SquadListView.Show

    var body: some View {
        // five across whenever they fit (also beside the side panel), else three and two
        ViewThatFits(in: .horizontal) { tiles(5); tiles(3) }
    }

    private func tiles(_ across: Int) -> some View {
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
        return LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: DS.Space.grid, alignment: .top), count: across), spacing: DS.Space.grid) {
            figure("First team", "\(first.count)", unit: "players",
                   sub: "avg age \(ages.isEmpty ? "–" : String(format: "%.1f", Double(ages.reduce(0, +)) / Double(ages.count))) · \(youthCount) in the youth teams")
            figure("First-team value", Fmt.money(Double(worth)), sub: "FM's transfer values")
            filter("Contracts ending", count("expiring"), sub: "within 12 months", .expiring)
            filter("On loan", count("loan"), sub: "\(out) out · \(inn) in", .loan)
            filter("Arranged moves", count("arranged"), sub: "\(coming) coming · \(going) going", .arranged)
        }
    }

    private func figure(_ label: String, _ value: String, unit: String? = nil, sub: String) -> some View {
        // the design's KPI card: p-14, 11.5 label, 24 value with its unit, 11 sub
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(.system(size: 11.5)).foregroundStyle(.secondary)
            HStack(alignment: .firstTextBaseline, spacing: 5) {
                NumberText(value, size: 24)
                if let unit { Text(unit).font(.system(size: 12)).foregroundStyle(.secondary) }
            }
            Text(sub).font(.system(size: 11)).foregroundStyle(.tertiary).lineLimit(1).minimumScaleFactor(0.85)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .frame(minWidth: 140)
        .hubCard()
        .accessibilityElement(children: .combine)
    }

    private func filter(_ label: String, _ n: Int, sub: String, _ target: SquadListView.Show) -> some View {
        let on = show == target
        return Button {
            show = on ? .all : target
        } label: {
            figure(label, "\(n)", sub: sub)
                .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .strokeBorder(on ? Palette.brandHigh.opacity(0.6) : .clear, lineWidth: 1))
                .overlay(alignment: .topTrailing) {
                    Text(on ? "Showing" : "Filter")
                        .font(.system(size: 10))
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .background(on ? Palette.brandHigh.opacity(0.16) : Color.primary.opacity(0.06), in: RoundedRectangle(cornerRadius: 4, style: .continuous))
                        .foregroundStyle(on ? Palette.brandHigh : .secondary)
                        .padding(12)
                }
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .help(on ? "Show everyone again" : "Show only these players")
        .accessibilityAddTraits(on ? .isSelected : [])
    }
}
