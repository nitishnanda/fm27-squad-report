import SwiftUI

/// Transfers: everything dated that changes the squad, month by month (moves, loans starting and ending, contracts
/// running out), then the moves and loans themselves. Facts from the save only, never a suggestion.
struct TransfersView: View {
    let report: Report

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                SectionTitle("Deals & loans")
                ComingUp(report: report)
                MoveColumns(report: report)
            }
            .padding(24)
            .frame(maxWidth: .infinity, alignment: .leading)
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
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text("Coming up").font(.title3.weight(.heavy).width(.condensed))
                Text("arranged moves, loans starting and ending, contracts running out · by month").foregroundStyle(.secondary)
            }
            if months.isEmpty {
                Text("Nothing arranged, and no loans or contracts ending in the next year.").foregroundStyle(.secondary)
            }
            // one row per year, so January 2028 can never read as if it came before May 2027
            ForEach(Self.years(months), id: \.year) { group in
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(String(group.year)).font(.system(size: 26, weight: .heavy).width(.condensed))
                    Rectangle().fill(.quaternary).frame(height: 1)
                }
                .padding(.top, 6)
                .accessibilityAddTraits(.isHeader)
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 230), spacing: 14, alignment: .top)], spacing: 18) {
                ForEach(group.months) { month in
                    VStack(alignment: .leading, spacing: 8) {
                        ZStack(alignment: .leading) {
                            Rectangle().fill(.quaternary).frame(height: 2)
                            Circle().fill(Palette.brandHigh).frame(width: 11, height: 11)
                        }
                        HStack(alignment: .firstTextBaseline, spacing: 8) {
                            Text(Self.monthFormat.string(from: month.start)).font(.title3.weight(.heavy).width(.condensed))
                            Text("\(month.count) \(month.count == 1 ? "thing" : "things")").font(.caption).foregroundStyle(.secondary)
                        }
                        ForEach(month.events) { e in event(e) }
                    }
                }
            }
            }
        }
    }

    private struct Year { let year: Int; let months: [TransferTimeline.Month] }

    private static func years(_ months: [TransferTimeline.Month]) -> [Year] {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "UTC")!
        let byYear = Dictionary(grouping: months) { cal.component(.year, from: $0.start) }
        return byYear.keys.sorted().map { Year(year: $0, months: byYear[$0]!) }
    }

    private func event(_ e: TimelineEvent) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Label(e.tag, systemImage: e.kind.symbol)
                .labelStyle(.titleAndIcon)
                .font(.caption.weight(.bold))
                .foregroundStyle(e.kind.color)
                .padding(.horizontal, 6).padding(.vertical, 2)
                .background(e.kind.color.opacity(0.14), in: Capsule())
                .overlay(Capsule().strokeBorder(e.kind.color.opacity(0.55),
                                                style: StrokeStyle(lineWidth: 1, dash: [.expiring, .loanInArranged, .loanOutArranged].contains(e.kind) ? [3, 2] : [])))
                .fixedSize()
            VStack(alignment: .leading, spacing: 2) {
                if e.grouped {
                    Text("\(e.detail) · \(Self.dayFormat.string(from: e.date))").fontWeight(.semibold)
                    Text(e.names.joined(separator: ", ")).font(.caption).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                } else {
                    Text(e.names.first ?? "").fontWeight(.semibold)
                    Text("\(e.detail) · \(Self.dayFormat.string(from: e.date))").font(.caption).foregroundStyle(.secondary)
                }
            }
        }
        .font(.callout)
        .padding(9)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.quaternary.opacity(0.45), in: RoundedRectangle(cornerRadius: 8))
        .accessibilityElement(children: .combine)
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
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                Text(title).font(.title3.weight(.heavy).width(.condensed))
                if let sub { Text(sub).foregroundStyle(.secondary) }
            }
            HStack(alignment: .top, spacing: 12) {
                ForEach(cols, id: \.1) { col in column(col) }
            }
        }
    }

    private func column(_ col: (String, String, PlayerStatus.Kind, String, String)) -> some View {
        let (title, key, kind, prep, when) = col
        let items = report.players.compactMap { p in p.status.moves.first { $0.kind == key }.map { (p, $0) } }
        let dashed = [.loanInArranged, .loanOutArranged].contains(kind)
        return VStack(alignment: .leading, spacing: 0) {
            HStack {
                Label(title, systemImage: kind.symbol).font(.headline.width(.condensed)).foregroundStyle(kind.color)
                Spacer()
                Text("\(items.count)").font(.caption.weight(.bold)).monospacedDigit()
                    .padding(.horizontal, 7).background(.quaternary, in: Capsule())
            }
            .padding(10)
            .background(kind.color.opacity(dashed ? 0.06 : 0.16))
            if items.isEmpty {
                Text("None right now").foregroundStyle(.secondary).padding(10)
            }
            ForEach(items, id: \.0.uid) { p, m in
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(p.name).fontWeight(.semibold)
                        Text("\(p.positions.natural.joined(separator: " ")) · \(p.age.map(String.init) ?? "")").font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 2) {
                        (Text("\(prep) ") + Text(m.club).fontWeight(.semibold)).font(.caption)
                        Text("\(when) \(Fmt.day(m.date))").font(.caption).foregroundStyle(.secondary)
                    }
                }
                .padding(.horizontal, 10).padding(.vertical, 7)
                Divider().opacity(0.5)
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .background(.quaternary.opacity(0.35))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(kind.color.opacity(0.35), style: StrokeStyle(lineWidth: 1, dash: dashed ? [4, 3] : [])))
    }
}
