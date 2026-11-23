"""Build the static demo site in docs/: the home page at the root and the app in app/, from demo/fake_save.py.

The real report needs your FM save, so the hosted app runs on made-up data (Liverpool names, invented ratings,
injuries and moves). Run from the repo root:  python3 demo/build_site.py

docs/ is self-contained (assets copied in, links relative), so it works from any address: GitHub Pages
(https://<user>.github.io/<repo>/), Vercel, or `python3 -m http.server -d docs`.
"""
import json
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
        report = fm.build(FakeSave(), Path("Demo career.fm"))
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
