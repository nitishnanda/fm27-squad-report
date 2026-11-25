import SwiftUI

/// Your managerial career: totals, breakdowns by season / club / calendar year (with points per game), transfer money
/// per window, and the best players you've coached. All from the engine's archive (history.json).
/// "Best" means the highest System ★ a player reached while you coached him (visible attributes only, his rule).
struct CareerView: View {
    let report: Report
    @Environment(AppModel.self) private var model
    @State private var split = Split.season

    enum Split: String, CaseIterable, Identifiable {
        case season = "Season", club = "Club", year = "Calendar year"
        var id: String { rawValue }
    }

    var body: some View {
        let career = report.career
        // friendlies don't count towards your record, like FM's own manager history
        let matches = (career?.matches ?? []).filter { !$0.friendly }
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                HubHeader(title: "Career stats", sub: subtitle(career))
                if matches.isEmpty {
                    ContentUnavailableView("No matches yet", systemImage: "trophy",
                                           description: Text("Your career record starts with your first first-team match."))
                        .frame(maxWidth: .infinity, minHeight: 300)
                } else {
                    totals(Record(matches))
                    breakdown(matches)
                    windows(career?.money ?? [])
                    bestPlayers(career?.players ?? [])
                }
            }
            .frame(maxWidth: 1172, alignment: .leading)
            .padding(.horizontal, 24).padding(.vertical, 20)
            .frame(maxWidth: .infinity)
        }
    }

    private func subtitle(_ c: Career?) -> String {
        guard let c, let first = c.matches.first else { return "Your record as a manager" }
        let clubs = Array(NSOrderedSet(array: c.matches.map(\.club))) as? [String] ?? []
        return "\(c.manager ?? "You") · \(clubs.joined(separator: " → ")) · since \(Fmt.day(first.date))"
    }

    // MARK: totals

    private func totals(_ r: Record) -> some View {
        // two even rows of four, like the Home snapshot
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(minimum: 150), spacing: 12, alignment: .top), count: 4), spacing: 12) {
            Stat(label: "Matches", value: "\(r.p)", sub: "competitive, friendlies left out")
            Stat(label: "Won", value: "\(r.w)", sub: String(format: "%.0f%% of matches", r.winPct), tint: DS.Delta.up)
            Stat(label: "Drawn", value: "\(r.d)", sub: r.p > 0 ? String(format: "%.0f%%", 100 * Double(r.d) / Double(r.p)) : "–")
            Stat(label: "Lost", value: "\(r.l)", sub: r.p > 0 ? String(format: "%.0f%%", 100 * Double(r.l) / Double(r.p)) : "–",
                 tint: DS.Delta.down)
            Stat(label: "Goals for", value: "\(r.gf)", sub: String(format: "%.2f per game", Double(r.gf) / Double(max(r.p, 1))))
            Stat(label: "Goals against", value: "\(r.ga)", sub: String(format: "%.2f per game", Double(r.ga) / Double(max(r.p, 1))))
            Stat(label: "Clean sheets", value: "\(r.cs)", sub: String(format: "%.0f%% of matches", 100 * Double(r.cs) / Double(max(r.p, 1))))
            Stat(label: "Points per game", value: String(format: "%.2f", r.ppg), sub: "3 for a win, 1 for a draw")
        }
    }

    // MARK: by season / club / year

    private func breakdown(_ matches: [Career.Match]) -> some View {
        let groups: [(String, [Career.Match])] = switch split {
        case .season: Dictionary(grouping: matches, by: \.season).sorted { $0.key > $1.key }
        case .year: Dictionary(grouping: matches, by: \.year).sorted { $0.key > $1.key }
        case .club:
            // in the order you managed them, latest first
            Dictionary(grouping: matches, by: \.club).sorted { ($0.value.last?.date ?? "") > ($1.value.last?.date ?? "") }
        }
        return VStack(alignment: .leading, spacing: 12) {
            HubHeader(title: "Record by \(split.rawValue.lowercased())", sub: "Points per game counts 3 for a win and 1 for a draw") {
                Picker("Split", selection: $split) { ForEach(Split.allCases) { Text($0.rawValue).tag($0) } }
                    .pickerStyle(.segmented).labelsHidden().fixedSize()
            }
            VStack(spacing: 0) {
                row(nil, header: true)
                ForEach(groups, id: \.0) { name, ms in
                    Rectangle().fill(Color.primary.opacity(0.06)).frame(height: 1)
                    row((name, Record(ms)), header: false)
                }
                Rectangle().fill(Color.primary.opacity(0.12)).frame(height: 1)
                row(("Career", Record(matches)), header: false, bold: true)
            }
            .hubCard()
        }
    }

    private func row(_ item: (String, Record)?, header: Bool, bold: Bool = false) -> some View {
        let r = item?.1
        let cells: [(String, CGFloat)] = header
            ? [("P", 40), ("W", 40), ("D", 40), ("L", 40), ("GF", 44), ("GA", 44), ("GD", 48), ("CS", 40), ("Win %", 56), ("PPG", 52)]
            : [("\(r!.p)", 40), ("\(r!.w)", 40), ("\(r!.d)", 40), ("\(r!.l)", 40), ("\(r!.gf)", 44), ("\(r!.ga)", 44),
               ("\(r!.gd > 0 ? "+" : "")\(r!.gd)", 48), ("\(r!.cs)", 40), (String(format: "%.0f", r!.winPct), 56),
               (String(format: "%.2f", r!.ppg), 52)]
        return HStack(spacing: 0) {
            Text(header ? split.rawValue : item!.0).frame(maxWidth: .infinity, alignment: .leading)
            ForEach(Array(cells.enumerated()), id: \.offset) { i, c in
                Text(c.0).frame(width: c.1, alignment: .trailing)
                    .foregroundStyle(!header && i == 9 ? (r!.ppg >= 2 ? DS.Delta.up : r!.ppg < 1.3 ? DS.Delta.down : .primary) : .primary)
            }
        }
        .font(.system(size: header ? 11.5 : 12.5, weight: header ? .medium : bold ? .semibold : .regular))
        .monospacedDigit()
        .foregroundStyle(header ? .secondary : .primary)
        .padding(.horizontal, 14)
        .frame(height: header ? 32 : 36)
    }

    // MARK: transfer windows

    /// The save has only the club's net transfer money per month (no single fees, so no biggest signing or sale).
    /// Months are grouped into windows: Jun–Sep is the summer window, Dec–Mar the January one (FM pays some fees in
    /// instalments, so a little money lands either side of the window itself).
    private func windows(_ money: [Career.Money]) -> some View {
        struct Window: Identifiable { let id: String; let club: String; let net: Double; let sort: String }
        var bucket: [String: (club: String, net: Double, sort: String)] = [:]
        for m in money {
            let y = Int(m.month.prefix(4)) ?? 0, mo = Int(m.month.suffix(2)) ?? 0
            let name: String, sort: String
            switch mo {
            case 6...9: (name, sort) = ("Summer \(y)", "\(y)-07")
            case 12: (name, sort) = ("January \(y + 1)", "\(y + 1)-01")
            case 1...3: (name, sort) = ("January \(y)", "\(y)-01")
            default: continue
            }
            let key = "\(m.club)|\(name)"
            bucket[key] = (m.club, (bucket[key]?.net ?? 0) + m.net, sort)
        }
        let list = bucket.map { Window(id: $0.key, club: $0.value.club, net: $0.value.net, sort: $0.value.sort) }
            .sorted { $0.sort > $1.sort }
        let spends = list.map { -$0.net }
        let biggest = list.min { $0.net < $1.net }
        let average = spends.isEmpty ? 0 : spends.reduce(0, +) / Double(spends.count)
        return VStack(alignment: .leading, spacing: 12) {
            HubHeader(title: "Transfer windows", sub: "Net spend per window: what went out minus what came in")
            if list.isEmpty {
                Text("No transfer money recorded yet.").font(.system(size: 12.5)).foregroundStyle(.secondary)
            } else {
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(minimum: 180), spacing: 12, alignment: .top), count: 3), spacing: 12) {
                    Stat(label: "Most spent in a window", value: biggest.map { Fmt.money(max(0, -$0.net)) } ?? "–",
                         sub: biggest.map { "\($0.id.split(separator: "|").last ?? "") · \($0.club)" } ?? "")
                    Stat(label: "Average per window", value: Fmt.money(abs(average)),
                         sub: "\(average >= 0 ? "net spend" : "net profit") over \(list.count) window\(list.count == 1 ? "" : "s")")
                    Stat(label: "Net across your career", value: Fmt.money(abs(spends.reduce(0, +))),
                         sub: spends.reduce(0, +) >= 0 ? "spent" : "profit")
                }
                VStack(spacing: 0) {
                    ForEach(Array(list.enumerated()), id: \.element.id) { i, w in
                        HStack(spacing: 12) {
                            Text(String(w.id.split(separator: "|").last ?? "")).font(.system(size: 12.5, weight: .medium))
                                .frame(maxWidth: .infinity, alignment: .leading)
                            Text(w.club).font(.system(size: 12)).foregroundStyle(.secondary)
                            Text(w.net <= 0 ? "spent \(Fmt.money(-w.net))" : "made \(Fmt.money(w.net))")
                                .font(.system(size: 12.5, weight: .semibold)).monospacedDigit()
                                .foregroundStyle(w.net <= 0 ? DS.Delta.down : DS.Delta.up)
                                .frame(width: 130, alignment: .trailing)
                        }
                        .padding(.horizontal, 14).frame(height: 36)
                        if i < list.count - 1 { Rectangle().fill(Color.primary.opacity(0.06)).frame(height: 1) }
                    }
                }
                .hubCard()
                Label("FM saves don't keep single transfer fees, so your biggest signing and biggest sale can't be shown. "
                      + "These are the club's net transfer money per window.", systemImage: "info.circle")
                    .font(.system(size: 11.5)).foregroundStyle(.tertiary)
            }
        }
    }

    // MARK: best players

    private func bestPlayers(_ players: [Career.Coached]) -> some View {
        let byClub = Dictionary(grouping: players, by: { $0.club ?? "?" })
        let clubBest = byClub.compactMap { $0.value.first }.sorted { ($0.club ?? "") < ($1.club ?? "") }
        return VStack(alignment: .leading, spacing: 12) {
            HubHeader(title: "Best players you've coached",
                      sub: "By the highest System ★ they reached under you, from visible attributes")
            if players.isEmpty {
                Text("Nobody yet.").font(.system(size: 12.5)).foregroundStyle(.secondary)
            } else {
                Text("AT EACH CLUB").font(.system(size: 11, weight: .semibold)).tracking(0.66).foregroundStyle(.tertiary)
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 260), spacing: 12, alignment: .top)], spacing: 12) {
                    ForEach(clubBest) { p in PlayerCardMini(player: p, showClub: true) }
                }
                Text("YOUR WHOLE CAREER").font(.system(size: 11, weight: .semibold)).tracking(0.66).foregroundStyle(.tertiary)
                    .padding(.top, 8)
                VStack(spacing: 0) {
                    ForEach(Array(players.prefix(10).enumerated()), id: \.element.id) { i, p in
                        HStack(spacing: 12) {
                            Text("\(i + 1)").font(.system(size: 11, weight: .semibold)).monospacedDigit().foregroundStyle(.tertiary)
                                .frame(width: 20, alignment: .leading)
                            Text(p.name ?? "?").font(.system(size: 12.5, weight: .medium)).frame(maxWidth: .infinity, alignment: .leading)
                            Text(p.slot ?? "").font(.system(size: 11.5, weight: .semibold)).foregroundStyle(.secondary).frame(width: 32)
                            Text(p.club ?? "").font(.system(size: 12)).foregroundStyle(.secondary).frame(width: 120, alignment: .leading)
                            StarsView(value: p.peak ?? 0, size: 11).frame(width: 70, alignment: .leading)
                            Text("\(p.apps) apps · \(p.goals) g · \(p.assists) a").font(.system(size: 11.5)).monospacedDigit()
                                .foregroundStyle(.tertiary).frame(width: 140, alignment: .trailing)
                        }
                        .padding(.horizontal, 14).frame(height: 36)
                        .contentShape(Rectangle())
                        .onTapGesture { if report.player(p.uid) != nil { model.inspect(p.uid) } }
                        if i < min(players.count, 10) - 1 { Rectangle().fill(Color.primary.opacity(0.06)).frame(height: 1) }
                    }
                }
                .hubCard()
            }
        }
    }
}

/// A KPI card in the Make design's style: label / value / sub.
private struct Stat: View {
    let label: String
    let value: String
    let sub: String
    var tint: Color? = nil

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label).font(.system(size: 12, weight: .medium)).foregroundStyle(.secondary)
            NumberText(value, size: 28).foregroundStyle(tint ?? .primary)
            Text(sub).font(.system(size: 11)).monospacedDigit().foregroundStyle(.tertiary).lineLimit(1)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .hubCard()
        .accessibilityElement(children: .combine)
    }
}

private struct PlayerCardMini: View {
    let player: Career.Coached
    let showClub: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(player.club ?? "").font(.system(size: 12, weight: .medium)).foregroundStyle(.secondary)
                Spacer()
                if let slot = player.slot {
                    Text(slot).font(.system(size: 11, weight: .bold))
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .background(Color.primary.opacity(0.06), in: RoundedRectangle(cornerRadius: 4, style: .continuous))
                }
            }
            Text(player.name ?? "?").font(.system(size: 17, weight: .semibold)).lineLimit(1)
            StarsView(value: player.peak ?? 0, size: 13)
            Text("\(player.apps) apps · \(player.goals) goals · \(player.assists) assists").font(.system(size: 11))
                .monospacedDigit().foregroundStyle(.tertiary)
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .hubCard()
        .accessibilityElement(children: .combine)
    }
}
