import SwiftUI

/// A run of results added up: played, won, drawn, lost, goals, clean sheets, points per game.
struct Record: Sendable {
    var p = 0, w = 0, d = 0, l = 0, gf = 0, ga = 0, cs = 0

    init(_ matches: some Sequence<Career.Match>) {
        for m in matches {
            p += 1
            gf += m.gf
            ga += m.ga
            if m.ga == 0 { cs += 1 }
            switch m.res { case "W": w += 1; case "L": l += 1; default: d += 1 }
        }
    }

    var points: Int { 3 * w + d }
    var ppg: Double { p > 0 ? Double(points) / Double(p) : 0 }
    var winPct: Double { p > 0 ? 100 * Double(w) / Double(p) : 0 }
    var gd: Int { gf - ga }
    var line: String { "P\(p) W\(w) D\(d) L\(l) · GF \(gf) GA \(ga) · \(String(format: "%.2f", ppg)) PPG" }
}

/// Every first-team result since you took the job, newest season first. From the engine's archive, so seasons FM
/// has already wiped are still here (as long as the app or engine read the save during that season).
struct ResultsView: View {
    let report: Report
    @State private var season = "All"

    var body: some View {
        let matches = report.career?.matches ?? []
        let seasons = Array(Set(matches.map(\.season))).sorted(by: >)
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                HubHeader(title: "Results", sub: "Every first-team result since you took the job, by season · friendlies shown but not counted") {
                    if seasons.count > 1 { pills(["All"] + seasons) }
                }
                if matches.isEmpty {
                    ContentUnavailableView("No results yet", systemImage: "calendar",
                                           description: Text("Your results show up here once you've played a first-team match."))
                        .frame(maxWidth: .infinity, minHeight: 300)
                }
                ForEach(seasons.filter { season == "All" || $0 == season }, id: \.self) { s in
                    SeasonBlock(season: s, matches: matches.filter { $0.season == s }.reversed())
                }
            }
            .frame(maxWidth: 1172, alignment: .leading)
            .padding(.horizontal, 24).padding(.vertical, 20)
            .frame(maxWidth: .infinity)
        }
    }

    private func pills(_ options: [String]) -> some View {
        HStack(spacing: 0) {
            ForEach(options, id: \.self) { o in
                Button { season = o } label: {
                    Text(o).font(.system(size: 11.5, weight: .medium)).monospacedDigit()
                        .foregroundStyle(season == o ? .primary : .secondary)
                        .padding(.horizontal, 10).padding(.vertical, 4)
                        .background(season == o ? Color.primary.opacity(0.08) : .clear, in: Capsule())
                        .contentShape(Capsule())
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(season == o ? .isSelected : [])
            }
        }
        .padding(2)
        .background(Color.primary.opacity(0.03), in: Capsule())
        .overlay(Capsule().strokeBorder(Color.primary.opacity(0.08)))
    }
}

private struct SeasonBlock: View {
    let season: String
    let matches: [Career.Match]   // newest first

    var body: some View {
        let rec = Record(matches.filter { !$0.friendly })   // the season's record leaves friendlies out
        let clubs = Array(Set(matches.map(\.club))).sorted().joined(separator: " & ")
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                Text(season).displayFont(16, .semibold).monospacedDigit()
                Text(clubs).font(.system(size: 12.5)).foregroundStyle(.secondary)
                Spacer(minLength: 8)
                Text(rec.line).font(.system(size: 12)).monospacedDigit().foregroundStyle(.secondary)
            }
            VStack(spacing: 0) {
                ForEach(Array(matches.enumerated()), id: \.element.id) { i, m in
                    ResultRow(match: m)
                    if i < matches.count - 1 { Rectangle().fill(Color.primary.opacity(0.06)).frame(height: 1) }
                }
            }
            .hubCard()
        }
    }
}

private struct ResultRow: View {
    let match: Career.Match

    var body: some View {
        let c = match.res == "W" ? DS.Delta.up : match.res == "L" ? DS.Delta.down : DS.Delta.flat
        HStack(spacing: 12) {
            Text(Fmt.day(match.date)).font(.system(size: 12)).monospacedDigit().foregroundStyle(.secondary)
                .frame(width: 92, alignment: .leading)
            Text(match.friendly ? "Friendly" : match.comp).font(.system(size: 11.5)).foregroundStyle(.tertiary).lineLimit(1)
                .frame(width: 140, alignment: .leading)
            Text(match.home ? "H" : "A").font(.system(size: 11, weight: .semibold)).foregroundStyle(.secondary)
                .frame(width: 16)
            Text(match.opp).font(.system(size: 12.5, weight: .medium)).lineLimit(1)
                .frame(maxWidth: .infinity, alignment: .leading)
            Text("\(match.gf)–\(match.ga)").font(.system(size: 13, weight: .semibold)).monospacedDigit()
                .frame(width: 44, alignment: .trailing)
            Text(match.res)
                .font(.system(size: 11, weight: .bold)).foregroundStyle(c)
                .frame(width: 24, height: 22)
                .background(c.opacity(0.16), in: RoundedRectangle(cornerRadius: 5, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 5, style: .continuous).strokeBorder(c.opacity(0.32)))
        }
        .padding(.horizontal, 14)
        .frame(height: 40)
        .opacity(match.friendly ? 0.6 : 1)   // shown, but quieter: friendlies don't count
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(Fmt.day(match.date)), \(match.comp), \(match.home ? "home to" : "away at") \(match.opp), \(match.res == "W" ? "won" : match.res == "L" ? "lost" : "drew") \(match.gf)–\(match.ga)")
    }
}
