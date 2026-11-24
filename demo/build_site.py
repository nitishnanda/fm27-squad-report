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
        report = fm.build(save, Path("Demo career.fm"))
    (out / "app" / "index.html").write_text(relative_links(fm.render(report), at_root=False), encoding="utf-8")
    (out / "index.html").write_text(relative_links(fm.landing_page(), at_root=True), encoding="utf-8")
    # the same made-up report as JSON, for the Mac app's previews and tests
    fixtures = ROOT / "mac" / "Fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    (fixtures / "report.json").write_text(json.dumps(fm.report_json(report), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    shutil.copytree(ROOT / "assets", out / "assets")
    (out / ".nojekyll").write_text("")                 # GitHub Pages: serve the files as they are
    print(f"Built {out}/index.html, {out}/app/index.html and {fixtures}/report.json")


if __name__ == "__main__":
    main()
