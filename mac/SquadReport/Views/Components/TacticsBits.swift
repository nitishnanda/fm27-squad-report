import SwiftUI

/// One cell per league team, yours lit. The top quarter is tinted green, the bottom half red, like the web app.
struct RankStrip: View {
    let rank: Int
    let of: Int
    let good: Bool

    var body: some View {
        let cut = max(3, Int((Double(of) * 0.25).rounded()))
        HStack(spacing: 2) {
            ForEach(1...max(of, 1), id: \.self) { k in
                RoundedRectangle(cornerRadius: 4)
                    .fill(color(k, cut: cut))
                    .frame(height: 7)
                    .overlay {
                        if k == rank {
                            RoundedRectangle(cornerRadius: 4).stroke((good ? Palette.transferIn : Palette.injuryLong).opacity(0.5), lineWidth: 3)
                        }
                    }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(Fmt.ordinal(rank)) of \(of)")
    }

    private func color(_ k: Int, cut: Int) -> Color {
        if k == rank { return good ? Palette.transferIn : Palette.injuryLong }
        if k <= cut { return Palette.transferIn.opacity(0.22) }
        if Double(k) > Double(of) / 2 { return Palette.injuryLong.opacity(0.18) }
        return Color.secondary.opacity(0.18)
    }
}

/// A fit score (/20) as a number and a bar: green 14+, grey from the floor, red below it.
struct FitBar: View {
    let value: Double
    var floor: Double = 12

    var body: some View {
        let color = value >= 14 ? Palette.transferIn : value >= floor ? Color.secondary : Palette.injuryLong
        HStack(spacing: 6) {
            Text(String(format: "%.1f", value))
                .font(.callout.weight(.semibold)).monospacedDigit()
                .foregroundStyle(value < floor ? Palette.injuryLong : .primary)
                .frame(width: 34, alignment: .trailing)
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(.quaternary)
                    Capsule().fill(color).frame(width: geo.size.width * max(0, min(1, (value - 5) / 15)))
                }
            }
            .frame(width: 60, height: 5)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(String(format: "fit %.1f out of 20", value))
    }
}

/// An attribute value tinted by band, the same bands as the web app: ≤8 red, 9–10 amber, 11–12 grey, 13–15 green, 16+ deep green.
struct AttrCell: View {
    let value: Int?

    var body: some View {
        Text(value.map(String.init) ?? "–")
            .font(.callout.weight(.semibold)).monospacedDigit()
            .frame(width: 30, height: 22)
            .foregroundStyle(ink)
            .background(fill, in: RoundedRectangle(cornerRadius: 4))
    }

    private var band: Int {
        guard let v = value else { return 0 }
        switch v {
        case ...8: return 1
        case 9...10: return 2
        case 11...12: return 3
        case 13...15: return 4
        default: return 5
        }
    }
    private var fill: Color {
        switch band {
        case 1: Palette.injuryLong.opacity(0.35)
        case 2: Palette.verdict("amber").opacity(0.28)
        case 3: Color.secondary.opacity(0.14)
        case 4: Palette.transferIn.opacity(0.2)
        case 5: Palette.transferIn.opacity(0.42)
        default: .clear
        }
    }
    private var ink: Color { band == 0 ? .secondary : .primary }
}

/// The colour key for attribute values.
struct AttrScale: View {
    var body: some View {
        HStack(spacing: 3) {
            ForEach([(8, "≤8"), (10, "9–10"), (12, "11–12"), (14, "13–15"), (16, "16+")], id: \.0) { v, label in
                Text(label).font(.caption2.weight(.semibold)).padding(.horizontal, 6).padding(.vertical, 2)
                    .background(AttrCell(value: v).fillColor, in: RoundedRectangle(cornerRadius: 4))
            }
        }
        .accessibilityHidden(true)
    }
}

extension AttrCell {
    var fillColor: Color { fill }
}

/// Chips for key attributes: blue in possession, red out of possession, purple both, amber for the style.
struct KeyChip: View {
    enum Kind { case ip, oop, both, style }
    let text: String
    let kind: Kind

    var body: some View {
        Text(text)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 7).padding(.vertical, 2)
            .foregroundStyle(color)
            .background(color.opacity(0.12), in: RoundedRectangle(cornerRadius: 4))
            .overlay(RoundedRectangle(cornerRadius: 4).stroke(color.opacity(0.5)))
    }

    private var color: Color {
        switch kind {
        case .ip: Palette.loanIn
        case .oop: Palette.injuryLong
        case .both: Palette.loanOut
        case .style: Palette.verdict("amber")
        }
    }
}
