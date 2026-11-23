import SwiftUI

/// The app's own colours (the "tactics board" brand) plus the status colours the web app uses,
/// so a loan out is purple and a long injury red everywhere.
enum Palette {
    static let brand = Color(hex: "#1C7F46")
    static let brandHigh = Color(hex: "#4FC77F")
    static let star = Color(hex: "#E9B949")
    static let starEmpty = Color.secondary.opacity(0.28)
    static let potential = Color(hex: "#5B9BF0")

    static let transferIn = Color(hex: "#22C55E")
    static let transferOut = Color(hex: "#EC4899")
    static let loanIn = Color(hex: "#3B82F6")
    static let loanOut = Color(hex: "#A855F7")
    static let injuryShort = Color(hex: "#FACC15")
    static let injuryLong = Color(hex: "#EF4444")
    static let suspended = Color(hex: "#94A3B8")

    static func verdict(_ level: String) -> Color {
        switch level {
        case "red": Color(hex: "#FF5D5D")
        case "amber": Color(hex: "#F59E0B")
        case "green": Color(hex: "#10B981")
        default: Color(hex: "#6B7A71")
        }
    }

    static func result(_ res: String) -> Color {
        switch res {
        case "W": Color(hex: "#15803D")
        case "L": Color(hex: "#B91C1C")
        default: Color(hex: "#7C8A80")
        }
    }
}

extension Color {
    /// "#C8102E" or "C8102E"
    init(hex: String) {
        var text = hex.trimmingCharacters(in: .whitespaces)
        if text.hasPrefix("#") { text.removeFirst() }
        var value: UInt64 = 0
        Scanner(string: text).scanHexInt64(&value)
        let r, g, b: Double
        if text.count == 3 {
            r = Double((value >> 8) & 0xF) / 15; g = Double((value >> 4) & 0xF) / 15; b = Double(value & 0xF) / 15
        } else {
            r = Double((value >> 16) & 0xFF) / 255; g = Double((value >> 8) & 0xFF) / 255; b = Double(value & 0xFF) / 255
        }
        self.init(.sRGB, red: r, green: g, blue: b, opacity: 1)
    }
}
