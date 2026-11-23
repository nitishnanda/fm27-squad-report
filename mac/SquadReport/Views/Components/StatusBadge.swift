import SwiftUI

/// A player's statuses, kept visually distinct (his rule): transfer vs loan, in vs out, arranged vs current,
/// short vs long injury. Each one has its own colour, its own symbol and a word, so colour is never the only clue.
struct PlayerStatus: Identifiable, Hashable, Sendable {
    enum Kind: String, Sendable {
        case transferIn, transferOut, loanInArranged, loanOutArranged, loanIn, loanOut
        case injuredShort, injuredLong, suspended, expiring
    }
    let kind: Kind
    let label: String
    let detail: String
    var id: String { kind.rawValue + detail }

    /// The same list and order as the web app's `badges()`.
    static func of(_ p: Player) -> [PlayerStatus] {
        var out: [PlayerStatus] = []
        let moves = Dictionary(p.status.moves.map { ($0.kind, $0) }, uniquingKeysWith: { a, _ in a })
        if let m = moves["deal_in"] { out.append(.init(kind: .transferIn, label: "Transfer in", detail: "from \(m.club) · joins \(Fmt.day(m.date))")) }
        if let m = moves["deal_out"] { out.append(.init(kind: .transferOut, label: "Transfer out", detail: "to \(m.club) · leaves \(Fmt.day(m.date))")) }
        if let m = moves["loan_in_arr"] { out.append(.init(kind: .loanInArranged, label: "Loan in (arranged)", detail: "from \(m.club) · joins \(Fmt.day(m.date))")) }
        if let m = moves["loan_out_arr"] { out.append(.init(kind: .loanOutArranged, label: "Loan out (arranged)", detail: "to \(m.club) · leaves \(Fmt.day(m.date))")) }
        if let m = moves["loan_in"] { out.append(.init(kind: .loanIn, label: "Loan in", detail: "from \(m.club) · until \(Fmt.day(m.date))")) }
        if let m = moves["loan_out"] { out.append(.init(kind: .loanOut, label: "Loan out", detail: "at \(m.club) · back \(Fmt.day(m.date))")) }
        if let inj = p.status.injury {
            out.append(.init(kind: inj.long ? .injuredLong : .injuredShort, label: "Injured",
                             detail: "\(Fmt.injury(days: inj.days)) · \(inj.what) · back \(Fmt.day(inj.back))"))
        }
        if let n = p.status.suspendedMatches {
            out.append(.init(kind: .suspended, label: "Suspended", detail: "\(n) ban\(n == 1 ? "" : "s")"))
        }
        if p.expiring, moves["deal_out"] == nil {
            out.append(.init(kind: .expiring, label: "Contract", detail: "ends \(Fmt.month(p.contractEnd))"))
        }
        return out
    }
}

struct StatusBadge: View {
    let status: PlayerStatus
    var showDetail = true

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: symbol).font(.system(size: 9, weight: .bold))
            Text(status.label).fontWeight(.bold)
            if showDetail { Text(status.detail).fontWeight(.regular).opacity(0.85) }
        }
        .font(.system(size: 11))
        .lineLimit(1)
        .padding(.horizontal, 7)
        .padding(.vertical, 2)
        .foregroundStyle(ink)
        .background(fill, in: Capsule())
        .overlay(Capsule().strokeBorder(edge, style: StrokeStyle(lineWidth: 1, dash: dashed ? [3, 2] : [])))
        .help("\(status.label): \(status.detail)")
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(status.label), \(status.detail)")
    }

    private var base: Color {
        switch status.kind {
        case .transferIn: Palette.transferIn
        case .transferOut: Palette.transferOut
        case .loanIn, .loanInArranged: Palette.loanIn
        case .loanOut, .loanOutArranged: Palette.loanOut
        case .injuredShort: Palette.injuryShort
        case .injuredLong: Palette.injuryLong
        case .suspended: Palette.suspended
        case .expiring: .secondary
        }
    }

    /// Arranged moves and contracts ending are dashed: they haven't happened yet.
    private var dashed: Bool { [.loanInArranged, .loanOutArranged, .expiring].contains(status.kind) }

    private var symbol: String {
        switch status.kind {
        case .transferIn: "arrow.down.circle.fill"
        case .transferOut: "arrow.up.circle.fill"
        case .loanIn: "arrow.down.circle"
        case .loanOut: "arrow.up.circle"
        case .loanInArranged, .loanOutArranged: "calendar.badge.clock"
        case .injuredShort: "cross.case.fill"
        case .injuredLong: "bed.double.fill"     // a different shape too, so it isn't colour alone
        case .suspended: "nosign"
        case .expiring: "doc.text"
        }
    }

    private var fill: Color {
        switch status.kind {
        case .injuredShort: Palette.injuryShort
        case .injuredLong: Palette.injuryLong
        case .suspended: Color(hex: "#111111")
        case .expiring, .loanInArranged, .loanOutArranged: .clear
        default: base.opacity(0.16)
        }
    }

    private var ink: Color {
        switch status.kind {
        case .injuredShort: Color(hex: "#221A00")
        case .injuredLong: .white
        case .suspended: Color(hex: "#E5E7EB")
        case .expiring: .secondary
        default: base
        }
    }

    private var edge: Color {
        switch status.kind {
        case .injuredShort, .injuredLong: .clear
        case .suspended: Palette.suspended
        case .expiring: Color.secondary.opacity(0.7)
        default: base.opacity(0.6)
        }
    }
}

/// The tag in front of a news item (Signing, Loan agreed, Injured…), coloured by its kind.
struct NewsTag: View {
    let item: NewsItem

    var body: some View {
        Text(item.tag)
            .font(.system(size: 10.5, weight: .bold))
            .padding(.horizontal, 7)
            .padding(.vertical, 1.5)
            .foregroundStyle(ink)
            .background(fill, in: Capsule())
            .overlay(Capsule().strokeBorder(edge, style: StrokeStyle(lineWidth: 1, dash: item.kind == "expiring" ? [3, 2] : [])))
    }

    private var base: Color {
        switch item.kind {
        case "deal-in": Palette.transferIn
        case "deal-out": Palette.transferOut
        case "loan-in": Palette.loanIn
        case "loan-out": Palette.loanOut
        case "inj-short": Palette.injuryShort
        case "inj-long": Palette.injuryLong
        case "sus": Palette.suspended
        case "warn": Palette.verdict("red")
        default: .secondary
        }
    }
    private var fill: Color {
        switch item.kind {
        case "inj-short", "inj-long", "warn": base
        case "sus": Color(hex: "#111111")
        case "expiring": .clear
        default: base.opacity(0.16)
        }
    }
    private var ink: Color {
        switch item.kind {
        case "inj-short": Color(hex: "#221A00")
        case "inj-long", "warn": .white
        case "sus": Color(hex: "#E5E7EB")
        case "expiring": .secondary
        default: base
        }
    }
    private var edge: Color { item.kind == "expiring" ? Color.secondary.opacity(0.7) : base.opacity(0.55) }
}
