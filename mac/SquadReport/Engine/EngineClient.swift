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

    /// The web app, for pages the Mac app doesn't draw yet.
    func webURL(route: String) -> URL {
        URL(string: "http://localhost:\(EngineClient.port)/app#\(route)")!
    }

    private func fetch(_ request: URLRequest) async throws -> (Data, URLResponse) {
        do { return try await Self.session.data(for: request) } catch { throw Problem.notRunning }
    }
}
