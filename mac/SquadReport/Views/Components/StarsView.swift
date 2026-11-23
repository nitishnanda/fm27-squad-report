import SwiftUI

/// Five stars filled to the nearest half star, like the web app. Read out as "4.5 stars".
struct StarsView: View {
    let value: Double
    var size: CGFloat = 11
    var tint: Color = Palette.star

    var body: some View {
        let shown = Fmt.half(min(5, max(0, value)))
        row(Palette.starEmpty)
            .overlay(alignment: .leading) {
                row(tint).mask(alignment: .leading) {
                    GeometryReader { geo in
                        Rectangle().frame(width: geo.size.width * shown / 5)
                    }
                }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(Fmt.stars(shown)) stars")
            .help("\(Fmt.stars(shown)) stars")
    }

    private func row(_ color: Color) -> some View {
        HStack(spacing: 0) {
            ForEach(0..<5, id: \.self) { _ in Image(systemName: "star.fill") }
        }
        .font(.system(size: size))
        .foregroundStyle(color)
    }
}

/// N natural · A accomplished, the same little badge as the web app.
struct FamiliarityBadge: View {
    let code: String

    var body: some View {
        Text(code)
            .font(.system(size: 9, weight: .heavy))
            .frame(width: 14, height: 14)
            .foregroundStyle(code == "N" ? Color(nsColor: .windowBackgroundColor) : .primary)
            .background(code == "N" ? Color.primary : .clear, in: RoundedRectangle(cornerRadius: 3))
            .overlay(RoundedRectangle(cornerRadius: 3).stroke(Color.primary.opacity(code == "N" ? 0 : 0.5), lineWidth: 1))
            .help(code == "N" ? "Natural in this position" : code == "A" ? "Accomplished in this position" : "Can play here")
            .accessibilityLabel(code == "N" ? "natural" : code == "A" ? "accomplished" : "can play")
    }
}
