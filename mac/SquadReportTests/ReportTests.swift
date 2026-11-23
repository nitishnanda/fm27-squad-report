import Foundation
import Testing
@testable import SquadReport

/// The made-up report that `demo/build_site.py` writes from the fake save.
private func fixture() throws -> Data {
    let url = URL(filePath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
        .appending(path: "Fixtures/report.json")
    return try Data(contentsOf: url)
}

@Suite("The report feed")
struct ReportFeedTests {
    @Test func decodesTheFixture() throws {
        let report = try Report.decode(try fixture())
        #expect(report.schema == Report.supportedSchema)
        #expect(report.club.name == "Liverpool")
        #expect(!report.players.isEmpty)
        #expect(report.xi1.count == 11)
        #expect(report.formation.rows.count == 11)
        #expect(report.verdicts.contains { $0.needsWork })
    }

    @Test func readsTheSchemaOfANewerFeed() {
        let newer = Data(#"{"schema": 99, "club": {}}"#.utf8)
        #expect(Report.schema(of: newer) == 99)
    }

    @Test func everyPlayerLandsInOneSquadGroup() throws {
        let report = try Report.decode(try fixture())
        let rows = SquadGroups.rows(report)
        #expect(rows.count == report.players.count)
        #expect(Set(rows.map(\.id)).count == rows.count)
        #expect(rows.contains { $0.group == SquadGroups.titles.firstIndex(of: "Out on loan") })
    }

    @Test func statusesStayDistinct() throws {
        let report = try Report.decode(try fixture())
        let kinds = Set(report.players.flatMap { PlayerStatus.of($0).map(\.kind) })
        // the fake save has every kind of move and injury in it
        #expect(kinds.isSuperset(of: [.transferIn, .transferOut, .loanOut, .injuredShort, .injuredLong, .suspended]))
        for p in report.players where p.status.injury?.long == true {
            #expect(PlayerStatus.of(p).contains { $0.kind == .injuredLong })
        }
        // injury badges keep it short; the injury itself is in the hover text
        let gomez = try #require(report.players.first { $0.name.hasSuffix("Gomez") })
        let injury = try #require(PlayerStatus.of(gomez).first { $0.kind == .injuredShort })
        #expect(injury.brief == "13 days")
        #expect(injury.detail.contains("Hamstring"))
    }
}

@Suite("Formats match the web app")
struct FormatTests {
    @Test func money() {
        #expect(Fmt.money(1_347_000_000) == "£1.35bn")
        #expect(Fmt.money(44_000_000) == "£44m")
        #expect(Fmt.money(2_600_000) == "£2.6m")
        #expect(Fmt.money(24_000) == "£24k")
        #expect(Fmt.money(nil) == "–")
    }

    @Test func wages() {
        #expect(Fmt.wage(5_170_000) == "£5.17m")
        #expect(Fmt.wage(229_000) == "£229k")
    }

    @Test func halfStars() {
        #expect(Fmt.half(4.24) == 4.0)
        #expect(Fmt.half(4.25) == 4.5)
        #expect(Fmt.half(4.74) == 4.5)
        #expect(Fmt.stars(4.5) == "4.5")
        #expect(Fmt.stars(3.0) == "3")
    }

    @Test func dates() {
        #expect(Fmt.day("2026-11-22") == "22 Nov 2026")
        #expect(Fmt.month("2027-06-30") == "Jun 2027")
        #expect(Fmt.month("2027-09-01") == "Sep 2027")
        #expect(Fmt.ordinal(1) == "1st")
        #expect(Fmt.ordinal(12) == "12th")
        #expect(Fmt.ordinal(23) == "23rd")
        #expect(Fmt.injury(days: 13) == "13 days")
        #expect(Fmt.injury(days: 28) == "4 wks")
    }

    @Test func routesMatchTheWebApp() {
        #expect(Route(webHash: "team/squad") == .squad)
        #expect(Route.fit.webHash == "tactics/fit")
        #expect(Route.training.section == .tactics)
    }
}
