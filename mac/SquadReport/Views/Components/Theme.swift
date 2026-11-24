import AppKit
import CoreText
import SwiftUI

/// The looks the Mac app carries: the original native design, and E "Glass + scoreboard" from the web app
/// (glass panels over a night pitch, scoreboard data: Bricolage Grotesque, Geist, Geist Mono, Doto numbers).
enum Look: String, CaseIterable, Identifiable, Sendable {
    case original, glass
    var id: String { rawValue }

    var title: String {
        switch self {
        case .original: "Original"
        case .glass: "Glass + scoreboard"
        }
    }

    var note: String {
        switch self {
        case .original: "The app's own design, light or dark with your Mac"
        case .glass: "Frosted panels over a night pitch, scoreboard numbers (the web app's look E)"
        }
    }
}

struct Theme: Sendable {
    let look: Look

    static let original = Theme(look: .original)

    var isGlass: Bool { look == .glass }

    // MARK: type

    /// Section titles and headings.
    func display(_ size: CGFloat, _ weight: Font.Weight = .heavy) -> Font {
        isGlass ? .custom(weight == .heavy || weight == .black ? "BricolageGrotesque96ptExtraBold-Regular_ExtraBold"
                          : "BricolageGrotesque96ptExtraBold-Regular_Bold", size: size)
                : .system(size: size, weight: weight).width(.condensed)
    }

    /// The club name in the hero.
    func hero(_ size: CGFloat) -> Font {
        isGlass ? .custom("BricolageGrotesque96ptExtraBold-Regular_ExtraBold", size: size)
                : .system(size: size, weight: .black).width(.compressed).italic()
    }

    /// Big numbers: key figures, league position.
    func number(_ size: CGFloat) -> Font {
        isGlass ? .custom("Doto-Black_Bold", size: size) : .system(size: size, weight: .heavy).width(.condensed)
    }

    /// Big ordinal like "7th": compressed italic in the original, scoreboard dots in glass.
    func position(_ size: CGFloat) -> Font {
        isGlass ? .custom("Doto-Black_Bold", size: size) : .system(size: size, weight: .black).width(.compressed).italic()
    }

    /// Slot names on cards (LW, CB): italic condensed in the original.
    func slot(_ size: CGFloat) -> Font {
        isGlass ? .custom("GeistMono-SemiBold", size: size * 0.8) : .system(size: size, weight: .heavy).width(.condensed).italic()
    }

    /// Small labels and data: Geist Mono in glass.
    func data(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        guard isGlass else { return .system(size: size, weight: weight) }
        let name = switch weight {
        case .bold, .heavy, .black: "GeistMono-SemiBold"
        case .semibold, .medium: "GeistMono-Medium"
        default: "GeistMono-Regular"
        }
        return .custom(name, size: size)
    }

    /// Body text.
    var bodyFont: Font? { isGlass ? .custom("Geist-Regular", size: 13) : nil }

    // MARK: colour

    var star: Color { isGlass ? Color(hex: "#4FC77F") : Palette.star }
    var accent: Color { Palette.brandHigh }
    var radius: CGFloat { isGlass ? 12 : 10 }
    var pitchStripes: (Color, Color) { isGlass ? (Color(hex: "#0F2B1B"), Color(hex: "#123220")) : (Color(hex: "#22603A"), Color(hex: "#1C5432")) }
    var pitchEdge: Color { isGlass ? Color.white.opacity(0.1) : Color(hex: "#275A37") }
    var cardFill: Color { isGlass ? Color(hex: "#09160F").opacity(0.86) : Color(hex: "#0E1512").opacity(0.94) }
}

extension EnvironmentValues {
    @Entry var theme: Theme = .original
}

// MARK: - applying it

/// Puts the chosen look on everything under it. Glass is always dark.
struct Themed: ViewModifier {
    @AppStorage("look") private var lookName = Look.original.rawValue

    func body(content: Content) -> some View {
        let theme = Theme(look: Look(rawValue: lookName) ?? .original)
        content
            .environment(\.theme, theme)
            .tint(theme.accent)
            .preferredColorScheme(theme.isGlass ? .dark : nil)
            .font(theme.bodyFont)
    }
}

extension View {
    func themed() -> some View { modifier(Themed()) }

    /// A card: soft grey in the original, frosted glass with a hairline in glass.
    func panel(_ radius: CGFloat? = nil) -> some View { modifier(PanelModifier(radius: radius, clip: true)) }
    /// Only the fill, for cards that draw their own shape and edge.
    func panelFill() -> some View { modifier(PanelModifier(radius: nil, clip: false)) }

    func displayFont(_ size: CGFloat, _ weight: Font.Weight = .heavy) -> some View { modifier(FontRole(role: .display(size, weight))) }
    func numberFont(_ size: CGFloat) -> some View { modifier(FontRole(role: .number(size))) }
    func positionFont(_ size: CGFloat) -> some View { modifier(FontRole(role: .position(size))) }
    func heroFont(_ size: CGFloat) -> some View { modifier(FontRole(role: .hero(size))) }
    func slotFont(_ size: CGFloat) -> some View { modifier(FontRole(role: .slot(size))) }
    func dataFont(_ size: CGFloat, _ weight: Font.Weight = .regular) -> some View { modifier(FontRole(role: .data(size, weight))) }

    /// The window behind the pages: the night pitch in glass.
    func pageBackground() -> some View { modifier(PageBackground()) }
}

private struct PanelModifier: ViewModifier {
    @Environment(\.theme) private var theme
    let radius: CGFloat?
    let clip: Bool

    func body(content: Content) -> some View {
        let shape = RoundedRectangle(cornerRadius: radius ?? theme.radius, style: .continuous)
        if theme.isGlass {
            let fill = LinearGradient(colors: [.white.opacity(0.06), .white.opacity(0.022)], startPoint: .top, endPoint: .bottom)
            if clip {
                content
                    .background(fill, in: shape)
                    .overlay(shape.strokeBorder(.white.opacity(0.11)).allowsHitTesting(false))
            } else {
                content.background(fill)
            }
        } else if clip {
            content.background(.quaternary.opacity(0.45), in: shape)
        } else {
            content.background(.quaternary.opacity(0.45))
        }
    }
}

private struct FontRole: ViewModifier {
    enum Role {
        case display(CGFloat, Font.Weight), number(CGFloat), position(CGFloat), hero(CGFloat), slot(CGFloat), data(CGFloat, Font.Weight)
    }
    @Environment(\.theme) private var theme
    let role: Role

    func body(content: Content) -> some View {
        switch role {
        case .display(let s, let w): content.font(theme.display(s, w))
        case .number(let s): content.font(theme.number(s)).monospacedDigit()
        case .position(let s): content.font(theme.position(s))
        case .hero(let s): content.font(theme.hero(s)).tracking(theme.isGlass ? -s * 0.04 : 0)
        case .slot(let s): content.font(theme.slot(s))
        case .data(let s, let w): content.font(theme.data(s, w))
        }
    }
}

private struct PageBackground: ViewModifier {
    @Environment(\.theme) private var theme
    @Environment(AppModel.self) private var model

    func body(content: Content) -> some View {
        if theme.isGlass {
            let kit = Color(hex: model.store.report?.club.kit ?? "#1C7F46")
            content.background {
                ZStack {
                    Color(hex: "#06110C")
                    RadialGradient(colors: [.white.opacity(0.10), .clear], center: UnitPoint(x: 0.05, y: -0.1), startRadius: 0, endRadius: 520)
                    RadialGradient(colors: [kit.opacity(0.32), .clear], center: UnitPoint(x: 0.98, y: -0.06), startRadius: 0, endRadius: 560)
                    RadialGradient(colors: [Color(hex: "#1C7F46").opacity(0.38), .clear], center: UnitPoint(x: 0.5, y: 1.2), startRadius: 0, endRadius: 700)
                }
                .ignoresSafeArea()
            }
        } else {
            content
        }
    }
}

// MARK: - fonts

/// The glass look's fonts ship inside the app (OFL; see Fonts/FONTS-LICENSE.txt), registered for this process only.
enum Fonts {
    static func register() {
        let urls = ["font-bricolage", "font-geist", "font-geist-mono", "font-doto"].compactMap {
            Bundle.main.url(forResource: $0, withExtension: "woff2")
        }
        guard !urls.isEmpty else { return }
        // the synchronous call, so the fonts exist before the first frame is drawn
        CTFontManagerRegisterFontsForURLs(urls as CFArray, .process, nil)
    }
}

/// A big number in the look's number face. In glass that's Doto, whose dotted full stop sits low and reads like a comma
/// ("£5,17m"), so the "." is drawn in Geist Mono and sits where a decimal point should.
struct NumberText: View {
    let text: String
    let size: CGFloat
    @Environment(\.theme) private var theme

    init(_ text: String, size: CGFloat) {
        self.text = text
        self.size = size
    }

    var body: some View {
        if theme.isGlass {
            let parts = text.split(separator: ".", omittingEmptySubsequences: false).map(String.init)
            parts.enumerated().reduce(Text("")) { acc, item in
                let piece = Text(item.element).font(theme.number(size))
                return item.offset == 0 ? acc + piece
                    : acc + Text(".").font(.custom("GeistMono-Bold", size: size * 0.9)) + piece
            }
            .monospacedDigit()
            .accessibilityLabel(text)
        } else {
            Text(text).font(theme.number(size)).monospacedDigit()
        }
    }
}
