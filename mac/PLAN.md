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
Release, and `mac/build.sh install` puts it in `/Applications` and opens it. Signed "to run locally", so no Apple ID is needed to build it.

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

## Phase 4: Mac extras ✅ done

His answers: keep the Dock icon *and* add the menu bar item; carry Original + E (Glass + scoreboard) only; keep
`Run Squad Report.command` as a backup. Built: one main `Window` (closing it keeps the app in the Dock and menu bar),
`MenuBarExtra` with Up to date / Reading your save, step n of 8 / New report ready / Engine problem and Open, Reload,
Settings, Quit; a notification when a *new save* has been read while the app isn't in front (the save stamp is the first
part of the engine version, so restarts and app updates don't count); Settings (project folder, open at login via
`SMAppService`, notifications status, potential stars on/off, look, phone access on/off with QR codes from the new
loopback-only `GET /api/phone`; turning phone access off restarts our engine with `--mac-only`); the Glass + scoreboard
look (`Theme`, `.themed()`, `.panel()`, font roles; the four OFL woff2 fonts ship in the app and are registered before
the first window); and the native Sandbox (drag players onto the pitch or click a slot, statuses, scouting targets with
a search sheet that adds them via `POST /scouting`, Swift port of the Hungarian algorithm, saved per save).


- Menu bar item: "Up to date" / "Reading your save, step 3 of 8" / "New report ready", with Open and Quit.
- Notification when a new save has been read ("Report updated: 22 Nov 2026").
- Settings window: Look, potential stars on/off, phone access on/off with the QR code for his iPhone, open at login.
- Looks: Original plus A to E as SwiftUI themes, with the same OFL fonts bundled.
- Sandbox: drag players onto the pitch, with a Swift port of the Hungarian algorithm. Last, because it's the biggest screen.

## Phase 5: finish ✅ done

- Every page checked in light and dark (and Glass), at the smallest window (900×600) and full screen (1920×1050).
  Fixed for narrow windows: Squad list key figures wrap (5 → 3 + 2) and its status filter becomes a pop-up; Tactical fit
  puts the style chips under the part picker; Sandbox's score bar goes onto two rows and its columns shrink; the Best XIs
  "Second XI" title no longer wraps.
- VoiceOver: each Sandbox pitch slot is one element ("ST: Isak", "4.5 stars, natural here", "Pick who plays here");
  scouting search results are real checkboxes instead of tap-only rows; decorative chevrons are hidden; the startup
  checklist says done / in progress / to do. Keyboard: everything is a button, menu or picker, plus ⌘1–6 and ⌘[ ⌘].
- Notifications: Settings asks again while macOS hasn't decided, links to System Settings when they're off, and has a
  Send Test Notification button.
- Installed: `mac/build.sh install` builds Release into `/Applications/Squad Report.app` (Launchpad, Spotlight, open at
  login). Dev builds live in `mac/build/DerivedData.noindex` so Spotlight only shows the installed copy.
- Python bundled: the app carries its own engine (below), so it no longer needs the project folder.

## Python inside the app ✅ done

- `Contents/Resources/Engine/python`: a relocatable python-build-standalone CPython 3.13 (trimmed: no Tk, IDLE,
  headers), with fmsave and backports-zstd (fmsave needs it before 3.14). `Engine/engine`: fm27_squad_report.py + assets.
  ~70 MB app. `mac/vendor_python.sh` prepares `mac/build/vendor/python` once (from uv's local copy of 3.13, fmsave from
  the project's .venv, the backports-zstd wheel kept in `mac/build/vendor/wheels`); the "Bundle the engine" build phase
  (`mac/bundle_engine.sh`) copies it and the current script into every build before signing.
- The engine writes to `~/Library/Application Support/Squad Report` (`SQUAD_REPORT_HOME`): data/ (star history, club,
  phone key), scouting.txt, Reports/ (with an `assets` link so saved pages still render). The first launch copies
  history, club, phone key and scouting list over from the project folder, once, never overwriting.
- fmsave: the app's copy works offline; once a day the app asks PyPI for the latest version and, if newer, installs it
  into `Application Support/Squad Report/python-packages` (first on the import path; dropped if it won't import).
- Settings › General › Engine: "Run the engine from a project folder instead" switches back to the old way (the folder's
  script and .venv), for working on the script. The .command still works and still uses the project folder's files.

## Phase 6 ✅ done: match the web app (from a code comparison of the web app and the Mac app, 24 Nov 2026)

Done: 1 Can play chips (any/all, Clear filters) · 2 Mentoring part (`mentoring_groups`, `training_advice.mentoring`) ·
3 "Doing it yourself" folded under What to change (`HOWTO_STEPS`/`HOWTO_CHEAT`, `training_howto`) · 4 × on scouting-list
targets (`target_source`, `target_club` in the feed; the demo build has one target of each kind) · 5 position + age pop-ups
in Find a scouted player · 6 Key popover in the toolbar + Help › Status Key window (⌘/) · 7 `Pitch3D` (Best XIs 3D/Flat,
3D best XI in the Home hero with Open best XIs) · 8 all six looks as `Theme`s with their fonts, ⌘L / ⇧⌘L.

Every web page has a native Mac page now, but these web features have no Mac version yet. Checked against
`fm27_squad_report.py` (the web app) and `mac/SquadReport`. In order of how much he'd notice:

1. **Squad list: filter by position.** The web squad list has position chips (GK, LB, CB, …, ST) with "any of these" /
   "all of these" and "Clear filters", on top of the status filters and search. The Mac squad list has status filters
   and search only. Use `positions.natural` + `positions.accomplished` from the feed.
2. **Training: Mentoring.** Web `training_page()` (`tr-mentor`): when the squad has young players (≤21) with
   Determination ≤11 and senior pros (26+, not youth) with Determination ≥16, it names both groups (up to 8 and 4) and says
   how to set up a mentoring group (Training → Mentoring → Create New Mentoring Group). Determination is visible, so it's
   allowed. Add it to the feed (`training_advice.mentoring`) so the rule lives in Python once, and show it as its own part.
3. **Training: "Doing it yourself next time".** Web `tr-howto`: a folded explainer, "how the advice above is worked out
   · seven steps and a cheat sheet" (symptom → which weeks/sessions → which attributes). Static text: send it in the feed
   (`training_howto`) rather than copying it, so the two can't drift. Show it folded (DisclosureGroup).
4. **Sandbox: remove a scouting target.** The web Sandbox has a × on targets that came from scouting.txt ("Remove from
   scouting.txt"), which POSTs `/scouting` `{"action": "remove", "name": …}`. The Mac app can add targets but not remove
   them. Targets from FM's Squad Planner can't be removed this way (the save controls those), same as the web.
5. **Sandbox player search: position and age filters.** The web picker has a position and an age filter (`GET /players`
   takes `pos` and `age`). The Mac search is name/club only. Keep his rule: public facts only (age, positions, club),
   ordered by name match, never by quality.
6. **A status key.** The web app has a "Key" popover with every badge (transfer in/out, loan in/out, arranged, short and
   long injury, suspended, contract ending) and the N/A/C/X letters. The Mac app explains things on hover and Positions
   has its own key, but there's nowhere to see them all. A Help menu item or toolbar popover would do.
7. **Best XIs 3D view (he wants it).** The web Flat/3D switch: two `pitch3d()` pitches you can drag to tilt and turn,
   cards standing on the pitch. Add a Flat / 3D segmented control to Best XIs (remember the choice only when he clicks it,
   like the web), and the same 3D pitch with an **"Open best XIs" button** in the Home hero (web `overview()`, "Your best
   XI. Drag to rotate"). SwiftUI: `rotation3DEffect` + a drag gesture, with a sensible clamp on the angles; flat when
   Reduce Motion is on.
8. **All the web looks (he wants them).** The Mac app has Original + E (Glass + scoreboard). Add A Matchday programme,
   B Floodlit glass, C Scoreboard and D Sticker album as `Theme`s, built from the web looks so they match:
   `THEME_A`, `B_FRAME`/`B_DATA`/`B_PITCH`/`THEME_B_TOKENS`, `C_FRAME`/`C_DATA`/`THEME_C_TOKENS`, `THEME_D`, plus
   `LIGHT_FIX` and `kit_on_light()` for the light ones (A and D: readable inks on paper, the club colour darkened for
   paper). Fonts are the OFL files in `assets/font-*.woff2` (license in `assets/FONTS-LICENSE.txt`): Archivo,
   Newsreader, Martian Mono (A), Bricolage, Hanken, JetBrains Mono (B), Geist, Geist Mono, Doto (C), Big Shoulders,
   Schibsted Grotesk (D). Settings › Look lists all six with the web's names and one-line descriptions (`THEMES`), and
   ⌘L / ⇧⌘L cycles like the web's L key. Check every page in each look at 900×600 and full screen (light looks in dark
   mode too: they stay light), and keep the Doto decimal fix and the status colours distinct in every look.

Left out on purpose (don't add): the web home page / About, the Positions "U21" tag (the age column shows it), and the training "Focus" options (dropped idea).
When a part is done: screenshots in demo mode or the real save (never the Phone settings), tests, commit and push.

## Phase 7 ✅ done: motion (after Phase 6, so the looks and 3D pitch exist)

Done: all durations in `Motion` (Views/Components/Motion.swift), all off with Reduce Motion. 1 `PageEntrance`: a new page
fades in and rises 10 pt over 0.25 s (on appear, so the old page never lingers on top) · 2 the squad table animates on any
filter change · 3 `LoaderBody`: pitch lines draw in, a scan line sweeps, the current step's arc spins, done steps pop a
tick; `ClubWipe` slides the club colour away when the first report arrives · 4 `PulseDot` on the status pill while a save is
read · 5 looks fade (Settings, ⌘L / ⇧⌘L, and `Themed` animates on the look) · 6 Back / Forward toolbar buttons and ⌘[ / ⌘]
(page history in AppModel); previous/next page in a section moved to ⌥⌘[ / ⌥⌘]. Checking motion: launch with
`-slowMotion 10` (everything 10x slower), `-demoLoader YES` (plays the loader and the wipe in demo mode), `-demoWipe YES`.

The web app animates a lot more than the Mac app, which only animates the Sandbox and "Show all" on Positions and
Tactical fit. Port these, kept quick and subtle (a Mac app should feel calmer than a website), and turn every one off
when Reduce Motion is on (`@Environment(\.accessibilityReduceMotion)`):

1. **Page changes.** Web `show()` in APP_JS: the new page fades in and rises 14px over 0.38s. On Mac, when the sidebar
   selection changes, fade the detail view in with a small rise (~0.25s), not a slide.
2. **Squad list filters.** Web uses GSAP Flip: rows glide to their new places and new rows fade in. On Mac, change the
   filter state inside `withAnimation(.snappy)` so rows move instead of jumping (if `Table` won't animate rows, a short
   cross-fade of the table is fine).
3. **The loader.** Web `boot_html()` / `BOOT_CSS` / `BOOT_JS`: the pitch lines draw themselves in (`bdraw`), a scan line
   sweeps the pitch while it waits (`bscan`), the current step's circle spins, done steps tick, and on launch a
   club-colour panel with the crest slides up and away. The Mac `EngineGate` loader is a plain progress view: give it
   the drawn pitch (`.trim` on the pitch shapes), the scan line and the step circles, and the club panel wipe when the
   report is ready. It should wear the current look like the web loader does (`BOOT_LOOKS`).
4. **The live status pill.** Web `.ah-live.busy` pulses amber (`lpulse`) while a save is being read. Pulse the Mac
   pill's dot the same way while `/api/status` says building; still when up to date.
5. **Changing looks.** The web cross-fades the whole page (View Transitions). On Mac, animate the look change
   (`withAnimation(.easeInOut(duration: 0.3))` around the `@AppStorage("look")` change) so it fades instead of snapping.
6. **Back and forward.** The web gets browser history for free. Give the Mac app a page history: Back/Forward
   toolbar buttons and ⌘[ / ⌘] (moving previous/next section to another shortcut if needed), like Finder or Safari.

Left out on purpose: sideways slides between Tactical fit / Training parts (feels webby on a Mac) and the scrolling
news ticker (the Mac "Latest" list on Home replaces it). The 3D pitch tilt-in is part of Phase 6, item 7.

## What he does once

1. Install Xcode, then sign into his Apple ID (Xcode → Settings → Accounts).
2. `brew install xcodegen`.
3. Connect the Mac to a Claude Code session (Remote Control) so builds and test runs happen there.

## Open questions (answered)

- Dock icon or menu bar only? Both.
- Which looks? Original + E (Glass + scoreboard).
- Keep `Run Squad Report.command`? Yes, as a backup.
