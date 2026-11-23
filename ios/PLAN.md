# Squad Report for iPhone: plan

A native SwiftUI app that shows the same squad report as the web app, built for the phone instead of squeezed onto it.
The Mac still does the reading: `fmsave` is Python, and FM saves live on the Mac. The app talks to the live server
over home Wi-Fi and keeps the last report on the phone, so it still opens on the bus.

His rules carry over unchanged: no CA/PA or hidden attributes (potential stars only, ≤23, as stars), no player or
transfer recommendations, "what's working" only from the game's visible data, every status visually distinct.

## How the pieces fit

```
FM27 save ──► Mac: fm27_squad_report.py (live server, :8027)
                 ├─ /app          web app (as now)
                 ├─ /api/report   the report as JSON   ◄── new
                 └─ /api/status   version + building    ◄── new
                        ▲
                        │ home Wi-Fi, key in a header
iPhone: Squad Report app ── cached copy on the phone (opens anywhere)
                        └─ widget (league position, form, next fixture)
```

Not a web view wrapper. That would be the current site with an icon, which the home-screen app already does.

## Phase 0: the Mac side (can be done now, no Mac needed)

- `GET /api/report`: the report as JSON from an explicit whitelist of fields, never the raw `build()` dict, so nothing
  hidden can leak by accident. Dates as ISO strings, star values as numbers, statuses as fixed strings.
- `GET /api/status`: `{version, building, step, error}`, same as `/status`.
- Auth: the phone key from `data/phone.json`, sent as an `X-FM27-Key` header (no cookies in a native app).
- `demo/build_site.py` also writes `ios/Fixtures/report.json` from the fake save, for SwiftUI previews and tests.
- Tests in Python: the JSON round-trips, carries no CA/PA field, and is refused without the key.

## Phase 1: skeleton and pairing

- Project generated from a text file (`ios/project.yml`, XcodeGen) so it lives in git cleanly; iOS 18+, SwiftUI,
  Swift 6, no third-party packages.
- Pairing: first launch opens the camera (VisionKit's scanner) and reads the same QR code the Mac already shows
  behind the phone icon. The app keeps the host and key in the Keychain.
- Info.plist: local network usage text and `NSAllowsLocalNetworking`, which plain http on Wi-Fi needs.
- `ReportStore`: fetches, decodes, saves the last good report to disk, polls `/api/status` while open, and shows
  "Updated 2 min ago" or "Can't reach your Mac, showing Saturday's report".
- Tab bar: Home · Team · Tactics · Transfers · More, with the same counts as the web app.
- First real screen: Home (club, position, form, news) and the Squad list.

## Phase 2: Team

- Best XIs: the pitch drawn with SwiftUI shapes, both XIs, tap a player for his card.
- Positions: the depth chart, red/amber positions first, the status markers as SF Symbols plus colour.
- Squad list: native `List` with search, status filters and folding groups, swipe-free (nothing to act on).

## Phase 3: Tactics, Transfers, Stats

- Tactical fit with the league-rank strips; role by role as a pitch picker.
- Training: the week as a horizontal schedule.
- Transfers: the "Coming up" timeline.
- Stats: Swift Charts for apps and ratings, tables that sort.

## Phase 4: extras

- Looks: Original plus A to E as SwiftUI themes (colours and the same OFL fonts bundled), chosen in More.
- Widget: league position, last five results, next fixture, from the cached report.
- Sandbox: the line-up builder with a Swift port of the Hungarian algorithm. Last, because it's the biggest screen.

## Phase 5: on his phone

- Build and run in the simulator, screenshot every screen in light and dark, check Dynamic Type and VoiceOver labels.
- Install over the cable with his Apple ID (free account: reinstall every 7 days; paid account removes that).

## What he does once

1. Sign into his Apple ID in Xcode (Settings → Accounts).
2. `brew install xcodegen`.
3. Plug the iPhone in once and tap Trust.
4. Connect the Mac to a Claude Code session (Remote Control) so builds, simulator and installs run there.

## Open questions

- Which looks should the app carry: all six, or just his favourite?
- Widget on the home screen, the lock screen, or both?
- Sandbox in the app, or keep it a big-screen thing?
