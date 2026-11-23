"""Build the static demo site in web/ for Vercel: the home page at / and the app at /app, from demo/fake_save.py.

The real report needs your FM save, so the hosted app runs on made-up data (Liverpool names, invented ratings,
injuries and moves). Run from the repo root:  python3 demo/build_site.py
Vercel copies assets/ into web/assets/ at build time (see vercel.json), so web/assets/ isn't committed.
"""
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

import fm27_squad_report as fm  # noqa: E402
from fake_save import FakeSave  # noqa: E402


def main() -> None:
    web = ROOT / "web"
    (web / "app").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        fm.HISTORY_FILE = Path(tmp) / "history.json"   # never touch your real star history
        report = fm.build(FakeSave(), Path("Demo career.fm"))
    (web / "app" / "index.html").write_text(fm.render(report), encoding="utf-8")
    (web / "index.html").write_text(fm.landing_page(), encoding="utf-8")
    if "--with-assets" in sys.argv:                    # for previewing web/ locally
        shutil.copytree(ROOT / "assets", web / "assets", dirs_exist_ok=True)
    print(f"Built {web}/index.html and {web}/app/index.html")


if __name__ == "__main__":
    main()
