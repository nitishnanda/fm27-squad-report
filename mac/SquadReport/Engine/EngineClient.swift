import Foundation

/// /api/status: how the engine is doing. `step` follows BUILD_STEPS while a save is being read.
struct EngineStatus: Decodable, Sendable, Equatable {
    let schema: Int?
    let version: String
    let building: Bool
    let step: Int
    let steps: [String]
    let error: String
    let ready: Bool
}

/// Talks to the engine on this Mac. The API only answers 127.0.0.1 with its own Host header.
struct EngineClient: Sendable {
    static let port = 8027
    let base = URL(string: "http://127.0.0.1:\(EngineClient.port)")!

    private static let session: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.timeoutIntervalForRequest = 20
        config.waitsForConnectivity = false
        return URLSession(configuration: config)
    }()

    enum Problem: Error {
        case notRunning
        case notAnEngine       // something else answers on 8027, e.g. an older copy without /api
        case notReady
    }

    func status(timeout: TimeInterval = 3) async throws -> EngineStatus {
        var request = URLRequest(url: base.appending(path: "api/status"))
        request.timeoutInterval = timeout
        let (data, response) = try await fetch(request)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw Problem.notAnEngine }
        do { return try JSONDecoder().decode(EngineStatus.self, from: data) } catch { throw Problem.notAnEngine }
    }

    func reportData() async throws -> Data {
        var request = URLRequest(url: base.appending(path: "api/report"))
        request.timeoutInterval = 60
        let (data, response) = try await fetch(request)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw Problem.notReady }
        return data
    }

    /// The links his iPhone can use (this Mac only): Bonjour name and IP, each with the phone key.
    func phone() async throws -> PhoneInfo {
        var request = URLRequest(url: base.appending(path: "api/phone"))
        request.timeoutInterval = 5
        let (data, response) = try await fetch(request)
        guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw Problem.notAnEngine }
        return try JSONDecoder().decode(PhoneInfo.self, from: data)
    }

    /// A player in the save found by name or club: public facts only, never ratings.
    struct Found: Decodable, Sendable, Identifiable {
        let uid: Int
        let n: String
        let c: String
        let a: Int?
        let p: String
        var id: Int { uid }
    }
    struct FoundList: Decodable, Sendable {
        let ready: Bool
        let total: Int
        let items: [Found]
    }

    func searchPlayers(_ query: String) async throws -> FoundList {
        var parts = URLComponents(url: base.appending(path: "players"), resolvingAgainstBaseURL: false)!
        parts.queryItems = [URLQueryItem(name: "q", value: query)]
        let (data, _) = try await fetch(URLRequest(url: parts.url!))
        return try JSONDecoder().decode(FoundList.self, from: data)
    }

    /// Adds scouting targets (the engine writes them to scouting.txt and reads the save again).
    func addTargets(_ uids: [Int]) async throws {
        var request = URLRequest(url: base.appending(path: "scouting"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["action": "add_uids", "uids": uids])
        let (data, _) = try await fetch(request)
        struct Answer: Decodable { let ok: Bool; let error: String? }
        let answer = try JSONDecoder().decode(Answer.self, from: data)
        if !answer.ok { throw NSError(domain: "SquadReport", code: 1, userInfo: [NSLocalizedDescriptionKey: answer.error ?? "failed"]) }
    }

    /// The web app, for pages the Mac app doesn't draw yet.
    func webURL(route: String) -> URL {
        URL(string: "http://localhost:\(EngineClient.port)/app#\(route)")!
    }

    private func fetch(_ request: URLRequest) async throws -> (Data, URLResponse) {
        do { return try await Self.session.data(for: request) } catch { throw Problem.notRunning }
    }
}

struct PhoneLink: Decodable, Sendable, Identifiable {
    let kind: String     // "name" (Bonjour, stays the same) or "ip"
    let url: String
    var id: String { kind + url }
}

struct PhoneInfo: Decodable, Sendable {
    let on: Bool
    let links: [PhoneLink]
}
