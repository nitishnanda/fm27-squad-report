import SwiftUI

/// Every status badge and the N/A/C/X letters in one place, like the web app's "Key" popover.
/// Built from the real `StatusBadge` and `FamiliarityBadge`, so the key always matches what the pages show.
struct StatusKey: View {
    private static let rows: [(PlayerStatus.Kind, String, String, String)] = [
        (.transferIn, "Transfer in", "", "a permanent move to your club is agreed"),
        (.transferOut, "Transfer out", "", "he's been sold"),
        (.loanIn, "Loan in", "", "here on loan from another club"),
        (.loanOut, "Loan out", "", "away on loan"),
        (.loanInArranged, "Loan in (arranged)", "", "loan agreed, not started yet (dashed)"),
        (.loanOutArranged, "Loan out (arranged)", "", "loan agreed, not started yet (dashed)"),
        (.injuredShort, "Injured", "under 4 wks", "back within four weeks"),
        (.injuredLong, "Injured", "4 wks +", "out for four weeks or more"),
        (.suspended, "Suspended", "", "banned for the next match or more"),
        (.expiring, "Contract", "ends ≤ 12 months", "contract ends within a year (dashed)"),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Key").font(.headline)
            Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 7) {
                ForEach(Self.rows, id: \.0.rawValue) { kind, label, brief, meaning in
                    GridRow {
                        StatusBadge(status: PlayerStatus(kind: kind, label: label, detail: meaning, brief: brief),
                                    showDetail: !brief.isEmpty)
                        Text(meaning).font(.callout).foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .accessibilityElement(children: .combine)
                }
            }
            Divider()
            Text("How well he knows a position").font(.subheadline.weight(.semibold))
            Grid(alignment: .leading, horizontalSpacing: 10, verticalSpacing: 6) {
                ForEach(["N", "A", "C", "X"], id: \.self) { code in
                    GridRow {
                        FamiliarityBadge(code: code)
                        Text(FamiliarityBadge.words(code)).font(.callout).foregroundStyle(.secondary)
                    }
                    .accessibilityElement(children: .combine)
                }
            }
            Divider()
            HStack(spacing: 6) {
                StarsView(value: 3.5, size: 11)
                Text("for your tactic or the position").font(.callout).foregroundStyle(.secondary)
            }
            HStack(spacing: 6) {
                StarsView(value: 3.5, size: 11, tint: Palette.potential)
                Text("potential (23 and under)").font(.callout).foregroundStyle(.secondary)
            }
        }
        .padding(16)
        .frame(width: 440)
    }
}

/// Help › Status Key: the key in its own small window, so it can stay open next to the report.
struct StatusKeyMenuButton: View {
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Button("Status Key") { openWindow(id: "key") }
            .keyboardShortcut("/", modifiers: .command)
    }
}
