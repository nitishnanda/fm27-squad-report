"""Build the static demo site in docs/: the home page at the root and the app in app/, from demo/fake_save.py.

The real report needs your FM save, so the hosted app runs on made-up data (Liverpool names, invented ratings,
injuries and moves). Run from the repo root:  python3 demo/build_site.py

docs/ is self-contained (assets copied in, links relative), so it works from any address: GitHub Pages
(https://<user>.github.io/<repo>/), Vercel, or `python3 -m http.server -d docs`.
"""
import json
from types import SimpleNamespace
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

import fm27_squad_report as fm  # noqa: E402
from fake_save import FakeSave  # noqa: E402


def relative_links(html: str, at_root: bool) -> str:
    """The live server serves the home page at / and the app at /app. A hosted copy can live under a sub-path
    (GitHub Pages puts it at /<repo>/), so swap those absolute links for relative ones."""
    if at_root:   # the home page: ../assets/ only works when the page is at the very top of the domain
        return html.replace("../assets/", "assets/").replace('href="/app"', 'href="app/"')
    return html.replace('href="/"', 'href="../"')


def seed_career(path: Path) -> None:
    """The demo save only has this season. Invent 2025/26 at Brighton (results, money, players), all made up, so the
    Results and Career pages show a two-club career like a real one would after a few seasons."""
    import random
    from datetime import date, timedelta
    rnd = random.Random(27)
    opps = ["Arsenal", "Chelsea", "Man City", "Man Utd", "Spurs", "Newcastle", "Aston Villa", "West Ham", "Everton",
            "Fulham", "Brentford", "Wolves", "Bournemouth", "Forest", "Crystal Palace", "Leeds", "Burnley", "Sunderland",
            "Liverpool"]
    matches, day = {}, date(2025, 8, 16)
    for i in range(46):
        comp = "Premier League" if i % 5 else ("FA Cup" if i % 2 else "EFL Cup")
        gf, ga = rnd.choice([0, 1, 1, 2, 2, 3, 4]), rnd.choice([0, 0, 1, 1, 2, 3])
        key = f"{day.isoformat()}|9{i}|8{i}|{comp}"
        matches[key] = {"date": day.isoformat(), "season": "2025/26", "club": "Brighton", "club_uid": 9001, "comp": comp,
                        "opp": opps[i % len(opps)], "home": i % 2 == 0, "gf": gf, "ga": ga}
        day += timedelta(days=rnd.choice([6, 7, 7, 8]))
    money = {f"9001|{m}": {"club": "Brighton", "month": m, "net": n} for m, n in
             [("2025-07", -38_500_000), ("2025-08", -12_000_000), ("2025-09", 4_000_000), ("2026-01", -21_750_000),
              ("2026-02", 1_500_000), ("2026-06", 55_000_000)]}
    players = {f"9001|{u}": {"uid": u, "club": "Brighton", "name": n, "peak": pk, "slot": sl, "peak_date": "2026-04-30",
                             "seasons": {"2025/26": {"apps": ap, "g": g, "a": a}}}
               for u, n, pk, sl, ap, g, a in [(900101, "Kaoru Mitoma", 4.5, "LW", 41, 11, 9),
                                              (900102, "Carlos Baleba", 4.5, "DM", 44, 3, 4),
                                              (900103, "João Pedro", 4.0, "ST", 39, 18, 6),
                                              (900104, "Bart Verbruggen", 4.0, "GK", 46, 0, 0)]}
    path.write_text(json.dumps({"career": {"Demo Manager": {"name": "Demo Manager", "matches": matches, "money": money,
                                                    "players": players}}}))


def main() -> None:
    out = ROOT / "docs"
    if out.exists():
        shutil.rmtree(out)
    (out / "app").mkdir(parents=True)
    with tempfile.TemporaryDirectory() as tmp:
        fm.HISTORY_FILE = Path(tmp) / "history.json"   # never touch your real star history
        save = FakeSave()
        # two made-up scouting targets, so the Sandbox shows both kinds: one from scouting.txt (removable in the app)
        # and one from FM's Squad Planner (the save controls that one)
        others = [p for p in save.players_ if p.club_uid != 1 and p.team_slot == 0 and not p.on_loan and p.age and p.age <= 27]
        listed, planned = others[3], others[11]
        fm.SCOUTING_FILE = Path(tmp) / "scouting.txt"   # never touch your real scouting list
        fm.SCOUTING_FILE.write_text(f"{listed.name}, {listed.club_name} [{listed.uid}]\n", encoding="utf-8")
        save.squad_planner = lambda: [SimpleNamespace(player_uids=[planned.uid])]
        seed_career(fm.HISTORY_FILE)   # a made-up earlier season, so the Career pages have more than one season
        report = fm.build(save, Path("Demo career.fm"))
        report_data = fm.report_json(report)   # while the scratch history still exists
    (out / "app" / "index.html").write_text(relative_links(fm.render(report), at_root=False), encoding="utf-8")
    (out / "index.html").write_text(relative_links(fm.landing_page(), at_root=True), encoding="utf-8")
    # the same made-up report as JSON, for the Mac app's previews and tests
    fixtures = ROOT / "mac" / "Fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    (fixtures / "report.json").write_text(json.dumps(report_data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    shutil.copytree(ROOT / "assets", out / "assets")
    (out / ".nojekyll").write_text("")                 # GitHub Pages: serve the files as they are
    print(f"Built {out}/index.html, {out}/app/index.html and {fixtures}/report.json")


if __name__ == "__main__":
    main()
