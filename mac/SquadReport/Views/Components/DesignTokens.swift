import SwiftUI

/// The values in DESIGN.md, in one place. Layout code uses these; a value outside them needs a comment saying why.
enum DS {
    /// Spacing scale: 4 · 8 · 12 · 16 · 20 · 24 · 32 · 48.
    enum Space {
        static let xxs: CGFloat = 4, xs: CGFloat = 8, s: CGFloat = 12, m: CGFloat = 16, l: CGFloat = 20
        static let xl: CGFloat = 24, xxl: CGFloat = 32, xxxl: CGFloat = 48
        /// Around every page.
        static let page: CGFloat = 24
        /// Between sections on a page.
        static let section: CGFloat = 32
        /// Between cards in a grid.
        static let grid: CGFloat = 12
    }

    /// Corner radii: 4 badges · 6 controls · 10 cards · 14 containers of cards.
    enum Radius {
        static let badge: CGFloat = 4, control: CGFloat = 6, card: CGFloat = 10, container: CGFloat = 14
    }

    /// Dark surfaces: neutral grey, each step about 1.8× brighter.
    enum Surface {
        static let canvas = Color(hex: "#0B0B0D")
        static let panel = Color(hex: "#151517")
        static let raised = Color(hex: "#1E1E21")
        static let selected = Color(hex: "#26282B")
        static let hairline = Color(hex: "#26272A")
        static let strong = Color(hex: "#34363A")
    }

    /// Up / down / flat and warnings. Statuses keep their own colours in Palette.
    enum Delta {
        static let up = Color(hex: "#4FC77F")
        static let down = Color(hex: "#F2555A")
        static let flat = Color(hex: "#8E9096")
        static let warn = Color(hex: "#F5A524")
    }

    /// KPI tiles: label / value / a 14 pt slot (a 6 pt meter, or stars) / sub.
    static let tileHeight: CGFloat = 148   // 20 + label 15 + 8 + value 41 + 8 + slot 14 + 8 + sub 14 + 20
    static let tileSlot: CGFloat = 14
    static let meterHeight: CGFloat = 6
}

/// A 6 pt meter: a meaning colour on a quiet track, never grey (DESIGN.md › Meter).
struct Meter: View {
    let value: Double
    let total: Double
    var color: Color = DS.Delta.up
    @Environment(\.theme) private var theme

    var body: some View {
        GeometryReader { geo in
            let f = total > 0 ? min(max(value / total, 0), 1) : 0
            ZStack(alignment: .leading) {
                Capsule().fill(theme.scheme == .light ? Color.black.opacity(0.08) : DS.Surface.selected)
                Capsule().fill(color).frame(width: geo.size.width * f)
            }
        }
        .frame(height: DS.meterHeight)
        .accessibilityElement()
        .accessibilityValue("\(Int((total > 0 ? value / total : 0) * 100)) percent")
    }
}
