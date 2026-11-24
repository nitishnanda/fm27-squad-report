import Foundation
import Observation

/// The Hungarian algorithm (the same one the engine and the web Sandbox use): the cheapest way to give each row one
/// column, every column used at most once. `cost` is rows × columns with rows ≤ columns. Returns the column per row.
enum Hungarian {
    static func solve(_ cost: [[Double]]) -> [Int] {
        let n = cost.count
        guard n > 0, let m = cost.first?.count, m >= n else { return Array(repeating: -1, count: n) }
        let inf = Double.greatestFiniteMagnitude / 4
        var u = [Double](repeating: 0, count: n + 1), v = [Double](repeating: 0, count: m + 1)
        var p = [Int](repeating: 0, count: m + 1), way = [Int](repeating: 0, count: m + 1)
        for i in 1...n {
            p[0] = i
            var j0 = 0
            var minv = [Double](repeating: inf, count: m + 1)
            var used = [Bool](repeating: false, count: m + 1)
            repeat {
                used[j0] = true
                let i0 = p[j0]
                var delta = inf, j1 = 0
                for j in 1...m where !used[j] {
                    let cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j] { minv[j] = cur; way[j] = j0 }
                    if minv[j] < delta { delta = minv[j]; j1 = j }
                }
                for j in 0...m {
                    if used[j] { u[p[j]] += delta; v[j] -= delta } else { minv[j] -= delta }
                }
                j0 = j1
            } while p[j0] != 0
            repeat {
                let j1 = way[j0]
                p[j0] = p[j1]
                j0 = j1
            } while j0 != 0
        }
        var result = [Int](repeating: -1, count: n)
        for j in 1...m where p[j] != 0 { result[p[j] - 1] = j - 1 }
        return result
    }
}

/// What-if: mark players injured, gone or away, sign scouting targets, and build an XI. Ratings change with the slot
/// you put someone in (his open rating there, with N/A/C/X familiarity). Kept per save, so it survives a restart.
@MainActor @Observable
final class SandboxModel {
    enum Status: String, CaseIterable, Codable, Sendable {
        case available, injured, suspended, left, away, target, signed

        var title: String {
            switch self {
            case .available: "Available"
            case .injured: "Injured"
            case .suspended: "Suspended"
            case .left: "Left club"
            case .away: "Away on loan"
            case .target: "Not signed"
            case .signed: "Signed"
            }
        }
        static let squadChoices: [Status] = [.available, .injured, .suspended, .left, .away]
        static let targetChoices: [Status] = [.target, .signed]
    }

    private struct Saved: Codable {
        var statuses: [String: Status]
        var lineup: [Int?]
        var auto: Bool
    }

    let report: Report
    private(set) var statuses: [Int: Status] = [:]
    private(set) var lineup: [Int?] = []
    private(set) var auto = true

    /// Everyone the Sandbox can use: your squad (incl. arriving and loaned out) and your scouting targets.
    let people: [Player]
    let targetIDs: Set<Int>

    init(report: Report) {
        self.report = report
        people = report.players + report.targets
        targetIDs = Set(report.targets.map(\.uid))
        reset(save: false)
        if let data = UserDefaults.standard.data(forKey: key), let saved = try? JSONDecoder().decode(Saved.self, from: data) {
            for (k, v) in saved.statuses {
                guard let uid = Int(k), people.contains(where: { $0.uid == uid }) else { continue }
                let isTarget = targetIDs.contains(uid)
                if isTarget == Status.targetChoices.contains(v) { statuses[uid] = v }   // a stale status for the other kind is dropped
            }
            if saved.lineup.count == rows.count {
                lineup = saved.lineup.map { uid in uid.flatMap { u in people.contains { $0.uid == u } ? u : nil } }
            }
            auto = saved.auto
        }
        if auto { autoPick() }
    }

    private var key: String { "sandbox1:\(report.club.name):\(report.saveName ?? "")" }
    var rows: [Formation.Row] { report.formation.rows }

    func player(_ uid: Int?) -> Player? { uid.flatMap { u in people.first { $0.uid == u } } }
    func isTarget(_ uid: Int) -> Bool { targetIDs.contains(uid) }
    func status(_ uid: Int) -> Status { statuses[uid] ?? .available }
    func isAvailable(_ uid: Int) -> Bool { [.available, .signed].contains(status(uid)) }
    func rating(_ uid: Int?, row: Int) -> Rating? { player(uid)?.openRating(row: row) }

    /// The status a player starts with, from the save.
    func startingStatus(_ p: Player) -> Status {
        if targetIDs.contains(p.uid) { return .target }
        if p.location == "loan_out" { return .away }
        if p.status.moves.contains(where: { ["deal_out", "loan_out_arr"].contains($0.kind) }) { return .left }
        if p.isInjured { return .injured }
        if p.isSuspended { return .suspended }
        return .available
    }

    // MARK: changes

    func setStatus(_ uid: Int, _ status: Status) {
        statuses[uid] = status
        if auto { autoPick() } else { lineup = lineup.map { $0.flatMap { isAvailable($0) ? $0 : nil } } }
        save()
    }

    /// Put a player in a slot. If he was in another slot, the two swap.
    func place(_ uid: Int?, at row: Int) {
        guard row < lineup.count else { return }
        if let uid, let from = lineup.firstIndex(of: uid), from != row {
            lineup[from] = lineup[row]
        }
        lineup[row] = uid
        auto = false
        save()
    }

    func autoPick() {
        auto = true
        let pool = people.filter { isAvailable($0.uid) }
        let n = rows.count
        guard !pool.isEmpty else {
            lineup = Array(repeating: nil, count: n)
            save()
            return
        }
        let penalty: [String: Double] = ["N": 0, "A": 0, "C": 4, "X": 8]
        let cost: [[Double]] = rows.indices.map { i in
            pool.map { p in
                guard let r = p.openRating(row: i) else { return 1e6 }
                return -r.stars + (penalty[r.fam] ?? 8) - (r.fam == "N" ? 0.01 : 0)
            } + Array(repeating: 1e3, count: n)      // "nobody" columns, so a slot can stay empty
        }
        let pick = Hungarian.solve(cost)
        lineup = pick.enumerated().map { i, j in j >= 0 && j < pool.count && cost[i][j] < 1e5 ? pool[j].uid : nil }
        save()
    }

    func reset(save doSave: Bool = true) {
        statuses = Dictionary(people.map { ($0.uid, startingStatus($0)) }, uniquingKeysWith: { a, _ in a })
        lineup = Array(repeating: nil, count: rows.count)
        auto = true
        autoPick()
        if doSave { save() }
    }

    private func save() {
        let saved = Saved(statuses: Dictionary(statuses.map { (String($0.key), $0.value) }, uniquingKeysWith: { a, _ in a }),
                          lineup: lineup, auto: auto)
        if let data = try? JSONEncoder().encode(saved) { UserDefaults.standard.set(data, forKey: key) }
    }

    // MARK: summary

    /// The best XI's stars in each slot, to compare against.
    var bestStars: [Double] {
        rows.indices.map { i in
            guard i < report.xi1.count, let p = report.player(report.xi1[i].uid) else { return 0 }
            return p.rating(row: i)?.stars ?? 0
        }
    }

    var average: Double {
        let total = rows.indices.compactMap { rating(lineup[$0], row: $0)?.stars }.reduce(0, +)
        return total / Double(max(rows.count, 1))
    }

    var changes: Int {
        rows.indices.filter { i in lineup[i] != (i < report.xi1.count ? report.xi1[i].uid : nil) }.count
    }

    var emptySlots: Int { rows.indices.filter { rating(lineup[$0], row: $0) == nil }.count }

    var outOfPosition: [String] {
        rows.indices.compactMap { i in
            guard let r = rating(lineup[i], row: i), r.fam == "C" || r.fam == "X" else { return nil }
            return player(lineup[i]).map { surname($0.name) }
        }
    }

    var ruledOut: [String] {
        people.filter { !isTarget($0.uid) && startingStatus($0) == .available && !isAvailable($0.uid) }.map { surname($0.name) }
    }

    var signed: [String] { people.filter { isTarget($0.uid) && status($0.uid) == .signed }.map { surname($0.name) } }
}
