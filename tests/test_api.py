"""The Mac app's feed (/api/report, /api/status) and --headless, on the made-up save.

Run from the repo root:  python3 -m unittest discover -s tests -v
"""
import json
import os
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

import fm27_squad_report as fm  # noqa: E402
from fake_save import FakeSave  # noqa: E402

TMP = Path(tempfile.mkdtemp())
fm.HISTORY_FILE = TMP / "history.json"   # never touch the real star history
FORBIDDEN_KEYS = {"ca", "pa", "raw", "rowraw", "araw", "orowraw", "posr"}


def build_report():
    return fm.build(FakeSave(), Path("Demo career.fm"))


def all_keys(v, out=None):
    out = set() if out is None else out
    if isinstance(v, dict):
        for k, x in v.items():
            out.add(k)
            all_keys(x, out)
    elif isinstance(v, list):
        for x in v:
            all_keys(x, out)
    return out


class ReportJson(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.R = build_report()
        cls.J = fm.report_json(cls.R)

    def test_round_trips_as_plain_json(self):
        text = json.dumps(self.J)
        self.assertEqual(json.loads(text), self.J)

    def test_nothing_hidden(self):
        keys = all_keys(self.J)
        self.assertFalse(keys & FORBIDDEN_KEYS, keys & FORBIDDEN_KEYS)
        self.assertFalse(keys & fm.HIDDEN_ATTRS, keys & fm.HIDDEN_ATTRS)
        text = json.dumps(self.J)
        for p in self.R["players"]:   # the CA/PA numbers themselves never appear as a field
            self.assertNotIn(f'"ca": {p["ca"]}', text)
            self.assertNotIn(f'"pa": {p["pa"]}', text)

    def test_plans_have_no_position_numbers(self):   # position work says "unconvincing", never 11/20
        for plan in self.J["plans"]:
            for w in plan["position_work"]:
                self.assertNotIn("fam", w)
                self.assertIsInstance(w["word"], str)

    def test_tactics_pages_have_their_data(self):
        self.assertTrue(all("value_text" in m for m in self.J["performance"]["metrics"]))
        self.assertTrue(self.J["training"] and all("sessions" in t for t in self.J["training"]))
        self.assertIn("changes", self.J["training_advice"])
        self.assertEqual(self.J["style"]["keys"], list(fm.STYLE_KEYS))

    def test_training_mentoring_and_howto(self):   # one rule, one text: the web page and the feed share them
        m = self.J["training_advice"]["mentoring"]
        low, high = fm.mentoring_groups(self.R)
        if m is None:
            self.assertFalse(low and high)
        else:
            self.assertEqual([p["uid"] for p in m["young"]], [p["uid"] for p in low])
            self.assertEqual([p["uid"] for p in m["seniors"]], [p["uid"] for p in high])
            self.assertTrue(all(p["age"] <= 21 and p["determination"] <= 11 for p in m["young"]))
            self.assertTrue(all(p["age"] >= 26 and p["determination"] >= 16 for p in m["seniors"]))
            self.assertLessEqual(len(m["young"]), 8)
            self.assertLessEqual(len(m["seniors"]), 4)
        howto = self.J["training_howto"]
        self.assertEqual(len(howto["steps"]), 7)
        self.assertEqual(len(howto["cheat"]), len(fm.HOWTO_CHEAT))
        page = fm.training_page(self.R)
        self.assertIn(fm.HOWTO_STEPS[0][0], page)   # the web shows the same words

    def test_familiarity_is_words_not_numbers(self):   # FM shows these words; the /20 ratings stay hidden
        words = {w for _, w in fm.FAMILIARITY_WORD} | {"ineffective"}
        for p in self.J["players"]:
            for pair in p["familiarity"].values():
                self.assertTrue(set(pair) <= words, pair)

    def test_hidden_attributes_dropped_even_if_the_save_has_them(self):
        p = dict(self.R["players"][0], attrs={**self.R["players"][0]["attrs"], "consistency": 15, "ambition": 20})
        self.assertNotIn("consistency", fm.player_json(p)["attributes"])
        self.assertNotIn("ambition", fm.player_json(p)["attributes"])

    def test_potential_follows_his_rules(self):
        for p in self.J["players"]:
            if p["potential"] is not None:
                self.assertLessEqual(p["age"], fm.POTENTIAL_MAX_AGE, p["name"])
                self.assertGreaterEqual(p["potential"] - p["best"]["stars"], fm.POTENTIAL_MIN_GAIN - 1e-6, p["name"])
        for t in self.J["targets"]:
            self.assertIsNone(t["potential"])
        target = dict(self.R["players"][0], where="target", potential=4.5)
        self.assertIsNone(fm.player_json(target)["potential"])

    def test_statuses_stay_distinct(self):
        kinds = {m["kind"] for p in self.J["players"] for m in p["status"]["moves"]}
        self.assertTrue({"loan_in", "loan_out", "deal_in", "deal_out", "loan_in_arr", "loan_out_arr"} <= kinds)
        injuries = [p["status"]["injury"] for p in self.J["players"] if "injury" in p["status"]]
        self.assertEqual({i["long"] for i in injuries}, {True, False})

    def test_misfit_without_a_better_role(self):   # happens in his real save, not in the made-up one
        R = dict(self.R, fit=dict(self.R["fit"], misfits=[dict(p=self.R["players"][0], why="Nothing suits him better.", best=None)]))
        m = fm.report_json(R)["fit"]["misfits"][0]
        self.assertEqual((m["uid"], m["best"], m["best_row"]), (self.R["players"][0]["uid"], None, None))

    def test_survives_missing_pieces(self):   # a save with gaps: nobody injured, no league, a player with no rating
        R = dict(self.R, perf={}, training=[], targets=[], xi2=[], verdicts=[])
        R["players"] = [dict(p, best=None, slots={}, aslots={}, ability=None, stats=None) for p in self.R["players"][:3]]
        json.dumps(fm.report_json(R))

    def test_xis_point_at_players(self):
        uids = {p["uid"] for p in self.J["players"]}
        for xi in ("xi1", "xi2"):
            self.assertEqual(len(self.J[xi]), len(fm.FORMATION))
            for spot in self.J[xi]:
                self.assertTrue(spot["uid"] is None or spot["uid"] in uids)

    def test_schema(self):
        self.assertEqual(self.J["schema"], fm.REPORT_SCHEMA)
        for key in ("club", "game_date", "formation", "players", "xi1", "verdicts", "fit", "performance", "training", "news"):
            self.assertIn(key, self.J)


def lan_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.254.254.254", 1))
            ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


class Server(unittest.TestCase):
    """The real live server in --headless mode, on a spare port, reading the made-up save."""

    @classmethod
    def setUpClass(cls):
        fake = TMP / "Demo career.fm"
        fake.write_text("x")
        (TMP / "tmp").mkdir(exist_ok=True)
        fm.LIVE_PORT = 18027
        fm.PHONE_FILE, fm.CLUB_FILE, fm.REPORT_DIR = TMP / "phone.json", TMP / "club.json", TMP / "Reports"
        fm.open_save = lambda p: (FakeSave(), TMP / "tmp" / "x")
        fm.candidate_saves = lambda: [fake]
        fm.LIVE_SETTLE_SECONDS = 0
        os.environ["FM27_NO_OPEN"] = "1"
        threading.Thread(target=fm.serve_live, args=(["--headless"],), daemon=True).start()
        cls.base = f"http://127.0.0.1:{fm.LIVE_PORT}"
        for _ in range(120):   # wait for the first build
            try:
                if json.load(urllib.request.urlopen(cls.base + "/api/status"))["ready"]:
                    return
            except (urllib.error.URLError, ConnectionError):
                pass
            time.sleep(0.5)
        raise RuntimeError("the server never finished its first build")

    def get(self, path, host=None, base=None):
        req = urllib.request.Request((base or self.base) + path, headers={"Host": host} if host else {})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_report_on_this_mac(self):
        code, body = self.get("/api/report")
        self.assertEqual(code, 200)
        data = json.loads(body)
        self.assertEqual(data["schema"], fm.REPORT_SCHEMA)
        self.assertFalse(all_keys(data) & FORBIDDEN_KEYS)

    def test_status(self):
        code, body = self.get("/api/status")
        self.assertEqual(code, 200)
        s = json.loads(body)
        self.assertTrue(s["ready"])
        self.assertEqual(len(s["steps"]), len(fm.BUILD_STEPS))

    def test_phone_links_for_the_mac_only(self):
        code, body = self.get("/api/phone")
        self.assertEqual(code, 200)
        self.assertIn("links", json.loads(body))
        self.assertEqual(self.get("/api/phone", host="evil.example:18027")[0], 403)

    def test_refuses_a_renamed_address(self):   # a web page pretending to be this Mac (DNS rebinding)
        self.assertEqual(self.get("/api/report", host="evil.example:18027")[0], 403)

    def test_refuses_the_network(self):
        ip = lan_ip()
        if not ip:
            self.skipTest("no network address here")
        code, _ = self.get("/api/report", host=f"{ip}:18027", base=f"http://{ip}:{fm.LIVE_PORT}")
        self.assertEqual(code, 403)
        key = json.loads((TMP / "phone.json").read_text())["key"]   # not even with the phone's key
        code, _ = self.get(f"/api/report?k={key}", base=f"http://{ip}:{fm.LIVE_PORT}")
        self.assertEqual(code, 403)

    def test_web_app_still_works(self):
        code, body = self.get("/app")
        self.assertEqual(code, 200)
        self.assertIn(b"Squad Report", body)


if __name__ == "__main__":
    unittest.main()
