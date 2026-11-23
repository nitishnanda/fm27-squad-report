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
    let finances: Finances
    let players: [Player]
    let targets: [Player]
    let xi1: [XISlot]
    let xi2: [XISlot]
    let xiLevel: Double?
    let verdicts: [Verdict]
    let performance: Performance
    let news: [NewsItem]
    let notes: [String]

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
        let ip: String
        let oop: String
        let ipRole: String
        let oopRole: String
    }
    let name: String
    let style: String?
    let rows: [Row]

    /// "4-2-3-1 Gegenpress", or just the shape for an engine that doesn't send the style yet.
    var title: String { [name, style].compactMap { $0 }.joined(separator: " ") }
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
    let record: Record?
    let form: [Result]
    let leagueName: String?
    let leagueSize: Int?
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

    var id: Int { uid }

    private enum CodingKeys: String, CodingKey {
        case uid, name, age, youth, value, wage, contractEnd, expiring, positions, best, system, abilityBest
        case potential, trend, stats, status
        case location = "where"
    }

    func rating(at slot: String) -> Rating? { system[slot] ?? nil }
    var isInjured: Bool { status.injury != nil }
    var isSuspended: Bool { status.suspendedMatches != nil }
    func has(_ token: String) -> Bool { status.tokens.contains(token) }
}
