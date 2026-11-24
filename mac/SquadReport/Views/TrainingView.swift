import SwiftUI

/// Training: what's set now (read from the save's calendars), what to change in the first team's schedule and why
/// (from your own match numbers), and an individual plan per player. FM doesn't let other tools read individual training,
/// so the plan is a recommendation to compare with his card in Training › Individual Training.
struct TrainingView: View {
    let report: Report

    enum Part: String, CaseIterable, Identifiable {
        case schedule = "Schedule", change = "What to change", individual = "Individual", prospects = "Prospects"
        var id: String { rawValue }
    }
    @State private var part: Part = .schedule
    @AppStorage("showPotential") private var showPotential = true

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Picker("Part", selection: $part) {
                    ForEach(Part.allCases.filter { showPotential || $0 != .prospects }) { Text($0.rawValue).tag($0) }
                }
                    .pickerStyle(.segmented).labelsHidden().fixedSize()
                Spacer()
            }
            .padding(.horizontal, 24).padding(.vertical, 12)
            Divider()
            ScrollView {
                Group {
                    switch part {
                    case .schedule: Schedules(report: report)
                    case .change: Changes(report: report)
                    case .individual: Plans(report: report, prospects: false)
                    case .prospects: Plans(report: report, prospects: true)
                    }
                }
                .padding(24)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}

// MARK: - the schedules in place

private struct Schedules: View {
    let report: Report

    var body: some View {
        let teams = report.training ?? []
        VStack(alignment: .leading, spacing: 16) {
            SectionTitle("Training in place", sub: "read from your save's calendars · schedule names are exactly what your Training screen shows")
            if teams.isEmpty {
                ContentUnavailableView("No training calendar in this save", systemImage: "calendar")
            }
            ForEach(teams) { team in TeamSchedule(team: team, detailed: team.name == "First team" || team.id == teams.first?.id) }
        }
    }
}

private struct TeamSchedule: View {
    let team: TrainingTeam
    let detailed: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .firstTextBaseline) {
                Text(team.name).font(.headline)
                Text(team.current ?? "–").displayFont(22)
                Spacer()
                Text("this week").font(.caption).foregroundStyle(.secondary)
            }
            if detailed, let grid = team.grid, !grid.isEmpty {
                WeekGrid(team: team, grid: grid)
                Text("Sessions without an exact name are shown by category: your Training screen has the exact session.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            HStack(alignment: .top, spacing: 28) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Next weeks").font(.caption.weight(.heavy)).foregroundStyle(.secondary)
                    ForEach(Array((team.upcoming ?? []).enumerated()), id: \.offset) { i, item in
                        HStack(spacing: 10) {
                            Circle().fill(i == 0 ? Palette.brandHigh : Color.secondary.opacity(0.4)).frame(width: 8, height: 8)
                            Text(Fmt.shortDay(item.first)).foregroundStyle(.secondary).monospacedDigit().frame(width: 48, alignment: .leading)
                            Text(item.count > 1 ? item[1] : "–")
                        }
                        .font(.callout)
                    }
                }
                VStack(alignment: .leading, spacing: 6) {
                    Text("Used this season").font(.caption.weight(.heavy)).foregroundStyle(.secondary)
                    let used = (team.rotation ?? [:]).sorted { $0.value > $1.value }
                    let most = Double(used.first?.value ?? 1)
                    ForEach(used, id: \.key) { name, n in
                        HStack(spacing: 8) {
                            Text(name).lineLimit(1).truncationMode(.middle).frame(minWidth: 280, alignment: .leading).help(name)
                            Capsule().fill(Color(hex: "#D0102E")).frame(width: max(4, 80 * Double(n) / most), height: 6)
                            Text("\(n)").monospacedDigit().foregroundStyle(.secondary)
                        }
                        .font(.callout)
                    }
                }
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .panel(10)
    }
}

/// This week, day by day, three sessions a day, coloured by category.
private struct WeekGrid: View {
    let team: TrainingTeam
    let grid: [TrainingTeam.Day]

    var body: some View {
        Grid(horizontalSpacing: 4, verticalSpacing: 4) {
            GridRow {
                ForEach(grid, id: \.day) { day in
                    Text(dayLabel(day.day)).font(.caption.weight(.bold)).foregroundStyle(.secondary).frame(maxWidth: .infinity)
                }
            }
            ForEach(0..<3, id: \.self) { slot in
                GridRow {
                    ForEach(grid, id: \.day) { day in
                        let code = slot < day.sessions.count ? day.sessions[slot] : nil
                        cell(code)
                    }
                }
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel("This week's sessions")
    }

    @ViewBuilder
    private func cell(_ code: Int?) -> some View {
        if let code, let s = team.session(code) {
            Text(s.name)
                .font(.system(size: 11, weight: s.kind == "match" ? .heavy : .medium))
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .foregroundStyle(s.kind == "extra" ? Color.secondary : .white)
                .frame(maxWidth: .infinity, minHeight: 34)
                .background(color(s.kind), in: RoundedRectangle(cornerRadius: 6))
                .help("\(s.name) · \(s.family)\(s.exact ? "" : " (category)")")
        } else {
            Color.clear.frame(maxWidth: .infinity, minHeight: 34)
        }
    }

    private func color(_ kind: String) -> Color {
        switch kind {
        case "tac": Color(hex: "#1E3A8A")
        case "prep": Color(hex: "#5B21B6")
        case "dev": Color(hex: "#166534")
        case "phys": Color(hex: "#9A3412")
        case "match": Color(hex: "#B91C1C")
        case "rest": Color.secondary.opacity(0.35)
        default: Color.secondary.opacity(0.15)
        }
    }

    private func dayLabel(_ iso: String) -> String {
        guard let d = Fmt.date(iso) else { return iso }
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = "EEE d"
        return f.string(from: d)
    }
}

// MARK: - what to change

private struct Changes: View {
    let report: Report

    var body: some View {
        let advice = report.trainingAdvice
        VStack(alignment: .leading, spacing: 16) {
            SectionTitle("What to change in the first team's schedule", sub: "each one from your own match numbers (Tactical fit › How it's going)")
            if advice?.changes.isEmpty ?? true {
                Label("Nothing to change: your numbers don't point at a schedule problem.", systemImage: "checkmark.seal.fill")
                    .foregroundStyle(Palette.transferIn)
            }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 440), spacing: 12, alignment: .top)], spacing: 12) {
                ForEach(advice?.changes ?? []) { c in
                    VStack(alignment: .leading, spacing: 8) {
                        Text(c.title).font(.headline)
                        line("Why", c.why)
                        line("Change", c.do)
                        line("Won't hurt", c.safe)
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .panelFill()
                    .overlay(alignment: .leading) { Rectangle().fill(Palette.star).frame(width: 3) }
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                }
            }
            if let keep = advice?.keep, !keep.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Leave these alone").font(.headline)
                    ForEach(keep, id: \.self) { Label($0, systemImage: "hand.thumbsup").font(.callout) }
                }
                .padding(14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .panel(10)
            }
        }
    }

    private func line(_ label: String, _ text: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text(label).font(.caption.weight(.heavy)).foregroundStyle(.secondary).frame(width: 74, alignment: .leading)
            Text(text).font(.callout).fixedSize(horizontal: false, vertical: true)
        }
    }
}

// MARK: - individual plans

private struct Plans: View {
    let report: Report
    let prospects: Bool
    @State private var everyone = false

    var body: some View {
        let all = (report.plans ?? []).compactMap { plan in report.player(plan.uid).map { (plan, $0) } }
        let rows: [(TrainingPlan, Player)] = prospects
            ? all.filter { ($0.1.potential ?? 0) >= 3.5 }.sorted { ($0.1.potential ?? 0) > ($1.1.potential ?? 0) }
            : all.filter { $0.1.location == "squad" && !$0.1.youth }
                .sorted { a, b in (a.0.inXi ? 0 : 1, -(a.1.best?.stars ?? 0)) < (b.0.inXi ? 0 : 1, -(b.1.best?.stars ?? 0)) }
        let shown = prospects || everyone ? rows : rows.filter(\.0.inXi)
        VStack(alignment: .leading, spacing: 14) {
            if prospects {
                SectionTitle("Prospects", sub: "players 23 and under with 3.5★+ potential")
            } else {
                SectionTitle("Individual training: first team", sub: "compare with his card in Training › Individual Training")
                Text("Set his IP and OOP roles to the ones he plays in your tactic, give him the focus shown, and use Position/Role or Individual Out of Possession Training for the position work. One focus at a time: change it once that attribute has gone up.")
                    .font(.callout).foregroundStyle(.secondary)
                Toggle("Show players outside the best XI too", isOn: $everyone)
            }
            Grid(alignment: .leading, horizontalSpacing: 14, verticalSpacing: 10) {
                GridRow {
                    Text("Player"); Text("Plays"); Text("Roles to train"); Text("Position work"); Text("Focus"); Text("Why")
                }
                .font(.caption.weight(.bold)).foregroundStyle(.secondary)
                Divider().gridCellUnsizedAxes(.horizontal)
                ForEach(shown, id: \.0.uid) { plan, p in
                    GridRow(alignment: .top) {
                        VStack(alignment: .leading, spacing: 2) {
                            HStack(spacing: 5) {
                                Text(p.name).fontWeight(.semibold)
                                if plan.inXi { XITag() }
                            }
                            if prospects {
                                Text("\(p.age.map(String.init) ?? "") · \(p.isLoanedOut ? "on loan" : p.youth ? "U21/U18" : "first team")")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        Text(plan.label).fontWeight(.semibold)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(plan.ipRole)
                            Text(plan.oopRole).foregroundStyle(.secondary)
                        }
                        .font(.callout)
                        VStack(alignment: .leading, spacing: 2) {
                            if plan.positionWork.isEmpty {
                                Text("Already natural: no position work").foregroundStyle(Palette.transferIn)
                            }
                            ForEach(plan.positionWork, id: \.self) { w in
                                Text("\(w.code) \(w.phase): \(w.word) · \(w.how)").fixedSize(horizontal: false, vertical: true)
                            }
                        }
                        .font(.caption)
                        VStack(alignment: .leading, spacing: 2) {
                            if let f = plan.focus {
                                Text("\(report.label(f.attribute)) \(f.value)").font(.callout.weight(.semibold))
                                    .padding(.horizontal, 7).padding(.vertical, 2)
                                    .background(Palette.star.opacity(0.15), in: RoundedRectangle(cornerRadius: 5))
                                    .overlay(RoundedRectangle(cornerRadius: 5).stroke(Palette.star.opacity(0.5)))
                            } else {
                                Text("Nothing at 13 or below").font(.caption).foregroundStyle(Palette.transferIn)
                            }
                            if let t = plan.then {
                                Text("then \(report.label(t.attribute)) (\(t.value))").font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        Text(plan.why + fixedNote(plan)).font(.caption).foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                            .frame(maxWidth: 360, alignment: .leading)
                    }
                    Divider().gridCellUnsizedAxes(.horizontal).opacity(0.5)
                }
            }
            if !prospects && !everyone && rows.count > shown.count {
                Button("Show \(rows.count - shown.count) more players outside your best XI") { everyone = true }
            }
        }
    }

    private func fixedNote(_ plan: TrainingPlan) -> String {
        guard !plan.fixed.isEmpty else { return "" }
        return " " + plan.fixed.map { a in
            a.attribute == "determination"
                ? "\(report.label(a.attribute)) \(a.value) can't really be trained: mentoring helps"
                : "\(report.label(a.attribute)) \(a.value) is largely fixed"
        }.joined(separator: "; ") + "."
    }
}
