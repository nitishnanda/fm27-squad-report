import SwiftUI

/// Home: the club, where you are in the league, the snapshot, the positions that need work, and the latest news.
/// Laid out 1:1 from his Figma Make design (~/Downloads/FM27 Squad Hub, src/components/HomeView.tsx): its sizes,
/// spacing and components, in the app's own fonts and colours (his call). Sizes from that file sit off the DESIGN.md
/// scale on purpose. No player recommendations: verdicts are about positions.
struct HomeView: View {
    let report: Report

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                Hero(report: report)
                Snapshot(report: report)
                NeedsWork(report: report)
                if !report.news.isEmpty { Latest(items: report.news) }
                if !report.notes.isEmpty { Notes(notes: report.notes) }
            }
            .frame(maxWidth: 1172, alignment: .leading)   // the design's max-w 1220 minus its 24 pt sides
            .padding(.horizontal, 24).padding(.vertical, 20)
            .frame(maxWidth: .infinity)
        }
    }
}

// MARK: - the design's card and bits

/// The design's `card-surface`: a raised panel, 1 pt edge, radius 10, a faint top highlight. Colours stay the look's.
private struct HubCard: ViewModifier {
    @Environment(\.theme) private var theme
    var hover = false

    func body(content: Content) -> some View {
        let shape = RoundedRectangle(cornerRadius: 10, style: .continuous)
        content
            .background(fill, in: shape)
            .overlay(shape.strokeBorder(Color.primary.opacity(hover ? 0.13 : 0.08)))
            .overlay(alignment: .top) {
                Rectangle().fill(Color.white.opacity(theme.scheme == .light ? 0 : 0.035)).frame(height: 1).padding(.horizontal, 10)
            }
            .clipShape(shape)
            .shadow(color: .black.opacity(theme.scheme == .light ? 0.08 : 0.35), radius: 1, y: 1)
    }

    private var fill: Color {
        if theme.scheme == .light { return hover ? Color(hex: "#F7F7F5") : .white }
        // programme: one step up from its #121211 stock; the other dark looks use the DESIGN.md panel
        if theme.look == .programme { return Color(hex: hover ? "#1E1E1C" : "#1A1A18") }
        return hover ? DS.Surface.raised : DS.Surface.panel
    }
}

/// A clickable card: the design's `card-surface-interactive` (lifts its fill and edge on hover).
private struct HubButton<Label: View>: View {
    let action: () -> Void
    @ViewBuilder var label: () -> Label
    @State private var hover = false

    var body: some View {
        Button(action: action) {
            label().contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .modifier(HubCard(hover: hover))
        .onHover { hover = $0 }
        .animation(.easeOut(duration: 0.14), value: hover)
    }
}

extension View {
    fileprivate func hubCard() -> some View { modifier(HubCard()) }
}

/// The design's StatusBadge: a capsule, 11 pt medium, tinted fill and edge, optional dot.
private struct Badge: View {
    let label: String
    let color: Color
    var dot = false

    var body: some View {
        HStack(spacing: 6) {
            if dot { Circle().fill(color).frame(width: 6, height: 6) }
            Text(label)
        }
        .font(.system(size: 11, weight: .medium))
        .foregroundStyle(color)
        .padding(.horizontal, 8).padding(.vertical, 2)
        .background(color.opacity(0.12), in: Capsule())
        .overlay(Capsule().strokeBorder(color.opacity(0.24)))
        .fixedSize()
    }
}

/// The design's section header: 16 pt title with a 12.5 pt line under it.
private struct HubHeader<Trailing: View>: View {
    let title: String
    let sub: String
    @ViewBuilder var trailing: () -> Trailing

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            VStack(alignment: .leading, spacing: 2) {
                Text(title).displayFont(16, .semibold).accessibilityAddTraits(.isHeader)
                Text(sub).font(.system(size: 12.5)).foregroundStyle(.secondary)
            }
            Spacer(minLength: 8)
            trailing()
        }
    }
}

extension HubHeader where Trailing == EmptyView {
    init(title: String, sub: String) { self.init(title: title, sub: sub, trailing: { EmptyView() }) }
}

private let positionNames = [
    "GK": "Goalkeeper", "LB": "Left Back", "CB": "Centre Back", "RB": "Right Back", "DM": "Defensive Mid",
    "CM": "Central Mid", "AM": "Attacking Mid", "LW": "Left Wing", "RW": "Right Wing", "ST": "Striker",
]

// MARK: - hero

private struct Hero: View {
    let report: Report
    @Environment(\.theme) private var theme
    @Environment(AppModel.self) private var model

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .center, spacing: 24) {
                left.frame(maxWidth: .infinity, alignment: .leading)
                pitch.frame(minWidth: 340, maxWidth: 420)      // the design's lg:col-span-5, compact pitch max-w 390
            }
            left.frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(24)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background {
            // the design's two faint glows: the club colour from the top-left, the brand green behind the pitch
            ZStack {
                RadialGradient(colors: [Color(hex: report.club.kit).opacity(0.065), .clear], center: .topLeading, startRadius: 0, endRadius: 640 * 0.6)
                RadialGradient(colors: [Palette.brandHigh.opacity(0.035), .clear], center: UnitPoint(x: 0.92, y: 0.5), startRadius: 0, endRadius: 520 * 0.65)
            }
        }
        .hubCard()
    }

    private var left: some View {
        VStack(alignment: .leading, spacing: 20) {
            VStack(alignment: .leading, spacing: 12) {
                eyebrow
                HStack(alignment: .firstTextBaseline, spacing: 12) {
                    Text(report.club.name.uppercased()).heroFont(38).lineLimit(1).minimumScaleFactor(0.5)
                    if let save = report.saveName {
                        Text("Save: \(save)").font(.system(size: 12, weight: .medium)).foregroundStyle(.tertiary)
                    }
                }
                meta
            }
            league
            buttons
        }
    }

    private var eyebrow: some View {
        HStack(spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: "sparkles").font(.system(size: 10)).foregroundStyle(DS.Delta.warn)
                Text("FM27 SQUAD REPORT").font(.system(size: 11, weight: .semibold)).tracking(0.77).foregroundStyle(.secondary)
            }
            Text("·").foregroundStyle(.tertiary)
            pill(report.formation.title, symbol: "shield", tint: Palette.brandHigh, strong: true)
            pill(Fmt.day(report.gameDate), symbol: "calendar", tint: .secondary, strong: false)
        }
    }

    private func pill(_ text: String, symbol: String, tint: some ShapeStyle, strong: Bool) -> some View {
        HStack(spacing: 6) {
            Image(systemName: symbol).font(.system(size: 10)).foregroundStyle(tint)
            Text(text).font(.system(size: 11.5, weight: strong ? .medium : .regular)).monospacedDigit()
                .foregroundStyle(strong ? .primary : .secondary)
        }
        .padding(.horizontal, 10).padding(.vertical, 2)
        .background(Color.primary.opacity(strong ? 0.06 : 0.04), in: Capsule())
        .overlay(Capsule().strokeBorder(Color.primary.opacity(strong ? 0.09 : 0.07)))
    }

    private var meta: some View {
        HStack(alignment: .top, spacing: 16) {
            metaCell("In-game date", Fmt.day(report.gameDate), strong: true)
            metaCell("Primary system", report.formation.title, strong: true)
            metaCell("Active save", report.saveName ?? "–", strong: false)
        }
        .padding(.top, 4)
        .frame(maxWidth: 490, alignment: .leading)
        .overlay(alignment: .top) { Rectangle().fill(Color.primary.opacity(0.06)).frame(height: 1) }
    }

    private func metaCell(_ label: String, _ value: String, strong: Bool) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.system(size: 11)).foregroundStyle(.tertiary)
            Text(value).font(.system(size: 13, weight: strong ? .semibold : .medium)).monospacedDigit()
                .foregroundStyle(strong ? .primary : .secondary).lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    /// The league position: the app's colours (club ink on paper looks, signal green on dark).
    private var positionInk: Color {
        switch theme.heroStyle {
        case .kit: Color(hex: report.club.ink)
        case .glass, .board: Palette.brandHigh
        case .paper, .sticker: theme.scheme == .light ? theme.kitOnLight : Color(hex: report.club.kit).mix(with: .white, by: 0.25)
        }
    }

    @ViewBuilder
    private var league: some View {
        if let rec = report.performance.record {
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .firstTextBaseline, spacing: 12) {
                    Text(Fmt.ordinal(rec.pos)).positionFont(32).foregroundStyle(positionInk)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(Fmt.ordinal(rec.pos)) of \(rec.of)\(report.performance.leagueName.map { " · \($0)" } ?? "") · \(rec.pts) pts")
                            .font(.system(size: 13, weight: .medium))
                        let gd = rec.gf - rec.ga
                        Text("P\(rec.p) W\(rec.w) D\(rec.d) L\(rec.l) · GD \(gd > 0 ? "+" : "")\(gd) (\(rec.gf)–\(rec.ga))")
                            .font(.system(size: 11.5)).foregroundStyle(.secondary)
                    }
                    .monospacedDigit()
                }
                if !report.performance.form.isEmpty {
                    HStack(spacing: 8) {
                        HStack(spacing: 6) {
                            ForEach(Array(report.performance.form.enumerated()), id: \.offset) { _, f in FormPill(form: f) }
                        }
                        Text("Last \(report.performance.form.count) matches").font(.system(size: 11)).foregroundStyle(.tertiary)
                    }
                }
            }
            .accessibilityElement(children: .contain)
        }
    }

    private var buttons: some View {
        HStack(spacing: 10) {
            CapsuleButton(title: "Open Best XIs", symbol: "arrow.right", primary: true) { model.go(Route.xis) }
            CapsuleButton(title: "Plan in Sandbox", symbol: nil, primary: false) { model.go(Route.sandbox) }
        }
    }

    private var pitch: some View {
        VStack(spacing: 6) {
            Pitch3D(report: report, xi: report.xi1, compact: true)
                .frame(maxWidth: .infinity).frame(height: 300)
            Text("Your best XI · Drag to tilt").font(.system(size: 11)).foregroundStyle(.tertiary)
        }
    }
}

/// W / D / L, 24 × 22, radius 5: tinted fill, coloured edge and letter (the design's form pills, the app's colours).
private struct FormPill: View {
    let form: Performance.Result
    @State private var hover = false

    var body: some View {
        let c = form.res == "W" ? DS.Delta.up : form.res == "L" ? DS.Delta.down : DS.Delta.flat
        Text(form.res)
            .font(.system(size: 11, weight: .bold))
            .foregroundStyle(c)
            .frame(width: 24, height: 22)
            .background(c.opacity(0.16), in: RoundedRectangle(cornerRadius: 5, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 5, style: .continuous).strokeBorder(c.opacity(0.32)))
            .offset(y: hover ? -2 : 0)
            .animation(.easeOut(duration: 0.14), value: hover)
            .onHover { hover = $0 }
            .help("\(form.score) \(form.home ? "vs" : "at") \(form.opp)")
            .accessibilityLabel("\(form.res == "W" ? "Won" : form.res == "L" ? "Lost" : "Drew") \(form.score) \(form.home ? "against" : "at") \(form.opp)")
    }
}

/// The design's hero buttons: 34 pt capsules. Primary is raised with an edge; secondary is a ghost.
private struct CapsuleButton: View {
    let title: String
    let symbol: String?
    let primary: Bool
    let action: () -> Void
    @State private var hover = false

    var body: some View {
        Button(action: action) {
            HStack(spacing: primary ? 8 : 6) {
                if let symbol {
                    Image(systemName: symbol).font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(hover ? .primary : .secondary)
                        .offset(x: hover ? 2 : 0)
                }
                Text(title).font(.system(size: primary ? 12.5 : 12, weight: primary ? .medium : .regular))
                    .foregroundStyle(primary || hover ? .primary : .secondary)
            }
            .padding(.horizontal, primary ? 16 : 14)
            .frame(height: 34)
            .background(primary ? Color.primary.opacity(hover ? 0.1 : 0.06) : Color.primary.opacity(hover ? 0.05 : 0), in: Capsule())
            .overlay(Capsule().strokeBorder(Color.primary.opacity(primary ? (hover ? 0.22 : 0.13) : 0.07)))
            .shadow(color: .black.opacity(primary ? 0.35 : 0), radius: 3, y: 2)
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .onHover { hover = $0 }
        .animation(.easeOut(duration: 0.14), value: hover)
    }
}

// MARK: - snapshot

private struct Snapshot: View {
    let report: Report
    @Environment(AppModel.self) private var model

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HubHeader(title: "Club snapshot", sub: "Financial headroom, starting XI quality, and current matchday availability")
            ViewThatFits(in: .horizontal) { tiles(4); tiles(2) }
        }
    }

    private func tiles(_ across: Int) -> some View {
        let squad = report.players.filter { $0.location == "squad" }
        let injured = squad.filter(\.isInjured).count
        let suspended = squad.filter(\.isSuspended).count
        let f = report.finances
        return LazyVGrid(columns: Array(repeating: GridItem(.flexible(minimum: 200), spacing: 12, alignment: .top), count: across), spacing: 12) {
            if let left = f.transferLeft {
                Tile(label: "Transfer budget left", value: Fmt.money(left), go: { model.go(Route.transfers) }) {
                    Text("as of \(Fmt.month(f.month)) month-end").font(.system(size: 11)).foregroundStyle(.tertiary)
                }
            }
            if let bill = f.wageBill, let budget = f.wageBudget, budget > 0 {
                let room = budget - bill
                Tile(label: "Wage bill / budget (p/w)", value: Fmt.wage(bill), unit: "/ \(Fmt.wage(budget))", go: { model.go(Route.squad) }) {
                    VStack(alignment: .leading, spacing: 6) {
                        Meter(value: min(bill, budget), total: budget, color: room >= 0 ? DS.Delta.up : DS.Delta.down)
                        Text("\(Fmt.wage(abs(room)))/wk \(room >= 0 ? "room" : "over")").font(.system(size: 11)).foregroundStyle(.tertiary)
                    }
                }
            }
            if let level = report.xiLevel {
                Tile(label: "XI level", value: String(format: "%.1f", level), unit: "★ average", go: { model.go(Route.xis) }) {
                    HStack {
                        StarsView(value: level, size: 13)
                        Spacer(minLength: 4)
                        Text("of your best XI").font(.system(size: 11)).foregroundStyle(.tertiary)
                    }
                }
            }
            Tile(label: "Unavailable now", value: "\(injured + suspended)", unit: "players", dot: injured + suspended > 0,
                 go: { model.go(Route.squad) }) {
                HStack(spacing: 6) {
                    Text("\(injured) injured").foregroundStyle(DS.Delta.warn.opacity(0.9))
                    Text("·").foregroundStyle(.tertiary)
                    Text("\(suspended) suspended").foregroundStyle(DS.Delta.down.opacity(0.9))
                }
                .font(.system(size: 11)).monospacedDigit()
            }
        }
    }
}

/// The design's snapshot card: p-16, min height 116, label / value (28) with its unit / a bottom line; clickable.
private struct Tile<Bottom: View>: View {
    let label: String
    let value: String
    var unit: String? = nil
    var dot = false
    let go: () -> Void
    @ViewBuilder var bottom: () -> Bottom

    var body: some View {
        HubButton(action: go) {
            VStack(alignment: .leading, spacing: 0) {
                HStack {
                    Text(label).font(.system(size: 12, weight: .medium)).foregroundStyle(.secondary)
                    Spacer(minLength: 4)
                    if dot { Circle().fill(DS.Delta.warn.opacity(0.8)).frame(width: 8, height: 8) }
                }
                Spacer(minLength: 6)
                HStack(alignment: .firstTextBaseline, spacing: 6) {
                    NumberText(value, size: 28)
                    if let unit { Text(unit).font(.system(size: 13, weight: .medium)).foregroundStyle(.secondary) }
                }
                Spacer(minLength: 6)
                bottom()
            }
            .padding(16)
            .frame(maxWidth: .infinity, minHeight: 116, alignment: .topLeading)
        }
        .accessibilityElement(children: .combine)
    }
}

// MARK: - where the squad needs work

private struct NeedsWork: View {
    let report: Report
    @Environment(AppModel.self) private var model
    @State private var width: CGFloat = 1100
    private var noteColumns: Int { width >= 900 ? 4 : 2 }

    var body: some View {
        let need = report.verdicts.filter(\.needsWork)
        let rest = report.verdicts.filter { !$0.needsWork }
        VStack(alignment: .leading, spacing: 12) {
            HubHeader(title: "Where the squad needs work",
                      sub: "After arranged transfers & loans go through · loaned-out players not counted") {
                Button { model.go(Route.positions) } label: {
                    HStack(spacing: 4) {
                        Text("All \(report.verdicts.count) positions")
                        Image(systemName: "chevron.right").font(.system(size: 10, weight: .semibold))
                    }
                    .font(.system(size: 12, weight: .medium)).foregroundStyle(.secondary)
                }
                .buttonStyle(.plain).pointerStyle(.link)
            }
            if need.isEmpty {
                Label("Nothing urgent: every position in your tactic is covered. 🔥", systemImage: "checkmark.seal.fill")
                    .foregroundStyle(Palette.verdict("green"))
            }
            cards(need)
            if !rest.isEmpty {
                notes(rest)
                    .padding(.top, 2)
            }
        }
        .onGeometryChange(for: CGFloat.self, of: { $0.size.width }) { width = $0 }
    }

    /// Three across on a wide window (the design's xl:grid-cols-3), then two, then one. A real Grid, so every card in
    /// a row is as tall as the tallest and Starter / Backup sit at the bottom, like the design's CSS grid rows.
    private func cards(_ need: [Verdict]) -> some View {
        NeedsGrid(need: need, report: report)
    }

    /// The design's compact strip for the positions that are fine: code, status, one line, chevron.
    private func notes(_ rest: [Verdict]) -> some View {
        // the design's lg:grid-cols-4: four equal columns (two when narrow), even when there are fewer than four
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 10, alignment: .top), count: noteColumns), spacing: 10) {
            ForEach(rest) { v in
                HubButton(action: { model.go(Route.positions) }) {
                    HStack(alignment: .top, spacing: 8) {
                        VStack(alignment: .leading, spacing: 4) {
                            HStack(spacing: 8) {
                                Text(v.slot).font(.system(size: 12, weight: .bold))
                                Badge(label: v.title, color: Palette.verdict(v.level))
                            }
                            Text(v.text).font(.system(size: 11)).foregroundStyle(.secondary).lineLimit(1).help(v.text)
                        }
                        Spacer(minLength: 0)
                        Image(systemName: "chevron.right").font(.system(size: 10, weight: .semibold)).foregroundStyle(.tertiary)
                            .padding(.top, 2)
                    }
                    .padding(.horizontal, 12).padding(.vertical, 10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .accessibilityElement(children: .combine)
            }
        }
    }
}

private struct NeedsGrid: View {
    let need: [Verdict]
    let report: Report
    @State private var width: CGFloat = 1100

    var body: some View {
        let across = max(1, min(3, Int((width + 12) / (320 + 12))))
        let rows = stride(from: 0, to: need.count, by: across).map { Array(need.enumerated())[$0..<min($0 + across, need.count)] }
        Grid(horizontalSpacing: 12, verticalSpacing: 12) {
            ForEach(Array(rows.enumerated()), id: \.offset) { _, row in
                GridRow {
                    ForEach(row, id: \.element.id) { i, v in
                        VerdictCard(rank: i + 1, verdict: v, report: report).frame(maxHeight: .infinity)
                    }
                    ForEach(0..<(across - row.count), id: \.self) { _ in Color.clear.gridCellUnsizedAxes([.horizontal, .vertical]) }
                }
            }
        }
        .frame(maxWidth: .infinity)
        .onGeometryChange(for: CGFloat.self, of: { $0.size.width }) { width = $0 }
    }
}

private struct VerdictCard: View {
    let rank: Int
    let verdict: Verdict
    let report: Report
    @State private var hover = false

    var body: some View {
        let color = Palette.verdict(verdict.level)
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Text("\(rank)").font(.system(size: 10.5, weight: .semibold)).monospacedDigit().foregroundStyle(.secondary)
                        .frame(width: 20, height: 20)
                        .background(Color.primary.opacity(0.05), in: Circle())
                        .overlay(Circle().strokeBorder(Color.primary.opacity(0.08)))
                    Text(verdict.slot).font(.system(size: 12, weight: .bold))
                        .padding(.horizontal, 8).padding(.vertical, 2)
                        .background(Color.primary.opacity(0.06), in: RoundedRectangle(cornerRadius: 5, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 5, style: .continuous).strokeBorder(Color.primary.opacity(0.10)))
                    if let name = positionNames[verdict.slot] {
                        Text(name).font(.system(size: 11.5)).foregroundStyle(.tertiary).lineLimit(1)
                    }
                    Spacer(minLength: 4)
                    Badge(label: verdict.title, color: color, dot: true)
                }
                // two lines at most, so Starter / Backup start at the same height in every card of a row
                Text(verdict.text)
                    .font(.system(size: 12.5)).foregroundStyle(.primary.opacity(0.9)).lineSpacing(3)
                    .lineLimit(2, reservesSpace: true)
                    .help(verdict.text)
            }
            Spacer(minLength: 0)
            VStack(spacing: 6) {
                people("Starter", "Starters", report.xi1, strong: true)
                people("Backup", "Backups", report.xi2, strong: false)
            }
            .padding(.top, 10)
            .overlay(alignment: .top) { Rectangle().fill(Color.primary.opacity(0.06)).frame(height: 1) }
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .overlay(alignment: .top) {
            // the design's 1.5 pt accent across the top, fading out to the right
            LinearGradient(stops: [.init(color: color.opacity(0.7), location: 0),
                                   .init(color: DS.Delta.warn.opacity(verdict.level == "red" ? 0.5 : 0.25), location: 0.5),
                                   .init(color: .clear, location: 1)], startPoint: .leading, endPoint: .trailing)
                .frame(height: 1.5)
        }
        .modifier(HubCard(hover: hover))
        .onHover { hover = $0 }
        .animation(.easeOut(duration: 0.14), value: hover)
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private func people(_ one: String, _ many: String, _ xi: [XISlot], strong: Bool) -> some View {
        let here = xi.filter { $0.slot == verdict.slot }
        if !here.isEmpty {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(here.count > 1 ? many : one).font(.system(size: 11, weight: .medium)).foregroundStyle(.tertiary)
                    .frame(width: 56, alignment: .leading)
                Spacer(minLength: 0)
                FlowRow(spacing: 12) {
                    ForEach(Array(here.enumerated()), id: \.offset) { _, slot in
                        if let p = report.player(slot.uid), let r = p.rating(at: verdict.slot) {
                            PersonChip(player: p, stars: r.stars, fam: r.fam, strong: strong)
                        } else {
                            Text("nobody left").font(.system(size: 12).italic()).foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
    }
}

/// Name, stars and familiarity letter; clicking opens the player in the side panel (the design's player buttons).
private struct PersonChip: View {
    let player: Player
    let stars: Double
    let fam: String
    let strong: Bool
    @Environment(AppModel.self) private var model
    @State private var hover = false

    var body: some View {
        Button { model.inspect(player.uid) } label: {
            HStack(spacing: 6) {
                Text(surname(player.name)).font(.system(size: 12, weight: .medium))
                    .foregroundStyle(strong || hover ? .primary : .secondary)
                if player.isInjured {
                    Image(systemName: "exclamationmark.triangle").font(.system(size: 10)).foregroundStyle(DS.Delta.warn)
                        .accessibilityLabel("Injured")
                }
                StarsView(value: stars, size: 10.5)
                FamiliarityBadge(code: fam)
            }
            .padding(.horizontal, 6).padding(.vertical, 2)
            .background(Color.primary.opacity(hover ? 0.06 : 0), in: RoundedRectangle(cornerRadius: 5, style: .continuous))
            .padding(.horizontal, -4)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { hover = $0 }
    }
}

// MARK: - latest

private struct Latest: View {
    @Environment(AppModel.self) private var model
    let items: [NewsItem]
    @State private var filter = "All"

    private static let groups = ["All", "Squad", "Transfers", "Medical", "Contracts"]

    private func group(_ kind: String) -> String {
        switch kind {
        case "deal-in", "deal-out", "loan-in", "loan-out": "Transfers"
        case "inj-short", "inj-long", "sus": "Medical"
        case "expiring": "Contracts"
        default: "Squad"
        }
    }

    var body: some View {
        let shown = filter == "All" ? items : items.filter { group($0.kind) == filter }
        VStack(alignment: .leading, spacing: 12) {
            HubHeader(title: "Latest", sub: "From your save: moves, injuries, bans, and expiring contracts") { pills }
            VStack(spacing: 0) {
                ForEach(Array(shown.enumerated()), id: \.offset) { i, item in
                    Row(item: item) { model.go(Route(webHash: item.route) ?? .home) }
                    if i < shown.count - 1 { Rectangle().fill(Color.primary.opacity(0.06)).frame(height: 1) }
                }
                if shown.isEmpty {
                    Text("Nothing under \(filter.lowercased()) right now.").font(.system(size: 12.5)).foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, minHeight: 40)
                }
            }
            .hubCard()
        }
    }

    /// The design's filter pills: a capsule track with the picked one raised.
    private var pills: some View {
        HStack(spacing: 0) {
            ForEach(Self.groups, id: \.self) { g in
                Button { filter = g } label: {
                    Text(g).font(.system(size: 11.5, weight: .medium))
                        .foregroundStyle(filter == g ? .primary : .secondary)
                        .padding(.horizontal, 10).padding(.vertical, 4)
                        .background(filter == g ? Color.primary.opacity(0.08) : .clear, in: Capsule())
                        .contentShape(Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(filter == g ? .isSelected : [])
            }
        }
        .padding(2)
        .background(Color.primary.opacity(0.03), in: Capsule())
        .overlay(Capsule().strokeBorder(Color.primary.opacity(0.08)))
        .animation(.easeOut(duration: 0.14), value: filter)
    }

    /// 40 pt row: tag (88 wide) / text / the date or detail at the right / chevron.
    private struct Row: View {
        let item: NewsItem
        let go: () -> Void
        @State private var hover = false

        var body: some View {
            let (text, meta) = split(item.text)
            Button(action: go) {
                HStack(spacing: 12) {
                    NewsTag(item: item).frame(width: 88, alignment: .leading)
                    Text(text).font(.system(size: 12.5)).lineLimit(1).frame(maxWidth: .infinity, alignment: .leading)
                    if let meta {
                        Text(meta).font(.system(size: 11.5)).monospacedDigit()
                            .foregroundStyle(hover ? .secondary : .tertiary).lineLimit(1)
                    }
                    Image(systemName: "chevron.right").font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(hover ? .primary : .tertiary)
                        .offset(x: hover ? 2 : 0)
                        .accessibilityHidden(true)
                }
                .padding(.horizontal, 14)
                .frame(height: 40)
                .background(hover ? Color.primary.opacity(0.04) : .clear)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .onHover { hover = $0 }
            .animation(.easeOut(duration: 0.14), value: hover)
        }

        /// "Curtis Jones joins Tottenham, 2 Jan 2027" → the move, and "2 Jan 2027" for the right-hand column.
        private func split(_ s: String) -> (String, String?) {
            guard let comma = s.range(of: ", ", options: .backwards) else { return (s, nil) }
            let tail = String(s[comma.upperBound...])
            guard tail.rangeOfCharacter(from: .decimalDigits) != nil, tail.count <= 24 else { return (s, nil) }
            return (String(s[..<comma.lowerBound]), tail)
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
    /// The first title on a page: 28 pt. Sections inside a page: 20 pt (DESIGN.md › Typography).
    var page = false
    @Environment(\.theme) private var theme

    init(_ title: String, sub: String? = nil, page: Bool = false) {
        self.title = title
        self.sub = sub
        self.page = page
    }

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            Text(title).displayFont(page ? 28 : 20)
                .accessibilityAddTraits(.isHeader)
            if let sub { Text(sub).font(.system(size: 13)).foregroundStyle(.secondary) }
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
