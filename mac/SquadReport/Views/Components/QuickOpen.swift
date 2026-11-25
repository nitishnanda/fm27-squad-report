import AppKit
import SwiftUI

/// ⌘K: type a page, a player or an action. Players show only what the lists already show (age, positions, stars).
struct QuickOpen: View {
    @Environment(AppModel.self) private var model
    @Environment(\.openWindow) private var openWindow
    @Environment(\.dismiss) private var dismiss
    @State private var query = ""
    @State private var picked = 0
    @FocusState private var focused: Bool

    private struct Item: Identifiable {
        let id: String
        let group: String
        let title: String
        let detail: String
        let symbol: String
        let run: @MainActor () -> Void
    }

    var body: some View {
        let items = results
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass").foregroundStyle(.secondary)
                TextField("Search pages, players and actions", text: $query)
                    .textFieldStyle(.plain)
                    .font(.title3)
                    .focused($focused)
                    .onSubmit { run(items) }
            }
            .padding(14)
            Divider()
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 0) {
                        ForEach(Array(items.enumerated()), id: \.element.id) { i, item in
                            if i == 0 || items[i - 1].group != item.group {
                                Text(item.group).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                                    .padding(.horizontal, 14).padding(.top, 10).padding(.bottom, 2)
                            }
                            row(item, selected: i == picked)
                                .id(item.id)
                                .onTapGesture { picked = i; run(items) }
                        }
                        if items.isEmpty {
                            Text("Nothing matches \"\(query)\".").foregroundStyle(.secondary).padding(14)
                        }
                    }
                    .padding(.vertical, 4)
                }
                .onChange(of: picked) { _, now in if now < items.count { proxy.scrollTo(items[now].id) } }
            }
            Divider()
            Text("↑↓ to move · Return to open · Esc to close")
                .font(.caption).foregroundStyle(.secondary)
                .padding(.horizontal, 14).padding(.vertical, 7)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(width: 520, height: 420)
        .onAppear { focused = true }
        .onChange(of: query) { picked = 0 }
        .onKeyPress(.downArrow) { picked = min(picked + 1, max(items.count - 1, 0)); return .handled }
        .onKeyPress(.upArrow) { picked = max(picked - 1, 0); return .handled }
    }

    private func row(_ item: Item, selected: Bool) -> some View {
        HStack(spacing: 10) {
            Image(systemName: item.symbol).frame(width: 18).foregroundStyle(selected ? .white : .secondary)
            Text(item.title).fontWeight(.medium)
            Spacer(minLength: 8)
            Text(item.detail).font(.callout).foregroundStyle(selected ? Color.white.opacity(0.85) : .secondary)
        }
        .foregroundStyle(selected ? .white : .primary)
        .padding(.horizontal, 10).padding(.vertical, 6)
        .background(selected ? AnyShapeStyle(.tint) : AnyShapeStyle(.clear), in: RoundedRectangle(cornerRadius: 6))
        .padding(.horizontal, 6)
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func run(_ items: [Item]) {
        guard picked < items.count else { return }
        let item = items[picked]
        dismiss()
        item.run()
    }

    // MARK: - what the search finds

    private func fold(_ s: String) -> String {
        s.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .current)
    }

    private var results: [Item] {
        let q = fold(query.trimmingCharacters(in: .whitespaces))
        var out: [Item] = []

        if !q.isEmpty, let report = model.store.report {
            let found = report.players
                .filter { $0.location != "target" && fold($0.name).contains(q) }
                .sorted { fold($0.name).hasPrefix(q) && !fold($1.name).hasPrefix(q) }
                .prefix(6)
            for p in found {
                var bits = [p.positions.natural.first, p.age.map(String.init)].compactMap { $0 }
                if let best = p.best { bits.append("\(Fmt.stars(best.stars))★") }
                if p.youth { bits.append("youth") }
                out.append(Item(id: "p\(p.uid)", group: "Players", title: p.name, detail: bits.joined(separator: " · "),
                                symbol: "person") { [model] in model.inspect(p.uid) })
            }
        }

        for route in Route.allCases where q.isEmpty || fold(route.title).contains(q) || fold(route.section.title).contains(q) {
            out.append(Item(id: "r\(route.rawValue)", group: "Pages", title: route.title, detail: route.section.title,
                            symbol: route.symbol) { [model] in model.go(route) })
        }

        let actions: [(String, String, String, @MainActor () -> Void)] = [
            ("Reload Report", "⌘R", "arrow.clockwise", { [model] in model.store.reload() }),
            ("Open Matchday Window", "⇧⌘M", "pin", { [openWindow] in openWindow(id: "matchday") }),
            ("Next Look", "⌘L", "paintpalette", { LookCycle.step(1) }),
            ("Open in Browser", "⇧⌘O", "safari", { [model] in model.openInBrowser() }),
            ("Settings…", "⌘,", "gearshape", { NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil) }),
        ]
        for (title, keys, symbol, run) in actions where q.isEmpty || fold(title).contains(q) {
            out.append(Item(id: "a\(title)", group: "Actions", title: title, detail: keys, symbol: symbol, run: run))
        }
        return out
    }
}
