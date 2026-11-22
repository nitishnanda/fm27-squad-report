FM27 SQUAD REPORT
=================

Reads your newest Football Manager 27 save and opens a report in your browser:
position verdicts, best & second XI, a sandbox to build your own XI, training advice, every position's
depth, tactical fit (key attributes for each role in your tactic plus your Gegenpress
style, and who doesn't fit), a filterable squad & transfer status list, deals & loans
(transfers vs loans, arranged vs current), and season stats split into first team and
youth teams.

HOW TO RUN
1. Double-click "Run Squad Report.command". The home page opens in your browser at
   http://localhost:8027. Press "Launch the app" (or bookmark http://localhost:8027/app to go straight in).
2. Leave the Terminal window open. Minimise it if you like.
3. Whenever you save in FM27 (autosave counts), it reads the new save by itself in about
   30 seconds. Just refresh the page. A small pop-up in the corner also tells you when a
   new report is ready.
4. Close the Terminal window when you're done. Next time, double-click it again.

When the tool itself gets updated (new files in this folder), it restarts into the new
version by itself, so a refresh shows that too. Every report is also saved in the "Reports"
folder. For a one-off report without the live page, run it with --once.

The first run takes a minute while it installs the save reader (fmsave). After that
it's quick, and fmsave updates itself so FM patches keep working.

FIRST TIME ON A MAC
macOS blocks scripts downloaded from the internet. If double-clicking says it can't be
opened: open System Settings > Privacy & Security, scroll down, and click "Open Anyway"
next to "Run Squad Report.command". You only have to do this once.

SCOUTING TARGETS (SANDBOX)
- FM doesn't let other tools read your scouting shortlist, so targets come from two places:
  anyone from another club in your FM Squad Planner, and names in scouting.txt (one per
  line; add ", Club" if the name isn't unique). On the live page you can also type a name
  into the Sandbox and it adds it for you.
- Set a target to "Signed" in the Sandbox to use him in your XI.
- Targets are rated from their real attributes, so only add players your scouts have fully
  reported on. Potential is never shown for them.

WHERE THE NUMBERS COME FROM
- Tactical fit > How it's going: your league numbers from the game's own match stats and
  league table, ranked against every team in the league, plus each player's league numbers
  per 90 compared with every league player in the same position. Nothing hidden.
- Training: your team schedules come straight from the save's training calendars. FM doesn't
  let other tools read each player's individual training, so the Training tab suggests what to
  set and you compare it with his card in Training > Individual Training.
- Positions: green = his natural position, blue = played there 5+ times this season
  (FM keeps each player's last ~20 matches, so it's recent games).

GOOD TO KNOW
- Read-only: it copies your save and reads the copy. Your save is never changed.
- No spoilers: current stars use visible attributes only (no CA or hidden attributes),
  so they're the tool's own stars and can be half a star off FM's.
- System stars = how good a player is in YOUR tactic and Gegenpress style.
  Ability stars = how good he is at that position in general.
- Potential stars (players 23 and under who could grow 1 star or more) are the one
  exception: they come from FM's hidden potential, shown as stars only. To hide them,
  set SHOW_POTENTIAL = False in the settings.
- Sandbox: mark players injured, suspended, gone or away and it re-picks the best XI,
  or choose each slot yourself. Your changes are remembered in that browser.
- If you change your tactical style, edit TACTICAL_STYLE and STYLE_KEYS in the settings.
- The ▲▼ arrows compare stars against your last run at an earlier in-game date.
- Your tactic (4-2-3-1, positions AND roles in and out of possession) and all the
  thresholds live in the SETTINGS block at the top of fm27_squad_report.py.
- Role key attributes: FM highlights them when you pick a role on the tactics screen.
  If FM27's differ from the ROLES lists in the settings, edit the lists to match.
- Arranged moves: a future move with a new contract shows as a transfer; one without
  a new contract (the parent club keeps him) shows as a loan.
- To reset the star scale and trends (e.g. new save or new club), delete the "data" folder.
- To use a specific save, drag the .fm file onto Terminal after the command:
  ./"Run Squad Report.command" "/path/to/your save.fm"

Save reading by fmsave (MIT licence) — github.com/rhiever/fmsave
