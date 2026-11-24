import SwiftUI

/// Home: the club, where you are in the league, the snapshot, the positions that need work, and the latest news.
/// Same content as the web app's Home, in Mac form. No player recommendations: verdicts are about positions.
struct HomeView: View {
    let report: Report

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 30) {
                Hero(report: report)
                Snapshot(report: report)
                NeedsWork(report: report)
                if !report.news.isEmpty { News(items: report.news) }
                if !report.notes.isEmpty { Notes(notes: report.notes) }
            }
            .padding(28)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

// MARK: - hero

private struct Hero: View {
    let report: Report
    @Environment(\.theme) private var theme

    var body: some View {
        let kit = Color(hex: report.club.kit)
        let ink = Color(hex: report.club.ink)
        let shape = RoundedRectangle(cornerRadius: theme.isGlass ? 26 : 14, style: .continuous)
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .bottom, spacing: 32) { identity; Spacer(minLength: 0); league }
            VStack(alignment: .leading, spacing: 24) { identity; league }
        }
        .foregroundStyle(theme.isGlass ? Color.primary : ink)
        .padding(32)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background {
            if theme.isGlass {
                // glass with the club colour glowing in from the corner, like the web app's look E
                ZStack {
                    LinearGradient(colors: [.white.opacity(0.08), .white.opacity(0.02)], startPoint: .top, endPoint: .bottom)
                    RadialGradient(colors: [kit.opacity(0.5), .clear], center: .topLeading, startRadius: 0, endRadius: 620)
                }
            } else {
                ZStack {
                    kit
                    LinearGradient(colors: [.white.opacity(0.08), .clear, .black.opacity(0.22)], startPoint: .topLeading, endPoint: .bottomTrailing)
                }
            }
        }
        .overlay(alignment: .bottom) {
            if !theme.isGlass { Rectangle().fill(Palette.brand).frame(height: 5) }
        }
        .clipShape(shape)
        .overlay(shape.strokeBorder(theme.isGlass ? Color.white.opacity(0.12) : .clear))
        .shadow(color: .black.opacity(theme.isGlass ? 0.5 : 0), radius: 40, y: 30)
    }

    private var identity: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("FM27 squad report").font(.headline).opacity(0.8)
            Text(report.club.name.uppercased())
                .heroFont(64)
                .lineLimit(1)
                .minimumScaleFactor(0.5)
            Grid(alignment: .leading, horizontalSpacing: 28, verticalSpacing: 4) {
                GridRow {
                    Text("In-game date").font(.caption).opacity(0.75)
                    Text("Tactic").font(.caption).opacity(0.75)
                    Text("Save").font(.caption).opacity(0.75)
                }
                GridRow {
                    Text(Fmt.day(report.gameDate)).displayFont(18, .bold)
                    Text(report.formation.title).displayFont(18, .bold)
                    Text(report.saveName ?? "–").font(.callout).lineLimit(1)
                }
            }
        }
    }

    @ViewBuilder
    private var league: some View {
        if let rec = report.performance.record {
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    Text(Fmt.ordinal(rec.pos))
                        .positionFont(60)
                        .foregroundStyle(theme.isGlass ? Palette.brandHigh : Color(hex: report.club.ink))
                        .shadow(color: theme.isGlass ? Palette.brandHigh.opacity(0.45) : .clear, radius: 12)
                    VStack(alignment: .leading, spacing: 1) {
                        Text("of \(rec.of)\(report.performance.leagueName.map { " · \($0)" } ?? "")")
                        Text("\(rec.pts) pts · P\(rec.p) W\(rec.w) D\(rec.d) L\(rec.l) · \(rec.gf)–\(rec.ga)")
                    }
                    .font(.callout)
                    .opacity(0.88)
                }
                if !report.performance.form.isEmpty {
                    HStack(spacing: 4) {
                        ForEach(Array(report.performance.form.enumerated()), id: \.offset) { _, f in
                            Text(f.res)
                                .font(.system(size: 11, weight: .heavy))
                                .foregroundStyle(.white)
                                .frame(width: 22, height: 22)
                                .background(Palette.result(f.res), in: RoundedRectangle(cornerRadius: 5))
                                .help("\(f.score) \(f.home ? "vs" : "at") \(f.opp)")
                                .accessibilityLabel("\(f.res == "W" ? "Won" : f.res == "L" ? "Lost" : "Drew") \(f.score) \(f.home ? "against" : "at") \(f.opp)")
                        }
                    }
                }
            }
            .accessibilityElement(children: .contain)
        }
    }
}

// MARK: - snapshot

private struct Snapshot: View {
    let report: Report

    var body: some View {
        let squad = report.players.filter { $0.location == "squad" }
        let injured = squad.filter(\.isInjured).count
        let suspended = squad.filter(\.isSuspended).count
        let f = report.finances
        VStack(alignment: .leading, spacing: 12) {
            SectionTitle("Club snapshot")
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 220), spacing: 12)], spacing: 12) {
                if let left = f.transferLeft {
                    Tile(label: "Transfer budget left", value: Fmt.money(left), sub: "as of \(Fmt.month(f.month)) month-end")
                }
                if let bill = f.wageBill, let budget = f.wageBudget, budget > 0 {
                    let room = budget - bill
                    Tile(label: "Wage bill / budget (p/w)", value: Fmt.wage(bill), unit: "/ \(Fmt.wage(budget))",
                         sub: "\(Fmt.wage(abs(room)))/wk \(room >= 0 ? "room" : "over")") {
                        ProgressView(value: min(bill, budget), total: budget)
                            .tint(room >= 0 ? Palette.brandHigh : Palette.verdict("red"))
                    }
                }
                if let level = report.xiLevel {
                    Tile(label: "XI level", value: String(format: "%.1f", level), unit: "★ average", sub: "of your best XI") {
                        StarsView(value: level, size: 14)
                    }
                }
                Tile(label: "Unavailable now", value: "\(injured + suspended)", unit: "players",
                     sub: "\(injured) injured · \(suspended) suspended")
            }
        }
    }
}

private struct Tile<Extra: View>: View {
    let label: String
    let value: String
    var unit: String? = nil
    let sub: String
    @ViewBuilder var extra: () -> Extra

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label).font(.callout).foregroundStyle(.secondary)
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                NumberText(value, size: 34)
                if let unit { Text(unit).foregroundStyle(.secondary) }
            }
            extra()
            Text(sub).font(.caption).foregroundStyle(.secondary)
        }
        .padding(16)
        .frame(maxWidth: .infinity, minHeight: 118, alignment: .topLeading)
        .panel(10)
        .accessibilityElement(children: .combine)
    }
}

extension Tile where Extra == EmptyView {
    init(label: String, value: String, unit: String? = nil, sub: String) {
        self.init(label: label, value: value, unit: unit, sub: sub, extra: { EmptyView() })
    }
}

// MARK: - where the squad needs work

private struct NeedsWork: View {
    let report: Report

    var body: some View {
        let need = report.verdicts.filter(\.needsWork)
        let fine = report.verdicts.filter { !$0.needsWork }
        VStack(alignment: .leading, spacing: 12) {
            SectionTitle("Where the squad needs work", sub: "after arranged transfers & loans go through · loaned-out players not counted")
            if need.isEmpty {
                Label("Nothing urgent: every position in your tactic is covered. 🔥", systemImage: "checkmark.seal.fill")
                    .foregroundStyle(Palette.verdict("green"))
            }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 320), spacing: 12, alignment: .top)], spacing: 12) {
                ForEach(Array(need.enumerated()), id: \.element.id) { i, v in
                    VerdictCard(rank: i + 1, verdict: v, report: report)
                }
            }
            if !fine.isEmpty {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 240), spacing: 8, alignment: .top)], spacing: 8) {
                    ForEach(fine) { v in
                        HStack(alignment: .firstTextBaseline, spacing: 8) {
                            Text(v.slot).slotFont(15)
                            Text(v.title).font(.caption.weight(.bold)).foregroundStyle(Palette.verdict(v.level))
                            Text(v.text).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                        }
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .panel(8)
                        .overlay(alignment: .leading) {
                            Rectangle().fill(Palette.verdict(v.level)).frame(width: 3)
                        }
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .accessibilityElement(children: .combine)
                    }
                }
            }
        }
    }
}

private struct VerdictCard: View {
    let rank: Int
    let verdict: Verdict
    let report: Report

    var body: some View {
        let color = Palette.verdict(verdict.level)
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                Text("\(rank)").font(.caption.weight(.bold)).frame(width: 22, height: 22)
                    .background(.quaternary, in: Circle())
                Text(verdict.slot).slotFont(22)
                Text(verdict.title).displayFont(15, .bold).foregroundStyle(color)
            }
            Text(verdict.text).fixedSize(horizontal: false, vertical: true)
            people("Starter", "Starters", report.xi1)
            people("Backup", "Backups", report.xi2)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .panelFill()
        .overlay(alignment: .leading) { Rectangle().fill(color).frame(width: 4) }
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private func people(_ one: String, _ many: String, _ xi: [XISlot]) -> some View {
        let here = xi.filter { $0.slot == verdict.slot }
        if !here.isEmpty {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(here.count > 1 ? many : one).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                    .frame(width: 58, alignment: .leading)
                FlowRow(spacing: 10) {
                    ForEach(Array(here.enumerated()), id: \.offset) { _, slot in
                        if let p = report.player(slot.uid), let r = p.rating(at: verdict.slot) {
                            HStack(spacing: 4) {
                                Text(surname(p.name)).font(.callout)
                                StarsView(value: r.stars)
                                FamiliarityBadge(code: r.fam)
                            }
                        } else {
                            Text("nobody left").font(.callout.italic()).foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
    }
}

// MARK: - news and notes

private struct News: View {
    @Environment(AppModel.self) private var model
    let items: [NewsItem]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionTitle("Latest", sub: "from your save: moves, injuries, bans and contracts")
            VStack(spacing: 0) {
                ForEach(Array(items.enumerated()), id: \.offset) { i, item in
                    Button {
                        model.go(Route(webHash: item.route) ?? .home)
                    } label: {
                        HStack(spacing: 10) {
                            NewsTag(item: item).frame(minWidth: 86, alignment: .leading)
                            Text(item.text).frame(maxWidth: .infinity, alignment: .leading)
                            Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary).accessibilityHidden(true)
                        }
                        .padding(.vertical, 8).padding(.horizontal, 12)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    if i < items.count - 1 { Divider().padding(.leading, 12) }
                }
            }
            .panel(10)
        }
    }
}

private struct Notes: View {
    let notes: [String]

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            ForEach(notes, id: \.self) { note in
                Label(note, systemImage: "info.circle").font(.callout).foregroundStyle(Palette.verdict("amber"))
            }
        }
    }
}

// MARK: - shared bits

struct SectionTitle: View {
    let title: String
    var sub: String?

    init(_ title: String, sub: String? = nil) {
        self.title = title
        self.sub = sub
    }

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            Text(title).displayFont(26)
                .accessibilityAddTraits(.isHeader)
            if let sub { Text(sub).font(.callout).foregroundStyle(.secondary) }
        }
    }
}

/// Lays children out in rows, wrapping when the line is full.
struct FlowRow: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0, widest: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > 0, x + size.width > width { x = 0; y += rowHeight + 4; rowHeight = 0 }
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
            widest = max(widest, x - spacing)
        }
        return CGSize(width: min(widest, width), height: y + rowHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, rowHeight: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x > bounds.minX, x + size.width > bounds.maxX { x = bounds.minX; y += rowHeight + 4; rowHeight = 0 }
            view.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}

/// Everything after the first name, like the web app: "Virgil van Dijk" → "van Dijk".
func surname(_ name: String) -> String {
    guard let space = name.firstIndex(of: " ") else { return name }
    return String(name[name.index(after: space)...])
}
