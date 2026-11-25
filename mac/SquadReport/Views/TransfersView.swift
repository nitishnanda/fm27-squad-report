import SwiftUI

/// Transfers: everything dated that changes the squad, month by month (moves, loans starting and ending, contracts
/// running out), then the moves and loans themselves. Facts from the save only, never a suggestion.
struct TransfersView: View {
    let report: Report

    var body: some View {
        // Laid out from his Figma Make design (TransfersView.tsx): month cards, then the moves and loans as cards.
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                SectionTitle("Deals & loans", sub: "Arranged permanent moves, loans starting and ending, and contracts running out, by month", page: true)
                ComingUp(report: report)
                MoveColumns(report: report)
            }
            .frame(maxWidth: 1172, alignment: .leading)
            .padding(.horizontal, 24).padding(.vertical, 20)
            .frame(maxWidth: .infinity)
        }
    }
}

// MARK: - coming up (data)

struct TimelineEvent: Identifiable, Sendable {
    let date: Date
    let kind: PlayerStatus.Kind
    let tag: String
    let names: [String]        // one player, or several on the same day
    let detail: String
    var id: String { "\(date.timeIntervalSince1970)-\(kind.rawValue)-\(names.joined(separator: ","))" }
    var grouped: Bool { names.count > 1 }
}

enum TransferTimeline {
    struct Month: Identifiable, Sendable {
        let start: Date
        let events: [TimelineEvent]
        let count: Int
        var id: Date { start }
    }

    private typealias Raw = (date: Date, kind: PlayerStatus.Kind, tag: String, name: String, detail: String)

    /// The same events as the web app's `deal_timeline()`. Three or more of the same thing on the same day
    /// become one card ("15 contracts end").
    static func months(_ report: Report) -> [Month] {
        var raw: [Raw] = []
        for p in report.players {
            for m in p.status.moves {
                guard let date = Fmt.date(m.date) else { continue }
                switch m.kind {
                case "deal_in": raw.append((date, .transferIn, "Joins", p.name, "from \(m.club)"))
                case "deal_out": raw.append((date, .transferOut, "Leaves", p.name, "to \(m.club)"))
                case "loan_in_arr": raw.append((date, .loanInArranged, "Loan starts", p.name, "from \(m.club)"))
                case "loan_out_arr": raw.append((date, .loanOutArranged, "Loan starts", p.name, "to \(m.club)"))
                case "loan_in": raw.append((date, .loanIn, "Loan ends", p.name, "back to \(m.club)"))
                case "loan_out": raw.append((date, .loanOut, "Back", p.name, "from \(m.club)"))
                default: break
                }
            }
            if p.expiring, !p.status.moves.contains(where: { $0.kind == "deal_out" }), let date = Fmt.date(p.contractEnd) {
                raw.append((date, .expiring, "Contract", p.name, "deal ends"))
            }
        }
        raw.sort { ($0.date, $0.kind.rawValue, $0.name) < ($1.date, $1.kind.rawValue, $1.name) }
        let many = ["Contract": "contracts end", "Back": "back from loan", "Joins": "join", "Leaves": "leave",
                    "Loan starts": "loans start", "Loan ends": "loans end"]
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "UTC")!
        let byMonth = Dictionary(grouping: raw) { cal.date(from: cal.dateComponents([.year, .month], from: $0.date))! }
        return byMonth.keys.sorted().map { start in
            let items = byMonth[start]!
            var order: [String] = []
            var same: [String: [Raw]] = [:]
            for item in items {
                let key = "\(item.date.timeIntervalSince1970)|\(item.kind.rawValue)|\(item.tag)"
                if same[key] == nil { order.append(key) }
                same[key, default: []].append(item)
            }
            var events: [TimelineEvent] = []
            for key in order {
                let group = same[key]!
                let first = group[0]
                if group.count >= 3 {
                    events.append(TimelineEvent(date: first.date, kind: first.kind, tag: first.tag,
                                                names: group.map { surname($0.name) }, detail: "\(group.count) \(many[first.tag] ?? "")"))
                } else {
                    events += group.map { TimelineEvent(date: $0.date, kind: $0.kind, tag: $0.tag, names: [$0.name], detail: $0.detail) }
                }
            }
            return Month(start: start, events: events, count: items.count)
        }
    }
}

// MARK: - coming up (view)

private struct ComingUp: View {
    let report: Report

    private static let monthFormat: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "MMM yyyy"
        return f
    }()
    private static let dayFormat: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "d MMM"
        return f
    }()

    var body: some View {
        let months = TransferTimeline.months(report)
        VStack(alignment: .leading, spacing: 20) {
            if months.isEmpty {
                Text("Nothing arranged, and no loans or contracts ending in the next year.").font(.system(size: 12.5)).foregroundStyle(.secondary)
            }
            // one block per year, so January 2028 can never read as if it came before May 2027
            ForEach(Self.years(months), id: \.year) { group in
                VStack(alignment: .leading, spacing: 12) {
                    SectionTitle("\(String(group.year)) horizon", sub: "What changes in your squad, month by month")
                    CardGrid(items: group.months, minWidth: 420, maxColumns: 2, spacing: 16) { month in monthCard(month) }
                }
            }
        }
    }

    /// The design's month card: a dot, the month, how many things; a rule; one row per move.
    private func monthCard(_ month: TransferTimeline.Month) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 8) {
                Circle().fill(Palette.brandHigh).frame(width: 8, height: 8)
                Text(Self.monthFormat.string(from: month.start)).font(.system(size: 15, weight: .bold))
                Spacer()
                Text("\(month.count) \(month.count == 1 ? "thing" : "things")").font(.system(size: 11.5)).monospacedDigit().foregroundStyle(.secondary)
            }
            .padding(.bottom, 10)
            .overlay(alignment: .bottom) { Rectangle().fill(Color.primary.opacity(0.06)).frame(height: 1) }
            ForEach(Array(month.events.enumerated()), id: \.element.id) { i, e in
                if i > 0 { Rectangle().fill(Color.primary.opacity(0.05)).frame(height: 1) }
                event(e)
            }
            Spacer(minLength: 0)
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .hubCard()
    }

    private struct Year { let year: Int; let months: [TransferTimeline.Month] }

    private static func years(_ months: [TransferTimeline.Month]) -> [Year] {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "UTC")!
        let byYear = Dictionary(grouping: months) { cal.component(.year, from: $0.start) }
        return byYear.keys.sorted().map { Year(year: $0, months: byYear[$0]!) }
    }

    private func event(_ e: TimelineEvent) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 10) {
                KindPill(kind: e.kind, label: e.tag)
                Text(e.grouped ? "\(e.detail) · \(Self.dayFormat.string(from: e.date))" : (e.names.first ?? ""))
                    .font(.system(size: 12.5, weight: .medium)).lineLimit(1)
                Spacer(minLength: 8)
                if !e.grouped {
                    Text("\(e.detail) · \(Self.dayFormat.string(from: e.date))").font(.system(size: 11.5)).monospacedDigit()
                        .foregroundStyle(.secondary).lineLimit(1)
                }
            }
            if e.grouped {
                Text(e.names.joined(separator: ", ")).font(.system(size: 11.5)).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true).padding(.leading, 4)
            }
        }
        .padding(.vertical, 8)
        .accessibilityElement(children: .combine)
    }
}

/// A status as the design's pill, in the status's own colour and symbol; arranged moves and contracts keep the dashed
/// edge (his rule: every status stays visually distinct).
private struct KindPill: View {
    let kind: PlayerStatus.Kind
    let label: String

    var body: some View {
        let dashed = [.expiring, .loanInArranged, .loanOutArranged].contains(kind)
        Label(label, systemImage: kind.symbol)
            .labelStyle(.titleAndIcon)
            .font(.system(size: 11, weight: .medium))
            .foregroundStyle(kind.color)
            .padding(.horizontal, 8).padding(.vertical, 2)
            .background(kind.color.opacity(dashed ? 0.06 : 0.12), in: Capsule())
            .overlay(Capsule().strokeBorder(kind.color.opacity(dashed ? 0.55 : 0.25), style: StrokeStyle(lineWidth: 1, dash: dashed ? [3, 2] : [])))
            .fixedSize()
    }
}

// MARK: - the moves and loans

private struct MoveColumns: View {
    let report: Report

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            group("Transfers arranged", "permanent moves that haven't happened yet", [
                ("Transfer in", "deal_in", PlayerStatus.Kind.transferIn, "from", "joins"),
                ("Transfer out", "deal_out", .transferOut, "to", "leaves")])
            group("Loans arranged", "agreed, starting later", [
                ("Loan in (arranged)", "loan_in_arr", .loanInArranged, "from", "joins"),
                ("Loan out (arranged)", "loan_out_arr", .loanOutArranged, "to", "leaves")])
            group("Current loans", nil, [
                ("Loaned in now", "loan_in", .loanIn, "from", "until"),
                ("Loaned out now", "loan_out", .loanOut, "at", "back")])
        }
    }

    private func group(_ title: String, _ sub: String?, _ cols: [(String, String, PlayerStatus.Kind, String, String)]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionTitle(title, sub: sub)
            HStack(alignment: .top, spacing: 16) {
                ForEach(cols, id: \.1) { col in column(col) }
            }
        }
    }

    /// The design's move card: a 2 pt edge in the status colour, the kind and count on top, then one line per player.
    private func column(_ col: (String, String, PlayerStatus.Kind, String, String)) -> some View {
        let (title, key, kind, prep, when) = col
        let items = report.players.compactMap { p in p.status.moves.first { $0.kind == key }.map { (p, $0) } }
        return VStack(alignment: .leading, spacing: 0) {
            HStack {
                Label(title, systemImage: kind.symbol).font(.system(size: 12, weight: .semibold)).foregroundStyle(kind.color)
                Spacer()
                Text("\(items.count)").font(.system(size: 12, weight: .semibold)).monospacedDigit().foregroundStyle(kind.color)
            }
            .padding(.bottom, 10)
            if items.isEmpty {
                Text("None right now").font(.system(size: 12)).foregroundStyle(.secondary)
            }
            ForEach(Array(items.enumerated()), id: \.element.0.uid) { i, item in
                let (p, m) = item
                if i > 0 { Rectangle().fill(Color.primary.opacity(0.05)).frame(height: 1) }
                HStack(alignment: .center) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(p.name).font(.system(size: 14, weight: .semibold))
                        Text("\(p.positions.natural.joined(separator: " / ")) · Age \(p.age.map(String.init) ?? "–")")
                            .font(.system(size: 11.5)).monospacedDigit().foregroundStyle(.secondary)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 2) {
                        Text("\(prep) \(m.club)").foregroundStyle(.secondary)
                        Text("\(when) \(Fmt.day(m.date))").foregroundStyle(.tertiary)
                    }
                    .font(.system(size: 11.5)).monospacedDigit()
                }
                .padding(.vertical, 8)
            }
            Spacer(minLength: 0)
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .overlay(alignment: .leading) { Rectangle().fill(kind.color).frame(width: 2) }
        .hubCard()
    }
}
