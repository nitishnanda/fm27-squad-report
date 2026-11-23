import SwiftUI

/// Positions: everyone who can play each position, best first. Positions that need work come first (red, then amber),
/// so the depth you're short of is the first thing you see. Same rules as the web app's depth chart.
struct PositionsView: View {
    let report: Report

    var body: some View {
        let cards = PositionCards.build(report)
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                SectionTitle("Position by position", sub: "everyone who can play there · positions that need work first · click a player for his card")
                PositionsKey(report: report)
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 330), spacing: 14, alignment: .top)], spacing: 14) {
                    ForEach(cards) { PositionCardView(card: $0, report: report) }
                }
            }
            .padding(28)
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
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(card.info.slot).font(.system(size: 22, weight: .heavy).width(.condensed).italic())
                Text(card.info.name).foregroundStyle(.secondary)
                Spacer()
                if let v = card.verdict {
                    Text(v.title)
                        .font(.caption.weight(.bold))
                        .padding(.horizontal, 8).padding(.vertical, 2)
                        .foregroundStyle(v.level == "grey" ? Color.secondary : color)
                        .background(color.opacity(0.16), in: Capsule())
                        .help(v.text)
                }
            }
            .padding(.horizontal, 12).padding(.top, 10).padding(.bottom, 8)
            if card.info.twoPhases {
                Text("\(card.info.ip) with the ball · \(card.info.oop) without it")
                    .font(.caption).foregroundStyle(.secondary)
                    .padding(.horizontal, 12).padding(.bottom, 6)
            }
            Divider()
            if card.entries.isEmpty {
                Text("Nobody can play here.").foregroundStyle(.secondary).padding(12)
            }
            ForEach(visible) { e in
                PositionRow(entry: e, card: card, report: report)
                Divider().opacity(0.5)
            }
            if card.entries.count > shown || card.moreYouth > 0 || !card.halfOK.isEmpty {
                if showAll {
                    if card.moreYouth > 0 {
                        Text("+\(card.moreYouth) more in your youth teams").font(.caption).foregroundStyle(.secondary)
                            .padding(.horizontal, 12).padding(.top, 6)
                    }
                    if !card.halfOK.isEmpty {
                        Text("Not listed: your tactic needs \(card.info.ip) in possession and \(card.info.oop) out of it. \(card.halfOK.joined(separator: ", "))")
                            .font(.caption).foregroundStyle(.secondary)
                            .padding(.horizontal, 12).padding(.top, 6)
                    }
                }
                Button {
                    withAnimation(.snappy(duration: 0.25)) { showAll.toggle() }
                } label: {
                    HStack(spacing: 4) {
                        Text(showAll ? "Show fewer" : moreLabel(shown))
                        Image(systemName: showAll ? "chevron.up" : "chevron.down").font(.caption2.weight(.bold))
                    }
                    .font(.callout.weight(.semibold))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
            }
        }
        .background(.quaternary.opacity(0.45))
        .overlay(alignment: .top) { Rectangle().fill(color).frame(height: 3) }
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        .accessibilityElement(children: .contain)
        .accessibilityLabel("\(card.info.name): \(card.verdict?.title ?? "")")
    }

    private func moreLabel(_ shown: Int) -> String {
        var text = card.entries.count > shown ? "Show all \(card.entries.count)" : "Show more"
        if card.moreYouth > 0 { text += " · +\(card.moreYouth) youth" }
        return text
    }
}

/// One line per player: familiarity, name, markers, stars, age. Details are in the hover text and the card.
private struct PositionRow: View {
    let entry: PositionEntry
    let card: PositionCard
    let report: Report
    @State private var showCard = false

    var body: some View {
        let p = entry.player
        let statuses = PlayerStatus.of(p)
        Button {
            showCard = true
        } label: {
            HStack(spacing: 6) {
                FamiliarityBadge(code: entry.rating.fam)
                Text(p.name).fontWeight(.semibold).lineLimit(1)
                ForEach(statuses.filter { $0.kind != .expiring }.prefix(2)) { StatusMarker(status: $0) }
                if (p.age ?? 99) <= 21 { Tag(text: "U21", color: .secondary) }
                if p.youth { Tag(text: "youth", color: .secondary) }
                Spacer(minLength: 4)
                if !entry.weak.isEmpty {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(Palette.verdict("amber"))
                        .font(.caption)
                        .help("Weak in one phase: your \(card.info.slot) plays \(card.info.ip) with the ball and \(card.info.oop) without it, and he's only \(entry.weak.joined(separator: ", ")).")
                        .accessibilityLabel("Weak in one phase: \(entry.weak.joined(separator: ", "))")
                }
                if let pot = p.potential {
                    Text("↑\(Fmt.stars(pot))").font(.caption.weight(.bold)).foregroundStyle(Palette.potential)
                        .help("Potential: could reach \(Fmt.stars(pot))★ (from FM's hidden potential)")
                }
                if entry.games > 0 {
                    Text("\(entry.games)")
                        .font(.caption2.weight(.heavy)).monospacedDigit()
                        .padding(.horizontal, 5).padding(.vertical, 1)
                        .foregroundStyle(entry.games >= (report.positions?.playedMany ?? 5) ? .white : Palette.loanIn)
                        .background(entry.games >= (report.positions?.playedMany ?? 5) ? Palette.loanIn.opacity(0.75) : .clear, in: RoundedRectangle(cornerRadius: 4))
                        .overlay(RoundedRectangle(cornerRadius: 4).stroke(Palette.loanIn.opacity(0.6)))
                        .help("\(entry.games) games at \(card.info.slot) this season")
                }
                StarsView(value: entry.rating.stars)
                Text(p.age.map(String.init) ?? "").font(.caption).foregroundStyle(.secondary).monospacedDigit()
                    .frame(width: 20, alignment: .trailing)
            }
            .font(.callout)
            .padding(.horizontal, 12).padding(.vertical, 5)
            .background(rowTint)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .popover(isPresented: $showCard, arrowEdge: .trailing) {
            PlayerCard(player: p, slotLabel: card.info.slot, card: card.info.slot, row: nil, report: report)
        }
        .accessibilityElement(children: .combine)
    }

    /// Green: one of his natural positions. Blue: not natural, but he's played here a lot this season.
    private var rowTint: Color {
        if entry.natural { return Palette.transferIn.opacity(0.10) }
        if entry.games >= (report.positions?.playedMany ?? 5) { return Palette.loanIn.opacity(0.13) }
        return .clear
    }
}

private struct Tag: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.system(size: 9.5, weight: .bold))
            .padding(.horizontal, 4).padding(.vertical, 0.5)
            .foregroundStyle(color)
            .overlay(RoundedRectangle(cornerRadius: 3).stroke(color.opacity(0.6)))
    }
}

/// The key, each item explaining itself on hover.
private struct PositionsKey: View {
    let report: Report

    var body: some View {
        let many = report.positions?.playedMany ?? 5
        let two = report.positions?.cards.first(where: \.twoPhases)
        FlowRow(spacing: 16) {
            item({ HStack(spacing: 2) { FamiliarityBadge(code: "N"); FamiliarityBadge(code: "A") } }, "natural / accomplished",
                 "How well he knows the position, from FM's own position ratings: N natural, A accomplished.")
            item({ swatch(Palette.transferIn.opacity(0.35)) }, "natural position", "Green row: one of his natural positions, where he's most at home.")
            item({ swatch(Palette.loanIn.opacity(0.4)) }, "played there \(many)+ times",
                 "Blue row: not natural for him, but he's played here in \(many) or more matches this season.")
            item({ Text("7").font(.caption2.weight(.heavy)).foregroundStyle(Palette.loanIn) }, "games there this season",
                 "Matches he's played in this position this season, from the game's own match data.")
            item({ Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(Palette.verdict("amber")) }, "weak in one phase",
                 two.map { "Your \($0.slot) is a \($0.ip) with the ball and a \($0.oop) without it. The warning means he knows one of those well but not the other, so he'll be a bit off in that half of the game." }
                 ?? "He knows the position in one phase of play but not the other.")
            item({ Text("↑4").font(.caption.weight(.bold)).foregroundStyle(Palette.potential) }, "potential",
                 "How good he could become, from FM's hidden potential: the only hidden number this app shows, and only for players 23 and under.")
            item({ Image(systemName: "cross.case.fill").foregroundStyle(Palette.injuryShort) }, "status",
                 "Injuries, bans, loans and moves, each with its own symbol and colour. Hover one for the details.")
        }
        .font(.callout)
        .foregroundStyle(.secondary)
    }

    private func swatch(_ color: Color) -> some View {
        RoundedRectangle(cornerRadius: 3).fill(color).frame(width: 14, height: 14)
    }

    private func item<V: View>(@ViewBuilder _ visual: () -> V, _ label: String, _ help: String) -> some View {
        HStack(spacing: 6) {
            visual()
            Text(label).underline(pattern: .dot, color: .secondary.opacity(0.6))
        }
        .help(help)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label): \(help)")
    }
}
