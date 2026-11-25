import AppKit
import SwiftUI

/// Best XIs: your strongest XI, then a second XI from who's left, each on its own pitch in your formation.
/// Click a player for his card.
struct BestXIsView: View {
    let report: Report
    /// "3d" (the web's default) or "flat". Written only when he clicks the switch, like the web.
    @AppStorage("xisView") private var view = "3d"
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.colorScheme) private var scheme
    @Environment(\.theme) private var theme
    @State private var copied = false

    var body: some View {
        // Laid out from his Figma Make design (BestXIsView.tsx): page header with Copy as Image and a 3D / Flat pill
        // switch, then the two XIs side by side, each in a card. Both pitches shrink to fit the window.
        GeometryReader { geo in
            let gap: CGFloat = 16, padH: CGFloat = 24, padV: CGFloat = 20, header: CGFloat = 52, cardChrome: CGFloat = 40 + 46
            let inner = min(geo.size.width, 1220) - padH * 2
            let tall = geo.size.height - padV * 2 - header - cardChrome
            let half = (inner - gap) / 2 - 40
            let threeD = view == "3d"
            // the 3D pitches use the whole card; the flat ones keep the pitch's shape
            let w = threeD ? half : max(220, min(tall * 0.68, half))
            VStack(alignment: .leading, spacing: 20) {
                PageHeader(title: "Best XIs",
                           sub: "\(report.formation.title) · rated for your roles in and out of possession · click any player for his card") {
                    HStack(spacing: 8) {
                        CapsuleAction(title: copied ? "Copied" : "Copy as Image", symbol: copied ? "checkmark" : "doc.on.doc") { copyImage() }
                            .help("Copies your best XI as a picture")
                        PillPicker(options: [("3D", "3d"), ("Flat", "flat")], selection: $view)
                            .help(reduceMotion ? "3D lies flat while Reduce Motion is on" : "3D: drag a pitch to turn it. Flat shows every badge.")
                    }
                }
                HStack(alignment: .top, spacing: gap) {
                    XIPitch(report: report, title: "Best XI", sub: "fully fit squad", xi: report.xi1, threeD: threeD, pitchWidth: w)
                    XIPitch(report: report, title: "Second XI", sub: "from who's left", xi: report.xi2, threeD: threeD, pitchWidth: w,
                            muted: true)
                }
                .frame(maxHeight: .infinity, alignment: .top)
            }
            .frame(maxWidth: 1172)
            .padding(.horizontal, padH).padding(.vertical, padV)
            .frame(maxWidth: .infinity)
        }
    }
}

extension BestXIsView {
    /// Liquid Glass on the switch in the dark looks (macOS 26+); a plain segmented control everywhere else.
    @ViewBuilder
    fileprivate var switcher: some View {
        if #available(macOS 26, *), scheme == .dark {
            GlassEffectContainer {
                HStack(spacing: 0) { segment("3D", "3d"); segment("Flat", "flat") }
                    .glassEffect(.regular.interactive(), in: .capsule)
            }
            .help(reduceMotion ? "3D lies flat while Reduce Motion is on" : "3D: drag a pitch to turn it. Flat shows every badge.")
        } else {
            Picker("View", selection: $view) {
                Text("3D").tag("3d")
                Text("Flat").tag("flat")
            }
            .pickerStyle(.segmented).labelsHidden().fixedSize()
            .help(reduceMotion ? "3D lies flat while Reduce Motion is on" : "3D: drag a pitch to turn it. Flat shows every badge.")
        }
    }

    private func segment(_ title: String, _ tag: String) -> some View {
        Button(title) { view = tag }
            .buttonStyle(.plain)
            .padding(.horizontal, 14).padding(.vertical, 5)
            .background(view == tag ? Color.white.opacity(0.22) : .clear, in: .capsule)
            .accessibilityAddTraits(view == tag ? .isSelected : [])
    }

    fileprivate func copyImage() {
        let card = XICard(report: report, title: "Best XI", xi: report.xi1)
            .environment(\.theme, theme)
            .environment(\.colorScheme, scheme)
        let renderer = ImageRenderer(content: card)
        renderer.scale = 2
        guard let image = renderer.nsImage else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.writeObjects([image])
        copied = true
        Task { try? await Task.sleep(for: .seconds(1.6)); copied = false }
    }
}

/// What "Copy as Image" draws: the club, the date and the flat pitch.
private struct XICard: View {
    let report: Report
    let title: String
    let xi: [XISlot]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Circle().fill(Color(hex: report.club.kit)).frame(width: 12, height: 12)
                Text("\(report.club.name) · \(title)").font(.headline)
                Spacer()
                Text("\(report.formation.title) · \(Fmt.day(report.gameDate))").font(.caption).foregroundStyle(.secondary)
            }
            Pitch { size in
                ForEach(Array(report.formation.rows.enumerated()), id: \.offset) { i, row in
                    PitchPlayer(report: report, row: i, rowInfo: row, player: report.player(i < xi.count ? xi[i].uid : nil), interactive: false)
                        .scaleEffect(min(1, size.width / 470))
                        .position(x: size.width * (row.x ?? 50) / 100, y: size.height * (row.y ?? 50) / 100)
                }
            }
        }
        .padding(16)
        .frame(width: 460)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}

private struct XIPitch: View {
    let report: Report
    let title: String
    let sub: String
    let xi: [XISlot]
    var threeD = false
    var pitchWidth: CGFloat = 300
    var muted = false

    var body: some View {
        let rows = report.formation.rows
        let ratings = xi.enumerated().compactMap { i, s in report.player(s.uid)?.rating(row: i)?.stars }
        let average = ratings.isEmpty ? nil : ratings.reduce(0, +) / Double(rows.count)
        let empty = rows.indices.filter { $0 >= xi.count || report.player(xi[$0].uid) == nil }.count
        VStack(alignment: .leading, spacing: 16) {
            // the design's card header: title, note, a red pill for empty slots; the average on the right; a rule under
            HStack(alignment: .center, spacing: 8) {
                Text(title).displayFont(16, .semibold).fixedSize()
                Text(sub).font(.system(size: 12)).foregroundStyle(.secondary).lineLimit(1)
                if empty > 0 { Badge(label: "\(empty) empty slot\(empty == 1 ? "" : "s")", color: DS.Delta.down) }
                Spacer(minLength: 8)
                if let average {
                    StarsView(value: average, size: 13)
                    Text(String(format: "%.1f", average)).font(.system(size: 14, weight: .bold)).monospacedDigit()
                        .foregroundStyle(muted ? .secondary : .primary)
                        .help("Average of the eleven, empty slots count as 0")
                }
            }
            .padding(.bottom, 12)
            .overlay(alignment: .bottom) { Rectangle().fill(Color.primary.opacity(0.06)).frame(height: 1) }
            Group {
                if threeD {
                    Pitch3D(report: report, xi: xi, startTilt: 38)   // flatter than the Home hero's, so the tall card is filled
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
                    .frame(width: pitchWidth)
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .hubCard()
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
        .clipShape(RoundedRectangle(cornerRadius: theme.pitchRadius, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: theme.pitchRadius, style: .continuous).stroke(theme.pitchEdge, lineWidth: theme.look == .sticker ? 3 : 1))
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
    @Environment(\.theme) private var theme

    var body: some View {
        let ink = theme.pitchLine
        Canvas { ctx, size in
            let w = size.width, h = size.height
            let line = GraphicsContext.Shading.color(ink)
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
        .modifier(OptionalPlayerActions(player: interactive ? player : nil))
        .popover(isPresented: $showCard, arrowEdge: .trailing) {
            if let player {
                PlayerCard(player: player, slotLabel: label, card: rowInfo.slot, row: row, report: report)
            }
        }
        .accessibilityLabel(player.map { "\(label): \($0.name), \(Fmt.stars(rating?.stars ?? 0)) stars" } ?? "\(label): nobody")
        .help(player.map { "\($0.name) — click for his card" } ?? "Nobody left for this slot")
    }
}

private struct OptionalPlayerActions: ViewModifier {
    let player: Player?
    func body(content: Content) -> some View {
        if let player { content.playerActions(player) } else { content }
    }
}
