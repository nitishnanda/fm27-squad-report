import AppKit
import SwiftUI

/// A player's card, shown in a popover when you click him on a pitch or in a list. Visible facts only: his stars here,
/// how well he knows the position (FM's words), statuses, this season's numbers. Never CA/PA or hidden attributes.
struct PlayerCard: View {
    let player: Player
    /// The slot he's being looked at in ("LCB"), its card ("CB") and formation row, when there is one.
    var slotLabel: String?
    var card: String?
    var row: Int?
    var report: Report?
    /// 300 pt in a popover; the side panel lets it fill the column.
    var fixedWidth = true
    @AppStorage("showPotential") private var showPotential = true

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(player.name).font(.title3.weight(.bold))
                Text(identity).font(.callout).foregroundStyle(.secondary)
            }
            if let here { hereBlock(here) }
            Grid(alignment: .leading, horizontalSpacing: 14, verticalSpacing: 6) {
                if let best = player.best {
                    GridRow {
                        Text("Best slot").foregroundStyle(.secondary)
                        HStack(spacing: 5) {
                            Text(best.slot).fontWeight(.semibold)
                            StarsView(value: best.stars)
                            FamiliarityBadge(code: best.fam)
                        }
                    }
                }
                if let ability = player.abilityBest {
                    GridRow {
                        Text("Ability").foregroundStyle(.secondary)
                        StarsView(value: ability).help("How good he is at his best position in general, ignoring your tactic")
                    }
                }
                if showPotential, let pot = player.potential {
                    GridRow {
                        Text("Potential").foregroundStyle(.secondary)
                        StarsView(value: pot, tint: Palette.potential).help("From FM's hidden potential (players 23 and under)")
                    }
                }
                if let s = player.stats, s.apps > 0 {
                    GridRow {
                        Text("This season").foregroundStyle(.secondary)
                        Text(seasonLine(s)).monospacedDigit()
                    }
                }
            }
            .font(.callout)
            let statuses = PlayerStatus.of(player, today: report?.gameDate)
            if !statuses.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(statuses) { StatusBadge(status: $0, full: true) }
                }
            }
            if !others.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Also rated at").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                    HStack(spacing: 12) {
                        ForEach(others, id: \.0) { slot, r in
                            HStack(spacing: 3) {
                                Text(slot).font(.caption.weight(.bold))
                                Text(Fmt.stars(r.stars) + "★").font(.caption).foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
        }
        .padding(16)
        .frame(minWidth: fixedWidth ? 300 : 240, maxWidth: fixedWidth ? 300 : .infinity, alignment: .leading)
    }

    private var identity: String {
        var bits: [String] = []
        if let age = player.age { bits.append("\(age)") }
        let pos = player.positions.natural.joined(separator: " ")
        if !pos.isEmpty { bits.append(pos) }
        if player.youth { bits.append("youth team") }
        return bits.joined(separator: " · ")
    }

    /// His rating in the slot you clicked him in.
    private var here: Rating? {
        if let row, let r = player.rating(row: row) ?? player.openRating(row: row) { return r }
        if let card { return player.rating(at: card) }
        return nil
    }

    @ViewBuilder
    private func hereBlock(_ r: Rating) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 6) {
                Text("At \(slotLabel ?? card ?? "this slot")").fontWeight(.semibold)
                StarsView(value: r.stars, size: 13)
                Text(Fmt.stars(r.stars) + "★").foregroundStyle(.secondary)
                FamiliarityBadge(code: r.fam)
            }
            if let card, let info = report?.positions?.cards.first(where: { $0.slot == card }) {
                let words = player.familiarity(at: card)
                Text(info.twoPhases
                     ? "\(info.ip) with the ball: \(words[0]) · \(info.oop) without it: \(words[1])"
                     : "\(info.ip): \(words[0])")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .panel(8)
    }

    private var others: [(String, Rating)] {
        player.system.compactMap { slot, r in r.map { (slot, $0) } }
            .filter { $0.0 != card && $0.0 != player.best?.slot }
            .sorted { $0.1.stars > $1.1.stars }
            .prefix(3)
            .map { $0 }
    }

    private func seasonLine(_ s: Player.SeasonStats) -> String {
        var bits = ["\(s.apps) apps", "\(s.g) g", "\(s.a) a"]
        if let avg = s.avg { bits.append(String(format: "%.2f avg", avg)) }
        return bits.joined(separator: " · ")
    }
}

/// Right-click a player anywhere: the side panel, the Squad list, copy his name. Plus a pointing hand on hover.
private struct PlayerActions: ViewModifier {
    let player: Player
    @Environment(AppModel.self) private var model

    func body(content: Content) -> some View {
        content
            .pointerStyle(.link)
            .contextMenu {
                Button("Show in Side Panel") { model.inspect(player.uid) }
                Button("Show in Squad List") { model.showInSquad(player) }
                Divider()
                Button("Copy Name") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(player.name, forType: .string)
                }
            }
    }
}

extension View {
    func playerActions(_ player: Player) -> some View { modifier(PlayerActions(player: player)) }
}
