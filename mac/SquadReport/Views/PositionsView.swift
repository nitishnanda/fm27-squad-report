import SwiftUI

/// Positions: everyone who can play each position, best first. Positions that need work come first (red, then amber),
/// so the depth you're short of is the first thing you see. Same rules as the web app's depth chart.
/// Laid out from his Figma Make design (PositionsView.tsx): a key bar, then a three-column grid of position cards.
struct PositionsView: View {
    let report: Report

    var body: some View {
        let cards = PositionCards.build(report)
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                PageHeader(title: "Position by position",
                           sub: "Everyone who can play each tactical slot · positions needing reinforcement listed first")
                PositionsKey(report: report)
                CardGrid(items: cards, minWidth: 320, maxColumns: 3, spacing: 14) { PositionCardView(card: $0, report: report) }
            }
            .frame(maxWidth: 1172, alignment: .leading)
            .padding(.horizontal, 24).padding(.vertical, 20)
            .frame(maxWidth: .infinity)
        }
    }
}

// MARK: - the data for each card

struct PositionEntry: Identifiable {
    let player: Player
    let rating: Rating
    let games: Int
    let natural: Bool          // natural here (18+) in either phase
    let weak: [String]         // e.g. ["RWB: unconvincing"]: a phase he doesn't know well
    var id: Int { player.uid }
}

struct PositionCard: Identifiable {
    let info: PositionsInfo.Card
    let verdict: Verdict?
    let row: Int?               // first formation row with this slot (for the Sandbox-style rating of regulars)
    let entries: [PositionEntry]    // seniors (loans out last), then the best youth
    let moreYouth: Int
    let halfOK: [String]            // "Bradley (RWB ✓ RB ✗)"
    var id: String { info.slot }
}

enum PositionCards {
    static let okWords: Set<String> = ["natural", "accomplished"]
    static let levelOrder = ["red": 0, "amber": 1, "green": 2, "grey": 3]

    static func build(_ report: Report) -> [PositionCard] {
        guard let pos = report.positions else { return [] }
        let verdicts = Dictionary(report.verdicts.map { ($0.slot, $0) }, uniquingKeysWith: { a, _ in a })
        let cards = pos.cards.enumerated().compactMap { order, info -> (Int, Int, PositionCard)? in
            guard let v = verdicts[info.slot] else { return nil }
            return (levelOrder[v.level] ?? 4, order, card(info, verdict: v, report: report, pos: pos))
        }
        return cards.sorted { ($0.0, $0.1) < ($1.0, $1.1) }.map(\.2)
    }

    static func card(_ info: PositionsInfo.Card, verdict: Verdict?, report: Report, pos: PositionsInfo) -> PositionCard {
        let row = report.formation.rows.firstIndex { $0.slot == info.slot }

        /// His rating here: if he can play it, or if he's played here a lot this season anyway.
        func here(_ p: Player) -> Rating? {
            if let r = p.rating(at: info.slot) { return r }
            if let row, p.games(at: info.slot) >= pos.playedMany { return p.openRating(row: row) }
            return nil
        }
        func entry(_ p: Player, _ r: Rating) -> PositionEntry {
            let words = p.familiarity(at: info.slot)
            let codes = info.twoPhases ? [info.ip, info.oop] : [info.ip]
            let weak = zip(codes, words).filter { !okWords.contains($0.1) }.map { "\($0.0): \($0.1)" }
            return PositionEntry(player: p, rating: r, games: p.games(at: info.slot), natural: words.contains("natural"), weak: weak)
        }

        let everyone = report.players.compactMap { p in here(p).map { (p, $0) } }
        let seniors = everyone.filter { !$0.0.youth }
            .sorted { a, b in
                (a.0.isLoanedOut ? 1 : 0, -a.1.stars, a.1.fam == "N" ? 0 : 1) < (b.0.isLoanedOut ? 1 : 0, -b.1.stars, b.1.fam == "N" ? 0 : 1)
            }
        let youth = everyone.filter { $0.0.youth }.sorted { $0.1.stars > $1.1.stars }
        let shownYouth = Array(youth.prefix(pos.youthPerCard))

        var half: [String] = []
        if info.twoPhases {
            for p in report.players where p.rating(at: info.slot) == nil && !p.youth && ["squad", "incoming"].contains(p.location) {
                let words = p.familiarity(at: info.slot)
                let ok = words.map { okWords.contains($0) }
                if ok.contains(true), ok.contains(false) {
                    let (good, bad) = ok[0] ? (info.ip, info.oop) : (info.oop, info.ip)
                    half.append("\(surname(p.name)) (\(good) ✓ \(bad) ✗)")
                }
            }
        }
        return PositionCard(info: info, verdict: verdict, row: row,
                            entries: (seniors + shownYouth).map { entry($0.0, $0.1) },
                            moreYouth: max(0, youth.count - pos.youthPerCard), halfOK: half)
    }
}

// MARK: - views

private struct PositionCardView: View {
    let card: PositionCard
    let report: Report
    @State private var showAll = false

    var body: some View {
        let shown = report.positions?.shown ?? 5
        let color = Palette.verdict(card.verdict?.level ?? "grey")
        let visible = showAll ? card.entries : Array(card.entries.prefix(shown))
        VStack(alignment: .leading, spacing: 0) {
            // the design's card head: code, name, the "with / without the ball" note, the status pill; a rule under
            HStack(alignment: .center, spacing: 8) {
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 8) {
                        Text(card.info.slot).font(.system(size: 15, weight: .bold))
                        Text(card.info.name).font(.system(size: 12)).foregroundStyle(.secondary).lineLimit(1)
                    }
                    if card.info.twoPhases {
                        Text("\(card.info.ip) with the ball · \(card.info.oop) without it")
                            .font(.system(size: 10.5)).foregroundStyle(.tertiary)
                    }
                }
                Spacer(minLength: 4)
                if let v = card.verdict {
                    Badge(label: v.title, color: v.level == "grey" ? .secondary : color).help(v.text)
                }
            }
            .padding(14)
            .overlay(alignment: .bottom) { Rectangle().fill(Color.primary.opacity(0.06)).frame(height: 1) }
            if card.entries.isEmpty {
                Text("Nobody can play here.").font(.system(size: 12)).foregroundStyle(.secondary).padding(14)
            }
            ForEach(Array(visible.enumerated()), id: \.element.id) { i, e in
                if i > 0 { Rectangle().fill(Color.primary.opacity(0.05)).frame(height: 1) }
                PositionRow(entry: e, card: card, report: report)
            }
            if card.entries.count > shown || card.moreYouth > 0 || !card.halfOK.isEmpty {
                Rectangle().fill(Color.primary.opacity(0.05)).frame(height: 1)
                if showAll {
                    if card.moreYouth > 0 {
                        Text("+\(card.moreYouth) more in your youth teams").font(.system(size: 11)).foregroundStyle(.tertiary)
                            .padding(.horizontal, 14).padding(.top, 8)
                    }
                    if !card.halfOK.isEmpty {
                        Text("Not listed: your tactic needs \(card.info.ip) in possession and \(card.info.oop) out of it. \(card.halfOK.joined(separator: ", "))")
                            .font(.system(size: 11)).foregroundStyle(.tertiary)
                            .padding(.horizontal, 14).padding(.top, 8)
                    }
                }
                Button {
                    withAnimation(.snappy(duration: 0.25)) { showAll.toggle() }
                } label: {
                    HStack(spacing: 4) {
                        Text(showAll ? "Show fewer" : moreLabel(shown))
                        Image(systemName: showAll ? "chevron.up" : "chevron.down").font(.system(size: 9, weight: .bold)).accessibilityHidden(true)
                    }
                    .font(.system(size: 11.5, weight: .medium))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 14).frame(height: 32)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .hubCard()
        .accessibilityElement(children: .contain)
        .accessibilityLabel("\(card.info.name): \(card.verdict?.title ?? "")")
    }

    private func moreLabel(_ shown: Int) -> String {
        var text = card.entries.count > shown ? "Show all \(card.entries.count)" : "Show more"
        if card.moreYouth > 0 { text += " · +\(card.moreYouth) youth" }
        return text
    }
}

/// One 36 pt line per player (the design's rows): familiarity, name, markers | potential, games, stars, age.
private struct PositionRow: View {
    let entry: PositionEntry
    let card: PositionCard
    let report: Report
    @State private var showCard = false
    @State private var hover = false
    @AppStorage("showPotential") private var showPotential = true

    var body: some View {
        let p = entry.player
        let statuses = PlayerStatus.of(p, today: report.gameDate)
        Button {
            showCard = true
        } label: {
            HStack(spacing: 8) {
                FamiliarityBadge(code: entry.rating.fam)
                Text(p.name).font(.system(size: 12, weight: .medium)).lineLimit(1).truncationMode(.tail)
                if p.youth {
                    Text("youth").font(.system(size: 10)).foregroundStyle(.secondary)
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .background(Color.primary.opacity(0.06), in: RoundedRectangle(cornerRadius: 4, style: .continuous))
                }
                // statuses keep their own symbol and colour (his rule: injured, banned, loans and moves stay distinct)
                ForEach(statuses.filter { $0.kind != .expiring }.prefix(2)) { StatusMarker(status: $0) }
                if !entry.weak.isEmpty {
                    Image(systemName: "exclamationmark.triangle").font(.system(size: 10)).foregroundStyle(DS.Delta.warn)
                        .help("Weak in one phase: your \(card.info.slot) plays \(card.info.ip) with the ball and \(card.info.oop) without it, and he's only \(entry.weak.joined(separator: ", ")).")
                        .accessibilityLabel("Weak in one phase: \(entry.weak.joined(separator: ", "))")
                }
                Spacer(minLength: 4)
                if showPotential, let pot = p.potential {
                    Text("pot \(String(format: "%.1f", pot))★")
                        .font(.system(size: 10, weight: .medium)).foregroundStyle(Palette.potential)
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .background(Palette.potential.opacity(0.12), in: RoundedRectangle(cornerRadius: 4, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 4, style: .continuous).strokeBorder(Palette.potential.opacity(0.2)))
                        .fixedSize()
                        .help("Potential: could reach \(Fmt.stars(pot))★ (from FM's hidden potential)")
                        .accessibilityLabel("Potential \(Fmt.stars(pot)) stars")
                }
                Text(entry.games > 0 ? "\(entry.games)" : "")
                    .font(.system(size: 11, weight: .semibold)).monospacedDigit().foregroundStyle(Palette.loanIn)
                    .frame(width: 18, alignment: .trailing)
                    .help(entry.games > 0 ? "\(entry.games) games at \(card.info.slot) this season" : "")
                StarsView(value: entry.rating.stars, size: 10).fixedSize()
                Text(p.age.map(String.init) ?? "").font(.system(size: 11)).foregroundStyle(.tertiary).monospacedDigit()
                    .frame(width: 18, alignment: .trailing)
            }
            .padding(.horizontal, 14)
            .frame(height: 36)
            .background(hover ? Color.primary.opacity(0.04) : .clear)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { hover = $0 }
        .playerActions(p)
        .popover(isPresented: $showCard, arrowEdge: .trailing) {
            PlayerCard(player: p, slotLabel: card.info.slot, card: card.info.slot, row: nil, report: report)
        }
        .accessibilityElement(children: .combine)
    }
}

/// The design's key bar: one line, each item explaining itself on hover.
private struct PositionsKey: View {
    let report: Report

    var body: some View {
        let two = report.positions?.cards.first(where: \.twoPhases)
        FlowRow(spacing: 20) {
            item({ HStack(spacing: 2) { FamiliarityBadge(code: "N"); FamiliarityBadge(code: "A") } }, "natural / accomplished",
                 "How well he knows the position, from FM's own position ratings: N natural, A accomplished.")
            item({ Text("13").font(.system(size: 11.5, weight: .semibold)).monospacedDigit().foregroundStyle(Palette.loanIn) },
                 "appearances this season", "Matches he's played in this position this season, from the game's own match data.")
            item({
                Text("pot 4.0★").font(.system(size: 10, weight: .medium)).foregroundStyle(Palette.potential)
                    .padding(.horizontal, 6).padding(.vertical, 1)
                    .background(Palette.potential.opacity(0.15), in: RoundedRectangle(cornerRadius: 4, style: .continuous))
            }, "high potential",
                 "How good he could become, from FM's hidden potential: the only hidden number this app shows, and only for players 23 and under.")
            item({ Image(systemName: "exclamationmark.triangle").font(.system(size: 10)).foregroundStyle(DS.Delta.warn) }, "phase gap / injury",
                 two.map { "The triangle: your \($0.slot) is a \($0.ip) with the ball and a \($0.oop) without it, and he knows only one of those well. Injuries, bans and moves have their own symbols; hover one for the details." }
                 ?? "He knows the position in one phase of play but not the other.")
        }
        .font(.system(size: 11.5))
        .foregroundStyle(.secondary)
        .padding(.horizontal, 14).padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.primary.opacity(0.03), in: RoundedRectangle(cornerRadius: 8, style: .continuous))   // the design's 8 pt bar
        .overlay(RoundedRectangle(cornerRadius: 8, style: .continuous).strokeBorder(Color.primary.opacity(0.07)))
    }

    private func item<V: View>(@ViewBuilder _ visual: () -> V, _ label: String, _ help: String) -> some View {
        HStack(spacing: 6) {
            visual()
            Text(label)
        }
        .help(help)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label): \(help)")
    }
}
