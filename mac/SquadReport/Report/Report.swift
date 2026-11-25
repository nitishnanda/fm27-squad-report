import Foundation

/// The report the engine serves at /api/report (see `report_json()` in fm27_squad_report.py).
/// Only the fields the app uses are decoded; the feed never carries CA/PA or hidden attributes.
struct Report: Decodable, Sendable {
    /// The feed version this app understands. The engine bumps REPORT_SCHEMA when a field changes meaning.
    static let supportedSchema = 1

    let schema: Int
    let club: Club
    let saveName: String?
    let gameDate: String?
    let lastRun: String?
    let formation: Formation
    let positions: PositionsInfo?
    let finances: Finances
    let players: [Player]
    let targets: [Player]
    let xi1: [XISlot]
    let xi2: [XISlot]
    let xiLevel: Double?
    let verdicts: [Verdict]
    let performance: Performance
    /// Your managerial record, kept by the engine across seasons (history.json). Nil from older engines.
    let career: Career?
    let news: [NewsItem]
    let notes: [String]
    let teamNames: [String: String]?
    let fit: TacticalFit?
    let style: Style?
    let attributeLabels: [String: String]?
    let attributeAbbr: [String: String]?
    let training: [TrainingTeam]?
    let trainingAdvice: TrainingAdvice?
    let trainingHowto: TrainingHowto?
    let plans: [TrainingPlan]?

    /// "Work Rate" for "work_rate". Dictionary keys may come back camelCased by the decoder, so both are tried.
    func label(_ attribute: String) -> String {
        attributeLabels?[attribute] ?? attributeLabels?[attribute.camelCased]
            ?? attribute.replacingOccurrences(of: "_", with: " ").capitalized
    }

    /// "Wor" for "work_rate", for tight table headers.
    func abbr(_ attribute: String) -> String {
        attributeAbbr?[attribute] ?? attributeAbbr?[attribute.camelCased] ?? String(label(attribute).prefix(3))
    }

    static func decode(_ data: Data) throws -> Report {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(Report.self, from: data)
    }

    /// Only reads the schema number, so a newer feed can say "update the app" instead of failing to decode.
    static func schema(of data: Data) -> Int? {
        struct Head: Decodable { let schema: Int }
        return try? JSONDecoder().decode(Head.self, from: data).schema
    }

    func player(_ uid: Int?) -> Player? {
        guard let uid else { return nil }
        return players.first { $0.uid == uid }
    }
}

struct Club: Decodable, Sendable {
    let name: String
    let kit: String
    let ink: String
    let kitOnLight: String?
    let initials: String?
}

struct Formation: Decodable, Sendable {
    struct Row: Decodable, Sendable {
        let slot: String
        let label: String?        // LCB / RCB, LDM / RDM
        let ip: String
        let oop: String
        let ipRole: String
        let oopRole: String
        let ipRoleName: String?
        let oopRoleName: String?
        let x: Double?            // where he stands on the pitch, % from the left
        let y: Double?            // % from the top (your goal at the bottom)
        let ipKeys: [String]?     // the key attributes of the in-possession role
        let oopKeys: [String]?
    }
    let name: String
    let style: String?
    let rows: [Row]

    /// "4-2-3-1 Gegenpress", or just the shape for an engine that doesn't send the style yet.
    var title: String { [name, style].compactMap { $0 }.joined(separator: " ") }
}

/// The Positions page: one card per position and what each plays with and without the ball.
struct PositionsInfo: Decodable, Sendable {
    struct Card: Decodable, Sendable, Identifiable {
        let slot: String
        let name: String
        let ip: String
        let oop: String
        var id: String { slot }
        var twoPhases: Bool { ip != oop }
    }
    let cards: [Card]
    let playedMany: Int
    let youthPerCard: Int
    let shown: Int
}

struct Finances: Decodable, Sendable {
    let transferLeft: Double?
    let wageBudget: Double?
    let wageBill: Double?
    let month: String?
}

struct XISlot: Decodable, Sendable {
    let slot: String
    let uid: Int?
}

struct Verdict: Decodable, Sendable, Identifiable {
    let slot: String
    let level: String   // red, amber, green, grey
    let title: String
    let text: String
    let gap: Double?

    var id: String { slot }
    var needsWork: Bool { level == "red" || level == "amber" }
}

struct NewsItem: Decodable, Sendable {
    let kind: String    // deal-in, deal-out, loan-in, loan-out, inj-short, inj-long, sus, expiring, warn
    let tag: String
    let text: String
    let route: String
}

struct Performance: Decodable, Sendable {
    struct Record: Decodable, Sendable {
        let pos: Int
        let of: Int
        let p: Int
        let w: Int
        let d: Int
        let l: Int
        let gf: Int
        let ga: Int
        let pts: Int
    }
    struct Result: Decodable, Sendable {
        let res: String
        let score: String
        let opp: String
        let home: Bool
        let date: String?
    }
    struct Metric: Decodable, Sendable, Identifiable {
        let key: String
        let label: String
        let value: Double
        let unit: String
        let rank: Int
        let of: Int
        let avg: Double
        let good: String
        let bad: String
        let higher: Bool?
        let above: Bool?
        let valueText: String?
        let avgText: String?
        var id: String { key }
    }
    struct PlayerItem: Decodable, Sendable {
        let key: String
        let label: String
        let value: Double
        let pctl: Double
        let press: Bool?
        let valueText: String?
    }
    struct PlayerNumbers: Decodable, Sendable {
        let group: String?
        let groupName: String?
        let good: [PlayerItem]
        let bad: [PlayerItem]
        let minutes: Int
        let avg: Double?
        let peers: Int?
    }
    let record: Record?
    let form: [Result]
    let metrics: [Metric]?
    let matches: Int?
    let leagueName: String?
    let leagueSize: Int?
    let insights: [String]?
    let minMinutes: Int?
    let players: [String: PlayerNumbers]?
}

/// Role-by-role fit: key attributes of each role (in and out of possession) blended with the style's attributes.
struct TacticalFit: Decodable, Sendable {
    struct Weak: Decodable, Sendable, Hashable {
        let value: Int
        let attribute: String
    }
    struct Entry: Decodable, Sendable, Identifiable {
        let uid: Int
        let xi: Bool
        let fit: Double?
        let ip: Double?
        let oop: Double?
        let style: Double?
        let weak: [Weak]
        let styleWeak: [Weak]
        var id: Int { uid }
    }
    struct Row: Decodable, Sendable, Identifiable {
        let label: String
        let slot: String
        let ipRole: String
        let oopRole: String
        let entries: [Entry]
        var id: String { label }
    }
    struct Misfit: Decodable, Sendable, Identifiable {
        let uid: Int
        let why: String
        let bestRow: String?
        let best: Entry?
        var id: Int { uid }
    }
    let rows: [Row]
    let misfits: [Misfit]
}

struct Style: Decodable, Sendable {
    let name: String
    let keys: [String]
}

struct TrainingTeam: Decodable, Sendable, Identifiable {
    struct Day: Decodable, Sendable {
        let day: String
        let sessions: [Int?]
    }
    struct Session: Decodable, Sendable {
        let name: String
        let family: String
        let kind: String      // tac, prep, dev, phys, rest, match, extra
        let exact: Bool
    }
    let slot: Int?
    let name: String
    let current: String?
    let week: String?
    let upcoming: [[String]]?
    let rotation: [String: Int]?
    let recentWeeks: Int?
    let grid: [Day]?
    let sessions: [String: Session]?
    var id: String { name }

    func session(_ code: Int) -> Session? { sessions?[String(code)] }
}

struct TrainingAdvice: Decodable, Sendable {
    struct Change: Decodable, Sendable, Identifiable {
        let title: String
        let why: String
        let `do`: String
        let safe: String
        var id: String { title }
    }
    let changes: [Change]
    let keep: [String]
    /// Youngsters with low Determination and senior pros with high Determination (nil when there aren't both).
    let mentoring: Mentoring?

    struct Mentoring: Decodable, Sendable {
        struct Person: Decodable, Sendable, Identifiable {
            let uid: Int
            let name: String
            let age: Int?
            let determination: Int?
            var id: Int { uid }
        }
        let young: [Person]
        let seniors: [Person]
        let advice: String
        let why: String
    }
}

/// "Doing it yourself next time": the web app's explainer, sent word for word.
struct TrainingHowto: Decodable, Sendable {
    struct Step: Decodable, Sendable, Hashable { let title: String; let text: String }
    struct Cheat: Decodable, Sendable, Hashable { let problem: String; let sessions: String; let focus: String }
    let steps: [Step]
    let cheat: [Cheat]
}

struct TrainingPlan: Decodable, Sendable, Identifiable {
    struct Work: Decodable, Sendable, Hashable {
        let code: String
        let phase: String
        let word: String
        let how: String
    }
    struct Attr: Decodable, Sendable, Hashable {
        let attribute: String
        let value: Int
    }
    let uid: Int
    let label: String
    let ipRole: String
    let oopRole: String
    let inXi: Bool
    let positionWork: [Work]
    let focus: Attr?
    let then: Attr?
    let why: String
    let fixed: [Attr]
    var id: Int { uid }
}

extension String {
    /// "work_rate" -> "workRate", the way JSONDecoder's snake-case strategy spells keys.
    var camelCased: String {
        let parts = split(separator: "_")
        guard let first = parts.first else { return self }
        return String(first) + parts.dropFirst().map { $0.prefix(1).uppercased() + $0.dropFirst() }.joined()
    }
}

struct Rating: Decodable, Sendable, Hashable {
    let stars: Double
    let fam: String     // N natural, A accomplished (C and X only appear in the Sandbox)
}

struct Player: Decodable, Sendable, Identifiable {
    struct Positions: Decodable, Sendable {
        let natural: [String]
        let accomplished: [String]
        let canPlay: [String]
    }
    struct Best: Decodable, Sendable {
        let slot: String
        let stars: Double
        let fam: String
    }
    struct SeasonStats: Decodable, Sendable {
        let apps: Int
        let g: Int
        let a: Int
        let avg: Double?
        let cs: Int?
        let y: Int?
        let r: Int?
        let team: Int?
    }
    struct Status: Decodable, Sendable {
        struct Injury: Decodable, Sendable {
            let days: Int
            let what: String
            let back: String?
            let long: Bool
        }
        struct Move: Decodable, Sendable {
            let kind: String   // deal_in, deal_out, loan_in, loan_out, loan_in_arr, loan_out_arr
            let club: String
            let date: String?
        }
        let tokens: [String]   // loan, injured, suspended, arranged, expiring
        let injury: Injury?
        let suspendedMatches: Int?
        let moves: [Move]
    }

    let uid: Int
    let name: String
    let age: Int?
    let location: String    // squad, incoming, loan_out, target
    let youth: Bool
    let value: Double?
    let wage: Double?
    let contractEnd: String?
    let expiring: Bool
    let positions: Positions
    let best: Best?
    let system: [String: Rating?]
    let abilityBest: Double?
    let potential: Double?
    let trend: Double?
    let stats: SeasonStats?
    let status: Status
    /// Scouting targets only: "scouting_list" (the app can remove these) or "squad_planner" (FM's, the save controls it).
    let targetSource: String?
    let targetClub: String?
    /// Per formation row ("0"…"10"): his rating in that exact slot, and the same for anyone (open rows, Sandbox-style).
    let rows: [String: Rating?]?
    let openRows: [String: Rating?]?
    /// Matches played at each card's position this season.
    let played: [String: Int]?
    /// Per card: FM's words for how well he knows the in- and out-of-possession positions. Missing = ineffective.
    let familiarity: [String: [String]]?
    /// Visible attributes only (the engine drops hidden ones before they reach the app).
    let attributes: [String: Int?]?
    let youthStats: [SeasonStats]?

    var id: Int { uid }

    func attribute(_ key: String) -> Int? { (attributes?[key] ?? attributes?[key.camelCased]) ?? nil }

    private enum CodingKeys: String, CodingKey {
        case uid, name, age, youth, value, wage, contractEnd, expiring, positions, best, system, abilityBest
        case potential, trend, stats, status, rows, openRows, played, familiarity, attributes, youthStats
        case targetSource, targetClub
        case location = "where"
    }

    func rating(at slot: String) -> Rating? { system[slot] ?? nil }
    func rating(row: Int) -> Rating? { rows?[String(row)] ?? nil }
    func openRating(row: Int) -> Rating? { openRows?[String(row)] ?? nil }
    func games(at slot: String) -> Int { played?[slot] ?? 0 }
    /// [in possession, out of possession] words for a card, e.g. ["accomplished", "unconvincing"].
    func familiarity(at slot: String) -> [String] { familiarity?[slot] ?? ["ineffective", "ineffective"] }
    var isLoanedOut: Bool { location == "loan_out" }
    var isInjured: Bool { status.injury != nil }
    var isSuspended: Bool { status.suspendedMatches != nil }
    func has(_ token: String) -> Bool { status.tokens.contains(token) }
}

/// The engine's career archive: every first-team result since you took each job, the club's net transfer money per
/// month (the save has no single fees), and each player's best System ★ while you coached him.
struct Career: Decodable, Sendable {
    struct Match: Decodable, Sendable, Identifiable {
        let date: String
        let season: String
        let club: String
        let comp: String
        let opp: String
        let home: Bool
        let gf: Int
        let ga: Int
        var id: String { "\(date)|\(opp)|\(comp)" }
        var res: String { gf > ga ? "W" : gf < ga ? "L" : "D" }
        var year: String { String(date.prefix(4)) }
    }
    struct Money: Decodable, Sendable {
        let club: String
        let month: String   // "2026-01"
        let net: Double
    }
    struct Coached: Decodable, Sendable, Identifiable {
        let uid: Int
        let name: String?
        let club: String?
        let peak: Double?
        let slot: String?
        let peakDate: String?
        let apps: Int
        let goals: Int
        let assists: Int
        var id: String { "\(club ?? "")|\(uid)" }
    }
    let manager: String?
    let matches: [Match]
    let money: [Money]
    let players: [Coached]
}
