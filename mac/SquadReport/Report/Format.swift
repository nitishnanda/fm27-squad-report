import Foundation

/// Number and date formats, matching the web app so both say the same thing.
enum Fmt {
    /// Stars are shown in half-star steps (Python: `math.floor(x * 2 + 0.5) / 2`).
    static func half(_ x: Double) -> Double { (x * 2 + 0.5).rounded(.down) / 2 }

    /// "4.5" / "3"
    static func stars(_ x: Double) -> String {
        let h = half(x)
        return h == h.rounded() ? String(Int(h)) : String(format: "%.1f", h)
    }

    /// £1.35bn, £44m, £2.6m, £24k
    static func money(_ v: Double?) -> String {
        guard let v else { return "–" }
        if abs(v) >= 1_000_000_000 { return String(format: "£%.2fbn", v / 1_000_000_000) }
        if abs(v) >= 1_000_000 {
            let m = v / 1_000_000
            return abs(m) < 10 ? String(format: "£%.1fm", m) : String(format: "£%.0fm", m)
        }
        return String(format: "£%.0fk", v / 1000)
    }

    /// £5.17m a week, £229k
    static func wage(_ v: Double?) -> String {
        guard let v else { return "–" }
        return v >= 1_000_000 ? String(format: "£%.2fm", v / 1_000_000) : String(format: "£%.0fk", v / 1000)
    }

    private static let iso: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    private static func display(_ format: String) -> DateFormatter {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")   // "Sep", like the web app
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = format
        return f
    }
    private static let dayFormat = display("d MMM yyyy")
    private static let shortDayFormat = display("d MMM")
    private static let monthFormat = display("MMM yyyy")

    /// ISO "2026-11-22" (or a full timestamp) to a date
    static func date(_ s: String?) -> Date? {
        guard let s, s.count >= 10 else { return nil }
        return iso.date(from: String(s.prefix(10)))
    }

    /// "22 Nov 2026"
    static func day(_ s: String?) -> String { date(s).map { dayFormat.string(from: $0) } ?? "–" }
    /// "22 Nov"
    static func shortDay(_ s: String?) -> String { date(s).map { shortDayFormat.string(from: $0) } ?? "–" }
    /// "Jun 2027"
    static func month(_ s: String?) -> String { date(s).map { monthFormat.string(from: $0) } ?? "–" }

    /// "1st", "2nd", "23rd", "11th"
    static func ordinal(_ n: Int) -> String {
        let tens = n % 100
        let suffix = (11...13).contains(tens) ? "th" : (["th", "st", "nd", "rd"] + Array(repeating: "th", count: 6))[n % 10]
        return "\(n)\(suffix)"
    }

    /// "5 days", "4 wks" (same as the web app)
    static func injury(days: Int) -> String {
        days < 14 ? "\(days) day\(days == 1 ? "" : "s")" : "\(Int((Double(days) / 7).rounded())) wks"
    }
}
