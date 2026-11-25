import SwiftUI

/// The web app's fake-3D pitch (`pitch3d()`): the pitch lies tilted back and turned, and every player card stands up
/// on its spot facing you. Drag (or the arrow keys) to turn and tilt it, within the web's limits; it sways slowly
/// until you touch it. With Reduce Motion on it lies flat and still.
struct Pitch3D: View {
    let report: Report
    let xi: [XISlot]
    /// The Home hero's copy: same pitch, smaller cards, no pop-up player cards.
    var compact = false

    @State private var turn: Double = -14          // web --rz
    @State private var tilt: Double           // web --rx (54)
    @State private var dragFrom: (turn: Double, tilt: Double)?
    @State private var touched = false             // the sway stops for good once he moves it
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.theme) private var theme

    init(report: Report, xi: [XISlot], compact: Bool = false, startTilt: Double = 54) {
        self.report = report
        self.xi = xi
        self.compact = compact
        _tilt = State(initialValue: startTilt)
    }

    static let turnRange: ClosedRange<Double> = -55...55
    static let tiltRange: ClosedRange<Double> = 24...70

    var body: some View {
        let still = reduceMotion || touched
        TimelineView(.animation(minimumInterval: 1.0 / 30, paused: still)) { timeline in
            // the web's sway: --rz goes to base + 9° and back over 5.5 s each way, eased
            let t = timeline.date.timeIntervalSinceReferenceDate
            let sway = still ? 0 : 4.5 - 4.5 * cos(t * .pi / 5.5)
            GeometryReader { geo in
                let cam = PitchCamera(turn: reduceMotion ? 0 : turn + sway, tilt: reduceMotion ? 0 : tilt,
                                      fitTurn: reduceMotion ? 0 : turn, size: geo.size, cardRoom: compact ? 40 : 58)
                ZStack {
                    Canvas { ctx, _ in cam.draw(in: &ctx, stripes: theme.pitchStripes, line: theme.pitchLine) }
                    ForEach(cam.backToFront(report.formation.rows), id: \.self) { i in
                        let row = report.formation.rows[i]
                        let spot = cam.project(xPercent: row.x ?? 50, yPercent: row.y ?? 50)
                        let player = report.player(i < xi.count ? xi[i].uid : nil)
                        let scale = spot.depth * cam.fit * (compact ? 0.85 : 0.9)
                        Ellipse().fill(.black.opacity(0.35))
                            .frame(width: 46 * scale, height: 12 * scale)
                            .position(x: spot.x, y: spot.y)
                        PitchPlayer(report: report, row: i, rowInfo: row, player: player, interactive: !compact)
                            .scaleEffect(scale, anchor: .bottom)
                            .position(x: spot.x, y: spot.y - 30)   // stands on its spot
                    }
                }
            }
        }
        .contentShape(Rectangle())
        .gesture(reduceMotion ? nil : drag)
        .focusable(!reduceMotion)
        .focusEffectDisabled()
        .onKeyPress(keys: [.leftArrow, .rightArrow, .upArrow, .downArrow]) { press in
            guard !reduceMotion else { return .ignored }
            touched = true
            withAnimation(.snappy) {
                switch press.key {
                case .leftArrow: turn = (turn - 6).clamped(to: Self.turnRange)
                case .rightArrow: turn = (turn + 6).clamped(to: Self.turnRange)
                case .upArrow: tilt = (tilt + 5).clamped(to: Self.tiltRange)
                default: tilt = (tilt - 5).clamped(to: Self.tiltRange)
                }
            }
            return .handled
        }
        .accessibilityElement(children: compact ? .ignore : .contain)
        .accessibilityLabel("Your XI on a 3D pitch. Drag or use the arrow keys to turn it.")
        .help(reduceMotion ? "" : "Drag to turn and tilt the pitch")
    }

    private var drag: some Gesture {
        DragGesture(minimumDistance: 3)
            .onChanged { g in
                if dragFrom == nil { dragFrom = (turn, tilt); touched = true }
                guard let from = dragFrom else { return }
                turn = (from.turn + g.translation.width * 0.3).clamped(to: Self.turnRange)
                tilt = (from.tilt - g.translation.height * 0.25).clamped(to: Self.tiltRange)
            }
            .onEnded { _ in dragFrom = nil }
    }
}

/// Turns pitch coordinates into screen points the way CSS does for the web pitch:
/// rotateZ(turn) on the pitch, then rotateX(tilt), seen through a 1500 pt perspective, scaled to fit.
struct PitchCamera {
    let turn: Double
    let tilt: Double
    /// The angle the size is worked out from: the resting turn without the sway, so the pitch doesn't pulse.
    let fitTurn: Double
    let size: CGSize
    let cardRoom: CGFloat

    // the pitch in its own units: 68 wide for every 100 long, like the flat one
    static let width: Double = 380
    static let length: Double = 380 / 0.68
    static let perspective: Double = 1500

    struct Spot { let x: CGFloat; let y: CGFloat; let z: Double; let depth: Double }

    /// Rotated and seen in perspective, before fitting: (x, y, z, depth).
    private static func raw(_ px: Double, _ py: Double, turn: Double, tilt: Double) -> (Double, Double, Double, Double) {
        let a = turn * .pi / 180, b = tilt * .pi / 180
        let x1 = px * cos(a) - py * sin(a)
        let y1 = px * sin(a) + py * cos(a)
        let y2 = y1 * cos(b)
        let z2 = y1 * sin(b)                         // negative = further away (the top of the pitch)
        let depth = perspective / (perspective - z2)
        return (x1 * depth, y2 * depth, z2, depth)
    }

    /// Scale and offset that fit the pitch's four corners (at the resting angle), with room above for the cards.
    var frame: (scale: Double, dx: Double, dy: Double) {
        let corners = [(-1.0, -1.0), (1, -1), (1, 1), (-1, 1)].map {
            Self.raw($0.0 * Self.width / 2, $0.1 * Self.length / 2, turn: fitTurn, tilt: tilt)
        }
        let xs = corners.map(\.0), ys = corners.map(\.1)
        let w = xs.max()! - xs.min()!, h = ys.max()! - ys.min()!
        let room = Double(cardRoom)
        let scale = max(0.2, min(size.width / w, (size.height - room) / h) * 0.94)
        let dx = size.width / 2 - scale * (xs.max()! + xs.min()!) / 2
        let dy = room + (size.height - room) / 2 - scale * (ys.max()! + ys.min()!) / 2
        return (scale, dx, dy)
    }

    var fit: Double { frame.scale }

    /// A point on the pitch (pitch units, centre = 0) to the screen.
    func project(_ px: Double, _ py: Double) -> Spot {
        let (x, y, z, depth) = Self.raw(px, py, turn: turn, tilt: tilt)
        let f = frame
        return Spot(x: f.dx + x * f.scale, y: f.dy + y * f.scale, z: z, depth: depth)
    }

    func project(xPercent: Double, yPercent: Double) -> Spot {
        project((xPercent / 100 - 0.5) * Self.width, (yPercent / 100 - 0.5) * Self.length)
    }

    /// Row indices sorted so nearer cards are drawn over farther ones.
    func backToFront(_ rows: [Formation.Row]) -> [Int] {
        rows.indices.sorted { project(xPercent: rows[$0].x ?? 50, yPercent: rows[$0].y ?? 50).z
            < project(xPercent: rows[$1].x ?? 50, yPercent: rows[$1].y ?? 50).z }
    }

    private func point(_ fx: Double, _ fy: Double) -> CGPoint {
        let s = project((fx - 0.5) * Self.width, (fy - 0.5) * Self.length)
        return CGPoint(x: s.x, y: s.y)
    }

    private func quad(_ x0: Double, _ y0: Double, _ x1: Double, _ y1: Double) -> Path {
        var p = Path()
        p.move(to: point(x0, y0)); p.addLine(to: point(x1, y0)); p.addLine(to: point(x1, y1)); p.addLine(to: point(x0, y1))
        p.closeSubpath()
        return p
    }

    /// Mown stripes, then the same markings as the flat pitch (fractions of width and length).
    func draw(in ctx: inout GraphicsContext, stripes: (Color, Color), line: Color) {
        for i in 0..<10 {
            ctx.fill(quad(0, Double(i) / 10, 1, Double(i + 1) / 10), with: .color(i.isMultiple(of: 2) ? stripes.0 : stripes.1))
        }
        let inset = 0.04, insetY = 0.04 * 0.68
        var lines = quad(inset, insetY, 1 - inset, 1 - insetY)
        lines.move(to: point(inset, 0.5)); lines.addLine(to: point(1 - inset, 0.5))
        lines.addPath(quad(0.22, insetY, 0.78, insetY + 0.14))
        lines.addPath(quad(0.22, 1 - insetY - 0.14, 0.78, 1 - insetY))
        lines.addPath(quad(0.36, insetY, 0.64, insetY + 0.05))
        lines.addPath(quad(0.36, 1 - insetY - 0.05, 0.64, 1 - insetY))
        // centre circle: radius 13% of the width
        let r = 0.13
        for k in 0...48 {
            let a = Double(k) / 48 * 2 * .pi
            let p = point(0.5 + r * cos(a), 0.5 + r * sin(a) * 0.68)
            if k == 0 { lines.move(to: p) } else { lines.addLine(to: p) }
        }
        ctx.stroke(lines, with: .color(line), lineWidth: 1.4)
        ctx.stroke(quad(0, 0, 1, 1), with: .color(.white.opacity(0.10)), lineWidth: 1)
    }
}

extension Comparable {
    func clamped(to range: ClosedRange<Self>) -> Self { min(max(self, range.lowerBound), range.upperBound) }
}
