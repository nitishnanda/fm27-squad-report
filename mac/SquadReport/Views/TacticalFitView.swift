import SwiftUI

/// Tactical fit: how the tactic is going (the game's own match numbers, ranked against the league), each player's numbers,
/// the style breakdown, who doesn't fit, and role by role on a pitch. Visible data only.
struct TacticalFitView: View {
    let report: Report

    enum Part: String, CaseIterable, Identifiable {
        case going = "How it's going", players = "Player by player", style = "Style", misfits = "Doesn't fit", roles = "Role by role"
        var id: String { rawValue }
    }
    @State private var part: Part = .going

    private var partPicker: some View {
        Picker("Part", selection: $part) {
            ForEach(Part.allCases) { p in
                Text(p == .style ? (report.style?.name ?? "Style") : p.rawValue).tag(p)
            }
        }
        .pickerStyle(.segmented)
        .labelsHidden()
        .fixedSize()
    }

    /// "Gegenpress asks for" and its key attributes: label above the chips next to the picker, beside them under it.
    @ViewBuilder private func styleChips(stacked: Bool) -> some View {
        if let style = report.style {
            let label = Text("\(style.name) asks for").font(.callout).foregroundStyle(.secondary).fixedSize()
            let chips = FlowRow(spacing: 4) {
                ForEach(style.keys, id: \.self) { KeyChip(text: report.label($0), kind: .style) }
            }
            if stacked {
                VStack(alignment: .trailing, spacing: 4) { label; chips }
            } else {
                HStack(alignment: .firstTextBaseline, spacing: 8) { label; chips }
            }
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            // side by side on a wide window; on a narrow one the style chips go under the picker
            ViewThatFits(in: .horizontal) {
                HStack(spacing: 14) {
                    partPicker
                    Spacer()
                    styleChips(stacked: true).frame(width: 420, alignment: .trailing)
                }
                VStack(alignment: .leading, spacing: 8) {
                    partPicker
                    styleChips(stacked: false)
                }
            }
            .padding(.horizontal, 24).padding(.vertical, 12)
            Divider()
            ScrollView {
                Group {
                    switch part {
                    case .going: HowItsGoing(report: report)
                    case .players: PlayerByPlayer(report: report)
                    case .style: StyleBreakdown(report: report)
                    case .misfits: Misfits(report: report)
                    case .roles: RoleByRole(report: report)
                    }
                }
                .padding(24)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}

// MARK: - how it's going

private struct HowItsGoing: View {
    let report: Report

    var body: some View {
        let perf = report.performance
        let metrics = perf.metrics ?? []
        VStack(alignment: .leading, spacing: 18) {
            SectionTitle("How the tactic is going", sub: "\(perf.leagueName ?? "League") only · from the game's own match stats\(perf.matches.map { " (\($0) of your matches have full reports)" } ?? "") · ranked against all \(metrics.first?.of ?? 20) teams")
            if metrics.isEmpty {
                ContentUnavailableView("No league match data yet", systemImage: "chart.bar",
                                       description: Text("Play a few league games and this fills in from the match reports."))
            } else {
                if let rec = perf.record {
                    HStack(alignment: .firstTextBaseline, spacing: 12) {
                        Text(Fmt.ordinal(rec.pos)).positionFont(44)
                        Text("of \(rec.of) · P\(rec.p) W\(rec.w) D\(rec.d) L\(rec.l) · \(rec.pts) pts · \(rec.gf)–\(rec.ga) goals")
                            .foregroundStyle(.secondary)
                        HStack(spacing: 4) {
                            ForEach(Array(perf.form.enumerated()), id: \.offset) { _, f in
                                Text(f.res).font(.system(size: 11, weight: .heavy)).foregroundStyle(.white)
                                    .frame(width: 22, height: 22).background(Palette.result(f.res), in: RoundedRectangle(cornerRadius: 5))
                                    .help("\(f.score) \(f.home ? "vs" : "at") \(f.opp)")
                            }
                        }
                    }
                }
                let of = metrics.first?.of ?? 20
                let cut = max(3, Int((Double(of) * 0.25).rounded()))
                let working = metrics.filter { $0.rank <= cut }.sorted { $0.rank < $1.rank }.prefix(6)
                let failing = metrics.filter { Double($0.rank) > Double(of) / 2 && $0.above != true }.sorted { $0.rank > $1.rank }.prefix(6)
                let weakest = metrics.sorted { $0.rank > $1.rank }.prefix(3)
                HStack(alignment: .top, spacing: 16) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("What's working").displayFont(20).foregroundStyle(Palette.transferIn)
                        if working.isEmpty { Text("Nothing in the top quarter of the league yet.").foregroundStyle(.secondary) }
                        ForEach(Array(working)) { MetricCard(metric: $0, good: true) }
                    }
                    VStack(alignment: .leading, spacing: 8) {
                        Text("What's not working").displayFont(20).foregroundStyle(Palette.injuryLong)
                        if failing.isEmpty {
                            Text("Nothing is below the league average. Your weakest areas:").foregroundStyle(.secondary)
                            ForEach(Array(weakest)) { MetricCard(metric: $0, good: false) }
                        }
                        ForEach(Array(failing)) { MetricCard(metric: $0, good: false) }
                    }
                }
                if let insights = perf.insights, !insights.isEmpty {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Putting it together").font(.headline)
                        ForEach(insights, id: \.self) { line in
                            Label(line, systemImage: "arrow.turn.down.right").font(.callout)
                        }
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .panel(10)
                }
            }
        }
    }
}

private struct MetricCard: View {
    let metric: Performance.Metric
    let good: Bool

    var body: some View {
        let showUnit = metric.unit != "%" && metric.key != "dist_diff"
        VStack(alignment: .leading, spacing: 5) {
            HStack(alignment: .firstTextBaseline) {
                Text(metric.label).fontWeight(.semibold)
                Spacer()
                Text((metric.valueText ?? String(format: "%.2f", metric.value)) + (showUnit ? " \(metric.unit)" : ""))
                    .fontWeight(.bold).monospacedDigit()
            }
            RankStrip(rank: metric.rank, of: metric.of, good: good)
            Text("\(Fmt.ordinal(metric.rank)) of \(metric.of) · league avg \(metric.avgText ?? String(format: "%.2f", metric.avg))")
                .font(.caption).foregroundStyle(.secondary)
            Text(good ? metric.good : metric.bad).font(.callout).foregroundStyle(.secondary)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .panelFill()
        .overlay(alignment: .leading) { Rectangle().fill(good ? Palette.transferIn : Palette.injuryLong).frame(width: 3) }
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .accessibilityElement(children: .combine)
    }
}

// MARK: - player by player

private struct PlayerByPlayer: View {
    let report: Report
    @State private var showAll = false

    var body: some View {
        let entries = (report.performance.players ?? [:])
            .compactMap { uid, v -> (Player, Performance.PlayerNumbers)? in
                guard let p = report.player(Int(uid)), p.location == "squad" else { return nil }
                return (p, v)
            }
            .sorted { $0.1.minutes > $1.1.minutes }
        let shown = showAll ? entries : Array(entries.prefix(10))
        VStack(alignment: .leading, spacing: 14) {
            SectionTitle("Player by player", sub: "league numbers per 90 minutes, ranked against every league player in the same position with \(report.performance.minMinutes ?? 450)+ minutes")
            if entries.isEmpty {
                Text("Nobody has \(report.performance.minMinutes ?? 450)+ league minutes yet.").foregroundStyle(.secondary)
            }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 420), spacing: 12, alignment: .top)], spacing: 12) {
                ForEach(shown, id: \.0.uid) { p, v in PerfCard(player: p, numbers: v) }
            }
            if entries.count > 10 {
                Button(showAll ? "Show fewer" : "Show \(entries.count - 10) more players") { withAnimation(.snappy) { showAll.toggle() } }
            }
        }
    }
}

private struct PerfCard: View {
    let player: Player
    let numbers: Performance.PlayerNumbers

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Text(player.name).font(.headline)
                Spacer()
                Text("\(numbers.avg.map { String(format: "%.2f avg · ", $0) } ?? "")\(numbers.minutes) mins · vs \(numbers.peers ?? 0) \(numbers.groupName ?? "")")
                    .font(.caption).foregroundStyle(.secondary)
            }
            if numbers.good.isEmpty && numbers.bad.isEmpty {
                Text("Nothing stands out either way: middle-of-the-pack numbers for his position.").font(.callout).foregroundStyle(.secondary)
            } else {
                row("Working", numbers.good, good: true)
                row("Not working", numbers.bad, good: false)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .panel(8)
    }

    private func row(_ title: String, _ items: [Performance.PlayerItem], good: Bool) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text(title).font(.caption.weight(.heavy)).foregroundStyle(good ? Palette.transferIn : Palette.injuryLong)
                .frame(width: 76, alignment: .leading)
            if items.isEmpty { Text("–").foregroundStyle(.secondary) }
            FlowRow(spacing: 5) {
                ForEach(items, id: \.key) { item in
                    let share = good ? max(1, Int((100 - item.pctl).rounded())) : max(1, Int(item.pctl.rounded()))
                    HStack(spacing: 4) {
                        Text(item.label)
                        Text(item.valueText ?? String(format: "%.2f", item.value)).fontWeight(.bold)
                        Text("\(good ? "top" : "bottom") \(share)%").foregroundStyle(.secondary)
                        if item.press == true {
                            Text("press").font(.system(size: 9, weight: .heavy)).padding(.horizontal, 3)
                                .background(Palette.verdict("amber").opacity(0.3), in: RoundedRectangle(cornerRadius: 3))
                        }
                    }
                    .font(.caption)
                    .padding(.horizontal, 7).padding(.vertical, 3)
                    .background((good ? Palette.transferIn : Palette.injuryLong).opacity(0.12), in: RoundedRectangle(cornerRadius: 6))
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke((good ? Palette.transferIn : Palette.injuryLong).opacity(0.35)))
                }
            }
        }
    }
}

// MARK: - style breakdown

private struct StyleBreakdown: View {
    let report: Report
    @State private var everyone = false

    var body: some View {
        let keys = report.style?.keys ?? []
        let xiIDs = Set(report.xi1.compactMap(\.uid))
        let rows = report.players
            .filter { ["squad", "incoming"].contains($0.location) && !$0.youth && $0.attributes != nil }
            .map { p -> (Player, [Int?], Double) in
                let vals = keys.map { p.attribute($0) }
                let known = vals.compactMap { $0 }
                return (p, vals, known.isEmpty ? 0 : Double(known.reduce(0, +)) / Double(known.count))
            }
            .filter { !$0.1.compactMap { $0 }.isEmpty }
            .sorted { $0.2 > $1.2 }
        let xi = rows.filter { xiIDs.contains($0.0.uid) }
        let shown = everyone ? rows : xi
        let exact = keys.indices.map { i -> Double? in
            let v = xi.compactMap { $0.1[i] }
            return v.isEmpty ? nil : Double(v.reduce(0, +)) / Double(v.count)
        }
        let teamAvg = exact.map { $0.map { Int($0.rounded()) } }
        let weakest = zip(keys, exact).compactMap { k, v in v.map { (k, $0) } }.sorted { $0.1 < $1.1 }.prefix(2)
        VStack(alignment: .leading, spacing: 14) {
            SectionTitle("\(report.style?.name ?? "Style") breakdown", sub: "the \(keys.count) attributes behind each player's \(report.style?.name.lowercased() ?? "style") score (/20) · the lowest are what to work on in training")
            if !weakest.isEmpty {
                Text("Your best XI is weakest at \(weakest.map { "\(report.label($0.0)) (\(String(format: "%.1f", $0.1)))" }.joined(separator: " and ")) as a group. These are FM's visible attributes, so you can check them on each player's profile.")
                    .foregroundStyle(.secondary)
            }
            HStack {
                Toggle("Show everyone, not just the best XI", isOn: $everyone)
                Spacer()
                AttrScale()
            }
            Grid(alignment: .leading, horizontalSpacing: 6, verticalSpacing: 4) {
                GridRow {
                    Text("Player").gridColumnAlignment(.leading)
                    Text("Best")
                    ForEach(keys, id: \.self) { Text(report.abbr($0)).help(report.label($0)) }
                    Text("/20")
                    Text("Holding him back")
                }
                .font(.caption.weight(.bold)).foregroundStyle(.secondary)
                GridRow {
                    Text("Best XI average").fontWeight(.bold)
                    Text("")
                    ForEach(teamAvg.indices, id: \.self) { AttrCell(value: teamAvg[$0]) }
                    Text("")
                    Text("")
                }
                Divider().gridCellUnsizedAxes(.horizontal)
                ForEach(shown, id: \.0.uid) { p, vals, avg in
                    GridRow {
                        HStack(spacing: 5) {
                            Text(p.name).fontWeight(.semibold).lineLimit(1)
                            if xiIDs.contains(p.uid) { XITag() }
                        }
                        Text(p.best?.slot ?? "–").font(.caption.weight(.bold)).foregroundStyle(.secondary)
                        ForEach(vals.indices, id: \.self) { AttrCell(value: vals[$0]) }
                        FitBar(value: avg)
                        let low = zip(keys, vals).compactMap { k, v in v.flatMap { $0 <= 12 ? (k, $0) : nil } }.sorted { $0.1 < $1.1 }.prefix(3)
                        if low.isEmpty {
                            Text("Nothing: all 13+").font(.caption).foregroundStyle(Palette.transferIn)
                        } else {
                            Text(low.map { "\(report.label($0.0)) \($0.1)" }.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
    }
}

struct XITag: View {
    var body: some View {
        Text("XI").font(.system(size: 9, weight: .heavy)).foregroundStyle(.black).fixedSize()
            .padding(.horizontal, 4).background(Palette.star, in: RoundedRectangle(cornerRadius: 3))
            .accessibilityLabel("in your best XI")
    }
}

// MARK: - players who don't fit

private struct Misfits: View {
    let report: Report

    var body: some View {
        let misfits = report.fit?.misfits ?? []
        VStack(alignment: .leading, spacing: 14) {
            SectionTitle("Players who don't fit the system", sub: "first team, judged on the key attributes of their best role in your tactic")
            if misfits.isEmpty {
                Label("Everyone in your first team suits a role in this tactic. 🔥", systemImage: "checkmark.seal.fill")
                    .foregroundStyle(Palette.transferIn)
            }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 320), spacing: 12, alignment: .top)], spacing: 12) {
                ForEach(misfits) { m in
                    if let p = report.player(m.uid) {
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text(p.name).font(.headline)
                                Spacer()
                                Text(p.age.map(String.init) ?? "").foregroundStyle(.secondary)
                            }
                            if let best = m.best, let rowName = m.bestRow, let row = report.fit?.rows.first(where: { $0.label == rowName }) {
                                let fr = report.formation.rows.first { ($0.label ?? $0.slot) == rowName }
                                Text("Best fit: \(rowName) · \(fr?.ipRoleName ?? row.ipRole) / \(fr?.oopRoleName ?? row.oopRole) · \(String(format: "%.1f", best.fit ?? 0))")
                                    .font(.callout).foregroundStyle(.secondary)
                            } else {
                                Text("No slot in your tactic").font(.callout).foregroundStyle(.secondary)
                            }
                            Text(m.why).font(.callout).foregroundStyle(Palette.verdict("amber"))
                            if let best = m.best {
                                FlowRow(spacing: 4) {
                                    ForEach(best.weak.prefix(4), id: \.self) { w in KeyChip(text: "\(report.label(w.attribute)) \(w.value)", kind: .oop) }
                                    ForEach(best.styleWeak.filter { !best.weak.contains($0) }.prefix(3), id: \.self) { w in
                                        KeyChip(text: "\(report.label(w.attribute)) \(w.value)", kind: .style)
                                    }
                                }
                            }
                        }
                        .padding(14)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .panelFill()
                        .overlay(alignment: .leading) { Rectangle().fill(Palette.verdict("amber")).frame(width: 4) }
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                    }
                }
            }
        }
    }
}

// MARK: - role by role

private struct RoleByRole: View {
    let report: Report
    @State private var picked: Int?
    @Environment(\.theme) private var theme

    var body: some View {
        let rows = report.formation.rows
        let fitRows = report.fit?.rows ?? []
        // the XI player's fit in each slot; open on the weakest one
        let xiFit: [Double?] = rows.indices.map { i in
            guard i < fitRows.count, i < report.xi1.count, let uid = report.xi1[i].uid else { return nil }
            return fitRows[i].entries.first { $0.uid == uid }?.fit
        }
        let weakest = xiFit.enumerated().compactMap { i, f in f.map { (i, $0) } }.min { $0.1 < $1.1 }?.0 ?? 0
        let current = picked ?? weakest
        VStack(alignment: .leading, spacing: 14) {
            SectionTitle("Role by role", sub: "fit = role key attributes (in & out of possession) blended with \(report.style?.name ?? "style") attributes · pick a position")
            HStack(spacing: 8) {
                KeyChip(text: "In possession", kind: .ip)
                KeyChip(text: "Out of possession", kind: .oop)
                KeyChip(text: "Both", kind: .both)
                Spacer()
                AttrScale()
            }
            // side by side when there's room; the pitch on top when the window is narrow
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .top, spacing: 20) { picker(rows, fitRows, xiFit, current); card(rows, fitRows, current) }
                VStack(alignment: .leading, spacing: 16) { picker(rows, fitRows, xiFit, current); card(rows, fitRows, current) }
            }
        }
    }

    private func picker(_ rows: [Formation.Row], _ fitRows: [TacticalFit.Row], _ xiFit: [Double?], _ current: Int) -> some View {
        Pitch { size in
            ForEach(rows.indices, id: \.self) { i in
                let row = rows[i]
                let uid = i < report.xi1.count ? report.xi1[i].uid : nil
                let fit = xiFit[i]
                Button { picked = i } label: {
                    VStack(spacing: 1) {
                        Text(row.label ?? row.slot).slotFont(11)
                            .foregroundStyle(i == current ? Palette.star : .secondary)
                        Text(fit.map { String(format: "%.1f", $0) } ?? "–").font(.system(size: 15, weight: .heavy)).monospacedDigit()
                            .foregroundStyle(fit.map { $0 >= 14 ? Palette.transferIn : $0 >= 12 ? Color.white : Palette.injuryLong } ?? .secondary)
                        Text(report.player(uid).map { surname($0.name) } ?? "nobody").font(.system(size: 10)).foregroundStyle(.white.opacity(0.8))
                            .lineLimit(1)
                    }
                    .frame(width: 74).padding(.vertical, 5)
                    .background(theme.cardFill, in: RoundedRectangle(cornerRadius: 7))
                    .overlay(RoundedRectangle(cornerRadius: 7).stroke(i == current ? Palette.star : .clear, lineWidth: 2))
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .position(x: size.width * (row.x ?? 50) / 100, y: size.height * (row.y ?? 50) / 100)
                .accessibilityLabel("\(row.label ?? row.slot): fit \(fit.map { String(format: "%.1f", $0) } ?? "none")")
                .accessibilityAddTraits(i == current ? .isSelected : [])
            }
        }
        .frame(width: 340)
    }

    @ViewBuilder
    private func card(_ rows: [Formation.Row], _ fitRows: [TacticalFit.Row], _ current: Int) -> some View {
        if current < fitRows.count {
            RoleCard(report: report, row: rows[current], fit: fitRows[current]).fixedSize(horizontal: true, vertical: false)
        }
    }
}

private struct RoleCard: View {
    let report: Report
    let row: Formation.Row
    let fit: TacticalFit.Row

    var body: some View {
        let ip = row.ipKeys ?? [], oop = row.oopKeys ?? []
        let keys = (ip + oop).reduce(into: [String]()) { if !$0.contains($1) { $0.append($1) } }
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(row.label ?? row.slot).slotFont(24)
                Text(row.ipRoleName ?? fit.ipRole).fontWeight(.semibold)
                Text("in possession ·").foregroundStyle(.secondary)
                Text(row.oopRoleName ?? fit.oopRole).fontWeight(.semibold)
                Text("out of possession").foregroundStyle(.secondary)
            }
            FlowRow(spacing: 4) {
                Text("Look for").font(.caption.weight(.bold)).foregroundStyle(.secondary)
                ForEach(keys, id: \.self) { k in
                    KeyChip(text: report.label(k), kind: ip.contains(k) && oop.contains(k) ? .both : ip.contains(k) ? .ip : .oop)
                }
            }
            Grid(alignment: .leading, horizontalSpacing: 5, verticalSpacing: 4) {
                GridRow {
                    Text("Player")
                    Text("Fit")
                    ForEach(keys, id: \.self) { k in
                        Text(report.abbr(k)).help(report.label(k))
                            .foregroundStyle(ip.contains(k) && oop.contains(k) ? Palette.loanOut : ip.contains(k) ? Palette.loanIn : Palette.injuryLong)
                    }
                    Text(String((report.style?.name ?? "Style").prefix(5))).foregroundStyle(Palette.verdict("amber"))
                }
                .font(.caption.weight(.bold))
                Divider().gridCellUnsizedAxes(.horizontal)
                ForEach(fit.entries.prefix(6)) { e in
                    if let p = report.player(e.uid) {
                        GridRow {
                            HStack(spacing: 5) {
                                Text(shortName(p.name)).fontWeight(.semibold).lineLimit(1)
                                if e.xi { XITag() }
                            }
                            .frame(width: 150, alignment: .leading)
                            FitBar(value: e.fit ?? 0).fixedSize()
                            ForEach(keys, id: \.self) { AttrCell(value: p.attribute($0)) }
                            AttrCell(value: e.style.map { Int($0.rounded()) })
                        }
                    }
                }
            }
            if fit.entries.isEmpty { Text("Nobody in your first team can play here.").foregroundStyle(.secondary) }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .panel(10)
    }
}

/// The web app's short name: the full name if it's 15 letters or fewer, otherwise without the first name.
func shortName(_ name: String) -> String {
    name.count <= 15 ? name : surname(name)
}
