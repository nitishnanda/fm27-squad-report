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

    var body: some View {
        VStack(spacing: 0) {
            ScoreBar(model: model)
            Divider()
            HStack(alignment: .top, spacing: 0) {
                GeometryReader { geo in
                    let width = min(geo.size.width - 40, (geo.size.height - 40) * 0.68)
                    SandboxPitch(model: model)
                        .frame(width: max(300, width))
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
                .frame(minWidth: 300)
                Divider()
                Roster(model: model)
                    .frame(minWidth: 330, idealWidth: 440, maxWidth: 520)
            }
        }
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
            Text("Your XI").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            HStack(spacing: 6) {
                StarsView(value: avg, size: 15)
                NumberText(String(format: "%.1f", avg), size: 26)
            }
            Text("\(diff >= 0 ? "+" : "")\(String(format: "%.1f", diff))★ vs best XI (\(String(format: "%.1f", level))) · \(model.changes) change\(model.changes == 1 ? "" : "s")")
                .font(.caption).foregroundStyle(.secondary)
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
        .font(.callout)
        .lineLimit(2)
        .frame(minWidth: 200, idealWidth: 300, maxWidth: .infinity, alignment: .leading)
        let buttons = HStack(spacing: 10) {
            Text(model.auto ? "auto-picking" : "your own picks").font(.caption).foregroundStyle(.secondary)
            Button("Auto-pick best XI") { withAnimation(.snappy) { model.autoPick() } }
                .buttonStyle(.borderedProminent)
            Button("Reset all changes") { withAnimation(.snappy) { model.reset() } }
        }
        .fixedSize()
        // one row on a wide window; on a narrow one the notes drop under the score
        ViewThatFits(in: .horizontal) {
            HStack(alignment: .center, spacing: 20) {
                score
                Divider().frame(height: 44)
                notes
                buttons
            }
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .center, spacing: 16) { score; Spacer(minLength: 0); buttons }
                notes
            }
        }
        .padding(.horizontal, 20).padding(.vertical, 12)
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
            HStack {
                TextField("Search players", text: $search).textFieldStyle(.roundedBorder)
                Toggle("Youth teams", isOn: $youth)
            }
            .padding(12)
            List {
                Section("Your squad · drag onto the pitch") {
                    ForEach(here) { RosterRow(model: model, player: $0, inXI: inXI.contains($0.uid)) }
                }
                if !arriving.isEmpty {
                    Section("Arriving · already agreed, rated as if they're here") {
                        ForEach(arriving) { RosterRow(model: model, player: $0, inXI: inXI.contains($0.uid)) }
                    }
                }
                if !away.isEmpty {
                    Section(isExpanded: Binding(get: { showAway || !q.isEmpty }, set: { showAway = $0 })) {
                        ForEach(away) { RosterRow(model: model, player: $0, inXI: inXI.contains($0.uid)) }
                    } header: {
                        Text("Away on loan · \(away.count) · set one to Available to try him")
                    }
                }
                Section {
                    ForEach(targets) { RosterRow(model: model, player: $0, inXI: inXI.contains($0.uid)) }
                    if targets.isEmpty {
                        Text("No scouting targets yet.").foregroundStyle(.secondary)
                    }
                    Button("Find a scouted player…") { finding = true }
                    Text("Targets are rated from their real attributes. Only add players your scouts have fully reported on; potential is never shown for them.")
                        .font(.caption).foregroundStyle(.secondary)
                } header: {
                    Text("Scouting targets · set to Signed to use them")
                }
            }
            .listStyle(.inset)
            .scrollContentBackground(.hidden)
        }
        .sheet(isPresented: $finding) { FindPlayers(client: app.engine.client, have: Set(model.report.targets.map(\.uid))) }
    }
}

private struct RosterRow: View {
    let model: SandboxModel
    let player: Player
    let inXI: Bool

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
                }
                Text(subtitle).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                HStack(spacing: 4) {
                    ForEach(Array(slots), id: \.0) { label, r in
                        Text("\(label) \(Fmt.stars(r.stars))★").font(.caption2.weight(.semibold))
                            .padding(.horizontal, 4).padding(.vertical, 1)
                            .background(r.fam == "N" ? Color.primary.opacity(0.18) : Color.primary.opacity(0.07), in: RoundedRectangle(cornerRadius: 3))
                    }
                    if slots.isEmpty { Text("no slot in your tactic").font(.caption2).foregroundStyle(.secondary) }
                }
            }
            Spacer(minLength: 4)
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

    private var subtitle: String {
        var bits = [player.positions.natural.joined(separator: " ")]
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

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Find a scouted player").font(.title3.weight(.bold))
            Text("FM doesn't let other tools read your scouting shortlist, so search here by name or club. Anyone in FM's Squad Planner is added by itself.")
                .font(.callout).foregroundStyle(.secondary)
            TextField("Name or club, e.g. Mrozek or Benfica", text: $query)
                .textFieldStyle(.roundedBorder)
                .onChange(of: query) { _, _ in Task { await search() } }
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
        .frame(width: 520, height: 520)
    }

    private func search() async {
        let q = query.trimmingCharacters(in: .whitespaces)
        guard q.count >= 2 else { results = []; message = q.isEmpty ? "" : "Keep typing: at least 2 letters."; return }
        guard let found = try? await client.searchPlayers(q) else { message = "Couldn't search right now."; return }
        guard q == query.trimmingCharacters(in: .whitespaces) else { return }   // a newer search is on its way
        results = found.items
        total = found.total
        message = total == 0 ? "No players match “\(q)” in your save." : total > results.count ? "Showing \(results.count) of \(total). Add a club to narrow it down." : "\(total) player\(total == 1 ? "" : "s")"
    }
}
