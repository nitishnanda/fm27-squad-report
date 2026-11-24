# Squad Report for Mac: plan

A native SwiftUI Mac app that replaces double-clicking `Run Squad Report.command` and reading the report in a browser.
It sits in the Dock (and the menu bar), notices new FM saves, and shows the report in proper Mac windows: a sidebar,
real sortable tables, keyboard shortcuts, notifications.

The Python engine stays. `fmsave` is Python and it's the only thing that reads FM27 saves, so the app runs
`fm27_squad_report.py` in the background and draws what it produces. The web app keeps working for his iPhone.

His rules carry over unchanged: saves are only ever read, no CA/PA or hidden attributes (potential stars only, ≤23,
as stars), no player or transfer recommendations, "what's working" only from the game's visible data, every status
visually distinct.

## How the pieces fit

```
Squad Report.app (SwiftUI)
 ├─ starts the engine:  python fm27_squad_report.py --headless   (no browser, no Terminal window)
 ├─ reads              http://127.0.0.1:8027/api/report  (JSON)  ◄── new
 ├─ follows            /api/status  (version, building, step)   ◄── new
 └─ shows              windows, menu bar item, notifications
Engine (unchanged job) ── watches the save folder, rebuilds, still serves /app to his iPhone over Wi-Fi
```

On a Mac, an app you build yourself in Xcode keeps running. There's no 7-day limit like on the iPhone, and no paid
developer account is needed for his own use.

## Phase 0: the engine side ✅ done

- `--headless`: start the live server without opening a browser or printing the Terminal instructions.
- `GET /api/report`: the report as JSON from an explicit whitelist of fields, never the raw `build()` dict, so nothing
  hidden can leak by accident. Dates as ISO strings, stars as numbers, statuses as fixed strings.
- `GET /api/status`: `{version, building, step, steps, error}`.
- Local only: the API answers 127.0.0.1, never the network (the phone keeps using `/app` with its key).
- `demo/build_site.py` also writes `mac/Fixtures/report.json` from the fake save, for SwiftUI previews and tests.
- Python tests: the JSON round-trips, has no CA/PA field, and the API refuses network requests.

## Phase 1: the app shell ✅ done (Home and Squad list native; other pages open in the web app for now)

Build and run: `mac/build.sh` (generates the project with XcodeGen, builds Debug, opens the app). `mac/build.sh test` runs the
Swift tests (fixture decoding, his-rules checks on statuses, formats that match the web app); `mac/build.sh release` builds
into `mac/build/Release/`. Signed "to run locally", so no Apple ID is needed to build it.

What's in it (`mac/SquadReport/`): `Engine/` (Python setup like the .command, the engine process, the API client),
`Report/` (feed models, `ReportStore` with the on-disk cache, formats), `App/` (model, routes, menus), `Views/`.
If an engine is already running on 8027 (the .command), the app uses it instead of starting a second one.


- Project from a text file (`mac/project.yml`, XcodeGen) so it lives in git cleanly. macOS 15+, SwiftUI, Swift 6,
  no third-party packages.
- Not sandboxed: the saves sit in `~/Library/Application Support/Sports Interactive`, which a sandboxed app can't read
  without asking every time. Fine for an app that never leaves his Mac.
- First launch: pick the `fm27-squad-report` folder once (kept as a bookmark). The app runs the same setup the
  `.command` does (`.venv`, install or update `fmsave`), with a progress view instead of Terminal text.
- `Engine`: starts and stops the Python process with the app, restarts it if it crashes, shows its errors in plain words.
- `ReportStore`: decodes the JSON, keeps the last good report on disk so the app opens instantly, follows rebuilds.
- Window: `NavigationSplitView` sidebar with Home · Team (Best XIs, Positions, Squad list) · Tactics (Tactical fit,
  Training) · Sandbox · Transfers · Stats. ⌘1 to ⌘6 jump between sections.
- The loader: the same eight build steps as the web app, as a native progress view.
- First real screens: Home and the Squad list.

## Phase 2: Team ✅ done

Best XIs (two SwiftUI pitches, player card popover), Positions (cards ordered red → amber → green → grey, status
markers as SF Symbols + colour, ⚠ for a weak phase, key with hover help) and the Squad list's native Table extras
(resize, reorder and hide columns by right-clicking a header, remembered; folding groups, "Out on loan" folded at
first). The feed gained `formation.rows[].label/x/y/ip_role_name/oop_role_name`, `positions` (cards, played_many,
youth_per_card, shown) and per-player `familiarity` (FM's words per card, never the /20 numbers).


- Best XIs: the pitch drawn in SwiftUI, both XIs, click a player for his card in a popover.
- Positions: the depth chart, red/amber positions first, status markers as SF Symbols plus colour.
- Squad list: a native `Table`: sort by any column, resize and hide columns, search, status filters, folding groups.

## Phase 3: Tactics, Transfers, Stats ✅ done

Tactical fit (How it's going with league-rank strips and "Putting it together", player by player, the style breakdown,
who doesn't fit, role by role as a pitch picker), Training (the week as a schedule grid, next weeks, what to change,
individual plans, prospects), Transfers (the "Coming up" timeline and the move/loan columns) and Stats (season leaders,
two Swift Charts and sortable tables). Only Sandbox still opens in the web app. The feed gained formatted metric
values, `insights`, per-player `group_name`/`value_text`, role key attributes, `style`, attribute labels/abbreviations,
session names per training calendar, `training_advice` and `plans` (FM's words for position work, never numbers).


- Tactical fit with the league-rank strips; role by role as a pitch picker.
- Training: the week as a schedule grid.
- Transfers: the "Coming up" timeline.
- Stats: Swift Charts plus sortable tables.

## Phase 4: Mac extras

- Menu bar item: "Up to date" / "Reading your save, step 3 of 8" / "New report ready", with Open and Quit.
- Notification when a new save has been read ("Report updated: 22 Nov 2026").
- Settings window: Look, potential stars on/off, phone access on/off with the QR code for his iPhone, open at login.
- Looks: Original plus A to E as SwiftUI themes, with the same OFL fonts bundled.
- Sandbox: drag players onto the pitch, with a Swift port of the Hungarian algorithm. Last, because it's the biggest screen.

## Phase 5: finish

- Check every screen in light and dark, at small and large window sizes, with VoiceOver labels and keyboard only.
- Archive it into `/Applications` so it's a normal app in Launchpad and Spotlight.
- Later, if wanted: bundle Python inside the app so it no longer needs the project folder.

## What he does once

1. Install Xcode, then sign into his Apple ID (Xcode → Settings → Accounts).
2. `brew install xcodegen`.
3. Connect the Mac to a Claude Code session (Remote Control) so builds and test runs happen there.

## Open questions

- Keep the Dock icon, or live only in the menu bar until he opens the window?
- Which looks should the app carry: all six, or just his favourite?
- Keep `Run Squad Report.command` as a backup, or retire it once the app works?
