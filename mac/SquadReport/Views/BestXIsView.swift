import SwiftUI

/// Best XIs: your strongest XI, then a second XI from who's left, each on its own pitch in your formation.
/// Click a player for his card.
struct BestXIsView: View {
    let report: Report
    /// "3d" (the web's default) or "flat". Written only when he clicks the switch, like the web.
    @AppStorage("xisView") private var view = "3d"
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        // Both pitches shrink to fit the window, so the whole XI is always on screen without scrolling.
        GeometryReader { geo in
            let gap: CGFloat = 20, pad: CGFloat = 24, header: CGFloat = 46, pitchTitle: CGFloat = 38
            let tall = geo.size.height - pad * 2 - header - pitchTitle
            let width = max(220, min(tall * 0.68, (geo.size.width - pad * 2 - gap) / 2))
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .bottom) {
                    SectionTitle("Best XIs", sub: "\(report.formation.title) · rated for your roles in and out of possession · click a player for his card")
                    Spacer(minLength: 12)
                    Picker("View", selection: $view) {
                        Text("3D").tag("3d")
                        Text("Flat").tag("flat")
                    }
                    .pickerStyle(.segmented).labelsHidden().fixedSize()
                    .help(reduceMotion ? "3D lies flat while Reduce Motion is on" : "3D: drag a pitch to turn it. Flat shows every badge.")
                }
                .frame(height: header - 12, alignment: .bottomLeading)
                let threeD = view == "3d"
                // the 3D pitches use the full half of the window; the flat ones keep the pitch's shape
                let w = threeD ? (geo.size.width - pad * 2 - gap) / 2 : width
                HStack(alignment: .top, spacing: gap) {
                    XIPitch(report: report, title: "Best XI", sub: "fully fit squad", xi: report.xi1, threeD: threeD).frame(width: w)
                    XIPitch(report: report, title: "Second XI", sub: "from who's left", xi: report.xi2, threeD: threeD).frame(width: w)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            }
            .padding(pad)
        }
    }
}

private struct XIPitch: View {
    let report: Report
    let title: String
    let sub: String
    let xi: [XISlot]
    var threeD = false

    var body: some View {
        let rows = report.formation.rows
        let ratings = xi.enumerated().compactMap { i, s in report.player(s.uid)?.rating(row: i)?.stars }
        let average = ratings.isEmpty ? nil : ratings.reduce(0, +) / Double(rows.count)
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline) {
                Text(title).displayFont(22).fixedSize()
                Text(sub).foregroundStyle(.secondary).lineLimit(1).truncationMode(.tail)
                Spacer()
                if let average {
                    StarsView(value: average, size: 12)
                    Text(String(format: "%.1f", average)).font(.callout.weight(.semibold)).monospacedDigit()
                        .help("Average of the eleven, empty slots count as 0")
                }
            }
            if threeD {
                Pitch3D(report: report, xi: xi)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
            Pitch { size in
                ForEach(Array(rows.enumerated()), id: \.offset) { i, row in
                    let slot = i < xi.count ? xi[i] : nil
                    PitchPlayer(report: report, row: i, rowInfo: row, player: report.player(slot?.uid))
                        .scaleEffect(min(1, size.width / 470))
                        .position(x: size.width * (row.x ?? 50) / 100, y: size.height * (row.y ?? 50) / 100)
                }
            }
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel(title)
    }
}

/// A pitch seen from above, your goal at the bottom. `players` gets the pitch size to place cards by percentage.
struct Pitch<Players: View>: View {
    @ViewBuilder var players: (CGSize) -> Players
    @Environment(\.theme) private var theme

    var body: some View {
        GeometryReader { geo in
            ZStack {
                PitchMarkings()
                players(geo.size)
            }
        }
        .aspectRatio(68.0 / 100.0, contentMode: .fit)
        .background(
            LinearGradient(stops: stripes, startPoint: .top, endPoint: .bottom)
        )
        .clipShape(RoundedRectangle(cornerRadius: theme.isGlass ? 22 : 12, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: theme.isGlass ? 22 : 12, style: .continuous).stroke(theme.pitchEdge, lineWidth: 1))
    }

    /// Mown stripes, ten of them.
    private var stripes: [Gradient.Stop] {
        let (a, b) = theme.pitchStripes
        return (0..<10).flatMap { i -> [Gradient.Stop] in
            let c = i.isMultiple(of: 2) ? a : b
            return [.init(color: c, location: Double(i) / 10), .init(color: c, location: Double(i + 1) / 10)]
        }
    }
}

private struct PitchMarkings: View {
    var body: some View {
        Canvas { ctx, size in
            let w = size.width, h = size.height
            let line = GraphicsContext.Shading.color(.white.opacity(0.22))
            let inset: CGFloat = w * 0.04
            var p = Path()
            p.addRect(CGRect(x: inset, y: inset, width: w - inset * 2, height: h - inset * 2))
            p.move(to: CGPoint(x: inset, y: h / 2)); p.addLine(to: CGPoint(x: w - inset, y: h / 2))
            p.addEllipse(in: CGRect(x: w / 2 - w * 0.13, y: h / 2 - w * 0.13, width: w * 0.26, height: w * 0.26))
            // boxes
            p.addRect(CGRect(x: w * 0.22, y: inset, width: w * 0.56, height: h * 0.14))
            p.addRect(CGRect(x: w * 0.22, y: h - inset - h * 0.14, width: w * 0.56, height: h * 0.14))
            p.addRect(CGRect(x: w * 0.36, y: inset, width: w * 0.28, height: h * 0.05))
            p.addRect(CGRect(x: w * 0.36, y: h - inset - h * 0.05, width: w * 0.28, height: h * 0.05))
            ctx.stroke(p, with: line, lineWidth: 1.5)
        }
        .accessibilityHidden(true)
    }
}

/// One player on the pitch: slot, surname, stars. Click for his card (unless `interactive` is off, as on Home).
struct PitchPlayer: View {
    let report: Report
    let row: Int
    let rowInfo: Formation.Row
    let player: Player?
    var interactive = true
    @State private var showCard = false
    @Environment(\.theme) private var theme

    var body: some View {
        let label = rowInfo.label ?? rowInfo.slot
        let rating = player?.rating(row: row)
        let statuses = player.map { PlayerStatus.of($0, today: report.gameDate) } ?? []
        Button {
            if player != nil && interactive { showCard = true }
        } label: {
            VStack(spacing: 3) {
                Text(label)
                    .slotFont(11)
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 2)
                    .background(Color(hex: report.club.kit))
                HStack(spacing: 3) {
                    Text(player.map { surname($0.name) } ?? "Nobody")
                        .font(.system(size: 12.5, weight: .semibold))
                        .foregroundStyle(player == nil ? Palette.verdict("red") : .white)
                        .lineLimit(1)
                        .minimumScaleFactor(0.75)
                    if let first = statuses.first(where: { $0.kind != .expiring }) {
                        StatusMarker(status: first, size: 9)
                    }
                }
                .padding(.horizontal, 6)
                if let rating {
                    HStack(spacing: 3) {
                        StarsView(value: rating.stars, size: 9)
                        FamiliarityBadge(code: rating.fam)
                            .colorScheme(.dark)
                    }
                    .padding(.bottom, 5)
                } else {
                    Spacer().frame(height: 5)
                }
            }
            .frame(width: 104)
            .background(theme.cardFill)
            .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
            .shadow(color: .black.opacity(0.45), radius: 8, y: 6)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .popover(isPresented: $showCard, arrowEdge: .trailing) {
            if let player {
                PlayerCard(player: player, slotLabel: label, card: rowInfo.slot, row: row, report: report)
            }
        }
        .accessibilityLabel(player.map { "\(label): \($0.name), \(Fmt.stars(rating?.stars ?? 0)) stars" } ?? "\(label): nobody")
        .help(player.map { "\($0.name) — click for his card" } ?? "Nobody left for this slot")
    }
}
