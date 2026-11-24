import SwiftUI

/// The app's motion in one place (Phase 7): quick and subtle, and nothing at all with Reduce Motion on.
/// `-slowMotion 8` as a launch argument stretches every duration, to check the motion frame by frame.
enum Motion {
    static var slow: Double {
        let v = UserDefaults.standard.double(forKey: "slowMotion")
        return v > 0 ? v : 1
    }

    /// A new page fades in and rises a little (the web's show(): 14 px over 0.38 s; calmer here).
    static var page: Animation { .easeOut(duration: 0.25 * slow) }
    static let pageRise: CGFloat = 10
    /// Filters: rows move instead of jumping.
    static var filter: Animation { .snappy(duration: 0.3 * slow) }
    /// Changing looks fades instead of snapping.
    static var look: Animation { .easeInOut(duration: 0.3 * slow) }
}

/// A new page fades in and rises a little as it appears. Done on appear, not as a transition, so the old page
/// never lingers on top while the new one comes in.
struct PageEntrance: ViewModifier {
    @State private var shown = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func body(content: Content) -> some View {
        let on = shown || reduceMotion
        content
            .opacity(on ? 1 : 0)
            .offset(y: on ? 0 : Motion.pageRise)
            .onAppear { withAnimation(Motion.page) { shown = true } }
    }
}
