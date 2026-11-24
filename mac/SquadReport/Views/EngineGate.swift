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

/// The eight build steps, ticked off as the engine reads the save.
private struct Loader: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        let status = model.store.status
        let steps = (status?.steps.isEmpty == false ? status?.steps : nil) ?? ReportStore.defaultSteps
        let current = status?.building == true ? max(0, status?.step ?? 0) : -1
        VStack(alignment: .leading, spacing: 18) {
            HStack(spacing: 14) {
                AppMark(size: 44)
                VStack(alignment: .leading, spacing: 2) {
                    Text(current >= 0 ? "Reading your save" : "Starting the engine").font(.title2.weight(.bold))
                    Text(current >= 0 ? "Takes about half a minute. Your save is only read, never changed."
                                      : "Getting the save reader going…")
                        .foregroundStyle(.secondary)
                }
            }
            ProgressView(value: Double(max(current, 0) + (current >= 0 ? 1 : 0)), total: Double(steps.count))
                .tint(Palette.brand)
            VStack(alignment: .leading, spacing: 9) {
                ForEach(Array(steps.enumerated()), id: \.offset) { i, label in
                    HStack(spacing: 10) {
                        Group {
                            if current < 0 || i > current {
                                Image(systemName: "circle").foregroundStyle(.tertiary)
                            } else if i < current {
                                Image(systemName: "checkmark.circle.fill").foregroundStyle(Palette.brandHigh)
                            } else {
                                ProgressView().controlSize(.small)
                            }
                        }
                        .frame(width: 18)
                        .accessibilityHidden(true)
                        Text(label).foregroundStyle(i == current ? .primary : .secondary)
                            .accessibilityValue(current < 0 || i > current ? "to do" : i < current ? "done" : "in progress")
                            .fontWeight(i == current ? .semibold : .regular)
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityValue(i < current ? "done" : i == current ? "in progress" : "to do")
                }
            }
        }
        .frame(maxWidth: 420)
        .padding(40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
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
