import AppKit
import CoreText
import SwiftUI

/// The looks, the same six as the web app (`THEMES`), built from the web's tokens (`THEME_A`, `B_FRAME`…, `C_FRAME`…,
/// `THEME_D`, `E_GLASS`). A and D are light paper looks and stay light in dark mode; B, C and E are always dark.
enum Look: String, CaseIterable, Identifiable, Sendable {
    case original, programme, floodlit, scoreboard, sticker, glass
    var id: String { rawValue }

    var title: String {
        switch self {
        case .original: "Original"
        case .programme: "Matchday programme"
        case .floodlit: "Floodlit glass"
        case .scoreboard: "Scoreboard"
        case .sticker: "Sticker album"
        case .glass: "Glass + scoreboard"
        }
    }

    /// The web's one-liners, with its letters.
    var note: String {
        switch self {
        case .original: "The app's own design, light or dark with your Mac"
        case .programme: "A · Editorial: light paper, print rules, serif notes"
        case .floodlit: "B · Frosted panels over a night pitch"
        case .scoreboard: "C · Mono numbers, LED strips, one signal green"
        case .sticker: "D · Bold outlines, hard shadows, mown pitch"
        case .glass: "E · Glass frame, scoreboard data (B and C)"
        }
    }
}

struct Theme: Sendable {
    enum Panel: Sendable { case soft, glass, rule, board, sticker }
    enum Hero: Sendable { case kit, glass, paper, board, sticker }
    enum Page: Sendable { case plain, night, paper, board, mown }

    let look: Look
    /// The club colour dark enough for paper and white text (the web's `kit_on_light()`), for the light looks.
    var kitOnLight = Color(hex: "#1C7F46")

    static let original = Theme(look: .original)

    /// Frosted glass frame (B and E).
    var isGlass: Bool { look == .glass || look == .floodlit }
    var scheme: ColorScheme? {
        switch look {
        case .original: nil
        case .sticker: .light
        case .programme, .floodlit, .scoreboard, .glass: .dark   // the programme is printed on dark stock now
        }
    }
    var panelStyle: Panel {
        switch look {
        case .original: .soft
        case .floodlit, .glass: .glass
        case .programme: .rule
        case .scoreboard: .board
        case .sticker: .sticker
        }
    }
    var heroStyle: Hero {
        switch look {
        case .original: .kit
        case .floodlit, .glass: .glass
        case .programme: .paper
        case .scoreboard: .board
        case .sticker: .sticker
        }
    }
    var page: Page {
        switch look {
        case .original: .plain
        case .floodlit, .glass: .night
        case .programme: .paper
        case .scoreboard: .board
        case .sticker: .mown
        }
    }
    // MARK: type

    private enum Face {
        case system(width: Font.Width, italic: Bool)
        case custom([Font.Weight: String])
    }

    private static let bricolage: [Font.Weight: String] = [.regular: "BricolageGrotesque96ptExtraBold-Regular_Regular",
        .medium: "BricolageGrotesque96ptExtraBold-Regular_Medium", .semibold: "BricolageGrotesque96ptExtraBold-Regular_SemiBold",
        .bold: "BricolageGrotesque96ptExtraBold-Regular_Bold", .heavy: "BricolageGrotesque96ptExtraBold-Regular_ExtraBold",
        .black: "BricolageGrotesque96ptExtraBold-Regular_ExtraBold"]
    private static let hanken: [Font.Weight: String] = [.regular: "HankenGrotesk-Regular", .medium: "HankenGrotesk-Regular_Medium",
        .semibold: "HankenGrotesk-Regular_SemiBold", .bold: "HankenGrotesk-Regular_Bold", .heavy: "HankenGrotesk-Regular_ExtraBold",
        .black: "HankenGrotesk-Regular_Black"]
    private static let jetbrains: [Font.Weight: String] = [.regular: "JetBrainsMono-Regular", .medium: "JetBrainsMonoRoman-Medium",
        .semibold: "JetBrainsMonoRoman-Bold", .bold: "JetBrainsMonoRoman-Bold", .heavy: "JetBrainsMonoRoman-ExtraBold",
        .black: "JetBrainsMonoRoman-ExtraBold"]
    private static let geist: [Font.Weight: String] = [.regular: "Geist-Regular", .medium: "Geist-Medium", .semibold: "Geist-SemiBold",
        .bold: "Geist-Bold", .heavy: "Geist-ExtraBold", .black: "Geist-Black"]
    private static let geistMono: [Font.Weight: String] = [.regular: "GeistMono-Regular", .medium: "GeistMono-Medium",
        .semibold: "GeistMono-SemiBold", .bold: "GeistMono-SemiBold", .heavy: "GeistMono-Bold", .black: "GeistMono-Bold"]
    private static let doto: [Font.Weight: String] = [.regular: "Doto-Black_Bold", .bold: "Doto-Black_Bold", .heavy: "Doto-Black_Bold",
        .black: "Doto-Black_Bold"]
    private static let bigShoulders: [Font.Weight: String] = [.regular: "BigShoulders-Regular", .medium: "BigShoulders-Medium",
        .semibold: "BigShoulders-SemiBold", .bold: "BigShoulders-Bold", .heavy: "BigShoulders-ExtraBold", .black: "BigShoulders-Black"]
    private static let schibsted: [Font.Weight: String] = [.regular: "SchibstedGrotesk-Regular", .medium: "SchibstedGrotesk-Regular_Medium",
        .semibold: "SchibstedGrotesk-Regular_SemiBold", .bold: "SchibstedGrotesk-Regular_Bold", .heavy: "SchibstedGrotesk-Regular_ExtraBold",
        .black: "SchibstedGrotesk-Regular_Black"]
    private static let martian: [Font.Weight: String] = [.regular: "MartianMono-SemiExpandedRegular_Regular",
        .medium: "MartianMono-SemiExpandedRegular_Medium", .semibold: "MartianMono-SemiExpandedRegular_SemiBold",
        .bold: "MartianMono-SemiExpandedRegular_Bold", .heavy: "MartianMono-SemiExpandedRegular_ExtraBold",
        .black: "MartianMono-SemiExpandedRegular_ExtraBold"]

    private func font(_ face: Face, _ size: CGFloat, _ weight: Font.Weight) -> Font {
        switch face {
        case .system(let width, let italic):
            let f = Font.system(size: size, weight: weight).width(width)
            return italic ? f.italic() : f
        case .custom(let names):
            return .custom(names[weight] ?? names[.bold] ?? names.values.first!, size: size)
        }
    }

    private var displayFace: Face {
        switch look {
        case .original: .system(width: .condensed, italic: false)
        case .programme: .system(width: .expanded, italic: false)        // Archivo at 125% isn't bundled: the system face, expanded
        case .floodlit, .glass: .custom(Self.bricolage)
        case .scoreboard: .custom(Self.geist)
        case .sticker: .custom(Self.bigShoulders)
        }
    }
    private var numberFace: Face {
        switch look {
        case .original: .system(width: .condensed, italic: false)
        case .programme: .system(width: .condensed, italic: true)        // the web's italic 900 figures
        case .floodlit: .custom(Self.bricolage)
        case .scoreboard, .glass: .custom(Self.geistMono)      // crisp figures; the dot-matrix face is kept for the one big ordinal
        case .sticker: .custom(Self.bigShoulders)
        }
    }
    private var dataFace: Face? {
        switch look {
        case .original: nil
        case .programme: .custom(Self.martian)
        case .floodlit: .custom(Self.jetbrains)
        case .scoreboard, .glass: .custom(Self.geistMono)
        case .sticker: .custom(Self.schibsted)
        }
    }

    /// Section titles and headings.
    func display(_ size: CGFloat, _ weight: Font.Weight = .heavy) -> Font {
        // look A's headings are big and tight like the printed programme; the expanded face runs wide, so a touch smaller
        font(displayFace, look == .programme ? size * 0.9 : size, weight)
    }

    /// The club name in the hero.
    func hero(_ size: CGFloat) -> Font {
        switch look {
        case .original: .system(size: size, weight: .black).width(.compressed).italic()
        case .programme: .system(size: size * 0.86, weight: .heavy).width(.expanded)
        case .sticker: .custom("BigShouldersStencilDisplayThin-Black", size: size * 1.1)
        default: font(displayFace, size, .black)
        }
    }

    /// Big numbers: key figures, league position.
    func number(_ size: CGFloat) -> Font {
        switch look {
        case .original: .system(size: size, weight: .heavy).width(.condensed)
        case .programme: .system(size: size, weight: .black).width(.condensed).italic()
        case .sticker: font(numberFace, size * 1.12, .black)
        default: font(numberFace, size, .heavy)
        }
    }

    /// Big ordinal like "7th".
    func position(_ size: CGFloat) -> Font {
        switch look {
        case .original: .system(size: size, weight: .black).width(.compressed).italic()
        case .scoreboard, .glass: font(.custom(Self.doto), size, .heavy)
        default: number(size)
        }
    }

    /// Slot names on cards (LW, CB).
    func slot(_ size: CGFloat) -> Font {
        switch look {
        case .original, .programme: .system(size: size, weight: .heavy).width(.condensed).italic()
        case .sticker: font(numberFace, size * 1.15, .black)
        default: font(dataFace ?? displayFace, size * 0.8, .semibold)
        }
    }

    /// Small labels and data.
    func data(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        guard let face = dataFace else { return .system(size: size, weight: weight) }
        return font(face, look == .programme ? size * 0.88 : size, weight)   // Martian runs wide
    }

    /// Body text.
    var bodyFont: Font? {
        switch look {
        case .original, .programme: nil
        case .floodlit: .custom("HankenGrotesk-Regular", size: 13)
        case .scoreboard, .glass: .custom("Geist-Regular", size: 13)
        case .sticker: .custom("SchibstedGrotesk-Regular", size: 13)
        }
    }


    // MARK: colour

    var star: Color {
        switch look {
        case .original: Palette.star
        case .programme: Palette.star
        case .floodlit: Color(hex: "#F4C95D")
        case .scoreboard, .glass: Palette.star        // ratings are gold, never the "good" green (DESIGN.md)
        case .sticker: Color(hex: "#111111")
        }
    }
    var accent: Color {
        switch look {
        case .sticker: kitOnLight
        default: Palette.brandHigh
        }
    }
    var radius: CGFloat {
        switch panelStyle {
        case .soft: 10
        case .glass: 12
        case .rule: 0
        case .board: 10
        case .sticker: 12
        }
    }
    var pitchRadius: CGFloat {
        switch look {
        case .floodlit, .glass: 22
        case .programme: 0
        case .scoreboard: 10
        case .sticker: 14
        case .original: 10
        }
    }
    var pitchStripes: (Color, Color) {
        switch look {
        case .original: (Color(hex: "#22603A"), Color(hex: "#1C5432"))
        case .floodlit, .glass: (Color(hex: "#0F2B1B"), Color(hex: "#123220"))
        case .programme: (Color(hex: "#1B1B19"), Color(hex: "#171715"))       // a pitch printed on dark stock
        case .scoreboard: (Color(hex: "#0E1411"), Color(hex: "#0C120F"))
        case .sticker: (Color(hex: "#2E9A57"), Color(hex: "#27904F"))
        }
    }
    /// Lines on the pitch: dark ink on the paper pitch, white elsewhere.
    var pitchLine: Color {
        switch look {
        case .programme: Color(hex: "#EDEDE6").opacity(0.35)
        case .scoreboard: Color(hex: "#4FC77F").opacity(0.5)
        default: .white.opacity(0.28)
        }
    }
    var pitchEdge: Color {
        switch look {
        case .original: Color(hex: "#275A37")
        case .programme: Color(hex: "#3A3A36")
        case .scoreboard: DS.Surface.hairline
        case .sticker: Color(hex: "#111111")
        default: .white.opacity(0.1)
        }
    }
    var cardFill: Color {
        switch look {
        case .original: Color(hex: "#0E1512").opacity(0.94)
        case .floodlit, .glass: Color(hex: "#09160F").opacity(0.86)
        case .programme: Color(hex: "#202020")
        case .scoreboard: DS.Surface.panel
        case .sticker: Color(hex: "#111111")
        }
    }
}

extension EnvironmentValues {
    @Entry var theme: Theme = .original
}

// MARK: - applying it

/// Puts the chosen look on everything under it, with its own light or dark scheme.
struct Themed: ViewModifier {
    @AppStorage("look") private var lookName = Look.original.rawValue
    @Environment(AppModel.self) private var model: AppModel?
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func body(content: Content) -> some View {
        var theme = Theme(look: Look(rawValue: lookName) ?? .original)
        if let hex = model?.store.report?.club.kitOnLight { theme.kitOnLight = Color(hex: hex) }
        return content
            .environment(\.theme, theme)
            .tint(theme.accent)
            .preferredColorScheme(theme.scheme)
            .font(theme.bodyFont)
            .animation(reduceMotion ? nil : Motion.look, value: lookName)   // a new look fades in (also from ⌘L)
    }
}

/// ⌘L / ⇧⌘L: the next or previous look, like the web's L key.
enum LookCycle {
    @MainActor static func step(_ delta: Int) {
        let all = Look.allCases
        let now = Look(rawValue: UserDefaults.standard.string(forKey: "look") ?? "") ?? .original
        let i = all.firstIndex(of: now) ?? 0
        UserDefaults.standard.set(all[(i + delta + all.count) % all.count].rawValue, forKey: "look")
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
        switch theme.panelStyle {
        case .glass:
            let fill = LinearGradient(colors: [.white.opacity(0.06), .white.opacity(0.022)], startPoint: .top, endPoint: .bottom)
            if clip {
                content
                    .background(fill, in: shape)
                    .overlay(shape.strokeBorder(.white.opacity(0.11)).allowsHitTesting(false))
            } else {
                content.background(fill)
            }
        case .soft:
            if clip { content.background(.quaternary.opacity(0.45), in: shape) } else { content.background(.quaternary.opacity(0.45)) }
        case .rule:
            // the programme: no box, a printed rule across the top
            content.overlay(alignment: .top) { Rectangle().fill(Color(hex: "#EDEDE6").opacity(0.8)).frame(height: 1).allowsHitTesting(false) }
        case .board:
            let fill = DS.Surface.panel
            if clip {
                content.background(fill, in: shape).overlay(shape.strokeBorder(DS.Surface.hairline).allowsHitTesting(false))
            } else {
                content.background(fill)
            }
        case .sticker:
            if clip {
                content
                    .background(shape.fill(.white).shadow(color: Color(hex: "#111111"), radius: 0, x: 4, y: 4))
                    .overlay(shape.strokeBorder(Color(hex: "#111111"), lineWidth: 2).allowsHitTesting(false))
            } else {
                content.background(.white)
            }
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
        case .hero(let s): content.font(theme.hero(s)).tracking(theme.isGlass || theme.look == .programme ? -s * 0.035 : 0)
        case .slot(let s): content.font(theme.slot(s))
        case .data(let s, let w): content.font(theme.data(s, w))
        }
    }
}

private struct PageBackground: ViewModifier {
    @Environment(\.theme) private var theme
    @Environment(AppModel.self) private var model

    func body(content: Content) -> some View {
        switch theme.page {
        case .plain:
            content
        case .night:
            let kit = Color(hex: model.store.report?.club.kit ?? "#1C7F46")
            content.background {
                ZStack {
                    Color(hex: theme.look == .floodlit ? "#06120C" : "#06110C")
                    RadialGradient(colors: [.white.opacity(0.10), .clear], center: UnitPoint(x: 0.05, y: -0.1), startRadius: 0, endRadius: 520)
                    RadialGradient(colors: [kit.opacity(0.32), .clear], center: UnitPoint(x: 0.98, y: -0.06), startRadius: 0, endRadius: 560)
                    RadialGradient(colors: [Color(hex: "#1C7F46").opacity(0.38), .clear], center: UnitPoint(x: 0.5, y: 1.2), startRadius: 0, endRadius: 700)
                }
                .ignoresSafeArea()
            }
        case .paper:
            content.background(Color(hex: "#121211").ignoresSafeArea())   // dark newsprint
        case .board:
            content.background(DS.Surface.canvas.ignoresSafeArea())
        case .mown:
            // the sticker album: every page is a white sticker sheet laid on a mown pitch
            content
                .background(.white, in: RoundedRectangle(cornerRadius: DS.Radius.container, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: DS.Radius.container, style: .continuous).strokeBorder(Color(hex: "#111111"), lineWidth: 3).allowsHitTesting(false))
                .compositingGroup()
                .shadow(color: Color(hex: "#111111"), radius: 0, x: 8, y: 8)
                .padding(.init(top: 12, leading: 12, bottom: 20, trailing: 20))
                .background {
                    Canvas { ctx, size in
                        var x: CGFloat = 0, i = 0
                        while x < size.width {
                            ctx.fill(Path(CGRect(x: x, y: 0, width: 96, height: size.height)),
                                     with: .color(Color(hex: i.isMultiple(of: 2) ? "#1C7F46" : "#1A7541")))
                            x += 96; i += 1
                        }
                    }
                    .ignoresSafeArea()
                }
        }
    }
}

// MARK: - fonts

/// The looks' fonts ship inside the app (OFL; see Fonts/FONTS-LICENSE.txt), registered for this process only.
enum Fonts {
    static func register() {
        let urls = ["font-bricolage", "font-geist", "font-geist-mono", "font-doto", "font-newsreader", "font-newsreader-italic",
                    "font-martian-mono", "font-hanken", "font-jetbrains-mono", "font-big-shoulders", "font-big-shoulders-stencil",
                    "font-schibsted"].compactMap {
            Bundle.main.url(forResource: $0, withExtension: "woff2")
        }
        guard !urls.isEmpty else { return }
        // one synchronous call per font, so they exist before the first frame is drawn
        for url in urls { CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil) }
    }
}

/// A big number in the look's number face. In glass that's Doto, whose dotted full stop sits low and reads like a comma
/// ("£5,17m"), so the "." is drawn in Geist Mono and sits where a decimal point should.
struct NumberText: View {
    let text: String
    let size: CGFloat
    @Environment(\.theme) private var theme
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    init(_ text: String, size: CGFloat) {
        self.text = text
        self.size = size
    }

    var body: some View {
        Text(text).font(theme.number(size)).monospacedDigit()
            .contentTransition(.numericText())
            .animation(reduceMotion ? nil : Motion.filter, value: text)   // figures roll to their new value
    }
}
