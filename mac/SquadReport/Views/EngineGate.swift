import AppKit
import SwiftUI

/// What you see until the first report arrives: setup on the first run, then the same eight build steps the
/// web app's loader shows, then the report. Problems are said in plain words with a way out.
struct EngineGate: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        switch model.engine.phase {
        case .failed(let why):
            ProblemView(title: "The engine isn't running", message: why,
                        action: ("Try again", { model.retryEngine() }))
        case .preparing(let text):
            Working(title: "Setting up", detail: text,
                    note: "The app keeps its own copy of the save reader, so this only takes a while the first time.")
        case .restarting(let why):
            Working(title: "Restarting the engine", detail: why, note: nil)
        default:
            if let error = model.store.status?.error, !error.isEmpty, model.store.status?.building != true {
                ProblemView(title: "No report yet", message: plain(error))
            } else {
                Loader()
            }
        }
    }

    private func plain(_ error: String) -> String {
        if error.contains("no FM27 save found") {
            return "No FM27 save found yet. Save your game in FM27 and the report builds by itself."
        }
        return "Couldn't read your save: \(error). Save again in FM27 and the app will try again."
    }
}

private struct Working: View {
    let title: String
    let detail: String
    let note: String?

    var body: some View {
        VStack(spacing: 14) {
            AppMark(size: 56)
            Text(title).font(.title2.weight(.bold))
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text(detail).foregroundStyle(.secondary)
            }
            if let note { Text(note).font(.callout).foregroundStyle(.tertiary).multilineTextAlignment(.center) }
        }
        .frame(maxWidth: 460)
        .padding(40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// The eight build steps, ticked off as the engine reads the save, next to a pitch drawing itself in (the web's
/// `boot_html()`: lines draw in, a scan line sweeps while it waits, the current step spins, done steps tick).
private struct Loader: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        let status = model.store.status
        let steps = (status?.steps.isEmpty == false ? status?.steps : nil) ?? ReportStore.defaultSteps
        let current = status?.building == true ? max(0, status?.step ?? 0) : -1
        LoaderBody(steps: steps, current: current)
    }
}

struct LoaderBody: View {
    let steps: [String]
    let current: Int            // -1: the engine is still starting

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .center, spacing: 44) { LoaderPitch().frame(width: 220, height: 323); list }
            VStack(spacing: 24) { LoaderPitch().frame(width: 150, height: 220); list }
        }
        .padding(40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var list: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 14) {
                AppMark(size: 44)
                VStack(alignment: .leading, spacing: 2) {
                    Text(current >= 0 ? "Reading your save" : "Starting the engine").displayFont(24)
                    Text(current >= 0 ? "Takes about half a minute. Your save is only read, never changed."
                                      : "Getting the save reader going…")
                        .foregroundStyle(.secondary)
                }
            }
            ProgressView(value: Double(max(current, 0) + (current >= 0 ? 1 : 0)), total: Double(steps.count))
                .tint(Palette.brand)
                .animation(.easeOut(duration: 0.4 * Motion.slow), value: current)
            VStack(alignment: .leading, spacing: 9) {
                ForEach(Array(steps.enumerated()), id: \.offset) { i, label in
                    let state: StepMark.State = current < 0 || i > current ? .todo : i < current ? .done : .now
                    HStack(spacing: 10) {
                        StepMark(state: state).frame(width: 18, height: 18).accessibilityHidden(true)
                        Text(label).foregroundStyle(i == current ? .primary : .secondary)
                            .fontWeight(i == current ? .semibold : .regular)
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityValue(state == .done ? "done" : state == .now ? "in progress" : "to do")
                }
            }
        }
        .frame(maxWidth: 400)
    }
}

/// To do: a hollow circle. Now: an arc spinning round it. Done: a tick that pops in.
private struct StepMark: View {
    enum State { case todo, now, done }
    let state: State
    @State private var spin = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.theme) private var theme

    var body: some View {
        ZStack {
            Circle().stroke(Color.secondary.opacity(0.35), lineWidth: 1.5)
            switch state {
            case .todo:
                EmptyView()
            case .now:
                Circle().trim(from: 0, to: 0.28)
                    .stroke(theme.accent, style: StrokeStyle(lineWidth: 2.2, lineCap: .round))
                    .rotationEffect(.degrees(spin ? 360 : 0))
                    .onAppear {
                        guard !reduceMotion else { return }
                        withAnimation(.linear(duration: 0.9 * Motion.slow).repeatForever(autoreverses: false)) { spin = true }
                    }
            case .done:
                Image(systemName: "checkmark.circle.fill").resizable().foregroundStyle(Palette.brandHigh)
                    .transition(reduceMotion ? .identity : .scale(scale: 0.4).combined(with: .opacity))
            }
        }
        .animation(.spring(duration: 0.35 * Motion.slow, bounce: 0.4), value: state)
    }
}

/// The pitch, in the look's colours: its lines draw themselves in, then a scan line sweeps down it while it waits.
private struct LoaderPitch: View {
    @State private var drawn: CGFloat = 0
    @State private var scan = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.theme) private var theme

    var body: some View {
        let (a, b) = theme.pitchStripes
        GeometryReader { geo in
            ZStack(alignment: .top) {
                VStack(spacing: 0) {
                    ForEach(0..<10, id: \.self) { i in (i.isMultiple(of: 2) ? a : b) }
                }
                PitchLines()
                    .trim(from: 0, to: reduceMotion ? 1 : drawn)
                    .stroke(theme.pitchLine.opacity(1.6), style: StrokeStyle(lineWidth: 1.6, lineCap: .round, lineJoin: .round))
                if !reduceMotion {
                    LinearGradient(colors: [.clear, Palette.brandHigh.opacity(0.35), .clear], startPoint: .top, endPoint: .bottom)
                        .frame(height: 46)
                        .offset(y: scan ? geo.size.height : -46)
                        .blendMode(.plusLighter)
                }
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: theme.pitchRadius, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: theme.pitchRadius, style: .continuous).stroke(theme.pitchEdge))
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 1.4 * Motion.slow)) { drawn = 1 }
            withAnimation(.linear(duration: 2.4 * Motion.slow).delay(1.2 * Motion.slow).repeatForever(autoreverses: false)) { scan = true }
        }
        .accessibilityHidden(true)
    }
}

/// The pitch's markings as one path, so `.trim` draws them in one stroke after another.
private struct PitchLines: Shape {
    func path(in r: CGRect) -> Path {
        let w = r.width, h = r.height, inset = w * 0.06
        var p = Path()
        p.addRect(CGRect(x: inset, y: inset, width: w - inset * 2, height: h - inset * 2))
        p.move(to: CGPoint(x: inset, y: h / 2)); p.addLine(to: CGPoint(x: w - inset, y: h / 2))
        p.addEllipse(in: CGRect(x: w / 2 - w * 0.14, y: h / 2 - w * 0.14, width: w * 0.28, height: w * 0.28))
        p.addRect(CGRect(x: w * 0.22, y: inset, width: w * 0.56, height: h * 0.15))
        p.addRect(CGRect(x: w * 0.22, y: h - inset - h * 0.15, width: w * 0.56, height: h * 0.15))
        p.addRect(CGRect(x: w * 0.37, y: inset, width: w * 0.26, height: h * 0.055))
        p.addRect(CGRect(x: w * 0.37, y: h - inset - h * 0.055, width: w * 0.26, height: h * 0.055))
        return p
    }
}

/// When the first report arrives: a club-colour panel with the club's name slides up and away (the web's launch wipe).
struct ClubWipe: View {
    let club: Club
    let done: () -> Void
    @State private var gone = false

    var body: some View {
        GeometryReader { geo in
            ZStack {
                Color(hex: club.kit)
                Text(club.name.uppercased()).heroFont(56).foregroundStyle(Color(hex: club.ink))
                    .opacity(gone ? 0 : 1)
            }
            .offset(y: gone ? -geo.size.height : 0)
        }
        .ignoresSafeArea()
        .allowsHitTesting(false)
        .task {
            // hold a moment on the club colour, slide it up and away, then take the panel out
            try? await Task.sleep(for: .seconds(0.35 * Motion.slow))
            withAnimation(.easeInOut(duration: 0.6 * Motion.slow)) { gone = true }
            try? await Task.sleep(for: .seconds(0.65 * Motion.slow))
            done()
        }
    }
}

/// The app's mark: the tactics-board logo on pitch green.
struct AppMark: View {
    var size: CGFloat

    var body: some View {
        Image(nsImage: NSApplication.shared.applicationIconImage)
            .resizable()
            .frame(width: size, height: size)
            .clipShape(RoundedRectangle(cornerRadius: size * 0.22, style: .continuous))
            .accessibilityHidden(true)
    }
}
