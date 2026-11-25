# FM27 Companion — handoff notes (formerly "Squad Report"; file, data-folder and bundle-ID names kept)

Nitish's tool for his Football Manager 27 save (Liverpool). It reads his newest save **read-only** and builds a
tabbed HTML report. Everything is in `fm27_squad_report.py` (one file, ~5,300 lines) plus `assets/` (GSAP, Lenis, crest, theme fonts). Built in a claude.ai
session; these notes carry that context over.

## How it runs
- The project lives in `~/fm27-squad-report` (out of ~/Downloads, which macOS guards; the Mac app follows it by bookmark).
- `Run Squad Report.command` creates `.venv`, installs/upgrades `fmsave` (PyPI, reads FM26/27 saves), runs the script.
- Default is **live mode**: a server on `http://localhost:8027`. A watcher rebuilds when a newer save
  appears (waits `LIVE_SETTLE_SECONDS` after the save is written) and **restarts itself when this script changes**
  (only once the new file compiles), so edits show up on a browser refresh. `--once` = old single-report mode.
- Output also goes to `Reports/` (dated copy + `latest.html`). `data/history.json` holds the star anchors and trends.
  Reset it to `{}` if the star scale changes.
- One build takes ~25–30 s on the real save (player match stats + season stats + team match stats are the slow reads).
- Saves live under `~/Library/Application Support/Sports Interactive/...`. That's a protected location for the Claude
  device bridge, so `candidate_saves()` finds them at run time instead.

## His rules (don't break these)
- **No spoilers:** never show CA/PA or hidden attributes. Stars come from visible attributes only. The one exception
  he asked for is **potential stars** (from hidden PA, shown as stars only, players ≤23 who could grow ≥1★,
  switchable with `SHOW_POTENTIAL`). Scouting targets never get potential.
- **No player recommendations / transfer suggestions.** Only which positions need strengthening or more depth.
- "What's working" analysis must come from the game's own visible data (match stats, league table), not hidden info.
- Statuses must stay visually distinct: loan in/out, arranged vs current, transfer in/out, short/long injuries.
- He likes a casual, chill tone (Gen Z slang, emojis, calls you "son"/"folk"; never "bradar").

## Tactic (hard-coded in `FORMATION`)
4-2-3-1 Gegenpress. Rows are `(slot, IP position, OOP position, IP role, OOP role)`:
GK BGK/SK · LB FB/FB · CB CB/CB · CB BCB/CB · RB (WBR in possession) WB/FB · DM DLP/PDM · DM DM/DM ·
LW (AML/ML) IF/WMF · AM SS/AM · RW (AMR/MR) IW/WMF · ST CFD/CFD. `STYLE_KEYS` = the 9 Gegenpress attributes.

## Rating model (short version)
- Visible-attribute position model (`VISIBLE_MODEL`, from fmsave's scouting weights) ranked against every natural
  in the save, blended with role key attributes (`ROLE_WEIGHT`) and style (`STYLE_WEIGHT`), minus a familiarity
  penalty per phase. Strict eligibility (best XI, verdicts): 15+ familiarity in one phase and 5+ in the other.
  `open_=True` rates everyone everywhere (codes N/A/C/X) for the Sandbox.
- Stars are squad-relative: 3rd-best senior = `STAR_TOP`, median = `STAR_MID`. "System ★" = for his tactic;
  "Ability ★" = position only. XIs via the Hungarian algorithm (Python and a JS copy in the Sandbox).

## Site structure (live mode)
- Branding: the app has its own identity (`APP_LOGO_SVG`, `assets/app-logo.svg`, "FM27 Companion", the graphite glass tactics-clipboard icon (his own Icon Composer file, `mac/SquadReport/Resources/AppIcon.icon`; the web mark is the flat clipboard version), neutral "tactics board"
  green-black + pitch green `#1C7F46` (white text on it; `--brand-hi` `#4FC77F` for green text on dark). He dropped the old yellow, so keep it out). The user's club only drives accents: `club_identity(name)` gives kit colour, readable
  ink and crest markup (Liverpool = Liver bird assets; any other club = initials shield). FM saves hold no club colours,
  so `CLUB_COLOURS` covers well-known clubs and other names get a stable generated colour. `data/club.json` remembers the
  last club so the loader can wear its colours before a save is read; with no club yet it shows the app brand.
- `/` = public home page (`landing_page()`): the same for everyone, no save data. Demo club = Liverpool's real XI from
  22 Nov 2026 with made-up stars (`DEMO_XI`, `DEMO_XI2`). Fake-3D draggable pitch (`pitch3d()`), pinned "What's inside"
  story (GSAP ScrollTrigger + Lenis; pins `.story-in`), does/won't lists, Launch buttons. The four previews are real app
  pages built from demo data (`demo_pages()` → `<iframe srcdoc>` at 1440x945, scaled with `--k`); the point of each step
  is `.focus`, everything else `.blur` (`MINI_CSS`). Custom cursor only over the 3D pitch.
- Launch → green wipe → `/app`. The app shows the loader (`boot_html()`, `BOOT_JS`) only when launched from the home page
  (sessionStorage `fm27-launch`). If the report isn't built yet, `/app` serves `loader_page()`, which follows the real
  rebuild through `/status` (`step` comes from `progress()` calls in `build()` / `make_report()`, labels in `BUILD_STEPS`).
- `/assets/<file>` serves `assets/` (whitelisted names only). Pages reference `../assets/` so `--once` report files work too.
- App navbar = 6 sections (`SECTIONS`): Home · Team (Best XIs, Positions, Squad list) · Tactics (Tactical fit, Training) ·
  Sandbox · Transfers · Stats. Hash routes like `#team/xis`; old `#xis`-style hashes still work. Keys 1–6 and `[` `]`.
- Club news ticker (`ticker_items()`) = real items from the save; pause button, still list under reduced motion.
  Status key lives in the "Key" popover. Best XIs has a Flat/3D switch; squad filters animate with GSAP Flip.
- Crest = the current Liver bird mark from liverpoolfc.com (`assets/liverbird-red.svg` on dark, `liverbird-white.svg` on red/pitch).
- Best XIs: 3D = two `pitch3d()` pitches (draggable), Flat = the detailed card pitches; the choice is saved only when clicked.
- Positions: a depth chart on a pitch (`.pform`, 3 columns: LW ST RW / DM AM CM / LB CB RB / GK), one line per player,
  top `POS_SHOWN` (5) then "Show all"; status, games and weak-phase detail are in the row's hover text and markers.
  The key above it (`positions_key()`) is made of `hint()` items: each explains itself on hover, focus or tap
  (tooltip linked with aria-describedby, kept on screen by `placeTip` in APP_JS).
- Squad list: key figures on top (`squad_kpis`; Contracts ending / On loan / Arranged moves are buttons that set the status
  filter and count exactly what it shows), accent-insensitive name search, groups fold ("Out on loan" starts folded; any
  filter or search unfolds what it finds), sticky table header. Phones hide the `.lo` columns instead of scrolling sideways.
- "Show N more": `more_btn(target, n, what)` + a `.clipped` container whose hidden items have `.xtra` (APP_JS handles it).
  Used for Player by player (first `PERF_CARDS_SHOWN`), the Gegenpress table and the individual plan (best XI first).
- Tactical fit: each working / not-working stat has a league-rank strip (one cell per team). Role by role is a position
  picker on a pitch (ARIA tabs, one role card at a time, opens on the weakest best-XI fit; the XI player per slot comes
  from `R["xi1"]` by row index, not from the `xi` flag, which is per position).
- Training: "Jump to" bar; "Doing it yourself next time" is folded in a `details.fold`.
- Transfers: "Coming up" month-by-month timeline (`deal_timeline`): moves, loans starting/ending, contracts ending; 3+ of
  the same thing on the same day merge into one card.
- Stats: Season leaders key figures (`stat_leaders`, rating needs a third of the top appearance count), apps bars,
  tables sort by any column and have sticky headers.
- Sandbox: one score bar that sticks under the header; roster grouped by a fixed group `g` (squad / Arriving / Away on
  loan, folded) so cards never jump when you change a status. Scouting targets: in live mode a picker searches every
  player in the save by name or club (`PLAYER_INDEX` built in `build()`, `search_players()`, `GET /players`), with
  position/age filters, multi-select and one "Add N" (`POST /scouting` `add_uids`, ~30 s rebuild). It shows public facts
  only (age, positions, club), never ratings or values, and sorts by name match, never by quality.
- `--ahh` = header height (set from `.ah` by a ResizeObserver) for anything sticky under the header.
- Looks (theme switch): "Look" button in the app header opens a popover with 6 radio options (`THEMES`): Original (no CSS,
  pixel-identical to the old design), A Matchday programme (light paper, Archivo + Newsreader + Martian Mono), B Floodlit glass
  (Bricolage + Hanken + JetBrains Mono), C Scoreboard (Geist + Geist Mono, Doto for big numbers), D Sticker album (Big Shoulders +
  Schibsted Grotesk, sections are white sticker panels on a mown pitch), E Glass + scoreboard (B's frame and pitch + C's data layer,
  his pick from the design research). Each look is plain CSS scoped by `scope_css()` to `:root[data-theme="X"]`; E is composed from
  `B_FRAME` + `C_DATA` + `B_PITCH` + `E_GLASS`. The light looks share `LIGHT_FIX` (pastel text turned into readable inks) and use
  `--kit-l` (`kit_on_light()`, the club colour dark enough for paper and white text). Choice is in localStorage `fm27-theme`, applied
  in `<head>` before paint (`LOOK_HEAD_JS`); `L` / `Shift+L` cycles. Fonts are vendored in `assets/font-*.woff2` (OFL, see
  `assets/FONTS-LICENSE.txt`) and only download when a look uses them. The home page has the same Look button and follows the look
  (`LAND_A`…`LAND_D`, E = `LAND_B` + `LAND_E`, in `LANDING_THEME_CSS`; it's club-neutral, so its accent is the pitch green). Its four
  previews get the look CSS copied in from `<style id="looks-css">` by LOOK_JS (`dress()`), so the CSS isn't shipped 4 extra times.
  The launch wipe takes each look's colour. The loader (`boot_html`, both the launch overlay and `loader_page()`) follows the look too:
  `BOOT_LOOKS` → `BOOT_THEME_CSS` (self-contained colours, since the loader page doesn't load THEME_CSS); on phones (≤700px) the
  looks turn the pitch into a faint backdrop so the taller type fits. Original keeps `BOOT_CSS` unchanged.
- Layout is fluid (no max width); `--gutter` scales with the window.
- Phones (≤860px, so small tablets in portrait too) get their own layout, not the desktop squeezed (`PHONE_CSS_RAW`, prefixed
  with `html:not(#_)` by `prefix_css()` so layout wins over every look while the looks keep colours and type; phone-only bits are
  hidden on desktop at the end of APP_CSS). Shell: bottom tab bar Home · Team · Tactics · Transfers · More with icons (`NAV_ICONS`,
  `nav_icon()`) and counts; More is a sheet (`more_sheet()`) with Stats, Sandbox, Look, Key, About; the header shows the section
  name (`#ahTitle`, set in `show()`); a section's pages are a segmented control; Key/Look/More slide up as bottom sheets
  (`@starting-style`). Pages: the ticker becomes a "Latest" list on Home (`ph-news`), Best XIs shows one XI at a time (`.xiseg`,
  `section[data-xi]`), Positions folds its key and puts red/amber positions first, the squad list becomes one card per player,
  chip rows swipe sideways, training's week scrolls, transfers is a vertical timeline, Sandbox says it's quicker on a bigger screen.
  Narrow desktop windows (861–1280px) get a tighter header and the squad list drops extra columns instead of scrolling sideways.
  His real iPhone opens it over home Wi-Fi (Phone access, below).
- Phone access (`PHONE_ACCESS`, off with `--mac-only`): the live server listens on the network (0.0.0.0), but only this Mac
  (loopback) gets in freely. Other devices need the key from `data/phone.json` (`phone_key()`, gitignored, delete it for a new
  one) once via `?k=key`, which sets the `fm27phone` cookie (a year); everyone else gets `PHONE_DENIED` (403). `/assets/` is public
  (scripts, fonts, crest, icons: nothing from the save). Pages served to a phone keep `?k=` in their address (`PHONE_URL_JS`) and
  their manifest link, because a home-screen copy of the app gets its own cookie jar; the manifest's `start_url` then carries the key.
  On the Mac, LIVE_JS fetches `/phone` (loopback only) and adds a phone icon before Look that opens `phone_popover()`: QR codes
  for the `.local` Bonjour name and the IP (`phone_links()`). The QR encoder is built in (`qr_matrix()`, byte mode, ECC M,
  versions 1–10), so there's nothing extra to install. Careful when testing: the server restarts into the real script when
  the file changes, so a test wrapper's patches (and its scratch `PHONE_FILE`) are lost on the first edit.

- Home-screen app: `app_head()` adds `assets/app.webmanifest` (start `../app/`, scope `../`), `app-icon-180/192/512.png` (drawn
  from `assets/app-icon.svg`, the logo full-bleed) and Apple's tags with `black-translucent` status bar. So the page runs under
  the clock: `.ah` pads by `env(safe-area-inset-top)`, the home page's `.lnav`/`.hero` get a transparent top border of that size
  (`HOME_SCREEN_CSS`, zero everywhere else), and the light looks A and D paint that strip #111 because iOS draws the status bar
  in white. `theme-color` follows the look (`THEME_COLORS`, set in LOOK_JS).

## Mac app (in progress, plan in `mac/PLAN.md`)
- A SwiftUI Mac app will replace the `.command` + browser. The Python engine stays (fmsave is Python); the app starts it
  with `--headless` (no browser, no Terminal tips) and reads `GET /api/report` and `GET /api/status`.
- `report_json(R)` builds the feed field by field (`player_json`, `_fit_entry`, `_plain`): never the raw `build()` dict, so
  no CA/PA, raw model scores, FM position ratings or `HIDDEN_ATTRS`. Potential is already filtered in `build()` and always
  None for targets. Bump `REPORT_SCHEMA` when a field changes meaning. `make_report()` keeps the last build in `LAST_REPORT`;
  the live server stores the JSON next to the page after each rebuild.
- `/api/*` answers only loopback with a `127.0.0.1`/`localhost` Host header (blocks the network and DNS rebinding), even
  with the phone key. `demo/build_site.py` writes `mac/Fixtures/report.json` from the fake save for SwiftUI previews.
- Tests: `python3 -m unittest discover -s tests -v` (feed contents, his rules, and the real server in headless mode).
- Phase 1 is built (`mac/`, see PLAN.md): SwiftUI, macOS 15+, Swift 6 strict concurrency, no packages, not sandboxed,
  ad-hoc signed. Project generated from `mac/project.yml` (XcodeGen; the .xcodeproj, `mac/build/` and Info.plist are
  gitignored). Build/test with `mac/build.sh` / `mac/build.sh test`; `mac/build.sh install` puts a Release build in
  `/Applications` (his everyday copy). Builds go to `mac/build/DerivedData.noindex` so Spotlight doesn't list dev copies.
  The app ships its own engine (`BundledEngine`, `Contents/Resources/Engine`: standalone Python 3.13 + fmsave +
  backports-zstd, plus the script and assets, copied in by `mac/bundle_engine.sh` from `mac/build/vendor/python`, which
  `mac/vendor_python.sh` makes). Script changes reach the installed app only through `mac/build.sh install`; to test
  script edits live, use Settings › Engine › "Run the engine from a project folder instead" (or the .command). The bundled
  engine runs with `SQUAD_REPORT_HOME` = `~/Library/Application Support/Squad Report`: the engine writes data/,
  scouting.txt and Reports/ there instead of next to the script (`HOME_DIR`; assets still come from `APP_DIR`).
  Never let it write into the app bundle (PYTHONDONTWRITEBYTECODE; .pyc files are compiled at vendoring time).
  Phase 5 checked every page at 900×600 (the min) and full screen, light/dark/Glass: keep narrow layouts working
  (`ViewThatFits`, adaptive grids) when adding to a page. Test light mode without touching his system setting by
  launching with `--args -NSRequiresAquaSystemAppearance YES`, and a window size with `"-NSWindow Frame main" "x y w h ..."`. First launch asks for the project folder (bookmark in
  UserDefaults `projectFolderBookmark`, domain `com.squadreport.mac`); `Engine` attaches to a running engine on 8027 or
  runs `PythonSetup` (find Python 3.12+, `.venv`, fmsave, upgrade once a day) and starts `--headless`, restarting it up to
  3 times in 2 minutes; quitting the app stops only an engine it started. `ReportStore` polls /api/status (1 s busy, 3 s
  idle), fetches /api/report on a new version and caches it in `~/Library/Application Support/Squad Report/last-report.json`.
  Every page is native now (Phases 2–4 in PLAN.md); the rest show "Open in Browser". Statuses use
  `PlayerStatus` + `StatusBadge` (colour + SF Symbol + word, dashed for arranged/contract ending). The feed's
  `formation.style` ("Gegenpress") was added for the Home hero; no schema bump (new field, same meanings).
  Positions logic lives in `PositionCards.build` (mirrors `position_cards()`: rated here, or `played_many`+ games at
  the card via `open_rows`; loans out last; best `youth_per_card` youth; "Not listed" half-phase note from
  `familiarity`). `PlayerCard` is the shared popover. Squad list columns persist in `@AppStorage("squadColumns")`.
  Tactical fit and Training use a segmented control for their parts instead of one long scroll. Swift Charts on this
  macOS draws category labels above each horizontal bar, so StatsView hides the y axis and labels bars itself with
  `.annotation(position: .top, alignment: .leading)`. Attribute dictionaries may come back camelCased from the decoder:
  use `Report.label/abbr` and `Player.attribute`, which try both spellings.
  Phase 7: motion lives in `Motion` (durations, `-slowMotion N` stretches them for checking) and is off with Reduce Motion;
  the page entrance is an on-appear fade (`PageEntrance`), not a transition, so pages never overlap. Demo switches for the
  loader: `-demoLoader YES`, `-demoWipe YES`. A `-look X` launch argument overrides the saved look (⌘L can't change it then).
  Phase 6: all six web looks are `Look` cases (original, programme A, floodlit B, scoreboard C, sticker D, glass E; the
  stored value "glass" kept its meaning). `Theme` describes a look from the web tokens: `scheme` (A/D light, B/C/E dark),
  `panelStyle`, `heroStyle`, `page` background (D wraps every page in a white sticker sheet on the mown pitch), fonts per
  role, `star`, `pitchStripes`/`pitchLine`/`pitchRadius`, `numbersAreDoto` (C, E: NumberText's decimal fix). The theme reads
  the club's `kitOnLight` through `Themed`, so `.themed()` must sit inside `.environment(model)`. Fonts: all the looks'
  OFL woff2 files are in Resources/Fonts, registered in `Fonts.register()`; Archivo (look A) isn't vendored, so A uses the
  system face, expanded. `Pitch3D` is the web's pitch3d() (manual projection, cards stand on their spots).
  Phase 4: looks are `Theme` in Views/Components/Theme.swift (`@AppStorage("look")`); use `.panel()` /
  `.panelFill()` for cards and the font roles (`.displayFont`, `.numberFont`, `.positionFont`, `.heroFont`, `.slotFont`,
  `.dataFont`) instead of hard-coded condensed system fonts, and `theme.star` / `theme.pitchStripes` / `theme.cardFill`.
  The glass fonts must be registered synchronously in `SquadReportApp.init()` (SwiftUI caches a failed lookup).
  Settings keys: `showPotential`, `phoneAccess`, `look`. Sandbox state: `SandboxModel` (Report/Sandbox.swift), saved in
  UserDefaults `sandbox1:<club>:<save>`. Never commit a screenshot of the Phone settings: its QR codes hold the phone key.
  Background UI tools can't drag from Sandbox roster rows or open pop-up menus; test those by hand.
  Demo mode: `open "…/FM27 Companion.app" --args -demoReport <path>/mac/Fixtures/report.json` (no engine).
  Testing UI: the shell can't screenshot windows (no Screen Recording grant); use computer-use `app_screenshot` on
  `com.squadreport.mac`.

- Next for the Mac app: **Phase 6 in mac/PLAN.md** (web features it doesn't have yet: position filter, mentoring,
  "Doing it yourself", removing scouting targets, picker filters, a status key, the 3D XIs and all six looks; he asked for both). Then **Phase 7** (motion: page fades,
  squad rows gliding, the animated loader, the pulsing live dot, look cross-fade, back/forward history).
- Home page "Mac app" section (`mac_section()`, `MAC_SHOTS`, `MAC_FACTS`): appears only once `assets/mac-home.jpg` etc. exist.
  Those screenshots must come from the app's demo mode (`-demoReport mac/Fixtures/report.json`), never his real save,
  because the demo site is public. `.jpg` is in `ASSET_TYPES`; `_jpeg_size()` gives the img width/height.

## Hosted demo
- `python3 demo/build_site.py` builds `docs/` from `demo/fake_save.py` (a made-up save: Liverpool names with invented ratings,
  injuries and moves; also handy for testing every tab without his save): home page at the root, app in `app/`, `assets/` copied
  in, links made relative (`relative_links()`), `.nojekyll`. So it works from any address, including GitHub Pages' `/<repo>/`
  sub-path. Rebuild `docs/` and push after UI changes; his real report stays local.
- Hosting: GitHub Pages (public: anyone with the link can open it, which is why it only ever carries the made-up save).
  `vercel.json` / `.vercelignore` serve only `docs/` if he moves it to Vercel (the Vercel connector couldn't create projects).

## What fmsave gives us (worked out in that session)
- `player_match_stats()`: position per match is a one-bit mask in FM order —
  0 GK, 1 SW, 2 DR, 3 DL, 4 DC, 5 WBR, 6 WBL, 7 DM, 8 MR, 9 ML, 10 MC, 11 AMR, 12 AML, 13 AMC, 14 ST
  (`MATCH_BIT_CODE`). Pressures are `None` in FM27.
- `team_match_stats()` + `fixtures()` + `league_tables()`: league comparison. Pick the league table by the
  competition with most of your fixtures (the CL league phase also contains your team).
- `squad_planner()`: non-club players there are treated as scouting targets. The real scouting shortlist is **not readable**
  (checked again in fmsave 0.14.3: no shortlist, scout report or knowledge reader), hence the Sandbox picker. scouting.txt
  lines can end in `[uid]` ("Name, Club [12345]"); the picker writes those and `scouting_targets()` matches them by id.
- `training()`: schedule names are exact. Session codes confirmed by fmsave: 0 Passing Style, 1 Build Up,
  2 Chance Creation, 5 Pressing Intensity, 6 Pressing Trap, 300 Rest, 301 Recovery, 302 Light Conditioning,
  303 Conditioning, 402 Travel, 500 Match. Others are shown by category (0–99 tactical, 100s match prep,
  200s playing development, 300s physical).
- **Individual training is not readable** from the save, so the Training tab recommends instead.

## Dropped ideas
- Training tab "Focus" column using FM27's real individual focus options: he decided against it (it feels like a
  cheat), so don't bring it back. The Training tab keeps recommending single attributes.

## Testing
- Run `build()` against a copy of his save and `render()` it; check every tab in a headless browser for JS errors.
- `slot_rating`, `build`, `render`, `serve_live` are the main entry points. Keep the file parsing at all times —
  the live server only restarts into a version that compiles.

## UI work: always use these skills
Load the matching skills before touching the site's look or behaviour (name them, or invoke with `/name`):
- Direction: `frontend-design:frontend-design`, `animatedwebs:animatedwebs-style`
- Motion: `hzblj-skills:gsap-timelines`, `gsap-scroll-trigger`, `gsap-text`, `gsap-performance`, `css-animations`, `ui-motion`
- Polish: `hzblj-skills:ui-interactions`, `ui-typography`, `ui-surfaces`, `polish`
- Behaviour and states: `ui-ux-behaves:ui-ux`, `ui-ux-tabs`, `ui-ux-table`, `ui-ux-passive`, `ui-ux-chart`; review with `ui-ux-behaves:review`
- Components: AnimatedWebs connector (`search_catalog`, `get_component`) and `animatedwebs:animatedwebs-components`
- Copy: `hzblj-skills:unslop`, `ui-ux-behaves:copy-check`
- Testing: Playwright browser tools (check every page, console errors, reduced motion, mobile)
Skip the React Native / Reanimated / Skia / Next.js / Vercel / monorepo skills: this is one Python file serving vanilla HTML/JS.
GSAP 3.15.1 (+ScrollTrigger, SplitText, Flip) and Lenis 1.3.27 live in `assets/` so the site works offline.

## Mac app UI: design rules and the "see it running" rule (required)
- `DESIGN.md` is the design spec for `mac/` (tokens, spacing scale, radii, type, components, Don'ts). Follow it
  exactly; any value outside it needs a code comment saying why. `REFERENCE_AUDIT.md` explains where it comes from.
- **After every UI edit in `mac/`, before saying it's done, installing or committing:**
  1. Build: `mac/build.sh` (or the Xcode `BuildProject` tool). Fix every error.
  2. Launch the dev build in demo mode: `open -n "mac/build/DerivedData.noindex/Build/Products/Debug/FM27 Companion.app"
     --args -demoReport "$PWD/mac/Fixtures/report.json" -look <look>` (quit the running copy first).
  3. Visually inspect it through Computer Use: `app_screenshot` (bundle `com.squadreport.mac`) of **every page the edit
     touches**, in the look he uses (`defaults read com.squadreport.mac look`) and in one light look when colours or
     surfaces changed. Take the screenshot after the page entrance has finished (a second capture if the first is
     mid-fade).
  4. Check the screenshots against `DESIGN.md` and fix what's off, then repeat 1–3.
  5. In the reply, say which pages and looks were checked and what wasn't.
- If the Mac is locked or a capture fails, say so plainly and **don't** describe the change as checked, installed
  for real use, or done. Demo mode only for anything saved or committed; never commit captures of his real save.

## Mac app (`mac/`): which skill does which task
Load the skill (Skill tool) **before** starting a task in its row, and say which one you loaded. A task can match two rows: load both.
| When the task is… | Load |
|---|---|
| Writing or changing any SwiftUI view, state (`@Observable`, `@State`, `@Bindable`), identity, layout, `Table`/`List`/lazy-stack scrolling, toolbars, inspectors, a custom `Layout`, or a SwiftUI rendering/state bug | `swiftui` |
| macOS specifics: windows and scenes, menu bar extras, commands and shortcuts, AppKit bridging (`NSViewRepresentable`, `NSWindow`), sandbox/entitlements, notifications, Dock badge, macOS 26/27 APIs, a code or UI review of the Mac app | `macos-development` |
| Design language: Liquid Glass, SF Symbols, typography, motion and feedback (haptics, number transitions, symbol effects), UX writing, design-system rules, colour and corner radii | `design` |
| A polish or review pass on how a screen looks and feels: spacing, alignment, optical balance, hover/focus/press states, shadows and radius, "make it feel professional", building a new component | `design-engineer` |
| Web UI (the Python-served site) | the web skills listed above, not these |

Also: use the Xcode tools (`BuildProject`, `GetBuildLog`, `RenderPreview`, …) when they're connected; `mac/build.sh` is the fallback. Screenshots of the running app go through computer-use `app_screenshot` (it fails while the Mac is locked). Peekaboo isn't installed here.
