import AppKit
import SwiftUI

/// A small window that floats over FM: your best XI on a mini pitch and who's out, banned or running out of contract.
/// Only what the report already shows (the XI and the news items).
struct MatchdayView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.theme) private var theme

    var body: some View {
        Group {
            if let report = model.store.report {
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Circle().fill(Color(hex: report.club.kit)).frame(width: 10, height: 10)
                        Text("Matchday").font(.headline)
                        Spacer()
                        Text(Fmt.day(report.gameDate)).font(.caption).foregroundStyle(.secondary)
                    }
                    Pitch { size in
                        ForEach(Array(report.formation.rows.enumerated()), id: \.offset) { i, row in
                            let p = i < report.xi1.count ? report.player(report.xi1[i].uid) : nil
                            Text(p.map { surname($0.name) } ?? "–")
                                .font(.system(size: 11, weight: .semibold))
                                .lineLimit(1).minimumScaleFactor(0.7)
                                .foregroundStyle(.white)
                                .padding(.horizontal, 6).padding(.vertical, 2)
                                .background(Color(hex: report.club.kit), in: RoundedRectangle(cornerRadius: 4))
                                .position(x: size.width * (row.x ?? 50) / 100, y: size.height * (row.y ?? 50) / 100)
                        }
                    }
                    let alerts = report.news.filter { ["inj-short", "inj-long", "sus", "expiring"].contains($0.kind) }
                    VStack(alignment: .leading, spacing: 5) {
                        ForEach(Array(alerts.prefix(6).enumerated()), id: \.offset) { _, n in
                            HStack(alignment: .firstTextBaseline, spacing: 6) {
                                Circle().fill(color(n.kind)).frame(width: 7, height: 7)
                                Text(n.text).font(.callout).lineLimit(2)
                            }
                        }
                        if alerts.isEmpty { Text("Nobody out or banned.").font(.callout).foregroundStyle(.secondary) }
                    }
                }
                .padding(14)
            } else {
                ContentUnavailableView("No report yet", systemImage: "pin")
            }
        }
        .frame(minWidth: 260)
        .background(FloatOverFullScreen())
    }

    private func color(_ kind: String) -> Color {
        switch kind {
        case "inj-long": Palette.injuryLong
        case "inj-short": Palette.verdict("amber")
        case "sus": Palette.verdict("red")
        default: .secondary
        }
    }
}

/// Keeps the window on top, also over a full-screen game and on every Space.
private struct FloatOverFullScreen: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView {
        let v = NSView()
        DispatchQueue.main.async {
            guard let w = v.window else { return }
            w.level = .floating
            w.collectionBehavior.insert([.canJoinAllSpaces, .fullScreenAuxiliary])
            w.isMovableByWindowBackground = true
        }
        return v
    }
    func updateNSView(_ nsView: NSView, context: Context) {}
}
