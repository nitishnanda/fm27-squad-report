import SwiftUI

/// Sandbox: try line-ups before you make them. Drag players onto the pitch (or click a slot to pick), mark people
/// injured, gone or away, sign scouting targets, and see how your XI compares with the best one.
struct SandboxView: View {
    let report: Report
    @State private var model: SandboxModel?

    var body: some View {
        Group {
            if let model { SandboxPage(model: model) } else { ProgressView() }
        }
        .onAppear { if model == nil { model = SandboxModel(report: report) } }
        .onChange(of: report.saveName) { _, _ in model = SandboxModel(report: report) }
        .onChange(of: report.players.count + report.targets.count) { _, _ in model = SandboxModel(report: report) }
    }
}

private struct SandboxPage: View {
    @Bindable var model: SandboxModel
    @State private var area = CGSize(width: 1100, height: 700)

    /// Side by side needs a pitch at least this wide, or the cards get too small to read.
    static let minPitch: CGFloat = 380
    static let rosterWidth: CGFloat = 420

    var body: some View {
        // Laid out from his Figma Make design (SandboxView.tsx): the score bar in a card, then the pitch and the squad
        // side by side, each in its own card. The pitch is 68 wide for every 100 tall, so a short window shrinks it too.
        let sideBySidePitch = min(area.width - Self.rosterWidth - 16 - 40, (area.height - 40) * 0.68)
        VStack(spacing: 16) {
            ScoreBar(model: model)
            Group {
                if sideBySidePitch >= Self.minPitch {
                    HStack(alignment: .top, spacing: 16) {
                        SandboxPitch(model: model)
                            .frame(width: sideBySidePitch)
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                            .hubCard()
                        Roster(model: model, stacked: false)
                            .frame(width: Self.rosterWidth)
                            .frame(maxHeight: .infinity)
                            .hubCard()
                    }
                } else {
                    // small window: the pitch at a readable size, the squad underneath, one scroll for both
                    ScrollView {
                        VStack(spacing: 16) {
                            SandboxPitch(model: model)
                                .frame(width: min(area.width - 40, 520))
                                .frame(maxWidth: .infinity)
                                .hubCard()
                            Roster(model: model, stacked: true).hubCard()
                        }
                    }
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .onGeometryChange(for: CGSize.self) { $0.size } action: { area = $0 }
        }
        .frame(maxWidth: 1172)
        .padding(.horizontal, 24).padding(.vertical, 20)
        .frame(maxWidth: .infinity)
    }
}

// MARK: - score bar

private struct ScoreBar: View {
    let model: SandboxModel

    var body: some View {
        let level = model.report.xiLevel ?? 0
        let avg = model.average
        let diff = ((avg - level) * 10).rounded() / 10 + 0.0    // + 0.0 turns -0.0 into 0.0
        let score = VStack(alignment: .leading, spacing: 2) {
            Text("Your XI level").font(.system(size: 11, weight: .medium)).foregroundStyle(.secondary)
            HStack(spacing: 8) {
                StarsView(value: avg, size: 14)
                NumberText(String(format: "%.1f", avg), size: 22)
            }
            Text("\(diff >= 0 ? "+" : "")\(String(format: "%.1f", diff))★ vs best XI \(String(format: "%.1f", level))★ · \(model.changes) change\(model.changes == 1 ? "" : "s")")
                .font(.system(size: 11)).monospacedDigit().foregroundStyle(.tertiary)
        }
        .fixedSize()
        let notes = VStack(alignment: .leading, spacing: 3) {
            if model.emptySlots > 0 {
                Text("\(model.emptySlots) empty slot\(model.emptySlots == 1 ? "" : "s")").foregroundStyle(Palette.injuryLong).fontWeight(.semibold)
            }
            if !model.outOfPosition.isEmpty { Text("Playing out of position: \(model.outOfPosition.joined(separator: ", "))") }
            if !model.ruledOut.isEmpty { Text("Ruled out: \(model.ruledOut.joined(separator: ", "))") }
            if !model.signed.isEmpty { Text("Signed: \(model.signed.joined(separator: ", "))").foregroundStyle(Palette.star) }
            if model.emptySlots == 0 && model.outOfPosition.isEmpty && model.ruledOut.isEmpty && model.signed.isEmpty {
                Text("Full-strength XI. Change someone's status, or drag a player onto the pitch.").foregroundStyle(.secondary)
            }
        }
        .font(.system(size: 12.5))
        .foregroundStyle(.secondary)
        .lineLimit(2)
        .frame(minWidth: 200, idealWidth: 300, maxWidth: .infinity, alignment: .leading)
        let buttons = HStack(spacing: 8) {
            Text(model.auto ? "auto-picking" : "your own picks").font(.system(size: 11)).foregroundStyle(.tertiary)
            // the design's two capsules: auto-pick in signal green, reset neutral
            CapsuleAction(title: "Auto-pick best XI", symbol: "wand.and.stars") { withAnimation(.snappy) { model.autoPick() } }
                .background(Palette.brandHigh.opacity(0.16), in: Capsule())
            CapsuleAction(title: "Reset", symbol: "arrow.counterclockwise", tint: .secondary) { withAnimation(.snappy) { model.reset() } }
                .help("Reset all changes")
        }
        .fixedSize()
        // one row on a wide window; on a narrow one the notes drop under the score
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .center, spacing: 20) {
                score
                Rectangle().fill(Color.primary.opacity(0.08)).frame(width: 1, height: 36)
                notes
                buttons
            }
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .center, spacing: 16) { score; Spacer(minLength: 0); buttons }
                notes
            }
        }
        .padding(16)
        .hubCard()
        .accessibilityElement(children: .contain)
    }
}

// MARK: - the pitch

private struct SandboxPitch: View {
    let model: SandboxModel

    var body: some View {
        Pitch { size in
            ForEach(model.rows.indices, id: \.self) { i in
                SlotCard(model: model, row: i)
                    .scaleEffect(min(1, size.width / 470))
                    .position(x: size.width * (model.rows[i].x ?? 50) / 100, y: size.height * (model.rows[i].y ?? 50) / 100)
            }
        }
        .padding(20)
    }
}

/// One slot: drop a player on it, drag him off it, or click it to pick from a list.
private struct SlotCard: View {
    let model: SandboxModel
    let row: Int
    @State private var targeted = false
    @Environment(\.theme) private var theme

    var body: some View {
        let info = model.rows[row]
        let uid = model.lineup.indices.contains(row) ? model.lineup[row] : nil
        let player = model.player(uid)
        let rating = model.rating(uid, row: row)
        let best = model.bestStars.indices.contains(row) ? model.bestStars[row] : 0
        let delta = Fmt.half(rating?.stars ?? 0) - Fmt.half(best)
        Menu {
            choices(info)
        } label: {
            VStack(spacing: 3) {
                Text(info.label ?? info.slot)
                    .font(.system(size: 11, weight: .heavy).width(.condensed).italic())
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity).padding(.vertical, 2)
                    .background(Color(hex: model.report.club.kit))
                Text(player.map { surname($0.name) } ?? "Empty")
                    .font(.system(size: 12.5, weight: .semibold))
                    .foregroundStyle(player == nil ? Palette.injuryLong : .white)
                    .lineLimit(1).minimumScaleFactor(0.75)
                    .padding(.horizontal, 6)
                HStack(spacing: 3) {
                    if let rating {
                        StarsView(value: rating.stars, size: 9)
                        FamiliarityBadge(code: rating.fam).colorScheme(.dark)
                    }
                    if delta != 0 {   // only when it differs from your best XI in this slot
                        Text("\(delta > 0 ? "↑" : "↓")\(Fmt.stars(abs(delta)))★")
                            .font(.system(size: 9, weight: .heavy))
                            .foregroundStyle(delta > 0 ? Palette.transferIn : Palette.injuryLong)
                            .help("\(delta > 0 ? "Better" : "Worse") than your best XI in this slot by \(Fmt.stars(abs(delta)))★")
                    }
                }
                .padding(.bottom, 5)
            }
            .frame(width: 112)
            .accessibilityElement(children: .ignore)
            .background(theme.cardFill)
            .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 6, style: .continuous)
                .strokeBorder(targeted ? Palette.star : (rating?.fam == "C" || rating?.fam == "X") ? Palette.verdict("amber") : .clear, lineWidth: 2))
            .shadow(color: .black.opacity(0.45), radius: 8, y: 6)
            .contentShape(Rectangle())
        }
        .menuStyle(.button)
        .buttonStyle(.plain)
        .menuIndicator(.hidden)
        .fixedSize()
        .help("\(info.ipRoleName ?? info.ipRole) in possession · \(info.oopRoleName ?? info.oopRole) out of possession. Drop a player here, or click to pick.")
        .draggable(uid.map(String.init) ?? "") { dragPreview(player) }
        .dropDestination(for: String.self) { items, _ in
            guard let text = items.first, let dropped = Int(text) else { return false }
            withAnimation(.snappy) { model.place(dropped, at: row) }
            return true
        } isTargeted: { targeted = $0 }
        .accessibilityLabel("\(info.label ?? info.slot): \(player?.name ?? "empty")")
        .accessibilityValue(rating.map { "\(Fmt.stars($0.stars)) stars, \(FamiliarityBadge.words($0.fam))" } ?? "")
        .accessibilityHint("Pick who plays here")
    }

    /// Everyone available, best first, grouped by how well they know the slot.
    @ViewBuilder
    private func choices(_ info: Formation.Row) -> some View {
        let groups: [(String, Set<String>)] = [("Plays here", ["N", "A"]), ("Can play here, not ideal", ["C"]), ("Out of position", ["X"])]
        Button("Nobody") { model.place(nil, at: row) }
        ForEach(groups, id: \.0) { title, codes in
            let ps = model.people
                .filter { model.isAvailable($0.uid) }
                .compactMap { p in model.rating(p.uid, row: row).map { (p, $0) } }
                .filter { codes.contains($0.1.fam) }
                .sorted { $0.1.stars > $1.1.stars }
            if !ps.isEmpty {
                Section(title) {
                    ForEach(ps, id: \.0.uid) { p, r in
                        Button("\(p.name) · \(Fmt.stars(r.stars))★\(model.isTarget(p.uid) ? " · target" : "")\(p.youth ? " · youth" : "")") {
                            withAnimation(.snappy) { model.place(p.uid, at: row) }
                        }
                    }
                }
            }
        }
    }
}

private func dragPreview(_ player: Player?) -> some View {
    Text(player?.name ?? "")
        .font(.callout.weight(.semibold))
        .padding(.horizontal, 10).padding(.vertical, 5)
        .background(.regularMaterial, in: Capsule())
}

// MARK: - the roster

private struct Roster: View {
    let model: SandboxModel
    /// Under the pitch (small window) instead of beside it: no List of its own, the page scrolls.
    let stacked: Bool
    @Environment(AppModel.self) private var app
    @State private var search = ""
    @State private var youth = false
    @State private var showAway = false
    @State private var finding = false

    var body: some View {
        let inXI = Set(model.lineup.compactMap { $0 })
        let q = search.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .current).trimmingCharacters(in: .whitespaces)
        let match: (Player) -> Bool = { q.isEmpty || $0.name.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: .current).contains(q) }
        let squad = model.report.players.filter { (youth || !$0.youth || inXI.contains($0.uid)) && match($0) }
            .sorted { ($0.best?.stars ?? 0) > ($1.best?.stars ?? 0) }
        let here = squad.filter { $0.location == "squad" }
        let arriving = squad.filter { $0.location == "incoming" }
        let away = squad.filter { $0.location == "loan_out" }
        let targets = model.report.targets.filter(match)
        VStack(alignment: .leading, spacing: 0) {
            // the design's roster head: a search capsule; a rule under
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 10) {
                    HStack(spacing: 6) {
                        Image(systemName: "magnifyingglass").font(.system(size: 11)).foregroundStyle(.tertiary)
                        TextField("Search squad…", text: $search).textFieldStyle(.plain).font(.system(size: 12))
                    }
                    .padding(.horizontal, 12).frame(height: 32)
                    .background(Color.black.opacity(0.25), in: Capsule())
                    .overlay(Capsule().strokeBorder(Color.primary.opacity(search.isEmpty ? 0.08 : 0.2)))
                    Toggle("Youth", isOn: $youth).toggleStyle(.checkbox).font(.system(size: 11.5))
                }
            }
            .padding(12)
            .overlay(alignment: .bottom) { Rectangle().fill(Color.primary.opacity(0.07)).frame(height: 1) }
            if stacked {
                LazyVStack(alignment: .leading, spacing: 0) {
                    sections(here: here, arriving: arriving, away: away, targets: targets, inXI: inXI, searching: !q.isEmpty)
                }
                .padding(.horizontal, 16).padding(.bottom, 20)
            } else {
                List {
                    sections(here: here, arriving: arriving, away: away, targets: targets, inXI: inXI, searching: !q.isEmpty)
                }
                .listStyle(.inset)
                .scrollContentBackground(.hidden)
            }
        }
        .sheet(isPresented: $finding) { FindPlayers(client: app.engine.client, have: Set(model.report.targets.map(\.uid))) }
    }
}

extension Roster {
    @ViewBuilder
    fileprivate func sections(here: [Player], arriving: [Player], away: [Player], targets: [Player], inXI: Set<Int>,
                              searching: Bool) -> some View {
        Section {
            ForEach(here) { row($0, inXI) }
        } header: { header("Your squad · drag onto the pitch") }
        if !arriving.isEmpty {
            Section {
                ForEach(arriving) { row($0, inXI) }
            } header: { header("Arriving · already agreed, rated as if they're here") }
        }
        if !away.isEmpty {
            let open = showAway || searching
            Section {
                if open { ForEach(away) { row($0, inXI) } }
            } header: {
                Button {
                    withAnimation(.snappy) { showAway.toggle() }
                } label: {
                    HStack(spacing: 5) {
                        Image(systemName: "chevron.right").font(.caption2.weight(.bold))
                            .rotationEffect(.degrees(open ? 90 : 0)).accessibilityHidden(true)
                        Text("Away on loan · \(away.count) · set one to Available to try him")
                    }
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .font(stacked ? .callout.weight(.semibold) : .subheadline.weight(.semibold))
                .foregroundStyle(.secondary)
                .padding(.top, stacked ? 14 : 0).padding(.bottom, stacked ? 4 : 0)
                .accessibilityValue(open ? "expanded" : "collapsed")
                .disabled(searching)
            }
        }
        Section {
            ForEach(targets) { row($0, inXI) }
            if targets.isEmpty {
                Text("No scouting targets yet.").foregroundStyle(.secondary).padding(.vertical, stacked ? 6 : 0)
            }
            Button("Find a scouted player…") { finding = true }
                .padding(.vertical, stacked ? 6 : 0)
            Text("Targets are rated from their real attributes. Only add players your scouts have fully reported on; potential is never shown for them.")
                .font(.caption).foregroundStyle(.secondary)
        } header: { header("Scouting targets · set to Signed to use them") }
    }

    @ViewBuilder
    private func header(_ text: String) -> some View {
        if stacked {
            Text(text).font(.callout.weight(.semibold)).foregroundStyle(.secondary)
                .padding(.top, 14).padding(.bottom, 4)
        } else {
            Text(text)
        }
    }

    @ViewBuilder
    private func row(_ p: Player, _ inXI: Set<Int>) -> some View {
        if stacked {
            RosterRow(model: model, player: p, inXI: inXI.contains(p.uid)).padding(.vertical, 6)
            Divider()
        } else {
            RosterRow(model: model, player: p, inXI: inXI.contains(p.uid))
        }
    }
}

private struct RosterRow: View {
    let model: SandboxModel
    let player: Player
    let inXI: Bool
    @Environment(AppModel.self) private var app
    @State private var removing = false
    @State private var removeProblem: String?

    var body: some View {
        let status = model.status(player.uid)
        let choices = model.isTarget(player.uid) ? SandboxModel.Status.targetChoices : SandboxModel.Status.squadChoices
        let slots = model.rows.indices.compactMap { i in player.openRating(row: i).map { (model.rows[i].label ?? model.rows[i].slot, $0) } }
            .filter { $0.1.fam != "X" }
            .sorted { $0.1.stars > $1.1.stars }
            .reduce(into: [(String, Rating)]()) { acc, item in if !acc.contains(where: { $0.0 == item.0 }) { acc.append(item) } }
            .prefix(3)
        HStack(spacing: 8) {
            Circle().fill(color(status)).frame(width: 8, height: 8).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 5) {
                    Text(player.name).fontWeight(.semibold).lineLimit(1)
                    if inXI { XITag() }
                    if player.targetSource == "squad_planner" {
                        Image(systemName: "list.clipboard").font(.caption).foregroundStyle(.secondary)
                            .help("From FM's Squad Planner: remove him there, in the game")
                            .accessibilityLabel("From FM's Squad Planner")
                    }
                }
                Text(subtitle).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                if slots.isEmpty {
                    Text("no slot in your tactic").font(.caption2).foregroundStyle(.secondary)
                } else {
                    // never wraps: as many of his best three slots as fit on one line
                    ViewThatFits(in: .horizontal) {
                        chips(Array(slots))
                        chips(Array(slots.prefix(2)))
                        chips(Array(slots.prefix(1)))
                    }
                }
            }
            Spacer(minLength: 4)
            if player.targetSource == "scouting_list" {
                Button {
                    Task { await remove() }
                } label: {
                    Image(systemName: removing ? "hourglass" : "xmark.circle.fill").foregroundStyle(.secondary)
                }
                .buttonStyle(.borderless)
                .disabled(removing)
                .help(removeProblem ?? "Remove from your scouting list")
                .accessibilityLabel("Remove \(player.name) from your scouting list")
            }
            Picker("Status", selection: Binding(get: { status }, set: { new in withAnimation(.snappy) { model.setStatus(player.uid, new) } })) {
                ForEach(choices, id: \.self) { Text($0.title).tag($0) }
            }
            .labelsHidden()
            .frame(width: 126)
        }
        .opacity([.injured, .suspended, .left, .away, .target].contains(status) ? 0.6 : 1)
        .contentShape(Rectangle())
        .draggable(String(player.uid)) { dragPreview(player) }
        .accessibilityElement(children: .combine)
    }

    private func chips(_ slots: [(String, Rating)]) -> some View {
        HStack(spacing: 4) {
            ForEach(slots, id: \.0) { label, r in
                Text("\(label) \(Fmt.stars(r.stars))★").font(.caption2.weight(.semibold))
                    .lineLimit(1).fixedSize()
                    .padding(.horizontal, 4).padding(.vertical, 1)
                    .background(r.fam == "N" ? Color.primary.opacity(0.18) : Color.primary.opacity(0.07), in: RoundedRectangle(cornerRadius: 4))
            }
        }
    }

    /// Takes him off scouting.txt; the engine rebuilds and he drops out of the next report (~30 s).
    private func remove() async {
        removing = true
        do {
            try await app.engine.client.removeTarget(name: player.name)
            removeProblem = "Removed. He goes when the report updates (about 30 seconds)."
        } catch {
            removing = false
            removeProblem = "Couldn't remove him: \(error.localizedDescription)"
        }
    }

    private var subtitle: String {
        var bits = [player.positions.natural.joined(separator: " ")]
        if let club = player.targetClub { bits.append(club) }
        if let age = player.age { bits.append("\(age)") }
        if let move = player.status.moves.first {
            switch move.kind {
            case "loan_out": bits.append("on loan at \(move.club)")
            case "deal_in", "loan_in_arr": bits.append("arriving from \(move.club) · \(Fmt.day(move.date))")
            case "deal_out", "loan_out_arr": bits.append("leaving for \(move.club)")
            default: break
            }
        }
        return bits.filter { !$0.isEmpty }.joined(separator: " · ")
    }

    private func color(_ s: SandboxModel.Status) -> Color {
        switch s {
        case .available: Palette.transferIn
        case .injured: Palette.injuryLong
        case .suspended: Palette.suspended
        case .left: Palette.transferOut
        case .away: Palette.loanOut
        case .signed: Palette.star
        case .target: Color.secondary
        }
    }
}

// MARK: - finding scouting targets

/// Search every player in the save by name or club and add them as targets. Public facts only (age, positions, club),
/// never ratings, so this can't be used to scout players FM's own scouts haven't seen.
private struct FindPlayers: View {
    let client: EngineClient
    let have: Set<Int>
    @Environment(\.dismiss) private var dismiss
    @State private var query = ""
    @State private var results: [EngineClient.Found] = []
    @State private var total = 0
    @State private var picked: Set<Int> = []
    @State private var message = ""
    @State private var position = ""        // "" = any position
    @State private var maxAge = 0           // 0 = any age

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Find a scouted player").font(.title3.weight(.bold))
            Text("FM doesn't let other tools read your scouting shortlist, so search here by name or club. Anyone in FM's Squad Planner is added by itself.")
                .font(.callout).foregroundStyle(.secondary)
            HStack(spacing: 8) {
                TextField("Name or club, e.g. Mrozek or Benfica", text: $query)
                    .textFieldStyle(.roundedBorder)
                Picker("Position", selection: $position) {
                    Text("Any position").tag("")
                    Divider()
                    ForEach(SquadListView.filterPositions, id: \.self) { Text($0).tag($0) }
                }
                .labelsHidden().fixedSize()
                Picker("Age", selection: $maxAge) {
                    Text("Any age").tag(0)
                    Divider()
                    ForEach([19, 21, 23], id: \.self) { Text("\($0) and under").tag($0) }
                }
                .labelsHidden().fixedSize()
            }
            .onChange(of: query) { _, _ in Task { await search() } }
            .onChange(of: position) { _, _ in Task { await search() } }
            .onChange(of: maxAge) { _, _ in Task { await search() } }
            Text(message).font(.caption).foregroundStyle(.secondary)
            List(results) { r in
                let already = have.contains(r.uid)
                Toggle(isOn: Binding(
                    get: { already || picked.contains(r.uid) },
                    set: { on in if on { picked.insert(r.uid) } else { picked.remove(r.uid) } }
                )) {
                    HStack {
                        VStack(alignment: .leading) {
                            Text(r.n).fontWeight(.semibold)
                            Text("\(r.a.map(String.init) ?? "–") · \(r.p) · \(r.c)").font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        if already { Text("already in the Sandbox").font(.caption).foregroundStyle(.secondary) }
                    }
                }
                .toggleStyle(.checkbox)
                .disabled(already)
                .accessibilityLabel("\(r.n), \(r.a.map { "age \($0)" } ?? "age unknown"), \(r.p), \(r.c)")
                .accessibilityHint(already ? "Already in the Sandbox" : "")
            }
            .frame(minHeight: 260)
            HStack {
                Spacer()
                Button("Cancel") { dismiss() }
                Button("Add \(picked.count) to the Sandbox") {
                    Task {
                        do {
                            try await client.addTargets(Array(picked))
                            message = "Added. The report updates by itself in about 30 seconds."
                            try? await Task.sleep(for: .seconds(1.5))
                            dismiss()
                        } catch {
                            message = "Couldn't add them: \(error.localizedDescription)"
                        }
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(picked.isEmpty)
            }
        }
        .padding(20)
        .frame(width: 620, height: 540)
    }

    private func search() async {
        let q = query.trimmingCharacters(in: .whitespaces)
        guard q.count >= 2 else { results = []; message = q.isEmpty ? "" : "Keep typing: at least 2 letters."; return }
        let (pos, age) = (position, maxAge)
        guard let found = try? await client.searchPlayers(q, position: pos.isEmpty ? nil : pos, maxAge: age == 0 ? nil : age)
        else { message = "Couldn't search right now."; return }
        // a newer search is on its way
        guard q == query.trimmingCharacters(in: .whitespaces), pos == position, age == maxAge else { return }
        results = found.items
        total = found.total
        let narrowed = (pos.isEmpty ? "" : " who can play \(pos)") + (age == 0 ? "" : ", \(age) or under")
        message = total == 0 ? "No players match “\(q)”\(narrowed) in your save." : total > results.count ? "Showing \(results.count) of \(total). Add a club to narrow it down." : "\(total) player\(total == 1 ? "" : "s")"
    }
}
