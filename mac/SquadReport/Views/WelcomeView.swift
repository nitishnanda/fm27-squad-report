import SwiftUI
import UniformTypeIdentifiers

/// First launch: pick the project folder once. The app remembers it.
struct WelcomeView: View {
    @Environment(AppModel.self) private var model
    @State private var picking = false

    var body: some View {
        VStack(spacing: 18) {
            AppMark(size: 84)
            Text("Squad Report").font(.largeTitle.weight(.heavy))
            Text("Reads your newest FM27 save and shows your squad: best XIs, the positions that need work, how your tactic is going. It only ever reads your saves, never changes them.")
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
                .frame(maxWidth: 460)
            VStack(spacing: 8) {
                Button {
                    picking = true
                } label: {
                    Text("Choose your Squad Report folder…").frame(minWidth: 240)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .keyboardShortcut(.defaultAction)
                Text("It's the folder with **Run Squad Report.command** and **fm27_squad_report.py** in it. You only do this once.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 420)
            }
            if let problem = model.folderProblem {
                Label(problem, systemImage: "exclamationmark.triangle.fill")
                    .foregroundStyle(Palette.verdict("red"))
                    .frame(maxWidth: 460)
            }
        }
        .padding(48)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .fileImporter(isPresented: $picking, allowedContentTypes: [.folder]) { result in
            if case .success(let url) = result { model.choose(folder: url) }
        }
    }
}
