#!/usr/bin/env python3
"""FM27 Squad Report — reads your Football Manager 27 save and builds a squad report.

    python3 fm27_squad_report.py                 # finds your newest FM27 save
    python3 fm27_squad_report.py path/to/x.fm    # or point it at one

Read-only: the save is copied first and never changed. No CA/PA or hidden attributes are
used anywhere: stars come from visible attributes only. Save reading is done by the
open-source fmsave library (MIT, github.com/rhiever/fmsave), which also supplies the
visible-attribute rating model embedded below.
"""
from __future__ import annotations

import bisect
import colorsys
import hashlib
import glob
import html
import json
import statistics
import math
import os
import re
import shutil
import sys
import tempfile
import time
import warnings
import webbrowser
from collections import Counter
from datetime import date, datetime
from pathlib import Path

# =============================================================================================
# SETTINGS — tweak these numbers if a verdict feels off
# =============================================================================================
FORMATION_NAME = "4-2-3-1"
# One row per player in the XI, left to right as on your tactics screen:
# (slot, in-possession position, out-of-possession position, in-possession role, out-of-possession role)
# Position codes: GK DL DC DR WBL WBR DM ML MC MR AML AMC AMR STC
FORMATION = [
    ("GK", "GK", "GK", "BGK", "SK"),
    ("LB", "DL", "DL", "FB", "FB"),
    ("CB", "DC", "DC", "CB", "CB"),
    ("CB", "DC", "DC", "BCB", "CB"),
    ("RB", "WBR", "DR", "WB", "FB"),     # wing-back in possession, full-back out of possession
    ("DM", "DM", "DM", "DLP", "PDM"),
    ("DM", "DM", "DM", "DM", "DM"),
    ("LW", "AML", "ML", "IF", "WMF"),    # inside forward in possession, wide midfielder out of possession
    ("AM", "AMC", "AMC", "SS", "AM"),
    ("RW", "AMR", "MR", "IW", "WMF"),    # winger cutting inside in possession, wide midfielder out of possession
    ("ST", "STC", "STC", "CFD", "CFD"),
]

# Key attributes per role, used by the Tactical fit page. FM highlights a role's key attributes when
# you pick it on the tactics screen: check yours there and edit these lists if FM27 differs.
# CB, BCB and WB are FM26's published key attributes; the striker list starts from the four FM26 says
# every scoring striker role shares (Off the Ball, Acceleration, Composure, Finishing); the rest are
# FM's standard key attributes for those roles.
ROLES = {
    "IP": {
        "BGK": ("Ball-Playing Goalkeeper", ["one_on_ones", "reflexes", "kicking", "passing", "first_touch", "composure", "decisions", "vision"]),
        "FB": ("Full-Back", ["crossing", "marking", "tackling", "positioning", "teamwork", "work_rate", "pace", "stamina"]),
        "CB": ("Centre-Back", ["heading", "marking", "tackling", "anticipation", "positioning", "jumping_reach", "strength"]),
        "BCB": ("Ball-Playing Centre-Back", ["heading", "marking", "passing", "tackling", "anticipation", "composure", "positioning", "jumping_reach", "strength"]),
        "WB": ("Wing-Back", ["crossing", "marking", "tackling", "teamwork", "work_rate", "acceleration", "pace", "stamina"]),
        "DLP": ("Deep-Lying Playmaker", ["first_touch", "passing", "technique", "composure", "decisions", "teamwork", "vision"]),
        "DM": ("Defensive Midfielder", ["tackling", "anticipation", "concentration", "positioning", "teamwork"]),
        "IF": ("Inside Forward", ["dribbling", "finishing", "first_touch", "technique", "off_the_ball", "acceleration", "agility"]),
        "SS": ("Second Striker", ["dribbling", "finishing", "first_touch", "anticipation", "composure", "off_the_ball", "acceleration"]),
        "IW": ("Inside Winger", ["dribbling", "passing", "technique", "vision", "decisions", "acceleration", "agility"]),
        "CFD": ("Centre Forward", ["finishing", "off_the_ball", "composure", "acceleration", "first_touch", "anticipation"]),
    },
    "OOP": {
        "SK": ("Sweeper Keeper", ["command_of_area", "one_on_ones", "reflexes", "rushing_out", "anticipation", "concentration", "positioning", "acceleration"]),
        "FB": ("Full-Back", ["marking", "tackling", "positioning", "concentration", "anticipation", "decisions"]),
        "CB": ("Centre-Back", ["heading", "marking", "tackling", "anticipation", "positioning", "jumping_reach", "strength"]),
        "PDM": ("Pressing Defensive Midfielder", ["tackling", "aggression", "work_rate", "stamina", "anticipation", "teamwork", "acceleration"]),
        "DM": ("Defensive Midfielder", ["tackling", "anticipation", "concentration", "positioning", "teamwork"]),
        "WMF": ("Wide Midfielder", ["work_rate", "teamwork", "stamina", "tackling", "positioning", "decisions"]),
        "AM": ("Attacking Midfielder", ["work_rate", "teamwork", "stamina", "anticipation", "decisions"]),
        "CFD": ("Centre Forward", ["work_rate", "stamina", "teamwork", "aggression", "acceleration"]),
    },
}
# Your tactical style. Its attributes are blended into every slot's system rating and the Tactical fit page.
TACTICAL_STYLE = "Gegenpress"
STYLE_KEYS = ["work_rate", "teamwork", "determination", "stamina", "natural_fitness", "aggression",
              "anticipation", "acceleration", "pace"]
STYLE_WEIGHT = 0.3   # share of the system fit that comes from the style (the roles get the rest)
STYLE_FLOOR = 11.0   # style attributes averaging below this -> "not built for gegenpress"

# Potential stars use FM's hidden potential (PA). Set to False if that feels like a spoiler.
SHOW_POTENTIAL = True
POTENTIAL_MAX_AGE = 23     # older players' potential says little about their future
POTENTIAL_MIN_GAIN = 1.0   # only shown when potential is at least this many stars above current

FIT_FLOOR = 11.0     # average of a role's key attributes below this -> doesn't fit
SUIT_GAP = 1.0       # key attributes this far below his own general level -> his strengths are elsewhere
WEAK_ATTR = 10       # a key attribute at or below this counts as a weakness
FIT_ROWS_SHOWN = 6   # players listed per role on the Tactical fit page
PERF_CARDS_SHOWN = 10  # "player by player" cards shown before "Show more" (most league minutes first)
EXTRA_CARDS = {"CM": ("MC", "MC")}   # shown on the Positions page for cover, not used in the XIs

NEEDS_STARTER_GAP = 1.0     # starter this many stars under your XI level -> "needs a better starter"
NEEDS_DEPTH_GAP = 1.5       # backup this many stars under your XI level -> "needs more depth"
AGEING_AGE_OUTFIELD = 31    # starter this age or older ...
AGEING_AGE_GK = 33
AGEING_DROP = 0.75          # ... with the next best option this many stars worse -> "ageing starter"
LONG_INJURY_DAYS = 28       # injuries this long or longer show red, shorter ones yellow
CONTRACT_WARNING_DAYS = 365 # contracts ending within this many days get the dashed badge
YOUTH_AGE = 21              # U21 tag
YOUTH_PER_CARD = 3          # best youth-team players listed on each position card
ACCOMPLISHED_PENALTY = 0.25 # how much worse a player rates outside his natural position (rating units)
# Penalty by FM position familiarity (1-20), per phase. A player counts for a slot if he's at least
# accomplished (15+) in one phase and not worse than awkward (5+) in the other.
FAMILIARITY_PENALTY = [(18, 0.0), (15, ACCOMPLISHED_PENALTY), (12, 0.5), (9, 0.8), (5, 1.2)]
FAMILIARITY_WORD = [(18, "natural"), (15, "accomplished"), (12, "competent"), (9, "unconvincing"), (5, "awkward")]
ROLE_WEIGHT = 0.5           # share of each slot rating that comes from the key attributes of your roles there
IP_WEIGHT = 0.6             # in-possession role's share of that (the out-of-possession role gets the rest)
STAR_TOP = 4.75             # your 3rd best senior player gets this many stars ...
STAR_MID = 3.0              # ... and your median senior player gets this many (like FM, stars are squad-relative)
LOW_MATCH_RATING, HIGH_MATCH_RATING = 6.85, 7.20   # season-stats colouring

APP_DIR = Path(__file__).resolve().parent
REPORT_DIR = APP_DIR / "Reports"
HISTORY_FILE = APP_DIR / "data" / "history.json"
LIVE_PORT = 8027            # the report lives at http://localhost:8027 while the window is open
LIVE_POLL_SECONDS = 4       # how often it checks for a new save
LIVE_SETTLE_SECONDS = 4     # waits this long after a save is written before reading it

# Visible-attribute rating model from fmsave's _scouting_v1.json ("visible": no CA/PA, no hidden
# attributes). i = intercept, w = weight per attribute on the 1-20 scale.
VISIBLE_MODEL = json.loads(r'''{"AM":{"i":5.805085,"w":{"dribbling":0.00538,"finishing":8.4e-05,"heading":-0.001356,"long_shots":0.001464,"marking":0.004421,"off_the_ball":0.003547,"passing":-0.003726,"tackling":-0.002045,"vision":0.002973,"decisions":0.00647,"positioning":-0.000304,"first_touch":0.002614,"technique":0.005135,"flair":-0.000424,"corners":0.002715,"acceleration":0.00734,"free_kick_taking":0.000619,"strength":0.004446,"stamina":0.01207,"pace":0.013849,"jumping_reach":0.001583,"leadership":0.002597,"balance":0.000932,"aggression":0.002585,"agility":0.008333,"natural_fitness":0.002137,"determination":0.003052}},"CB":{"i":6.074788,"w":{"heading":0.001499,"marking":0.000282,"passing":0.001215,"tackling":0.003687,"vision":0.00123,"anticipation":0.004906,"decisions":0.009609,"positioning":0.008536,"flair":0.000954,"corners":-0.001501,"acceleration":8.9e-05,"strength":0.000848,"stamina":0.002204,"pace":0.003307,"jumping_reach":0.01189,"leadership":0.000408,"balance":0.001311,"bravery":0.000923,"agility":0.001079,"natural_fitness":0.001966,"determination":0.001058,"concentration":0.004409}},"CM":{"i":5.730307,"w":{"crossing":0.004076,"dribbling":0.004002,"heading":0.00437,"marking":0.002039,"penalty_taking":0.002278,"tackling":0.002978,"vision":0.010423,"anticipation":0.001497,"decisions":0.010844,"first_touch":0.001636,"technique":0.004852,"corners":0.000398,"teamwork":-0.001532,"work_rate":0.004938,"free_kick_taking":-0.002617,"stamina":0.009941,"pace":0.003418,"jumping_reach":-0.000487,"leadership":0.000736,"balance":-0.002444,"bravery":0.00386,"aggression":-0.000163,"agility":0.006615,"natural_fitness":0.00444,"composure":0.004322}},"DM":{"i":5.873479,"w":{"dribbling":9.5e-05,"heading":0.000679,"long_shots":0.001198,"marking":0.001508,"off_the_ball":-0.000376,"tackling":0.006056,"vision":0.007161,"anticipation":0.007686,"decisions":0.006509,"positioning":0.004608,"technique":0.004414,"corners":0.00241,"teamwork":0.005343,"work_rate":0.00106,"acceleration":0.005921,"free_kick_taking":-0.003109,"stamina":0.011405,"pace":0.002397,"jumping_reach":0.004505,"leadership":-0.00046,"balance":0.000635,"bravery":0.000425,"aggression":-0.001129,"agility":0.001207,"natural_fitness":0.00127,"determination":0.000881,"composure":0.008806,"concentration":0.00088}},"FB/WB":{"i":5.982705,"w":{"heading":0.001527,"long_shots":0.000991,"marking":0.002125,"off_the_ball":0.001629,"passing":0.00078,"penalty_taking":-0.000271,"tackling":0.00353,"vision":0.003983,"anticipation":0.003569,"decisions":0.006158,"positioning":0.004182,"first_touch":0.003063,"technique":0.002369,"flair":0.001449,"corners":0.001845,"work_rate":0.001017,"long_throws":0.000422,"acceleration":0.003498,"strength":0.001677,"stamina":0.009883,"pace":0.004711,"jumping_reach":0.00503,"leadership":0.000528,"balance":0.000543,"bravery":0.000102,"agility":0.002993,"natural_fitness":0.002519,"determination":0.002007,"concentration":0.006151}},"GK":{"i":5.945662,"w":{"aerial_reach":0.005531,"command_of_area":0.006161,"communication":0.002879,"eccentricity":-3.9e-05,"handling":0.001518,"one_on_ones":0.00856,"punching":-0.002847,"reflexes":0.007275,"rushing_out":0.001927,"throwing":0.004055,"anticipation":0.003895,"bravery":0.000395,"composure":0.000188,"concentration":0.00524,"decisions":0.011877,"determination":1e-05,"leadership":0.000172,"off_the_ball":-0.001727,"positioning":0.003935,"teamwork":-0.001128,"vision":0.004038,"acceleration":0.000685,"agility":0.000483,"natural_fitness":0.002654,"stamina":-4.1e-05,"strength":-0.000214,"technique":0.002615}},"ST":{"i":5.781741,"w":{"dribbling":0.003203,"finishing":0.003852,"heading":0.004454,"long_shots":-0.002414,"off_the_ball":0.005962,"passing":0.002114,"penalty_taking":0.001524,"tackling":-0.001811,"vision":0.003945,"anticipation":0.003498,"decisions":0.005787,"first_touch":0.00019,"technique":0.005881,"flair":0.003035,"corners":0.001058,"teamwork":0.000719,"work_rate":0.000387,"long_throws":-0.000969,"acceleration":0.003244,"stamina":0.013847,"pace":0.010791,"jumping_reach":0.005363,"leadership":0.002894,"balance":0.0017,"aggression":0.000843,"natural_fitness":0.002161,"determination":0.003042,"composure":0.00218}},"WIDE":{"i":5.76274,"w":{"crossing":0.004993,"dribbling":0.008284,"finishing":0.001361,"heading":0.001806,"marking":0.001271,"off_the_ball":0.004416,"passing":0.000677,"penalty_taking":-0.000114,"tackling":-0.001831,"vision":0.00521,"anticipation":0.003715,"decisions":0.01419,"positioning":0.000432,"first_touch":0.001986,"flair":0.003666,"acceleration":0.006073,"strength":0.000845,"stamina":0.015807,"pace":0.009517,"jumping_reach":0.003612,"leadership":0.002551,"balance":-0.000815,"bravery":0.001086,"aggression":0.000213,"agility":0.005118,"natural_fitness":0.002876,"determination":0.002318,"composure":0.001276}}}''')

GROUP_OF = {"GK": "GK", "SW": "CB", "DC": "CB", "DL": "FB/WB", "DR": "FB/WB", "WBL": "FB/WB",
            "WBR": "FB/WB", "DM": "DM", "MC": "CM", "AMC": "AM", "ML": "WIDE", "MR": "WIDE",
            "AML": "WIDE", "AMR": "WIDE", "STC": "ST", "ST": "ST"}
POS_FIELD = {"GK": "gk", "SW": "sw", "DL": "dl", "DC": "dc", "DR": "dr", "DM": "dm", "ML": "ml",
             "MC": "mc", "MR": "mr", "AML": "aml", "AMC": "amc", "AMR": "amr", "STC": "stc",
             "WBL": "wbl", "WBR": "wbr"}
SLOT_NAMES = {"GK": "Goalkeeper", "LB": "Left back", "CB": "Centre back", "RB": "Right back",
              "DM": "Defensive mid", "CM": "Central mid", "AM": "Attacking mid", "LW": "Left wing",
              "RW": "Right wing", "ST": "Striker"}
PITCH_ROW = {"ST": 0, "LW": 1, "AM": 1, "RW": 1, "CM": 2, "DM": 3, "LB": 4, "CB": 4, "RB": 4, "GK": 5}
LEFT_TO_RIGHT = ["LB", "LW", "CB", "DM", "CM", "AM", "ST", "GK", "RB", "RW"]
CARD_ORDER = ["GK", "LB", "CB", "RB", "DM", "CM", "AM", "LW", "RW", "ST"]
POS_SHOWN = 5               # players shown per Positions card before "Show all"
POS_LABEL = {"GK": "GK", "SW": "SW", "DL": "LB", "DC": "CB", "DR": "RB", "WBL": "LWB", "WBR": "RWB", "DM": "DM",
             "ML": "LM", "MC": "CM", "MR": "RM", "AML": "LW", "AMC": "AM", "AMR": "RW", "STC": "ST", "ST": "ST"}
HIDDEN = {"consistency", "important_matches", "injury_proneness", "versatility", "dirtiness"}
NEEDED_ATTRS = sorted(({k for ph in ROLES.values() for _, keys in ph.values() for k in keys}
                       | {k for m in VISIBLE_MODEL.values() for k in m["w"]} | set(STYLE_KEYS)
                       | {"reflexes", "one_on_ones", "handling", "long_shots", "crossing", "dribbling", "agility", "bravery",
                          "concentration", "heading", "jumping_reach", "strength", "vision", "passing", "first_touch",
                          "composure", "decisions", "finishing", "off_the_ball", "positioning", "tackling"}) - HIDDEN)
LEAVING = {"deal_out", "loan_out_arr"}
ATTR_LABEL = {"off_the_ball": "Off the Ball", "first_touch": "First Touch", "work_rate": "Work Rate",
              "jumping_reach": "Jumping Reach", "one_on_ones": "One on Ones", "command_of_area": "Command of Area",
              "rushing_out": "Rushing Out", "aerial_reach": "Aerial Reach", "long_shots": "Long Shots",
              "free_kick_taking": "Free Kicks", "penalty_taking": "Penalties", "natural_fitness": "Natural Fitness",
              "long_throws": "Long Throws"}


ATTR_ABBR = {"corners": "Cor", "crossing": "Cro", "dribbling": "Dri", "finishing": "Fin", "first_touch": "Fir",
             "free_kick_taking": "Fre", "heading": "Hea", "long_shots": "Lon", "long_throws": "LTh", "marking": "Mar",
             "passing": "Pas", "penalty_taking": "Pen", "tackling": "Tck", "technique": "Tec", "aggression": "Agg",
             "anticipation": "Ant", "bravery": "Bra", "composure": "Cmp", "concentration": "Cnt", "decisions": "Dec",
             "determination": "Det", "flair": "Fla", "leadership": "Ldr", "off_the_ball": "OtB", "positioning": "Pos",
             "teamwork": "Tea", "vision": "Vis", "work_rate": "Wor", "acceleration": "Acc", "agility": "Agi",
             "balance": "Bal", "jumping_reach": "Jum", "natural_fitness": "Nat", "pace": "Pac", "stamina": "Sta",
             "strength": "Str", "aerial_reach": "Aer", "command_of_area": "Cmd", "communication": "Com",
             "eccentricity": "Ecc", "handling": "Han", "kicking": "Kic", "one_on_ones": "1v1", "reflexes": "Ref",
             "rushing_out": "TRO", "punching": "Pun", "throwing": "Thr"}


def attr_label(a: str) -> str:
    return ATTR_LABEL.get(a, a.replace("_", " ").title())


def arriving(p):
    return (p.get("deal_in") or p.get("loan_in_arr") or (None, None))[1]


# =============================================================================================
# Finding and opening the save
# =============================================================================================
def candidate_saves() -> list[Path]:
    home = Path.home()
    patterns = [
        home / "Library/Application Support/Sports Interactive/Football Manager 27/games/**/*.fm",
        home / "Library/Application Support/Steam/userdata/*/4530370/remote/**/*.fm",
        home / "Documents/Sports Interactive/Football Manager 27/games/**/*.fm",
        home / "OneDrive/Documents/Sports Interactive/Football Manager 27/games/**/*.fm",
    ]
    found = set()
    for pattern in patterns:
        for f in glob.glob(str(pattern), recursive=True):
            found.add(Path(f))
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def pick_save(argv: list[str]) -> Path:
    if argv:
        path = Path(argv[0].strip().strip("'\"")).expanduser()
        if not path.is_file():
            sys.exit(f"Can't find a save at {path}")
        return path
    saves = candidate_saves()
    if saves:
        return saves[0]
    print("Couldn't find your FM27 saves folder automatically.")
    typed = input("Drag your .fm save into this window and press Enter: ").strip().strip("'\"")
    path = Path(typed.replace("\\ ", " ")).expanduser()
    if not path.is_file():
        sys.exit("That isn't a file — try again.")
    return path


def open_save(path: Path):
    try:
        import fmsave
    except ImportError:
        sys.exit("fmsave isn't installed. Run:  python3 -m pip install fmsave")
    tmp = Path(tempfile.mkdtemp(prefix="fm27report-")) / path.name
    shutil.copy2(path, tmp)          # read a copy so a game that is saving can't clash
    try:
        return fmsave.open(tmp), tmp
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(tmp.parent, ignore_errors=True)
        sys.exit(f"Couldn't read {path.name}: {exc}\n"
                 "If FM27 just got patched, fmsave may need an update — it updates itself on the next run.")


# =============================================================================================
# Ratings: visible attributes -> position rating -> stars
# =============================================================================================
def visible_score(player, group: str) -> float | None:
    model = VISIBLE_MODEL[group]
    attrs = player.attributes
    total = model["i"]
    for name, weight in model["w"].items():
        value = getattr(attrs, name, None)
        if value is None:
            return None
        total += weight * min(max(value, 1), 20)
    return total


class Ratings:
    """Turns a visible-attribute score into a rating comparable across positions.

    Each score is ranked against every player in the save who is natural in that position
    group, so "top 0.1% of centre backs" and "top 0.1% of wingers" land on the same rating.
    rating = -log10(share of that group who are as good or better).
    """

    def __init__(self, players):
        pools: dict[str, list[float]] = {g: [] for g in VISIBLE_MODEL}
        for p in players:
            if p.age is None or not 16 <= p.age <= 40 or p.club_uid is None:
                continue
            groups = {GROUP_OF.get(code) for code in p.natural_positions} - {None}
            for g in groups:
                s = visible_score(p, g)
                if s is not None:
                    pools[g].append(s)
        self.pools = {g: sorted(v) for g, v in pools.items()}

        # role pools: everyone natural in the row's in-possession group, scored on your roles' key attributes
        self.role_pools: dict[int, list[float]] = {}
        for i, row in enumerate(FORMATION):
            group = GROUP_OF[row[1]]
            vals = []
            for p in players:
                if p.age is None or not 16 <= p.age <= 40 or p.club_uid is None:
                    continue
                if group in {GROUP_OF.get(code) for code in p.natural_positions}:
                    f = role_score(p.attributes, row)
                    if f is not None:
                        vals.append(f)
            self.role_pools[i] = sorted(vals)

    @staticmethod
    def _rank(pool: list[float], score: float) -> float:
        pool = pool or [score]
        better_or_equal = len(pool) - bisect.bisect_left(pool, score)
        return -math.log10(max(better_or_equal, 1) / len(pool))

    def rating(self, score: float, group: str) -> float:
        return self._rank(self.pools.get(group), score)

    def role_rating(self, score: float, row_index: int) -> float:
        return self._rank(self.role_pools.get(row_index), score)


def role_score(attrs, row) -> float | None:
    """Weighted average of the key attributes of a row's two roles (1-20 scale)."""
    _, _, _, ip_role, oop_role = row
    def avg(keys):
        vals = [getattr(attrs, k, None) for k in keys]
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else None
    ip, oop, style = avg(ROLES["IP"][ip_role][1]), avg(ROLES["OOP"][oop_role][1]), avg(STYLE_KEYS)
    if ip is None or oop is None:
        return None
    roles = IP_WEIGHT * ip + (1 - IP_WEIGHT) * oop
    return roles if style is None else (1 - STYLE_WEIGHT) * roles + STYLE_WEIGHT * style


def familiarity_penalty(rating: int) -> float | None:
    for floor, pen in FAMILIARITY_PENALTY:
        if rating >= floor:
            return pen
    return None


def familiarity_word(rating: int) -> str:
    for floor, word in FAMILIARITY_WORD:
        if rating >= floor:
            return word
    return "ineffective"


OUT_OF_POSITION_PENALTY = 1.8   # familiarity under 5 ("ineffective") — only used in the sandbox


def slot_rating(player, ratings: Ratings, positions: tuple[str, str], cache: dict, row_index: int | None = None,
                open_: bool = False):
    """(rating, 'N'|'A') for a slot played in two phases, or None if he can't play it.

    Half of it is how good he is at the position (visible-attribute model), half how good he is
    at the key attributes of your two roles there, so a quick, fit full-back doesn't pass for a
    winger. Each phase is docked by how familiar he is with that phase's position, weighted the
    same way as the roles (in possession counts a bit more).
    """
    fams = [getattr(player.positions, POS_FIELD[pos], 0) or 0 for pos in positions]
    eligible = max(fams) >= 15 and min(fams) >= FAMILIARITY_PENALTY[-1][0]
    if not eligible and not open_:
        return None
    if open_ and ((getattr(player.positions, "gk", 0) or 0) >= 15) != (positions[0] == "GK"):
        return None          # keepers stay in goal, outfielders stay out of it
    weights = [IP_WEIGHT, 1 - IP_WEIGHT] if positions[0] != positions[1] else [0.5, 0.5]
    model, penalty = 0.0, 0.0
    for pos, fam, w in zip(positions, fams, weights):
        group = GROUP_OF[pos]
        key = (player.uid, group)
        if key not in cache:
            sc = visible_score(player, group)
            cache[key] = None if sc is None else ratings.rating(sc, group)
        if cache[key] is None:
            return None
        model += w * cache[key]
        penalty += w * (familiarity_penalty(fam) if fam >= FAMILIARITY_PENALTY[-1][0] else OUT_OF_POSITION_PENALTY)
    rating = model
    if row_index is not None:
        rs = role_score(player.attributes, FORMATION[row_index])
        if rs is not None:
            rating = (1 - ROLE_WEIGHT) * model + ROLE_WEIGHT * ratings.role_rating(rs, row_index)
    natural = any(f >= 18 for f in fams)
    code = ("N" if natural else "A") if eligible else ("C" if max(fams) >= 9 else "X")
    return rating - penalty, code, model - penalty


def to_stars(rating: float, anchor: dict) -> float:
    spread = max(anchor["top"] - anchor["mid"], 0.05)
    return min(5.0, max(0.5, STAR_MID + (rating - anchor["mid"]) / spread * (STAR_TOP - STAR_MID)))


def half(x: float) -> float:
    return math.floor(x * 2 + 0.5) / 2


# =============================================================================================
# Best XI picking (Hungarian algorithm: best total, every player used once)
# =============================================================================================
def hungarian(cost: list[list[float]]) -> list[int]:
    n, m = len(cost), len(cost[0])
    INF = float("inf")
    u, v, p, way = [0.0] * (n + 1), [0.0] * (m + 1), [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minv, used = [INF] * (m + 1), [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], INF, 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    result = [-1] * n
    for j in range(1, m + 1):
        if p[j]:
            result[p[j] - 1] = j - 1
    return result


def pick_xi(pool: list[dict]) -> list[tuple[str, dict | None]]:
    slots = [row[0] for row in FORMATION]
    n_dummy = len(slots)
    cost = []
    for i, slot in enumerate(slots):
        row = []
        for p in pool:
            r = p["rows"].get(i)
            row.append(1e6 if r is None else -(r[0] + (0.01 if r[1] == "N" else 0)))
        row += [1e3] * n_dummy
        cost.append(row)
    picks = hungarian(cost)
    return [(slot, pool[j] if j < len(pool) else None) for slot, j in zip(slots, picks)]


# =============================================================================================
# Reading the save into plain dicts
# =============================================================================================
BUILD_STEPS = ("Opening your save", "Players and contracts", "Injuries and season stats", "Positions played this season",
               "This season's matches", "Rating the squad", "Best XIs and verdicts", "Writing the report")
PROGRESS_HOOK = None   # the live server sets this to follow a rebuild step by step


def progress(i: int) -> None:
    if PROGRESS_HOOK:
        try:
            PROGRESS_HOOK(i)
        except Exception:  # noqa: BLE001 - progress is cosmetic, never break a build over it
            pass


def build(save, save_path: Path) -> dict:
    notes: list[str] = []
    info = save.info
    today: date = info.game_date
    progress(1)
    managed = list(save.managed_clubs())
    if not managed:
        sys.exit("This save has no club you're managing right now.")
    club = managed[0]
    my = club.club_uid

    print("Reading players…")
    everyone = list(save.players())
    by_uid = {p.uid: p for p in everyone}
    print(f"  {len(everyone):,} players in the database")
    ratings = Ratings(everyone)

    squad = [p for p in everyone if p.club_uid == my]
    loaned_out = [p for p in everyone if p.on_loan and p.loan_parent_club_uid == my and p.club_uid != my]

    # arranged moves (future records in contract chains)
    # A future record with a new contract attached is a transfer; one without (the contract stays
    # with the parent club) is a loan.
    moves_in, moves_out = {}, {}
    loaned_out_uids = {p.uid for p in loaned_out}
    global PLAYER_INDEX
    PLAYER_INDEX = player_index(everyone, {p.uid for p in squad} | loaned_out_uids, my)
    try:
        for c in save.contracts():
            for entry in c.chain:
                if entry.start is None or entry.start <= today:
                    continue
                kind = "transfer" if entry.has_terms else "loan"
                if entry.club_uid == my and c.club_uid != my and c.player_uid in by_uid:
                    moves_in[c.player_uid] = (kind, c.club_name or "?", entry.start)
                elif entry.club_uid not in (my, None) and (c.club_uid == my or c.player_uid in loaned_out_uids):
                    prev = moves_out.get(c.player_uid)
                    if prev is None or entry.start < prev[2]:
                        moves_out[c.player_uid] = (kind, entry.club_name or "another club", entry.start)
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Couldn't read arranged transfers and loans ({type(exc).__name__}).")
    incoming = [by_uid[uid] for uid in moves_in if by_uid[uid].club_uid != my]

    progress(2)
    # injuries: typed rows dated after today are expected return dates
    injuries = {}
    try:
        for row in save.injuries():
            if str(row.kind) == "typed" and row.player_uid is not None and row.date and row.date > today:
                prev = injuries.get(row.player_uid)
                if prev is None or row.date > prev[0]:
                    injuries[row.player_uid] = (row.date, row.type_name or "Injury")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Couldn't read injuries ({type(exc).__name__}).")

    # season stats
    stats: dict[int, list] = {}
    season_rows: list = []
    try:
        print("Reading season stats…")
        season_rows = list(save.player_season_stats())
        for row in season_rows:
            if str(row.kind) != "overall" or row.club_uid != my:
                continue
            apps = row.starts + row.substitute_appearances
            if apps > 0:
                stats.setdefault(row.player_uid, []).append(
                    dict(apps=apps, g=row.goals, a=row.assists, avg=row.average_rating, cs=row.clean_sheets,
                         y=row.yellow_cards, r=row.red_cards, team=row.team_slot))
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Couldn't read season stats ({type(exc).__name__}).")

    finances = None
    try:
        rows = [r for r in save.finances() if r.club_uid == my]
        if rows:
            last = max(rows, key=lambda r: r.month)
            finances = dict(transfer_left=last.transfer_budget_remaining, wage_budget=last.wage_budget_weekly,
                            wage_bill=last.wage_payroll_weekly, month=last.month)
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Couldn't read finances ({type(exc).__name__}).")

    # the first-team squad is whichever team slot holds most senior players
    slot_counts: dict = {}
    for p in squad:
        if (p.age or 0) >= 23:
            slot_counts[p.team_slot] = slot_counts.get(p.team_slot, 0) + 1
    first_slot = max(slot_counts, key=slot_counts.get) if slot_counts else None
    # name the youth teams by average age: older one U21, younger U18
    ages: dict = {}
    for p in squad:
        if p.team_slot != first_slot and p.age:
            ages.setdefault(p.team_slot, []).append(p.age)
    youth_order = sorted(ages, key=lambda t: -sum(ages[t]) / len(ages[t]))
    team_names = {first_slot: "First team"}
    for n, t in enumerate(youth_order):
        team_names[t] = ["U21", "U18"][n] if n < 2 else f"Youth team {n + 1}"

    # ---- this season, from the game's own match data -------------------------------------------
    season_start = date(today.year if today.month >= 7 else today.year - 1, 7, 1)
    first_team_id = None
    try:
        my_club = next(c for c in save.clubs() if c.uid == my)
        first_team_id = next((t.team_id for t in my_club.teams if t.slot == (first_slot or 0)), None)
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Couldn't find your first team ({type(exc).__name__}).")
    played: dict[int, Counter] = {}
    watch_uids = {p.uid for p in squad} | loaned_out_uids | set(moves_in)
    try:
        progress(3)
        print("Reading match records…")
        for r in save.player_match_stats():
            if r.player_uid not in watch_uids or not r.has_stats or r.date < season_start:
                continue
            card = CARD_OF_CODE.get(match_code(r.position))
            if card:
                played.setdefault(r.player_uid, Counter())[card] += 1
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Couldn't read which positions players have played ({type(exc).__name__}).")
    training = []
    try:
        training = read_training(save, today, season_start, team_names)
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Couldn't read your training calendars ({type(exc).__name__}).")
    perf = None
    try:
        progress(4)
        print("Reading this season's matches…")
        perf = season_performance(save, my, first_team_id, season_start, today)
        if perf:
            perf["players"] = player_performance(season_rows, by_uid, my, perf["league_clubs"], played)
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Couldn't read this season's match data ({type(exc).__name__}: {exc}).")

    # ---- per-player records -------------------------------------------------------------
    cache: dict = {}
    slot_defs = {row[0]: (row[1], row[2]) for row in FORMATION}
    slot_defs.update(EXTRA_CARDS)

    def record(p, where: str) -> dict:
        c = p.contract
        rec = dict(uid=p.uid, name=p.name or "Unknown", age=p.age, where=where,
                   youth=(where == "squad" and first_slot is not None and p.team_slot != first_slot),
                   value=p.transfer_value if str(p.transfer_value_state) == "ok" else None,
                   wage=c.wage if c else None, contract_end=c.end if c else None,
                   raw={}, slots={},
                   stats=next((r for r in stats.get(p.uid, []) if r["team"] == first_slot), None),
                   ystats=[r for r in stats.get(p.uid, []) if r["team"] != first_slot])
        rec["rowraw"], rec["araw"] = {}, {}
        for i, row in enumerate(FORMATION):
            r = slot_rating(p, ratings, (row[1], row[2]), cache, i)
            if r is not None:
                rec["rowraw"][i] = r[:2]
                if row[0] not in rec["raw"] or r[0] > rec["raw"][row[0]][0]:
                    rec["raw"][row[0]] = r[:2]
                rec["araw"][row[0]] = max(rec["araw"].get(row[0], -99), r[2])
        rec["orowraw"] = {}
        for i, row in enumerate(FORMATION):
            r = rec["rowraw"].get(i) or slot_rating(p, ratings, (row[1], row[2]), cache, i, open_=True)
            if r is not None:
                rec["orowraw"][i] = r[:2]
        rec["played"] = dict(played.get(p.uid, {}))
        for slot, positions in EXTRA_CARDS.items():
            r = slot_rating(p, ratings, positions, cache)
            if r is not None:
                rec["raw"][slot] = r[:2]
                rec["araw"][slot] = r[2]
        rec["ca"], rec["pa"] = p.ability.current, p.ability.potential   # used only for potential stars
        rec["posr"] = {code: getattr(p.positions, field, 0) or 0 for code, field in POS_FIELD.items()}
        rec["fm_nat"] = [POS_LABEL.get(c, c) for c in p.natural_positions]
        rec["fm_acc"] = [POS_LABEL.get(c, c) for c in p.accomplished_positions]
        if where == "loan_out":
            rec["loan_out"] = (p.club_name or "?", p.loan_end)
        if where == "squad" and p.on_loan:
            rec["loan_in"] = (p.loan_parent_club_name or "?", p.loan_end)
        if p.uid in moves_out:
            kind, club_n, start = moves_out[p.uid]
            rec["deal_out" if kind == "transfer" else "loan_out_arr"] = (club_n, start)
        if where == "incoming":
            kind, club_n, start = moves_in[p.uid]
            rec["deal_in" if kind == "transfer" else "loan_in_arr"] = (club_n, start)
        rec["attrs"] = {a: getattr(p.attributes, a, None) for a in NEEDED_ATTRS}
        rec["groups"] = [GROUP_OF[c] for c in p.natural_positions if c in GROUP_OF]
        rec["natural"] = list(p.natural_positions)
        if p.uid in injuries and where != "incoming":
            ret, what = injuries[p.uid]
            rec["inj"] = ((ret - today).days, what, ret)
        if where == "squad" and p.suspensions:
            recent = [s for s in p.suspensions if (today - s.issued_date).days <= 90]
            if recent:
                rec["sus"] = len(recent)
        if (c and c.end and where in ("squad", "loan_out") and not p.on_loan
                and (c.end - today).days <= CONTRACT_WARNING_DAYS):
            rec["expiring"] = True
        return rec

    players = ([record(p, "squad") for p in squad] + [record(p, "loan_out") for p in loaned_out]
               + [record(p, "incoming") for p in incoming])

    # scouting targets (squad planner + scouting.txt) — only used in the sandbox
    targets = []
    try:
        skip = {p["uid"] for p in players}
        t_players, t_src, t_missing = scouting_targets(save, everyone, by_uid, my, skip)
        for tp, src in zip(t_players, t_src):
            rec = record(tp, "target")
            rec["source"], rec["club"] = src, tp.club_name or "?"
            targets.append(rec)
        if t_missing:
            notes.append("Couldn't find these scouting.txt names in your save: " + ", ".join(t_missing))
    except Exception as exc:  # noqa: BLE001
        notes.append(f"Couldn't read your scouting targets ({type(exc).__name__}).")

    progress(5)
    # ---- stars: squad-relative, anchored on the first run so they stay comparable -------
    history = load_history()
    key = f"{club.club_uid}:{club.club_name}"
    hist = history.setdefault(key, {"anchor": None, "runs": []})
    best_raw = sorted((max(r[0] for r in p["raw"].values()) for p in players
                       if p["raw"] and p["where"] == "squad" and not p["youth"]), reverse=True)
    seniors = [p for p in players if p["raw"] and p["where"] == "squad" and not p["youth"]]
    best_ab = sorted((max(p["araw"].values()) for p in seniors if p["araw"]), reverse=True)
    if not isinstance(hist.get("anchor"), dict) or "atop" not in hist["anchor"]:
        if best_raw and best_ab:
            hist["anchor"] = {"top": best_raw[min(2, len(best_raw) - 1)], "mid": best_raw[len(best_raw) // 2],
                              "atop": best_ab[min(2, len(best_ab) - 1)], "amid": best_ab[len(best_ab) // 2]}
    anchor = hist.get("anchor") if isinstance(hist.get("anchor"), dict) else {"top": 1.0, "mid": 0.0}
    a_anchor = {"top": anchor.get("atop", anchor["top"]), "mid": anchor.get("amid", anchor["mid"])}
    for p in players + targets:
        p["slots"] = {s: (to_stars(r, anchor), fam) for s, (r, fam) in p["raw"].items()}
        p["rows"] = {i: (to_stars(r, anchor), fam) for i, (r, fam) in p["rowraw"].items()}
        p["orows"] = {i: (to_stars(r, anchor), fam) for i, (r, fam) in p["orowraw"].items()}
        p["aslots"] = {s: to_stars(r, a_anchor) for s, r in p["araw"].items()}

    # potential: the hidden potential is put on the same star scale as current ability, by fitting
    # this squad's system stars against its (hidden) current ability. Only the stars are ever shown.
    fit_pts = [(p["ca"], max(r[0] for r in p["slots"].values())) for p in seniors if p.get("ca") and p["slots"]]
    line = None
    if len(fit_pts) >= 6 and len({x for x, _ in fit_pts}) > 1:
        try:
            slope, icpt = statistics.linear_regression([x for x, _ in fit_pts], [y for _, y in fit_pts])
            line = (slope, icpt) if slope > 0 else None
        except statistics.StatisticsError:
            line = None
    for p in players + targets:
        p["trend"] = 0
        p["best"] = max(p["slots"].items(), key=lambda kv: (kv[1][0], kv[1][1] == "N")) if p["slots"] else None
        p["ability"] = p["aslots"].get(p["best"][0]) if p["best"] else None
        p["potential"] = None
        if (SHOW_POTENTIAL and line and p["best"] and p.get("pa") and p.get("ca") and p["where"] != "target"
                and (p["age"] or 99) <= POTENTIAL_MAX_AGE):
            slope, icpt = line
            cur = p["best"][1][0]
            pot = icpt + slope * p["pa"]
            if cur > 0.5:   # keep some of how well he suits your system compared with his raw level
                pot += 0.5 * max(-0.75, min(0.75, cur - (icpt + slope * p["ca"])))
            pot = max(cur, min(5.0, pot))
            if pot - cur >= POTENTIAL_MIN_GAIN:
                p["potential"] = pot

    # trends vs the previous run at an earlier in-game date
    earlier = [r for r in hist["runs"] if r["date"] < today.isoformat()]
    last_run = max(earlier, key=lambda r: r["date"]) if earlier else None
    for p in players:
        p["trend"] = 0
        if last_run and p["best"] and str(p["uid"]) in last_run["stars"]:
            diff = half(p["best"][1][0]) - last_run["stars"][str(p["uid"])]
            if abs(diff) >= 0.5:
                p["trend"] = diff
    hist["runs"] = [r for r in hist["runs"] if r["date"] != today.isoformat()]
    hist["runs"].append({"date": today.isoformat(),
                         "stars": {str(p["uid"]): half(p["best"][1][0]) for p in players if p["best"]}})
    hist["runs"] = sorted(hist["runs"], key=lambda r: r["date"])[-40:]
    save_history(history)

    progress(6)
    # ---- XIs and verdicts (after arranged deals; loaned-out players not counted) ----------
    pool = [p for p in players if p["where"] in ("squad", "incoming") and not LEAVING & p.keys()]
    xi1 = pick_xi(pool)
    used = {id(p) for _, p in xi1 if p}
    xi2 = pick_xi([p for p in pool if id(p) not in used])
    xi_level = sum(p["rows"].get(i, p["slots"][s])[0] for i, (s, p) in enumerate(xi1) if p) / len(FORMATION)
    verdicts = make_verdicts(xi1, xi2, pool, xi_level)
    fit = tactical_fit(players, xi1)

    if not info.known_build:
        notes.append(f"fmsave hasn't fully verified FM build {info.build} yet, so a few numbers could be off.")

    return dict(club=club.club_name, save_name=Path(info.save_name or save_path.stem).stem,
                game_date=today, last_run=last_run["date"] if last_run else None, finances=finances,
                team_names=team_names, targets=targets, perf=perf, training=training,
                players=players, xi1=xi1, xi2=xi2, xi_level=xi_level, verdicts=verdicts, fit=fit, notes=notes)


def load_history() -> dict:
    try:
        return json.loads(HISTORY_FILE.read_text())
    except (OSError, ValueError):
        return {}


def save_history(history: dict) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(history))


# =============================================================================================
# Verdicts
# =============================================================================================
def surname(name: str) -> str:
    return name.split(" ", 1)[1] if " " in name else name


def fmt_stars(x: float) -> str:
    return f"{half(x):g}★"


def make_verdicts(xi1, xi2, pool, xi_level):
    out = []
    groups = list(dict.fromkeys(row[0] for row in FORMATION))
    for g in groups:
        starters = [p for s, p in xi1 if s == g and p]
        backups = [p for s, p in xi2 if s == g]
        n_slots = sum(1 for row in FORMATION if row[0] == g)
        st = lambda p: p["slots"][g][0]   # noqa: E731
        if not starters:
            out.append((g, "red", "Needs a starter", f"Nobody in your squad can play {g} in this tactic.",
                        2.0))
            continue
        weakest = min(starters, key=st)
        strongest = max(starters, key=st)
        gap = xi_level - st(weakest)
        naturals = [p for p in pool if g in p["slots"] and p["slots"][g][1] == "N"]
        best_nat = max((st(p) for p in naturals), default=None)
        others = [p for p in pool if g in p["slots"] and p not in starters]
        next_best = max(others, key=st, default=None)

        # 1. out of position and no natural good enough
        if weakest["slots"][g][1] == "A" and (best_nat is None or best_nat < xi_level - NEEDS_STARTER_GAP):
            nat_txt = f"above {fmt_stars(best_nat)}" if best_nat is not None else "at all"
            out.append((g, "red", "Needs a better starter",
                        f"No natural {g} {nat_txt}. Your best XI only works by playing "
                        f"{surname(weakest['name'])} there out of position.", gap + 0.5))
            continue
        # 2. starter well under the XI level
        if gap >= NEEDS_STARTER_GAP:
            if n_slots > 1 and st(strongest) - st(weakest) >= NEEDS_STARTER_GAP:
                why = (f"{surname(strongest['name'])} ({fmt_stars(st(strongest))}) is carrying it — your next best "
                       f"{g} is {fmt_stars(st(weakest))}, {gap:.1f}★ under your XI level.")
                if (strongest["age"] or 0) >= AGEING_AGE_OUTFIELD:
                    why += f" He's also {strongest['age']}."
            else:
                why = f"Best {g} is {fmt_stars(st(weakest))}, {gap:.1f}★ under your XI level."
                similar = [p for p in pool if g in p["slots"] and abs(st(p) - st(weakest)) <= 0.25]
                if len(similar) >= 3:
                    why += f" {len(similar)} options, all around {fmt_stars(st(weakest))} — it's quality, not numbers."
            out.append((g, "red", "Needs a better starter", why, gap))
            continue
        # 3. ageing starter, big drop behind him
        limit = AGEING_AGE_GK if g == "GK" else AGEING_AGE_OUTFIELD
        old = [p for p in starters if (p["age"] or 0) >= limit]
        if old:
            o = max(old, key=st)
            drop = st(o) - (st(next_best) if next_best else 0)
            if next_best is None or drop >= AGEING_DROP:
                nb = (f"Next best is {surname(next_best['name'])} on {fmt_stars(st(next_best))} — "
                      f"a {half(drop):g}★ drop when he goes." if next_best else "There's nobody behind him.")
                out.append((g, "amber", "Ageing starter", f"{surname(o['name'])} ({fmt_stars(st(o))}) is {o['age']}. {nb}",
                            0.5 + drop / 5))
                continue
        # 4. depth
        missing = sum(1 for b in backups if b is None)
        real_backups = [b for b in backups if b]
        weakest_b = min(real_backups, key=st, default=None)
        if missing:
            out.append((g, "amber", "Needs more depth",
                        f"No backup left. Everyone who can play {g} is already in your first or second XI.", 0.6))
            continue
        if weakest_b and xi_level - st(weakest_b) >= NEEDS_DEPTH_GAP:
            why = (f"Backup is {surname(weakest_b['name'])} ({fmt_stars(st(weakest_b))}, {weakest_b['age']}), "
                   f"{xi_level - st(weakest_b):.1f}★ under your XI level.")
            hurt = [p for p in starters if p.get("inj") and p["inj"][0] >= LONG_INJURY_DAYS]
            if hurt:
                why += f" And {surname(hurt[0]['name'])}'s out for {round(hurt[0]['inj'][0] / 7)} weeks."
            out.append((g, "amber", "Needs more depth", why, 0.5 + (xi_level - st(weakest_b)) / 10))
            continue
        # 5. fine
        s_txt = " and ".join(f"{surname(p['name'])} {fmt_stars(st(p))}" for p in starters)
        b_txt = ", ".join(f"{surname(p['name'])} {fmt_stars(st(p))}" +
                          (f" (arriving {arriving(p).day} {arriving(p):%b})" if arriving(p) else "")
                          for p in real_backups)
        out.append((g, "green", "Sorted", f"{s_txt}, with {b_txt} as cover." if b_txt else f"{s_txt}.", 0))
    order = {"red": 0, "amber": 1, "green": 2}
    out.sort(key=lambda v: (order[v[1]], -v[4]))
    for slot in EXTRA_CARDS:
        out.append((slot, "grey", "Not in your tactic", "Shown for cover only.", 0))
    return out


# =============================================================================================
# Tactical fit (visible attributes only)
# =============================================================================================
def row_labels() -> list[str]:
    totals: dict[str, int] = {}
    for row in FORMATION:
        totals[row[0]] = totals.get(row[0], 0) + 1
    seen: dict[str, int] = {}
    labels = []
    for row in FORMATION:
        s = row[0]
        seen[s] = seen.get(s, 0) + 1
        if totals[s] == 1:
            labels.append(s)
        elif totals[s] == 2:
            labels.append(("L" if seen[s] == 1 else "R") + s)
        else:
            labels.append(f"{s}{seen[s]}")
    return labels


def mean(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def role_fit(p, row):
    _, ip_pos, oop_pos, ip_role, oop_role = row
    ip_keys, oop_keys = ROLES["IP"][ip_role][1], ROLES["OOP"][oop_role][1]
    a = p["attrs"]
    ip_fit, oop_fit = mean(a.get(k) for k in ip_keys), mean(a.get(k) for k in oop_keys)
    style = mean(a.get(k) for k in STYLE_KEYS)
    if ip_fit is None or oop_fit is None:
        return None
    roles = IP_WEIGHT * ip_fit + (1 - IP_WEIGHT) * oop_fit
    fit = roles if style is None else (1 - STYLE_WEIGHT) * roles + STYLE_WEIGHT * style
    general = mean(a.get(k) for k in VISIBLE_MODEL[GROUP_OF[ip_pos]]["w"])
    keys = list(dict.fromkeys(ip_keys + oop_keys))
    weak = sorted((a[k], k) for k in keys if a.get(k) is not None and a[k] <= WEAK_ATTR)
    style_weak = sorted((a[k], k) for k in STYLE_KEYS if a.get(k) is not None and a[k] <= WEAK_ATTR)
    return dict(fit=fit, ip=ip_fit, oop=oop_fit, style=style, suit=fit - (general or fit), weak=weak,
                style_weak=style_weak)


def tactical_fit(players, xi1):
    labels = row_labels()
    in_xi = {(s, id(p)) for s, p in xi1 if p}
    usable = [p for p in players if p["where"] in ("squad", "incoming") and not p["youth"]
              and not LEAVING & p.keys()]
    rows = []
    for label, row in zip(labels, FORMATION):
        slot = row[0]
        entries = []
        for p in usable:
            if slot not in p["slots"]:
                continue
            f = role_fit(p, row)
            if f:
                entries.append(dict(p=p, xi=(slot, id(p)) in in_xi, **f))
        entries.sort(key=lambda e: -e["fit"])
        rows.append(dict(label=label, row=row, entries=entries))

    misfits = []
    for p in usable:
        options = [(e, r) for r in rows for e in r["entries"] if e["p"] is p]
        if not options:
            half = []
            for row in FORMATION:
                ip_f, oop_f = p["posr"].get(row[1], 0), p["posr"].get(row[2], 0)
                if max(ip_f, oop_f) >= 15 and row[1] != row[2]:
                    weak_code = row[2] if ip_f >= oop_f else row[1]
                    phase = "out of possession" if weak_code == row[2] else "in possession"
                    half.append(f"your {row[0]} plays {POS_LABEL[weak_code]} {phase} and he can't")
            if half:
                why = "Plays the position, but " + "; ".join(dict.fromkeys(half)) + "."
            else:
                nat = ", ".join(POS_LABEL.get(c, c) for c in p.get("natural") or []) or "?"
                why = f"None of his positions ({nat}) are in your tactic."
            misfits.append(dict(p=p, why=why, best=None))
            continue
        e, r = max(options, key=lambda er: er[0]["fit"])
        reasons = []
        if e["fit"] < FIT_FLOOR:
            reasons.append(f"his key attributes for {r['label']} only average {e['fit']:.1f}")
        if e["suit"] <= -SUIT_GAP:
            reasons.append("his strengths don't match what the role needs")
        if len(e["weak"]) >= 2:
            reasons.append(f"{len(e['weak'])} key attributes at {WEAK_ATTR} or below")
        if e["style"] is not None and e["style"] < STYLE_FLOOR:
            reasons.append(f"not built for {TACTICAL_STYLE.lower()} (its attributes average {e['style']:.1f})")
        if reasons:
            why = "; ".join(reasons)
            misfits.append(dict(p=p, why=why[0].upper() + why[1:] + ".", best=(e, r)))
    misfits.sort(key=lambda m: (m["best"] is not None, m["best"][0]["fit"] if m["best"] else 0))
    return dict(rows=rows, misfits=misfits)


# =============================================================================================
# This season, from the game's own match data (what FM's Data Hub shows) — no hidden info
# =============================================================================================
# The save stores the position a player filled in each match as one bit, in FM's position order.
MATCH_BIT_CODE = {0: "GK", 1: "SW", 2: "DR", 3: "DL", 4: "DC", 5: "WBR", 6: "WBL", 7: "DM", 8: "MR", 9: "ML",
                  10: "MC", 11: "AMR", 12: "AML", 13: "AMC", 14: "STC"}
CARD_OF_CODE = {"GK": "GK", "SW": "CB", "DC": "CB", "DL": "LB", "WBL": "LB", "DR": "RB", "WBR": "RB", "DM": "DM",
                "MC": "CM", "ML": "LW", "AML": "LW", "MR": "RW", "AMR": "RW", "AMC": "AM", "STC": "ST", "ST": "ST"}
CARD_CODES = {}
for _code, _card in CARD_OF_CODE.items():
    CARD_CODES.setdefault(_card, []).append(_code)


def match_code(pos) -> str | None:
    raw = getattr(pos, "raw", None)
    if not raw or raw & (raw - 1):
        return None
    return MATCH_BIT_CODE.get(raw.bit_length() - 1)


# Team numbers: (key, label, higher is better, unit, what it says when it's one of your best / worst)
TEAM_METRICS = [
    ("gf", "Goals scored", True, "per game", "you're scoring freely", "goals are drying up"),
    ("ga", "Goals conceded", False, "per game", "hard to score against", "leaking goals"),
    ("xg", "Expected goals (xG)", True, "per game", "creating big chances", "not creating enough good chances"),
    ("xga", "xG against", False, "per game", "opponents barely get a sniff", "opponents get good chances"),
    ("shots", "Shots", True, "per game", "constant pressure on goal", "not many shots"),
    ("ccc", "Clear-cut chances", True, "per game", "carving teams open", "few clear-cut chances"),
    ("ccc_ag", "Clear-cut chances conceded", False, "per game", "rarely opened up", "getting opened up"),
    ("poss", "Possession", True, "%", "dominating the ball", "losing the ball battle"),
    ("pass_pct", "Pass completion", True, "%", "keeping the ball well", "sloppy in possession"),
    ("prog", "Progressive passes", True, "per game", "moving the ball forward quickly", "struggling to progress the ball"),
    ("final3", "Final-third passes", True, "per game", "living in the final third", "not getting into the final third"),
    ("opp_pass_pct", "Opponents' pass completion", False, "%", "the press is biting — they can't keep the ball",
     "opponents pass through your press too easily"),
    ("opp_final3", "Opponents' final-third passes", False, "per game", "keeping teams pinned back",
     "opponents get into your final third a lot"),
    ("tackle_pct", "Tackles won", True, "%", "winning the ball back", "losing too many tackles"),
    ("aerial_pct", "Aerial duels won", True, "%", "strong in the air", "losing headers"),
    ("dist", "Distance covered", True, "km per game", "outrunning teams", "being outrun"),
    ("dist_diff", "Running vs opponents", True, "km per game", "outworking opponents", "opponents run more than you"),
    ("cross_pct", "Cross accuracy", True, "%", "crosses are finding people", "crosses aren't landing"),
    ("finishing", "Goals vs xG", True, "per game", "finishing above expectation", "wasting chances"),
    ("keeping", "Goals conceded vs xG against", True, "per game", "keeper and defence beat expectation",
     "conceding more than the chances deserve"),
    ("fouls", "Fouls", False, "per game", "disciplined", "giving away a lot of fouls"),
]


def season_performance(save, my: int, first_team_id: int | None, season_start: date, today: date) -> dict | None:
    """League-wide team numbers for this season, ranked, plus your record. Built from fixtures,
    league tables and the match stats screens the game keeps."""
    if first_team_id is None:
        return None
    clubs = list(save.clubs())
    team_club = {t.team_id: c for c in clubs for t in c.teams}
    fx = [f for f in save.fixtures() if f.played and f.date and season_start <= f.date <= today]
    mine = sorted((f for f in fx if first_team_id in (f.home_team_id, f.away_team_id)), key=lambda f: f.date)
    if not mine:
        return None
    comp_counts: dict = {}
    for f in mine:
        comp_counts[f.competition_id] = comp_counts.get(f.competition_id, 0) + 1
    tables = {t.competition_id: t for t in save.league_tables() if any(r.team_id == first_team_id for r in t.rows)}
    league = next((c for c, _ in sorted(comp_counts.items(), key=lambda kv: -kv[1]) if c in tables), None)
    table = tables.get(league)
    league_teams = [r.team_id for r in table.rows] if table else []

    goals = {(f.competition_id, f.home_team_id, f.away_team_id, f.date): (f.home_goals, f.away_goals) for f in fx}
    per_team: dict[int, list] = {t: [] for t in league_teams}
    rows = [r for r in save.team_match_stats() if r.competition_id == league and season_start <= r.date <= today]
    by_match: dict = {}
    for r in rows:
        by_match.setdefault((r.competition_id, r.home_team_id, r.away_team_id, r.date), []).append(r)
    for key, pair in by_match.items():
        if len(pair) != 2:
            continue
        hg, ag = goals.get(key, (None, None))
        for own, opp in ((pair[0], pair[1]), (pair[1], pair[0])):
            if own.team_id in per_team:
                gf, ga = (hg, ag) if own.is_home else (ag, hg)
                per_team[own.team_id].append((own, opp, gf, ga))

    # goals per game come from every league result, not just the matches with stored reports
    results: dict[int, list] = {t: [] for t in league_teams}
    for f in fx:
        if f.competition_id != league or f.home_goals is None or f.away_goals is None:
            continue
        if f.home_team_id in results:
            results[f.home_team_id].append((f.home_goals, f.away_goals))
        if f.away_team_id in results:
            results[f.away_team_id].append((f.away_goals, f.home_goals))

    def pct(a, b):
        return 100.0 * a / b if b else None

    def metrics(team):
        ms, res = per_team.get(team, []), results.get(team, [])
        out = {}
        if res:
            out["gf"] = sum(g for g, _ in res) / len(res)
            out["ga"] = sum(g for _, g in res) / len(res)
        if len(ms) < 3:
            return out, len(ms)
        n = len(ms)
        avg = lambda f: sum(f(o, x) for o, x, _, _ in ms) / n  # noqa: E731
        out.update(
            xg=avg(lambda o, x: o.expected_goals), xga=avg(lambda o, x: x.expected_goals),
            shots=avg(lambda o, x: o.shots), ccc=avg(lambda o, x: o.clear_cut_chances),
            ccc_ag=avg(lambda o, x: x.clear_cut_chances), poss=avg(lambda o, x: o.possession_percent),
            prog=avg(lambda o, x: o.progressive_passes or 0), final3=avg(lambda o, x: o.final_third_passes),
            opp_final3=avg(lambda o, x: x.final_third_passes), dist=avg(lambda o, x: o.distance_km),
            dist_diff=avg(lambda o, x: o.distance_km - x.distance_km), fouls=avg(lambda o, x: o.fouls_made),
            pass_pct=pct(sum(o.passes_completed for o, *_ in ms), sum(o.passes_attempted for o, *_ in ms)),
            opp_pass_pct=pct(sum(x.passes_completed for _, x, *_ in ms), sum(x.passes_attempted for _, x, *_ in ms)),
            tackle_pct=pct(sum(o.tackles_completed for o, *_ in ms), sum(o.tackles_attempted for o, *_ in ms)),
            aerial_pct=pct(sum(o.headers_won for o, *_ in ms), sum(o.aerial_challenges_attempted for o, *_ in ms)),
            cross_pct=pct(sum(o.crosses_completed for o, *_ in ms), sum(o.crosses_attempted for o, *_ in ms)),
        )
        known = [(o, x, gf, ga) for o, x, gf, ga in ms if gf is not None]
        if known:
            out["finishing"] = sum(gf - o.expected_goals for o, _, gf, _ in known) / len(known)
            out["keeping"] = sum(x.expected_goals - ga for _, x, _, ga in known) / len(known)
        return out, n

    all_m = {t: metrics(t)[0] for t in league_teams}
    mine_m, reports = metrics(first_team_id)
    ranked = []
    for key, label, higher, unit, good, bad in TEAM_METRICS:
        if mine_m.get(key) is None:
            continue
        vals = [m[key] for m in all_m.values() if m.get(key) is not None]
        if len(vals) < 6:
            continue
        better = sum(1 for v in vals if (v > mine_m[key] if higher else v < mine_m[key]))
        league_avg = sum(vals) / len(vals)
        ranked.append(dict(key=key, label=label, value=mine_m[key], unit=unit, rank=better + 1, of=len(vals),
                           avg=league_avg, good=good, bad=bad, higher=higher,
                           above=(mine_m[key] >= league_avg) if higher else (mine_m[key] <= league_avg)))

    record = None
    if table:
        row = next(r for r in table.rows if r.team_id == first_team_id)
        record = dict(pos=row.position, of=len(table.rows), p=row.played, w=row.won, d=row.drawn, l=row.lost,
                      gf=row.goals_for, ga=row.goals_against, pts=row.points)
    form = []
    for f in mine[-6:]:
        if f.home_goals is None or f.away_goals is None:
            continue
        home = f.home_team_id == first_team_id
        us, them = (f.home_goals, f.away_goals) if home else (f.away_goals, f.home_goals)
        opp = team_club.get(f.away_team_id if home else f.home_team_id)
        form.append(dict(res="W" if us > them else "D" if us == them else "L", score=f"{us}–{them}",
                         opp=opp.short_name or opp.name if opp else "?", home=home, date=f.date))
    league_clubs = {team_club[t].uid for t in league_teams if t in team_club}
    league_name = None
    try:
        league_name = next((c.name for c in save.competitions() if c.id == league), None)
    except Exception:  # noqa: BLE001
        pass
    return dict(metrics=ranked, record=record, form=form[-5:], reports=reports, league=league,
                league_name=league_name, league_clubs=league_clubs)


# Player numbers per 90 minutes, by position group: (key, label, higher is better, gegenpress-related)
PLAYER_METRICS = {
    "GK": [("xgp", "xG prevented", True, False), ("save_pct", "Save %", True, False),
           ("pass_pct", "Pass completion", True, False), ("mistakes", "Mistakes leading to goals", False, False)],
    "CB": [("aerial_pct", "Headers won %", True, False), ("tackle_pct", "Tackles won %", True, False),
           ("int90", "Interceptions", True, True), ("won90", "Possession won", True, True),
           ("blocks90", "Blocks", True, False), ("pass_pct", "Pass completion", True, False),
           ("prog90", "Progressive passes", True, False), ("lost90", "Possession lost", False, False),
           ("mistakes", "Mistakes leading to goals", False, False)],
    "FB/WB": [("prog90", "Progressive passes", True, False), ("kp90", "Key passes", True, False),
              ("xa90", "Expected assists (xA)", True, False), ("crossc90", "Crosses completed", True, False),
              ("tackles90", "Tackles won", True, True), ("int90", "Interceptions", True, True),
              ("won90", "Possession won", True, True), ("dist90", "Distance covered", True, True),
              ("sprints90", "Sprints", True, True), ("lost90", "Possession lost", False, False)],
    "DM": [("won90", "Possession won", True, True), ("int90", "Interceptions", True, True),
           ("tackle_pct", "Tackles won %", True, True), ("tackles90", "Tackles won", True, True),
           ("pass_pct", "Pass completion", True, False), ("prog90", "Progressive passes", True, False),
           ("kp90", "Key passes", True, False), ("dist90", "Distance covered", True, True),
           ("lost90", "Possession lost", False, False)],
    "CM": [("prog90", "Progressive passes", True, False), ("kp90", "Key passes", True, False),
           ("pass_pct", "Pass completion", True, False), ("won90", "Possession won", True, True),
           ("tackles90", "Tackles won", True, True), ("dist90", "Distance covered", True, True),
           ("xa90", "Expected assists (xA)", True, False), ("lost90", "Possession lost", False, False)],
    "AM": [("npxg90", "Non-penalty xG", True, False), ("xa90", "Expected assists (xA)", True, False),
           ("kp90", "Key passes", True, False), ("ccc90", "Clear-cut chances created", True, False),
           ("dribbles90", "Dribbles", True, False), ("shots90", "Shots", True, False),
           ("won90", "Possession won", True, True), ("dist90", "Distance covered", True, True),
           ("finish", "Goals vs xG", True, False), ("lost90", "Possession lost", False, False)],
    "WIDE": [("npxg90", "Non-penalty xG", True, False), ("xa90", "Expected assists (xA)", True, False),
             ("dribbles90", "Dribbles", True, False), ("kp90", "Key passes", True, False),
             ("ccc90", "Clear-cut chances created", True, False), ("shots90", "Shots", True, False),
             ("won90", "Possession won", True, True), ("sprints90", "Sprints", True, True),
             ("finish", "Goals vs xG", True, False), ("lost90", "Possession lost", False, False)],
    "ST": [("npxg90", "Non-penalty xG", True, False), ("finish", "Goals vs xG", True, False),
           ("sot_pct", "Shots on target %", True, False), ("shots90", "Shots", True, False),
           ("xa90", "Expected assists (xA)", True, False), ("headers90", "Headers won", True, False),
           ("won90", "Possession won", True, True), ("sprints90", "Sprints", True, True),
           ("offsides90", "Offsides", False, False)],
}


def player_numbers(r) -> dict:
    m = max(r.minutes, 1) / 90.0
    def div(a, b):
        return None if not b else 100.0 * a / b
    saves = sum(v or 0 for v in (r.saves_held, r.saves_parried, r.saves_tipped))
    return dict(
        xgp=r.expected_goals_prevented / m, save_pct=div(saves, r.shots_on_target_faced),
        pass_pct=div(r.passes_completed, r.passes_attempted), mistakes=r.mistakes_leading_to_goal,
        aerial_pct=div(r.headers_won or 0, r.aerial_challenges_attempted), tackle_pct=div(r.tackles_completed, r.tackles_attempted),
        int90=r.interceptions / m, won90=r.possession_won / m, blocks90=(r.blocks or 0) / m, prog90=r.progressive_passes / m,
        lost90=r.possession_lost / m, kp90=r.key_passes / m, xa90=r.expected_assists / m,
        crossc90=r.crosses_completed / m, tackles90=r.tackles_completed / m, dist90=r.distance_km / m,
        sprints90=r.high_intensity_sprints / m, npxg90=r.non_penalty_expected_goals / m,
        ccc90=r.clear_cut_chances_created / m, dribbles90=r.dribbles / m, shots90=r.shots / m,
        finish=(r.goals - r.penalties_scored - r.non_penalty_expected_goals) / m,
        sot_pct=div(r.shots_on_target, r.shots), headers90=(r.headers_won or 0) / m, offsides90=r.offsides / m,
    )


PERF_GROUP_OF_CARD = {"GK": "GK", "CB": "CB", "LB": "FB/WB", "RB": "FB/WB", "DM": "DM", "CM": "CM", "AM": "AM",
                      "LW": "WIDE", "RW": "WIDE", "ST": "ST"}
PERF_GROUP_OF_CODE = {"GK": "GK", "SW": "CB", "DC": "CB", "DL": "FB/WB", "DR": "FB/WB", "WBL": "FB/WB",
                      "WBR": "FB/WB", "DM": "DM", "MC": "CM", "AMC": "AM", "ML": "WIDE", "MR": "WIDE",
                      "AML": "WIDE", "AMR": "WIDE", "STC": "ST", "ST": "ST"}
PERF_GROUP_NAME = {"GK": "goalkeepers", "CB": "centre backs", "FB/WB": "full-backs", "DM": "defensive midfielders",
                   "CM": "central midfielders", "AM": "attacking midfielders", "WIDE": "wingers", "ST": "strikers"}
PERF_MIN_MINUTES = 450
PERF_GOOD, PERF_BAD = 75, 25   # percentiles vs league players in the same position


def player_performance(season_rows, by_uid, my: int, league_clubs: set, played: dict) -> dict:
    """Each of your first-team players' league numbers per 90, as percentiles against every league
    player in the same position group with enough minutes."""
    peers: dict[str, list[dict]] = {}
    mine: dict[int, tuple[str, dict, int, float | None]] = {}
    for r in season_rows:
        if str(r.kind) != "league" or r.team_slot not in (0, None) or r.minutes < PERF_MIN_MINUTES:
            continue
        if r.club_uid not in league_clubs and r.club_uid != my:
            continue
        p = by_uid.get(r.player_uid)
        if p is None:
            continue
        nat = next((c for c in p.natural_positions if c in PERF_GROUP_OF_CODE), None)
        if r.club_uid == my and played.get(r.player_uid):
            card = played[r.player_uid].most_common(1)[0][0]
            group = PERF_GROUP_OF_CARD.get(card) or PERF_GROUP_OF_CODE.get(nat)
        else:
            group = PERF_GROUP_OF_CODE.get(nat)
        if group is None:
            continue
        nums = player_numbers(r)
        peers.setdefault(group, []).append(nums)
        if r.club_uid == my:
            mine[r.player_uid] = (group, nums, r.minutes, r.average_rating)
    out = {}
    for uid, (group, nums, minutes, avg) in mine.items():
        good, bad = [], []
        pool = peers.get(group, [])
        if len(pool) < 8:
            continue
        for key, label, higher, press in PLAYER_METRICS[group]:
            v = nums.get(key)
            vals = [n[key] for n in pool if n.get(key) is not None]
            if v is None or len(vals) < 8:
                continue
            below = sum(1 for x in vals if x < v)
            equal = sum(1 for x in vals if x == v)
            pctl = 100.0 * (below + 0.5 * equal) / len(vals)
            if not higher:
                pctl = 100 - pctl
            item = dict(key=key, label=label, value=v, pctl=pctl, press=press, higher=higher)
            if pctl >= PERF_GOOD:
                good.append(item)
            elif pctl <= PERF_BAD:
                bad.append(item)
        good.sort(key=lambda i: -i["pctl"])
        bad.sort(key=lambda i: i["pctl"])
        out[uid] = dict(group=group, good=good[:4], bad=bad[:3], minutes=minutes, avg=avg, peers=len(pool))
    return out


# =============================================================================================
# Scouting targets: players from your FM squad planner + names you list in scouting.txt
# =============================================================================================
SCOUTING_FILE = APP_DIR / "scouting.txt"
SCOUTING_HELP = """# Players you're scouting. One per line, e.g.
#   Fabian Mrozek
#   Joshua Kimmich, Bayern     <- add the club after a comma if the name isn't unique
# Anyone from another club in your FM Squad Planner is added automatically.
"""


def norm_name(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "")
    return " ".join("".join(ch for ch in s if not unicodedata.combining(ch)).lower().replace("-", " ").split())


PLAYER_INDEX: list = []   # every player in the save who isn't yours, for the Sandbox's player picker (live mode)


def player_index(everyone, skip_uids: set, my: int) -> list[tuple]:
    """(uid, name, club, age, positions, search key). Public facts only: no attributes, values or ratings,
    so the picker can't be used to scout players the way FM's own scouts would."""
    out = []
    for p in everyone:
        if not p.name or p.uid in skip_uids or p.club_uid == my:
            continue
        club = p.club_name or "Free agent"
        pos = " ".join(dict.fromkeys(POS_LABEL.get(c, c) for c in p.natural_positions))
        out.append((p.uid, p.name, club, p.age, pos, norm_name(f"{p.name} {club}")))
    return out


def search_players(q: str, pos: str = "", max_age: str = "", limit: int = 40) -> dict:
    """Name or club search over PLAYER_INDEX. Sorted by how well the name matches, then club and name, never by quality."""
    if not PLAYER_INDEX:
        return {"ready": False, "total": 0, "items": []}
    words = norm_name(q).split()
    if len("".join(words)) < 2:
        return {"ready": True, "total": 0, "items": []}
    cap = int(max_age) if max_age.isdigit() else None
    joined = " ".join(words)
    hits = []
    for uid, name, club, age, poss, key in PLAYER_INDEX:
        if not all(w in key for w in words):
            continue
        if pos and pos not in poss.split():
            continue
        if cap is not None and (age is None or age > cap):
            continue
        nn = norm_name(name)
        parts = nn.split()
        rank = (0 if nn == joined or parts[-1:] == [joined] else 1 if nn.startswith(joined)
                else 2 if any(part.startswith(words[0]) for part in parts) else 3)
        hits.append((rank, club.lower(), nn, uid, name, club, age, poss))
    hits.sort()
    items = [dict(uid=h[3], n=h[4], c=h[5], a=h[6], p=h[7]) for h in hits[:limit]]
    return {"ready": True, "total": len(hits), "items": items}


def scouting_targets(save, everyone, by_uid: dict, my: int, skip: set) -> tuple[list, list[str], list[str]]:
    """(players, where each came from, names that couldn't be found)."""
    found, source, missing = [], [], []
    seen = set(skip)
    try:
        for slot in save.squad_planner():
            for uid in slot.player_uids:
                p = by_uid.get(uid) if uid else None
                if p is not None and p.club_uid != my and uid not in seen:
                    seen.add(uid)
                    found.append(p)
                    source.append("squad planner")
    except Exception:  # noqa: BLE001
        pass
    try:
        lines = SCOUTING_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    index: dict[str, list] = {}
    for p in everyone:
        if p.name:
            index.setdefault(norm_name(p.name), []).append(p)
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tagged = re.search(r"\[(\d+)\]\s*$", line)
        if tagged:
            p = by_uid.get(int(tagged.group(1)))
            if p is not None:
                if p.uid not in seen and p.club_uid != my:
                    seen.add(p.uid)
                    found.append(p)
                    source.append("your scouting list")
                continue
            line = line[:tagged.start()].strip()   # not in this save any more: fall back to the name
        name, _, club_hint = (part.strip() for part in line.replace("|", ",").partition(","))
        cands = index.get(norm_name(name), [])
        if not cands:   # surname only, or a slightly different spelling of the first name
            q = norm_name(name).split()
            cands = [p for k, ps in index.items() if q and k.split()[-1:] == q[-1:] and
                     all(w in k.split() for w in q) for p in ps]
        if club_hint:
            hinted = [p for p in cands if norm_name(club_hint) in norm_name(p.club_name or "")]
            cands = hinted or cands
        if not cands:
            missing.append(line)
            continue
        p = max(cands, key=lambda x: x.transfer_value or 0)
        if p.uid in seen or p.club_uid == my:
            continue
        seen.add(p.uid)
        found.append(p)
        source.append("your scouting list")
    return found, source, missing



# =============================================================================================
# HTML
# =============================================================================================
E = html.escape


def money(v):
    if v is None:
        return "–"
    if abs(v) >= 1_000_000_000:
        return f"£{v / 1_000_000_000:.2f}bn"
    if abs(v) >= 1_000_000:
        m = v / 1_000_000
        return f"£{m:.1f}m" if abs(m) < 10 else f"£{m:.0f}m"
    return f"£{v / 1000:.0f}k"


def wage(v):
    if v is None:
        return "–"
    return f"£{v / 1_000_000:.2f}m" if v >= 1_000_000 else f"£{v / 1000:.0f}k"


def d(dt, fmt=None):
    if not dt:
        return "–"
    return dt.strftime(fmt) if fmt else f"{dt.day} {dt:%b %Y}"


def stars(r, small=False):
    r = half(r)
    cls = "stars sm" if small else "stars"
    return (f'<span class="{cls}" title="{r:g} stars">★★★★★'
            f'<span class="on" style="width:{r / 5 * 100:.0f}%">★★★★★</span></span>')


def trend(t):
    if not t:
        return ""
    return f'<span class="trend {"up" if t > 0 else "down"}">{"▲" if t > 0 else "▼"} {abs(t):g}</span>'


def short(name):
    return name if len(name) <= 15 else name.split(" ", 1)[1]


def injury_text(days):
    return f"{days} day{'s' if days != 1 else ''}" if days < 14 else f"{round(days / 7)} wks"


def badges(p, compact=False):
    out = []
    if "deal_in" in p:
        out.append(("deal-in", "Transfer in", f"from {p['deal_in'][0]} · joins {d(p['deal_in'][1])}"))
    if "deal_out" in p:
        out.append(("deal-out", "Transfer out", f"to {p['deal_out'][0]} · leaves {d(p['deal_out'][1])}"))
    if "loan_in_arr" in p:
        out.append(("loan-in arr", "Loan in (arranged)", f"from {p['loan_in_arr'][0]} · joins {d(p['loan_in_arr'][1])}"))
    if "loan_out_arr" in p:
        out.append(("loan-out arr", "Loan out (arranged)", f"to {p['loan_out_arr'][0]} · leaves {d(p['loan_out_arr'][1])}"))
    if "loan_in" in p:
        out.append(("loan-in", "Loan in", f"from {p['loan_in'][0]} · until {d(p['loan_in'][1])}"))
    if "loan_out" in p:
        out.append(("loan-out", "Loan out", f"at {p['loan_out'][0]} · back {d(p['loan_out'][1])}"))
    if "inj" in p:
        days, what, _ = p["inj"]
        out.append(("inj-long" if days >= LONG_INJURY_DAYS else "inj-short", "Injured",
                    f"{injury_text(days)} · {what} · back {d(p['inj'][2])}"))
    if "sus" in p:
        out.append(("sus", "Suspended", f"{p['sus']} ban" + ("s" if p["sus"] > 1 else "")))
    if p.get("expiring") and "deal_out" not in p:
        out.append(("expiring", "Contract", f"ends {d(p['contract_end'], '%b %Y')}"))
    if compact:
        return "".join(f'<span class="badge {c}" title="{E(lbl)} — {E(det)}">{E(lbl)}</span>' for c, lbl, det in out)
    return "".join(f'<span class="badge {c}"><b>{E(lbl)}</b> {E(det)}</span>' for c, lbl, det in out)


def row_state(p):
    for key, cls in (("deal_out", "deal-out"), ("deal_in", "deal-in"), ("loan_out_arr", "loan-out"),
                     ("loan_in_arr", "loan-in"), ("loan_out", "loan-out"), ("loan_in", "loan-in")):
        if key in p:
            return cls
    if "inj" in p:
        return "inj-long" if p["inj"][0] >= LONG_INJURY_DAYS else "inj-short"
    return "sus" if "sus" in p else ""


STATUS_KEYS = ("deal_in", "deal_out", "loan_in_arr", "loan_out_arr", "loan_in", "loan_out")


def overview(R):
    f = R["finances"]
    squad = [p for p in R["players"] if p["where"] == "squad"]
    inj = sum(1 for p in squad if "inj" in p)
    sus = sum(1 for p in squad if "sus" in p)
    tiles = []
    if f:
        room = f["wage_budget"] - f["wage_bill"]
        pct = min(100, f["wage_bill"] / f["wage_budget"] * 100) if f["wage_budget"] else 0
        tiles.append(f"""<div class="tile"><div class="lbl">Transfer budget left</div><div class="val">{money(f['transfer_left'])}</div>
          <div class="sub">as of {E(d(f['month'], '%b %Y'))} month-end</div></div>""")
        tiles.append(f"""<div class="tile"><div class="lbl">Wage bill / budget (p/w)</div>
          <div class="val">{wage(f['wage_bill'])} <span class="of">/ {wage(f['wage_budget'])}</span></div>
          <div class="bar"><i style="width:{pct:.0f}%"></i></div><div class="sub">{wage(abs(room))}/wk {'room' if room >= 0 else 'over'}</div></div>""")
    tiles.append(f"""<div class="tile"><div class="lbl">XI level</div><div class="val">{stars(R['xi_level'])} <span class="of">{R['xi_level']:.1f}</span></div>
      <div class="sub">average of your best XI</div></div>""")
    tiles.append(f"""<div class="tile"><div class="lbl">Unavailable now</div><div class="val">{inj + sus} <span class="of">players</span></div>
      <div class="sub">{inj} injured · {sus} suspended</div></div>""")

    by_uid = {id(p): p for p in R["players"]}
    need = [v for v in R["verdicts"] if v[1] in ("red", "amber")]
    ok = [v for v in R["verdicts"] if v[1] in ("green", "grey")]
    cards = []
    for i, (slot, level, title, reason, _) in enumerate(need, 1):
        xi = [p for s, p in R["xi1"] if s == slot]
        bk = [p for s, p in R["xi2"] if s == slot]

        def line(label, people):
            bits = []
            for p in people:
                if p is None:
                    bits.append('<em class="none">nobody left</em>')
                    continue
                r, fam = p["slots"][slot]
                bits.append(f'{E(surname(p["name"]))} {stars(r, True)}<span class="fam {fam}">{fam}</span>')
            return f'<div class="who"><span class="wl">{label}</span>{" · ".join(bits)}</div>'

        cards.append(f"""<div class="vcard {level}"><div class="vhead"><span class="rank">{i}</span><span class="slot">{slot}</span>
          <span class="vtitle">{E(title)}</span></div><p>{E(reason)}</p>
          {line('Starters' if len(xi) > 1 else 'Starter', xi)}{line('Backups' if len(bk) > 1 else 'Backup', bk)}</div>""")
    chips = "".join(f'<div class="okchip {lvl}"><span class="slot">{s}</span><b>{E(t)}</b><span>{E(r)}</span></div>'
                    for s, lvl, t, r, _ in ok)
    empty = '<div class="allgood">Nothing urgent — every position in your tactic is covered. 🔥</div>' if not need else ""
    del by_uid
    news = "".join(f'<li><a href="#{r}"><span class="tag {c}">{E(t)}</span><span>{E(x)}</span></a></li>' for c, t, x, r in ticker_items(R)[:8])
    latest = f'<section class="ph-only ph-news"><h2>Latest</h2><ul class="news">{news}</ul></section>' if news else ""
    return f"""{home_hero(R)}{latest}<section><h2>Club snapshot</h2><div class="fin">{''.join(tiles)}</div></section>
<div class="explain"><b>How to read the stars.</b> <span class="kc sty">System ★</span> = how good a player is in <i>your</i>
  {E(FORMATION_NAME)} {E(TACTICAL_STYLE)}: his position, the key attributes of your roles there, and the {E(TACTICAL_STYLE.lower())} attributes.
  <span class="kc both">Ability ★</span> = how good he is at that position in general, ignoring your tactic.
  So a 5★ system player is elite <i>for your system</i>; his ability ★ (Squad tab) shows whether he's elite full stop.
  {'<span class="kc ip">Potential ★</span> appears for players ' + str(POTENTIAL_MAX_AGE) + ' and under who could grow ' + format(POTENTIAL_MIN_GAIN, 'g') + '★+ more.' if SHOW_POTENTIAL else ''}</div>
<section><h2>Where the squad needs work <span class="h2sub">after arranged transfers &amp; loans go through · loaned-out players not counted</span></h2>
  {empty}<div class="vgrid">{''.join(cards)}</div><div class="okrow">{chips}</div></section>"""


def pitch(title, xi, sub):
    rows: dict[int, list] = {}
    for i, (slot, p) in enumerate(xi):
        rows.setdefault(PITCH_ROW.get(slot, 2), []).append((slot, p, i))
    html_rows = []
    for k in sorted(rows):
        cells = sorted(rows[k], key=lambda sp: (LEFT_TO_RIGHT.index(sp[0]) if sp[0] in LEFT_TO_RIGHT else 5, sp[2]))
        out = []
        for slot, p, i in cells:
            if p is None:
                out.append(f'<div class="pchip empty"><span class="ps">{slot}</span><b>No option</b></div>')
                continue
            r, fam = p["rows"].get(i, p["slots"][slot])
            out.append(f"""<div class="pchip {row_state(p)}"><span class="ps">{slot}</span><b>{E(short(p['name']))}</b>
              <div class="pr">{stars(r, True)}<span class="fam {fam}">{fam}</span>{trend(p['trend'])}</div>
              <div class="pb">{badges(p, compact=True)}</div></div>""")
        html_rows.append(f'<div class="prow">{"".join(out)}</div>')
    filled = [p["rows"].get(i, p["slots"][s])[0] for i, (s, p) in enumerate(xi) if p]
    avg = sum(filled) / len(xi) if xi else 0
    return f"""<div class="pitchwrap"><div class="ptitle"><h3>{E(title)}</h3><span>{E(sub)} · avg {stars(avg, True)} {avg:.1f}</span></div>
      <div class="pitch"><div class="lines"><i class="half"></i><i class="circle"></i><i class="box top"></i><i class="box bot"></i></div>{''.join(html_rows)}</div></div>"""


def pitch3d_card(title, xi, sub, crest) -> str:
    filled = [p["rows"].get(i, p["slots"][s])[0] for i, (s, p) in enumerate(xi) if p]
    avg = sum(filled) / len(xi) if xi else 0
    return f"""<div class="p3w"><div class="ptitle"><h3>{E(title)}</h3><span>{E(sub)} · avg {stars(avg, True)} {avg:.1f}</span></div>
      {pitch3d(xi_cards(xi), f"{title} on a 3D pitch, average {avg:.1f} stars. Drag or use the arrow keys to rotate it.", crest)}</div>"""


def xis(R):
    crest = club_identity(R["club"])["pitch"]
    return f"""<section><h2>Best XI &amp; second XI <span class="h2sub">{E(FORMATION_NAME)} · rated in both phases · every player used once</span></h2>
  <div class="xtools" role="group" aria-label="Pitch view"><button class="seg" type="button" data-view="3d" aria-pressed="true">3D</button><button class="seg" type="button" data-view="2d" aria-pressed="false">Flat</button>
   <span class="xhint">3D: drag a pitch to turn it. Flat shows every badge.</span>
   <span class="xiseg ph-only" role="group" aria-label="Which XI"><button class="seg" type="button" data-xi="1" aria-pressed="true">Best XI</button><button class="seg" type="button" data-xi="2" aria-pressed="false">Second XI</button></span></div>
  <div class="pitches3d">{pitch3d_card('Best XI', R['xi1'], 'fully fit squad', crest)}{pitch3d_card('Second XI', R['xi2'], "from who's left", crest)}</div>
  <div class="pitches" hidden>{pitch('Best XI', R['xi1'], 'fully fit squad')}{pitch('Second XI', R['xi2'], "from who's left")}</div></section>"""


def position_cards(R):
    verdict = {v[0]: v for v in R["verdicts"]}
    cards = []
    for slot in [s for s in CARD_ORDER if s in verdict]:
        level, label = verdict[slot][1], verdict[slot][2]
        row_i = next((i for i, row in enumerate(FORMATION) if row[0] == slot), None)

        def here(p):   # (stars, familiarity code) at this card, also for someone who's played here a lot
            if slot in p["slots"]:
                return p["slots"][slot]
            if row_i is not None and p.get("played", {}).get(slot, 0) >= PLAYED_MANY and row_i in p["orows"]:
                return p["orows"][row_i]
            return None
        for p in R["players"]:
            p["_here"] = here(p)
        senior = [p for p in R["players"] if p["_here"] and not p["youth"]]
        youth = sorted((p for p in R["players"] if p["_here"] and p["youth"]),
                       key=lambda p: -p["_here"][0])
        shown_youth, more = youth[:YOUTH_PER_CARD], len(youth) - YOUTH_PER_CARD
        people = sorted(senior, key=lambda p: ("loan_out" in p, -p["_here"][0], p["_here"][1] != "N"))
        people += shown_youth
        rows = []
        for p in people:
            r, fam = p["_here"]
            games = p.get("played", {}).get(slot, 0)
            main = any(p["posr"].get(c, 0) >= 18 for c in CARD_CODES.get(slot, []))
            hl = " main" if main else (" many" if games >= PLAYED_MANY else "")
            gp = (f'<span class="gp{" lots" if games >= PLAYED_MANY else ""}" title="Games at {slot} this season '
                  f'(FM keeps each player\'s last ~20 matches)">{games} here</span>') if games else ""
            u21 = '<span class="u21">U21</span>' if (p["age"] or 99) <= YOUTH_AGE else ""
            yt = '<span class="yt">youth</span>' if p["youth"] else ""
            phases_here = next(((row[1], row[2]) for row in FORMATION if row[0] == slot), EXTRA_CARDS.get(slot))
            weak = []
            if phases_here:
                for code in dict.fromkeys(phases_here):
                    fr = p["posr"].get(code, 0)
                    if fr < 15:
                        weak.append(f"{POS_LABEL[code]} {familiarity_word(fr)} ({fr}/20)")
            # one line per player: the details live in the hover text and the row's coloured edge
            status = " ".join(re.sub(r"<[^>]+>", " ", badges(p)).split())
            tip = " · ".join(x for x in (status, f"{games} games at {slot} this season" if games else "",
                                         ("Weak in one phase: " + ", ".join(weak)) if weak else "") if x)
            gpc = (f'<span class="gpc{" lots" if games >= PLAYED_MANY else ""}" title="{games} games at {slot} this season">{games}</span>'
                   if games else "")
            wpc = ""
            if weak and phases_here:
                ip_c, oop_c = phases_here
                wpc = (f'<span class="wpc" title="Weak in one phase: your {slot} plays {POS_LABEL[ip_c]} with the ball and '
                       f'{POS_LABEL[oop_c]} without it, and he\'s only {E(", ".join(weak))}">!</span>')
            potc = (f'<span class="potc" title="Potential: could reach {fmt_stars(p["potential"])}★ (from FM\'s hidden potential)">'
                    f'↑{fmt_stars(p["potential"])}</span>' if p.get("potential") else "")
            rows.append(f"""<div class="prow2 c {row_state(p)}{hl}"{f' title="{E(tip)}"' if tip else ""}><span class="fam {fam}">{fam}</span>"""
                        f"""<span class="nm">{E(p['name'])}</span>{u21}{yt}{wpc}{potc}{gpc}<span class="st">{stars(r, True)}</span>"""
                        f"""<span class="ag">{p['age'] or ''}</span></div>""")
        n_pl = len(rows)
        if more > 0:
            rows.append(f'<div class="more">+{more} more in your youth teams</div>')
        phases = next(((row[1], row[2]) for row in FORMATION if row[0] == slot), None)
        if phases and phases[0] != phases[1]:
            half_ok = []
            for p in R["players"]:
                if slot in p["slots"] or p["youth"] or p["where"] not in ("squad", "incoming"):
                    continue
                ok = [p["posr"].get(c, 0) >= 15 for c in phases]
                if any(ok) and not all(ok):
                    good, bad = (phases[0], phases[1]) if ok[0] else (phases[1], phases[0])
                    half_ok.append(f"{surname(p['name'])} ({POS_LABEL[good]} ✓ {POS_LABEL[bad]} ✗)")
            if half_ok:
                rows.append(f'<div class="halfnote">Not listed — your tactic needs {POS_LABEL[phases[0]]} in possession '
                            f'and {POS_LABEL[phases[1]]} out of it: {E(", ".join(half_ok))}</div>')
        if not rows:
            rows.append('<div class="more">Nobody can play here.</div>')
        body, tail = "".join(rows[:min(n_pl, POS_SHOWN)]), "".join(rows[n_pl:])
        if n_pl > POS_SHOWN:
            extra = f" · +{more} youth" if more > 0 else ""
            body += (f'<div class="pmore" id="pm-{slot}" hidden>{"".join(rows[POS_SHOWN:n_pl])}{tail}</div>'
                     f'<button class="pexp" type="button" aria-expanded="false" aria-controls="pm-{slot}" data-n="{n_pl}{extra}">'
                     f'Show all {n_pl}{extra}</button>')
        else:
            body += tail
        cards.append(f"""<div class="pcard {level}" style="grid-area:{slot.lower()}"><div class="pch"><span class="slot">{slot}</span>
            <span class="pname">{E(SLOT_NAMES.get(slot, slot))}</span><span class="vtag {level}">{E(label)}</span></div>
            <div class="plist">{body}</div></div>""")
    return f"""<section><h2>Position by position <span class="h2sub">everyone who can play there · natural first · hover a player for status and details</span></h2>
  <details class="pkey-fold" open><summary>What the markers mean</summary>{positions_key()}</details>
  <p class="ph-only ph-note">The positions that need work come first.</p>
  <div class="pform"><i class="pf-box t"></i><i class="pf-box b"></i>{''.join(cards)}</div></section>"""


def hint(key: str, visual: str, label: str, text: str) -> str:
    """A key item that explains itself on hover, keyboard focus or tap (the tooltip is linked with aria-describedby)."""
    return (f'<span class="hint"><button type="button" class="hint-b" aria-describedby="tip-{key}">{visual}<u>{label}</u></button>'
            f'<span class="tip" role="tooltip" id="tip-{key}">{text}</span></span>')


def positions_key() -> str:
    ex = next((r for r in FORMATION if r[1] != r[2]), None)   # a slot your tactic plays as two positions
    two = (f"Your tactic plays some spots as one position with the ball and another without it: your {ex[0]} is a "
           f"<b>{POS_LABEL[ex[1]]}</b> in possession and a <b>{POS_LABEL[ex[2]]}</b> out of possession. " if ex else
           "Your tactic can ask for one position with the ball and another without it. ")
    items = [
        hint("fam", '<span class="fam N">N</span><span class="fam A">A</span>', "natural / accomplished",
             "How well he knows this position, from FM's own position ratings: <b>N</b> natural (18–20 out of 20), "
             "<b>A</b> accomplished (15–17). To be listed he needs 15+ in one phase and at least some feel for the other."),
        hint("main", '<span class="sw main"></span>', "natural position",
             "Green row: one of his natural positions (18+ out of 20), so this is where he's most at home."),
        hint("many", '<span class="sw many"></span>', f"played there {PLAYED_MANY}+ times",
             f"Blue row: not a natural position for him, but he's played here in {PLAYED_MANY} or more matches this season, "
             "so it's somewhere you've actually been using him."),
        hint("games", '<span class="gpc">7</span>', "games there this season",
             "How many matches he's played in this position this season, from the game's own match data "
             "(FM keeps roughly each player's last 20 matches)."),
        hint("weak", '<span class="wpc">!</span>', "weak in one phase",
             two + "<b>!</b> means he knows one of those positions well but not the other (under 15 out of 20), "
             "so he'll be a bit off in that half of the game. Hover the ! next to a name to see which."),
    ]
    if SHOW_POTENTIAL:
        items.append(hint("pot", '<span class="potc">↑4</span>', "potential",
                          f"How good he could become, in stars. It comes from FM's hidden potential, the only hidden "
                          f"number this app shows, and only for players {POTENTIAL_MAX_AGE} and under who could grow by "
                          f"{POTENTIAL_MIN_GAIN:g}★ or more. Potential isn't a promise: it needs minutes and training."))
    items.append(hint("tags", '<span class="u21">U21</span><span class="yt">youth</span>', "tags",
                      f"<b>U21</b>: {YOUTH_AGE} or younger. <b>youth</b>: he plays for your U21 or U18 side, not the first team."))
    return f'<div class="poslegend" role="group" aria-label="Key">{"".join(items)}</div>'


POS_GROUP = {"GK": 0, "SW": 1, "DL": 1, "DC": 1, "DR": 1, "WBL": 1, "WBR": 1, "DM": 2, "MC": 2, "ML": 2, "MR": 2,
             "AMC": 2, "AML": 3, "AMR": 3, "STC": 3, "ST": 3}


def group_of_best(p):
    """Goalkeepers / defenders / midfielders / attackers by his main FM position."""
    nat = p.get("natural") or []
    if nat:
        return POS_GROUP.get(nat[0], 4)
    slot = p["best"][0] if p["best"] else "ZZ"
    return {"GK": 0, "LB": 1, "CB": 1, "RB": 1, "DM": 2, "CM": 2, "AM": 2, "LW": 3, "RW": 3, "ST": 3}.get(slot, 4)


FILTER_POS = ["GK", "LB", "LWB", "CB", "RB", "RWB", "DM", "CM", "LM", "RM", "AM", "LW", "RW", "ST"]


def status_tokens(p):
    t = []
    if "loan_in" in p or "loan_out" in p:
        t.append("loan")
    if "inj" in p:
        t.append("injured")
    if "sus" in p:
        t.append("suspended")
    if any(k in p for k in ("deal_in", "deal_out", "loan_in_arr", "loan_out_arr")):
        t.append("arranged")
    if p.get("expiring"):
        t.append("expiring")
    return " ".join(t)


def can_play(p):
    return " ".join(dict.fromkeys(POS_LABEL[c] for c, r in p.get("posr", {}).items() if r >= 15 and c in POS_LABEL))


def pot_html(p, empty="", tag=False):
    if not p.get("potential"):
        return empty
    label = '<span class="potl">pot</span>' if tag else ""
    return f'<span class="pot" title="Potential, from FM\'s hidden potential">{label}{stars(p["potential"], True)}</span>'


def more_btn(target: str, n: int, what: str) -> str:
    """A "show the rest" button for a container with the class "clipped"; hidden items carry the class "xtra"."""
    label = f"Show {n} more {what}"
    return (f'<button type="button" class="morebtn" aria-expanded="false" aria-controls="{target}" '
            f'data-more="{E(label)}">{E(label)}</button>')


def squad_kpis(R) -> str:
    """Key figures above the squad list. The last three are buttons that filter the list to the players behind them,
    so they count exactly what the filter shows (youth-team players only show up with "Include youth teams")."""
    ps = R["players"]
    first = [p for p in ps if p["where"] == "squad" and not p["youth"]]
    ages = [p["age"] for p in first if p["age"]]
    youth = sum(1 for p in ps if p["where"] == "squad" and p["youth"])
    worth = sum(p["value"] or 0 for p in first)

    def count(token):
        return sum(1 for p in ps if not p["youth"] and token in status_tokens(p).split())

    def tile(label, value, sub, st=None, unit=""):
        unit_html = f' <span class="of">{unit}</span>' if unit else ""
        inner = f'<div class="lbl">{label}</div><div class="val">{value}{unit_html}</div><div class="sub">{sub}</div>'
        if not st:
            return f'<div class="tile">{inner}</div>'
        return (f'<button type="button" class="tile tbtn" data-st="{st}" aria-pressed="false" aria-controls="squadTable" '
                f'title="Show only these players in the list">{inner}</button>')

    avg_age = f"{sum(ages) / len(ages):.1f}" if ages else "–"
    coming = sum(1 for p in ps if "deal_in" in p or "loan_in_arr" in p)
    going = sum(1 for p in ps if "deal_out" in p or "loan_out_arr" in p)
    tiles = [tile("First team", len(first), f"avg age {avg_age} · {youth} more in the youth teams", unit="players"),
             tile("First-team value", money(worth), "FM's transfer values"),
             tile("Contracts ending", count("expiring"), f"within {CONTRACT_WARNING_DAYS // 30} months", "expiring"),
             tile("On loan", count("loan"), f"{sum(1 for p in ps if 'loan_out' in p)} out · "
                                            f"{sum(1 for p in ps if 'loan_in' in p)} in", "loan"),
             tile("Arranged moves", count("arranged"), f"{coming} coming · {going} going", "arranged")]
    return f'<div class="fin k5 sqk">{"".join(tiles)}</div>'


def squad_row(p, group):
    if p["best"]:
        slot, (r, _) = p["best"]
        st = stars(r, True) + f'<span class="bs">{slot}</span>' + trend(p["trend"])
        others = sorted(((v, s_) for s_, (v, _) in p["slots"].items() if s_ != slot), reverse=True)[:3]
        if others:
            st += '<div class="also">' + " · ".join(f"{s_} {fmt_stars(v)}" for v, s_ in others) + "</div>"
        ab = stars(p["ability"], True) if p.get("ability") is not None else ""
    else:
        st = ab = '<span class="acc">—</span>'
    nat, acc = p.get("fm_nat") or [], p.get("fm_acc") or []
    pos = " ".join(nat) + (f' <span class="acc">{" ".join(acc)}</span>' if acc else "")
    youth = "1" if p["youth"] else "0"
    exp = ' class="exp lo"' if p.get("expiring") else ' class="lo"'
    return f"""<tr class="{row_state(p)}" data-g="{group}" data-pos="{can_play(p)}" data-st="{status_tokens(p)}" data-youth="{youth}">
      <td class="nm">{E(p['name'])}</td><td class="lo">{pos}</td><td>{p['age'] or ''}</td>
      <td>{st}</td><td class="lo">{ab}</td><td class="lo">{pot_html(p, '<span class="acc">–</span>')}</td><td class="r lo">{money(p['value'])}</td>
      <td class="r lo">{wage(p['wage'])}</td><td{exp}>{E(d(p['contract_end'], '%b %Y'))}</td><td class="bd">{badges(p)}</td></tr>"""


def squad_table(R):
    cols = ('<tr><th>Player</th><th class="lo">FM positions <span class="acc">(grey = accomplished)</span></th><th>Age</th>'
            f'<th title="How good he is in your {E(FORMATION_NAME)} {E(TACTICAL_STYLE)}: position + role key attributes + style">System ★</th>'
            '<th class="lo" title="How good he is at that position in general, ignoring your tactic">Ability ★</th>'
            f'<th class="lo" title="Players {POTENTIAL_MAX_AGE} and under whose potential is {POTENTIAL_MIN_GAIN:g}★+ above current">Potential ★</th>'
            '<th class="r lo">Value</th><th class="r lo">Wage p/w</th><th class="lo">Contract</th><th>Status</th></tr>')
    current = [p for p in R["players"] if p["where"] == "squad"]
    groups = []
    for gi, title in enumerate(["Goalkeepers", "Defenders", "Midfielders", "Attackers", "Other"]):
        groups.append((title, sorted((p for p in current if group_of_best(p) == gi and not p["youth"]),
                                     key=lambda p: -(p["best"][1][0] if p["best"] else 0))))
    groups.append(("Arriving (transfers & loans arranged)", [p for p in R["players"] if p["where"] == "incoming"]))
    groups.append(("Out on loan", [p for p in R["players"] if p["where"] == "loan_out"]))
    groups.append(("Youth teams", sorted((p for p in current if p["youth"]),
                                         key=lambda p: (group_of_best(p), -(p["best"][1][0] if p["best"] else 0)))))
    body = []
    for gi, (title, members) in enumerate(groups):
        if members:
            open_ = "false" if title == "Out on loan" else "true"   # loans start folded: they're not in your plans now
            body.append(f'<tr class="grp" data-gh="{gi}"><td colspan="10"><button type="button" class="gtog" aria-expanded="{open_}">'
                        f'{title}<span class="gn">{len(members)}</span></button></td></tr>')
            body += [squad_row(p, gi) for p in members]
    st_chips = "".join(f'<button class="fchip{" on" if k == "all" else ""}" data-st="{k}">{lbl}</button>' for k, lbl in
                       (("all", "All"), ("loan", "On loan"), ("injured", "Injured"), ("suspended", "Suspended"),
                        ("arranged", "Arranged moves"), ("expiring", "Contract ending")))
    pos_chips = "".join(f'<button class="fchip pos" data-pos="{c}">{c}</button>' for c in FILTER_POS)
    return f"""<section><h2>Squad &amp; transfer status <span class="h2sub">everyone at the club, arriving or out on loan · tap a group to fold it</span></h2>
  {squad_kpis(R)}
  <div class="filters">
    <div class="frow ftop"><input type="search" id="sqSearch" class="fsearch" placeholder="Search by name" aria-label="Search players by name" autocomplete="off" spellcheck="false">
      <label class="ytog"><input type="checkbox" id="incYouth"> Include youth teams</label>
      <span class="fcount" id="fcount" role="status" aria-live="polite"></span><button class="fchip clear" id="fclear">Clear filters</button></div>
    <div class="frow"><span class="fl">Show</span>{st_chips}</div>
    <div class="frow"><span class="fl">Can play</span>{pos_chips}
      <span class="mode"><button class="fchip mode on" data-mode="any">any of these</button><button class="fchip mode" data-mode="all">all of these</button></span></div>
  </div>
  <table class="squad sq sticky-h" id="squadTable"><caption class="sr">Squad list, grouped by position and status</caption>
  <thead>{cols}</thead><tbody>{''.join(body)}</tbody></table></section>"""


def _day(dt):
    """Dates from the save can be datetimes or dates; compare them as dates."""
    return dt.date() if isinstance(dt, datetime) else dt


def deal_timeline(R) -> str:
    """Everything dated that changes the squad, month by month: arranged moves, loans starting or ending, contracts ending."""
    events = []
    for p in R["players"]:
        def add(dt, cls, tag, detail):
            if dt:
                events.append((_day(dt), cls, tag, p["name"], detail))
        if "deal_in" in p:
            add(p["deal_in"][1], "deal-in", "Joins", f"from {p['deal_in'][0]}")
        if "deal_out" in p:
            add(p["deal_out"][1], "deal-out", "Leaves", f"to {p['deal_out'][0]}")
        if "loan_in_arr" in p:
            add(p["loan_in_arr"][1], "loan-in", "Loan starts", f"from {p['loan_in_arr'][0]}")
        if "loan_out_arr" in p:
            add(p["loan_out_arr"][1], "loan-out", "Loan starts", f"to {p['loan_out_arr'][0]}")
        if "loan_in" in p:
            add(p["loan_in"][1], "loan-in", "Loan ends", f"back to {p['loan_in'][0]}")
        if "loan_out" in p:
            add(p["loan_out"][1], "loan-out", "Back", f"from {p['loan_out'][0]}")
        if p.get("expiring") and "deal_out" not in p:
            add(p.get("contract_end"), "expiring", "Contract", "deal ends")
    if not events:
        return '<div class="acc">Nothing arranged, and no loans or contracts ending in the next year.</div>'
    months: dict = {}
    for ev in sorted(events, key=lambda ev: (ev[0], ev[1], ev[3])):
        months.setdefault((ev[0].year, ev[0].month), []).append(ev)
    many = {"Contract": "contracts end", "Back": "back from loan", "Joins": "join", "Leaves": "leave",
            "Loan starts": "loans start", "Loan ends": "loans end"}
    cols = []
    for (y, m), items in months.items():
        same: dict = {}
        for ev in items:   # several of the same thing on the same day become one card
            same.setdefault((ev[0], ev[1], ev[2]), []).append(ev)
        lis = []
        for (dt, cls, tag), evs in same.items():
            if len(evs) >= 3:
                names = ", ".join(surname(ev[3]) for ev in evs)
                lis.append(f'<li class="grp"><span class="tag {cls}">{tag}</span><div><b>{len(evs)} {many[tag]} · {dt.day} {dt:%b}</b>'
                           f'<span>{E(names)}</span></div></li>')
            else:
                lis += [f'<li><span class="tag {cls}">{tag}</span><div><b>{E(name)}</b><span>{E(detail)} · {dt.day} {dt:%b}</span></div></li>'
                        for _, _, _, name, detail in evs]
        lis = "".join(lis)
        cols.append(f'<div class="tlm"><div class="tlh"><b>{date(y, m, 1):%b %Y}</b><span>{len(items)} '
                    f'{"thing" if len(items) == 1 else "things"}</span></div><ul>{lis}</ul></div>')
    return f'<div class="tline">{"".join(cols)}</div>'


def deals(R):
    def col(title, cls, key, fmt):
        items = [p for p in R["players"] if key in p]
        lis = "".join(f"""<li><div><b>{E(p['name'])}</b><span>{E(" ".join(p.get('fm_nat') or []) or (p['best'][0] if p['best'] else '?'))} · {p['age'] or ''}</span></div>
            <div class="dd">{fmt(p[key])}</div></li>""" for p in items) or '<li class="empty">None right now</li>'
        return f'<div class="dcol {cls}"><h3>{title}<span>{len(items)}</span></h3><ul>{lis}</ul></div>'
    return f"""<section><h2>Deals &amp; loans</h2>
  <h3 class="dgroup">Coming up <span>arranged moves, loans starting and ending, contracts running out · by month</span></h3>
  {deal_timeline(R)}
  <h3 class="dgroup">Transfers arranged <span>permanent moves that haven't happened yet</span></h3>
  <div class="deals two">
    {col('Transfer in', 'deal-in', 'deal_in', lambda v: f"from <b>{E(v[0])}</b><br>joins {E(d(v[1]))}")}
    {col('Transfer out', 'deal-out', 'deal_out', lambda v: f"to <b>{E(v[0])}</b><br>leaves {E(d(v[1]))}")}
  </div>
  <h3 class="dgroup">Loans arranged <span>agreed, starting later</span></h3>
  <div class="deals two">
    {col('Loan in (arranged)', 'loan-in arr', 'loan_in_arr', lambda v: f"from <b>{E(v[0])}</b><br>joins {E(d(v[1]))}")}
    {col('Loan out (arranged)', 'loan-out arr', 'loan_out_arr', lambda v: f"to <b>{E(v[0])}</b><br>leaves {E(d(v[1]))}")}
  </div>
  <h3 class="dgroup">Current loans</h3>
  <div class="deals two">
    {col('Loaned in now', 'loan-in', 'loan_in', lambda v: f"from <b>{E(v[0])}</b><br>until {E(d(v[1]))}")}
    {col('Loaned out now', 'loan-out', 'loan_out', lambda v: f"at <b>{E(v[0])}</b><br>back {E(d(v[1]))}")}
  </div></section>"""


def attr_cell(v):
    if v is None:
        return '<td class="av">–</td>'
    cls = "a5" if v >= 16 else "a4" if v >= 13 else "a3" if v >= 11 else "a2" if v > WEAK_ATTR - 2 else "a1"
    return f'<td class="av {cls}">{v}</td>'


def fit_bar(f):
    pct = max(0, min(100, (f - 5) / 15 * 100))
    cls = "good" if f >= 14 else "ok" if f >= FIT_FLOOR else "bad"
    return f'<div class="fitv {cls}"><b>{f:.1f}</b><i><u style="width:{pct:.0f}%"></u></i></div>'


PLAYED_MANY = 5   # games at a position this season to count as "played there a lot"


def ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def fmt_team(key: str, v: float, unit: str) -> str:
    if unit == "%":
        return f"{v:.0f}%"
    if key == "dist_diff":
        return f"{v:+.1f} km"
    if key in ("finishing", "keeping"):
        return f"{v:+.2f}"
    if unit.startswith("km"):
        return f"{v:.1f} km"
    return f"{v:.2f}" if v < 10 else f"{v:.1f}"


def fmt_player(key: str, v: float) -> str:
    if key.endswith("_pct"):
        return f"{v:.0f}%"
    if key == "mistakes":
        return f"{int(v)} this season"
    if key == "finish":
        return f"{v:+.2f}/90"
    if key == "dist90":
        return f"{v:.1f} km/90"
    return f"{v:.2f}/90"


def team_insights(ms: dict) -> list[str]:
    """A few readings that only make sense when two numbers are put side by side."""
    r = {k: m["rank"] for k, m in ms.items()}
    of = next(iter(ms.values()))["of"] if ms else 20
    top, low = lambda k: r.get(k, 99) <= max(5, of // 4), lambda k: r.get(k, 0) >= of * 0.6  # noqa: E731
    out = []
    if top("shots") and low("ccc"):
        out.append("Lots of shots but few clear-cut chances: they're coming from poor positions rather than from "
                   "working the ball into the box.")
    if low("finishing") and not low("xg"):
        out.append("The chances are there but aren't being finished — you're scoring fewer than your xG says you should.")
    if top("opp_final3") and low("opp_pass_pct"):
        out.append("You keep teams out of your final third, but they still pass comfortably once they're past the "
                   "first wave of the press.")
    if (top("dist_diff") or top("dist")) and low("tackle_pct"):
        out.append("You outrun teams but don't win enough of your tackles, so the pressing effort isn't turning into turnovers.")
    if low("poss") and low("pass_pct"):
        out.append("Low possession and low pass completion together: the ball is being given away cheaply after you win it.")
    if top("xga") and low("keeping"):
        out.append("Opponents don't create much, but more of it goes in than it should — look at the keeper and finishing "
                   "against you rather than the system.")
    if low("aerial_pct") and low("ccc_ag"):
        out.append("Losing headers and conceding clear-cut chances — direct balls in behind or into the box are a problem.")
    return out


def rank_strip(rank: int, of: int) -> str:
    """One cell per league team, yours lit; top quarter tinted green, bottom half red."""
    cut = max(3, round(of * 0.25))
    cells = "".join(f'<i class="{"me" if k == rank else "top" if k <= cut else "bot" if k > of / 2 else ""}"></i>' for k in range(1, of + 1))
    return f'<div class="rk" style="--n:{of}" aria-hidden="true">{cells}</div>'


def perf_section(R) -> str:
    P = R.get("perf")
    if not P or not P.get("metrics"):
        return """<section id="fit-perf"><h2>How the tactic is going</h2>
  <div class="explain">No league match data for this season yet — play a few games and it'll fill in.</div></section>"""
    of = P["metrics"][0]["of"]
    league = P.get("league_name") or "the league"
    rec = P.get("record")
    head = ""
    if rec:
        head = (f'<div class="rec"><span class="big">{ordinal(rec["pos"])}</span><span>of {rec["of"]}</span>'
                f'<span>P{rec["p"]} · W{rec["w"]} D{rec["d"]} L{rec["l"]} · {rec["pts"]} pts · {rec["gf"]}–{rec["ga"]} goals</span>')
        head += "".join(f'<span class="frm {f["res"]}" title="{E(f["score"])} {"vs" if f["home"] else "at"} {E(f["opp"])}">{f["res"]}</span>'
                        for f in P.get("form", []))
        head += "</div>"
    ms = P["metrics"]
    cut = max(3, round(of * 0.25))
    working = sorted((m for m in ms if m["rank"] <= cut), key=lambda m: m["rank"])[:6]
    failing = sorted((m for m in ms if m["rank"] > of / 2 and not m["above"]), key=lambda m: -m["rank"])[:6]

    def strip(m):
        return rank_strip(m["rank"], m["of"])

    def item(m, good):
        return f"""<div class="wi {'good' if good else 'bad'}"><div class="wl"><b>{E(m['label'])}</b>
          <span>{fmt_team(m['key'], m['value'], m['unit'])} {'' if m['unit'] in ('%',) or m['key'] in ('dist_diff',) else E(m['unit'])}</span></div>
          {strip(m)}<div class="wr">{ordinal(m['rank'])} of {m['of']} · league avg {fmt_team(m['key'], m['avg'], m['unit'])}</div>
          <div class="wt">{E(m['good'] if good else m['bad'])}</div></div>"""
    w_html = "".join(item(m, True) for m in working) or '<div class="acc">Nothing in the top quarter of the league yet.</div>'
    if failing:
        f_html = "".join(item(m, False) for m in failing)
    else:
        weakest = sorted(ms, key=lambda m: -m["rank"])[:3]
        f_html = ('<div class="acc">Nothing is below the league average. Your weakest areas:</div>'
                  + "".join(item(m, False) for m in weakest))
    ins = team_insights({m["key"]: m for m in ms})
    ins_html = ("".join(f"<li>{E(t)}</li>" for t in ins))
    ins_html = f'<div class="insights"><b>Putting it together</b><ul>{ins_html}</ul></div>' if ins else ""

    byuid = {p["uid"]: p for p in R["players"]}
    cards = []
    for uid, v in sorted(P.get("players", {}).items(), key=lambda kv: -kv[1]["minutes"]):
        p = byuid.get(uid)
        if not p or p["where"] != "squad":
            continue
        def chip(i, good):
            share = max(1, round(100 - i["pctl"])) if good else max(1, round(i["pctl"]))
            tag = '<em>press</em>' if i["press"] else ""
            return (f'<span class="pc {"good" if good else "bad"}" title="{"top" if good else "bottom"} {share}% of league '
                    f'{PERF_GROUP_NAME[v["group"]]}">{E(i["label"])} <b>{fmt_player(i["key"], i["value"])}</b>'
                    f'<i>{"top" if good else "bottom"} {share}%</i>{tag}</span>')
        good = "".join(chip(i, True) for i in v["good"])
        bad = "".join(chip(i, False) for i in v["bad"])
        if not good and not bad:
            body = '<div class="acc">Nothing stands out either way — middle-of-the-pack numbers for his position.</div>'
        else:
            body = (f'<div class="pcrow"><span class="pcl ok">Working</span>{good or "<span class=acc>—</span>"}</div>'
                    f'<div class="pcrow"><span class="pcl no">Not working</span>{bad or "<span class=acc>—</span>"}</div>')
        avg = f'{v["avg"]:.2f} avg rating · ' if v.get("avg") else ""
        xtra = " xtra" if len(cards) >= PERF_CARDS_SHOWN else ""
        cards.append(f"""<div class="perfcard {row_state(p)}{xtra}"><div class="pctop"><b>{E(p['name'])}</b>
          <span>{avg}{v['minutes']} league mins · vs {v['peers']} {PERF_GROUP_NAME[v['group']]}</span></div>{body}</div>""")
    cards_html = "".join(cards) or '<div class="acc">Nobody has 450+ league minutes yet.</div>'
    hidden = max(0, len(cards) - PERF_CARDS_SHOWN)
    perf_more = more_btn("perfAll", hidden, "players") if hidden else ""
    return f"""<section id="fit-perf"><h2>How the tactic is going <span class="h2sub">{E(league)} only · from the game's own match stats
  ({P['reports']} of your matches have full reports) · ranked against all {of} teams</span></h2>
  {head}
  <div class="wgrid"><div><h3 class="wh ok">What's working</h3>{w_html}</div><div><h3 class="wh no">What's not working</h3>{f_html}</div></div>
  {ins_html}
  <h3 class="sub3">Player by player <span class="h2sub">league numbers per 90 minutes, ranked against every league player in the same position with {PERF_MIN_MINUTES}+ minutes · <em class="presskey">press</em> = part of your {E(TACTICAL_STYLE.lower())}</span></h3>
  <div class="perfgrid clipped" id="perfAll">{cards_html}</div>{perf_more}</section>"""


def gegen_section(R) -> str:
    usable = [p for p in R["players"] if p["where"] in ("squad", "incoming") and not p["youth"]
              and not LEAVING & p.keys() and p.get("attrs")]
    xi_ids = {id(p) for _, p in R["xi1"] if p}
    rows = []
    for p in usable:
        vals = [p["attrs"].get(k) for k in STYLE_KEYS]
        known = [v for v in vals if v is not None]
        if not known:
            continue
        avg = sum(known) / len(known)
        low = sorted(((v, k) for v, k in zip(vals, STYLE_KEYS) if v is not None and v <= 12), key=lambda t: t[0])[:3]
        rows.append((avg, p, vals, low))
    rows.sort(key=lambda r: -r[0])
    head = "".join(f'<th class="ak sty" title="{E(attr_label(k))}">{E(ATTR_ABBR.get(k, attr_label(k)[:3]))}</th>' for k in STYLE_KEYS)
    body = []
    for avg, p, vals, low in rows:
        xi = '<span class="xi">XI</span>' if id(p) in xi_ids else ""
        back = ("".join(f'<span class="wk">{E(attr_label(k))} {v}</span>' for v, k in low)
                or '<span class="okk">Nothing — all 13+</span>')
        slot = p["best"][0] if p["best"] else "–"
        xtra = "" if id(p) in xi_ids else " xtra"
        body.append(f"""<tr class="{row_state(p)}{xtra}"><td class="nm">{E(short(p['name']))}{xi}</td><td>{slot}</td>
          {''.join(attr_cell(v) for v in vals)}<td>{fit_bar(avg)}</td><td class="back">{back}</td></tr>""")
    others = sum(1 for _, p, _, _ in rows if id(p) not in xi_ids)
    xi_players = [p for _, p in R["xi1"] if p and p.get("attrs")]
    team_avgs = [mean(p["attrs"].get(k) for p in xi_players) for k in STYLE_KEYS]
    team_row = "".join(attr_cell(round(v) if v is not None else None) for v in team_avgs)
    weakest = sorted(((v, k) for v, k in zip(team_avgs, STYLE_KEYS) if v is not None))[:2]
    weak_txt = " and ".join(f"{attr_label(k)} ({v:.1f})" for v, k in weakest)
    return f"""<section id="fit-gegen"><h2>{E(TACTICAL_STYLE)} breakdown <span class="h2sub">the {len(STYLE_KEYS)} attributes behind each player's
  {E(TACTICAL_STYLE.lower())} score (/20) · the lowest ones are what to work on in individual training</span></h2>
  <div class="explain">Your best XI is weakest at <b>{E(weak_txt)}</b> as a group. These are FM's visible attributes, so
  you can check them on each player's profile. Lower ones (12 or below) are listed under <i>holding him back</i>.</div>
  <div class="ftable gegen clipped" id="gegenT"><table><thead><tr><th>Player</th><th>Best</th>{head}<th>{E(TACTICAL_STYLE)} /20</th><th>Holding him back</th></tr></thead>
  <tbody><tr class="teamrow"><td class="nm">Best XI average</td><td></td>{team_row}<td>{fit_bar(mean(team_avgs) or 0)}</td><td></td></tr>
  {''.join(body)}</tbody></table></div>{more_btn("gegenT", others, "players outside your best XI") if others else ""}</section>"""


# =============================================================================================
# Training: what's set now (team calendars) and what to change
# =============================================================================================
# Session codes as the save stores them. fmsave has confirmed these; the rest are named by their
# category (FM27 lists the sessions in each category in the same order the codes run).
SESSION_NAME = {0: "Passing Style", 1: "Build Up", 2: "Chance Creation", 5: "Pressing Intensity", 6: "Pressing Trap",
                300: "Rest", 301: "Recovery", 302: "Light Conditioning", 303: "Conditioning", 402: "Travel", 500: "Match"}


def session_family(code: int) -> tuple[str, str]:
    """(css class, category name) for a session code."""
    if code == 500:
        return "match", "Match"
    if code < 100:
        return "tac", "Tactical Understanding"
    if code < 200:
        return "prep", "Match Preparation"
    if code < 300:
        return "dev", "Playing Development"
    if code < 400:
        return ("rest" if code in (300, 301) else "phys"), "Physical & Recovery"
    return "extra", "Travel / extra-curricular"


def read_training(save, today: date, season_start: date, team_names: dict) -> list[dict]:
    out = []
    for t in save.training():
        weeks = [w for w in t.weeks if w.week_start]
        started = [w for w in weeks if w.week_start <= today]
        cur = max(started, key=lambda w: w.week_start) if started else None
        upcoming = sorted((w for w in weeks if w.week_start > today), key=lambda w: w.week_start)[:4]
        season = [w for w in weeks if season_start <= w.week_start <= today]
        rotation = Counter(w.schedule_name for w in season)
        recent = sorted(started, key=lambda w: w.week_start)[-4:]
        codes = Counter(getattr(s, "raw", None) for w in recent for day in w.days for s in day.sessions)
        grid = []
        if cur:
            for day in cur.days:
                grid.append(dict(day=day.day, sessions=[getattr(s, "raw", None) for s in day.sessions]))
        out.append(dict(slot=t.team_slot, name=team_names.get(t.team_slot, f"Team {t.team_slot}"),
                        current=cur.schedule_name if cur else None, week=cur.week_start if cur else None,
                        upcoming=[(w.week_start, w.schedule_name) for w in upcoming], rotation=rotation,
                        recent_codes=codes, recent_weeks=len(recent), grid=grid))
    return sorted(out, key=lambda t: (t["slot"] is None, t["slot"]))


# Which attributes sit behind each per-90 number (used to pick an individual focus that fixes what isn't working)
PERF_ATTRS = {"sprints90": ["pace", "acceleration", "stamina"], "dist90": ["stamina", "work_rate"],
              "won90": ["anticipation", "tackling", "aggression", "work_rate"], "tackles90": ["tackling", "aggression"],
              "tackle_pct": ["tackling", "positioning"], "int90": ["anticipation", "positioning", "concentration"],
              "aerial_pct": ["heading", "jumping_reach", "strength"], "headers90": ["heading", "jumping_reach"],
              "pass_pct": ["passing", "first_touch", "composure", "decisions"],
              "lost90": ["first_touch", "composure", "decisions", "passing"], "finish": ["finishing", "composure"],
              "npxg90": ["off_the_ball", "anticipation", "finishing"], "sot_pct": ["finishing", "composure"],
              "xa90": ["vision", "passing", "crossing"], "kp90": ["vision", "passing"], "ccc90": ["vision", "passing"],
              "dribbles90": ["dribbling", "agility"], "crossc90": ["crossing"], "prog90": ["passing", "vision"],
              "blocks90": ["bravery", "positioning"], "mistakes": ["concentration", "composure", "decisions"],
              "save_pct": ["reflexes", "one_on_ones", "handling"], "xgp": ["reflexes", "one_on_ones", "positioning"],
              "offsides90": ["off_the_ball", "decisions"], "shots90": ["off_the_ball", "long_shots"]}
NOT_TRAINABLE = {"determination", "natural_fitness", "leadership"}   # personality / largely fixed in FM
FOCUS_MAX = 13   # only suggest a focus for an attribute at or below this


def xi_row_of(R, p) -> int | None:
    for i, (_, q) in enumerate(R["xi1"]):
        if q is p:
            return i
    for card, _ in Counter(p.get("played") or {}).most_common():   # otherwise where he's actually been playing
        here = [(v[0], i) for i, v in p["rows"].items() if FORMATION[i][0] == card]
        if here:
            return max(here)[1]
    if p["rows"]:
        return max(p["rows"].items(), key=lambda kv: kv[1][0])[0]
    return None


def individual_plan(R, p) -> dict | None:
    i = xi_row_of(R, p)
    if i is None or not p.get("attrs"):
        return None
    slot, ip_pos, oop_pos, ip_role, oop_role = FORMATION[i]
    a = p["attrs"]
    perf = (R.get("perf") or {}).get("players", {}).get(p["uid"])
    # position work: make an accomplished position natural, or fix the phase he can't play
    pos_work = []
    phases = [(ip_pos, "in possession"), (oop_pos, "out of possession")] if ip_pos != oop_pos else [(ip_pos, "both phases")]
    for code, phase in phases:
        fam = p["posr"].get(code, 0)
        if fam < 18:
            how = "Individual Out of Possession Training" if phase == "out of possession" else "Position/Role"
            pos_work.append(dict(code=POS_LABEL.get(code, code), fam=fam, phase=phase, how=how,
                                 word=familiarity_word(fam) if fam >= 5 else "ineffective"))
    # individual focus: lowest trainable attribute that matters, preferring ones behind a weak number
    linked = {}
    for item in (perf or {}).get("bad", []):
        for attr in PERF_ATTRS.get(item["key"], []):
            linked.setdefault(attr, item)
    role_keys = set(ROLES["IP"][ip_role][1]) | set(ROLES["OOP"][oop_role][1])
    cands = []
    style_keys = set() if slot == "GK" else set(STYLE_KEYS)   # keepers train keeping, not pressing
    for attr in (role_keys | style_keys | set(linked)) - NOT_TRAINABLE:
        v = a.get(attr)
        if v is None or v > FOCUS_MAX:
            continue
        oop_only = attr in ROLES["OOP"][oop_role][1] and attr not in ROLES["IP"][ip_role][1] and attr not in style_keys
        score = (v - (2.5 if attr in linked else 0) - (1 if attr in role_keys and attr in style_keys else 0)
                 + (1 if oop_only else 0))
        cands.append((score, v, attr))
    cands.sort()
    focus, why = None, ""
    if cands:
        _, v, attr = cands[0]
        focus = (attr, v)
        if attr in linked:
            it = linked[attr]
            why = (f"He's in the bottom {max(1, round(it['pctl']))}% of league {PERF_GROUP_NAME[perf['group']]} for "
                   f"{it['label'][0].lower() + it['label'][1:]}, and {attr_label(attr)} ({v}) is one of the attributes behind it.")
        elif attr in role_keys and attr in style_keys:
            why = f"{attr_label(attr)} ({v}) is a key attribute for his role and for {TACTICAL_STYLE.lower()}, and it's his lowest."
        elif attr in style_keys:
            why = f"{attr_label(attr)} ({v}) is his weakest {TACTICAL_STYLE.lower()} attribute."
        else:
            role_name = ROLES["IP"][ip_role][0] if attr in ROLES["IP"][ip_role][1] else ROLES["OOP"][oop_role][0]
            why = f"{attr_label(attr)} ({v}) is his weakest key attribute as a {role_name}."
    second = None
    if len(cands) > 1:
        second = (cands[1][2], cands[1][1])
    untrain = sorted((a.get(k), k) for k in STYLE_KEYS if k in NOT_TRAINABLE and a.get(k) is not None and a[k] <= 10)
    return dict(slot=slot, label=row_labels()[i], ip_role=ROLES["IP"][ip_role][0], oop_role=ROLES["OOP"][oop_role][0],
                pos_work=pos_work, focus=focus, why=why, second=second, untrain=untrain, in_xi=any(q is p for _, q in R["xi1"]))


def team_training_advice(R, first: dict | None) -> tuple[list[dict], list[str]]:
    """Recommendations for the first team's schedule, each with the reasoning, plus what to leave alone."""
    P = R.get("perf") or {}
    ms = {m["key"]: m for m in P.get("metrics", [])}
    of = next(iter(ms.values()))["of"] if ms else 20
    bad = lambda k: k in ms and ms[k]["rank"] > of / 2 and not ms[k]["above"]  # noqa: E731
    good = lambda k: k in ms and ms[k]["rank"] <= max(5, of // 4)  # noqa: E731
    rank = lambda k: f"{ordinal(ms[k]['rank'])} of {of}" if k in ms else "?"  # noqa: E731
    rot = first["rotation"] if first else Counter()
    ip_w = sum(n for s, n in rot.items() if "In Possession" in s)
    oop_w = sum(n for s, n in rot.items() if "Out Of Possession" in s)
    bal_w = sum(n for s, n in rot.items() if "Balanced" in s)
    codes = first["recent_codes"] if first else Counter()
    weeks = max(1, first["recent_weeks"] if first else 1)
    per_week = lambda c: codes.get(c, 0) / weeks  # noqa: E731
    xi = [q for _, q in R["xi1"] if q and q.get("attrs")]
    style_avg = {k: mean(q["attrs"].get(k) for q in xi) for k in STYLE_KEYS}
    recs, keep = [], []

    press_bad = [k for k in ("opp_pass_pct", "tackle_pct", "opp_final3") if bad(k)]
    if press_bad or oop_w < ip_w / 2:
        why = []
        if press_bad:
            why.append("your press isn't biting hard enough: " + ", ".join(f"{ms[k]['label'].lower()} {rank(k)}" for k in press_bad))
        why.append(f"this season you've run In Possession weeks {ip_w}×, Out Of Possession {oop_w}× and Balanced {bal_w}×, "
                   f"so Pressing Intensity and Pressing Trap come round about {per_week(5) + per_week(6):.1f}× a week")
        recs.append(dict(
            title="Train the press more: more Out Of Possession weeks",
            why="For a " + TACTICAL_STYLE.lower() + " side the press is the identity, but " + "; ".join(why) + ".",
            do="Alternate Tactical Focus – In Possession and Tactical Focus – Out Of Possession week to week "
               "(or use Balanced in weeks with two matches), so Pressing Intensity, Pressing Trap and Out Of Possession "
               "Shape come up every week.",
            safe="It swaps which tactical sessions you do, not how many — same three sessions a day, same match rhythm, "
                 "same load. You keep In Possession every other week, so the attacking work isn't dropped."))
    if bad("ccc") or (good("shots") and bad("ccc")) or bad("final3"):
        recs.append(dict(
            title="Better chances, not more shots: Chance Creation + Final Third",
            why=(f"You're {rank('shots')} for shots but {rank('ccc')} for clear-cut chances, so the shots are coming from poor "
                 f"positions." if good("shots") else f"You're {rank('ccc')} for clear-cut chances.")
                + f" Chance Creation is in your week about {per_week(2):.1f}× right now.",
            do="Keep Chance Creation in the In Possession weeks, and on the day before a match make one Match Preparation "
               "session Final Third, so the last session before kick-off is about working the ball into the box.",
            safe="Match Preparation sessions are light and only replace another Match Preparation session, so condition and "
                 "injury risk don't change. You're swapping what the pre-match session is about, not adding one."))
    if bad("finishing"):
        recs.append(dict(
            title="Finishing is a player problem: fix it individually",
            why=f"Goals vs xG is {rank('finishing')} — the chances you do create aren't going in.",
            do="Don't change the team schedule for this. Give your forwards with Finishing or Composure at 13 or below "
               "that as their individual focus (see the table below). If you want team work on it, use Attacking Ball Work "
               "in place of one Playing Development session, only in weeks with one match.",
            safe="Individual focus sits on top of team training rather than replacing it, so nothing else in the week drops out."))
    if bad("aerial_pct"):
        recs.append(dict(
            title="Losing headers: set pieces in match prep + individual focus",
            why=f"Aerial duels won is {rank('aerial_pct')}" + (f", and clear-cut chances conceded is {rank('ccc_ag')}" if bad("ccc_ag") else "") + ".",
            do="Use Corners and Free Kicks as the Match Preparation sessions before matches against physical sides, and give "
               "centre backs and your striker with Heading or Jumping Reach at 13 or below that as their focus.",
            safe="Set-piece sessions are Match Preparation (light) and only replace another pre-match session."))
    if bad("pass_pct") and bad("poss"):
        recs.append(dict(
            title="Giving the ball away: one possession session a week",
            why=f"Pass completion is {rank('pass_pct')} and possession {rank('poss')}.",
            do="Swap one Playing Development session for Possession Ball Work in one-match weeks. Also check your tactic: very "
               "direct passing and high tempo lower pass completion on purpose in a " + TACTICAL_STYLE.lower() + ".",
            safe="It replaces a session of the same category and intensity, so the physical load stays the same."))
    stam = style_avg.get("stamina")
    if stam is not None and stam < 14 and not good("dist_diff") and not good("dist"):
        recs.append(dict(
            title="Fitness for the press: one Conditioning session in one-match weeks",
            why=f"Your best XI averages {stam:.1f} Stamina and you're {rank('dist_diff')} for running vs opponents.",
            do="Two days after a match, swap one of that day's Playing Development sessions for Conditioning — only in weeks with a single match.",
            safe="Conditioning raises fatigue and injury risk, which is why it goes two days after a match (when players have "
                 "recovered) and never in two-match weeks. Leave Recovery the day after every match."))
    elif stam is not None and stam < 14:
        keep.append(f"Stamina is your best XI's weakest {TACTICAL_STYLE.lower()} attribute ({stam:.1f}), but you're still "
                    f"{rank('dist_diff')} for running vs opponents — don't add Conditioning; it would raise injury risk for no gain.")
    agg = style_avg.get("aggression")
    if agg is not None and agg < 14:
        line = f"Aggression is low across your XI ({agg:.1f})"
        if bad("fouls"):
            line += (f", but you're already {rank('fouls')} for fouls — training it team-wide would add fouls and cards. Only "
                     f"give it as an individual focus to players who are also poor at winning the ball back.")
        else:
            line += " — handle it with individual focus for the players who need it, not the team schedule."
        keep.append(line)
    for k in ("shots", "dist_diff", "opp_final3", "xga", "ga"):
        if good(k):
            keep.append(f"{ms[k]['label']} ({rank(k)}): {ms[k]['good']} — don't take out the sessions behind it.")
    if not recs:
        recs.append(dict(title="Your schedule is doing its job", why="Nothing in your numbers points at a training problem.",
                         do="Keep the current rotation.", safe="—"))
    return recs, keep


def training_page(R) -> str:
    T = R.get("training") or []
    first = next((t for t in T if t["name"] == "First team"), T[0] if T else None)
    team_cards = []
    for t in T:
        def sh(name):   # drop the family prefix when the column is narrow
            return name if t is first else name.replace("Development Focus - ", "").replace("Tactical Focus - ", "")
        rot = "".join(f'<div class="rot" title="{E(name)}"><span>{E(sh(name))}</span><i style="width:{min(100, n * 8)}%"></i><b>{n}</b></div>'
                      for name, n in t["rotation"].most_common())
        nxt = "".join(f'<li title="{E(name)}"><span>{d(ws, "%d %b")}</span>{E(sh(name))}</li>' for ws, name in t["upcoming"])
        grid = ""
        if t is first and t["grid"]:
            head = "".join(f'<th>{d(g["day"], "%a %d")}</th>' for g in t["grid"])
            body = ""
            for k in range(3):
                cells = ""
                for g in t["grid"]:
                    code = g["sessions"][k] if k < len(g["sessions"]) else None
                    if code is None:
                        cells += "<td></td>"
                        continue
                    cls, fam = session_family(code)
                    name = SESSION_NAME.get(code, fam)
                    cells += f'<td class="ses {cls}" title="{E(fam)}">{E(name)}</td>'
                body += f"<tr>{cells}</tr>"
            grid = (f'<div class="tgrid"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'
                    '<div class="acc tnote">Sessions without a name here are shown by category — your Training screen has the exact session.</div>')
        team_cards.append(f"""<div class="tcard"><div class="tch"><b>{E(t['name'])}</b><span>this week</span></div>
          <div class="tnow">{E(t['current'] or '—')}</div>{grid}
          <div class="tcols"><div><div class="tl">Next weeks</div><ul class="tnext">{nxt}</ul></div>
          <div><div class="tl">Used this season</div>{rot}</div></div></div>""")
    teams_html = "".join(team_cards) or '<div class="acc">No training calendar found in this save.</div>'

    recs, keep = team_training_advice(R, first)
    rec_html = "".join(f"""<div class="trec"><h4>{E(r['title'])}</h4>
      <div class="tr1"><span class="tl">Why</span><p>{E(r['why'])}</p></div>
      <div class="tr1"><span class="tl">Change</span><p>{E(r['do'])}</p></div>
      <div class="tr1"><span class="tl">Won't hurt</span><p>{E(r['safe'])}</p></div></div>""" for r in recs)
    keep_html = "".join(f"<li>{E(k)}</li>" for k in keep)

    # individual training
    first_team = [p for p in R["players"] if p["where"] == "squad" and not p["youth"] and not LEAVING & p.keys()]
    xi_ids = {id(q) for _, q in R["xi1"] if q}
    first_team.sort(key=lambda p: (id(p) not in xi_ids, -(p["best"][1][0] if p["best"] else 0)))
    rows, folded = [], 0
    for p in first_team:
        plan = individual_plan(R, p)
        if not plan:
            continue
        pw = "".join(f'<div class="pw"><b>{E(w["code"])}</b> {E(w["phase"])} — {E(w["word"])} ({w["fam"]}/20) · '
                     f'<span class="acc">{E(w["how"])}</span></div>' for w in plan["pos_work"]) or '<span class="okk">Natural — none</span>'
        if plan["focus"]:
            attr, v = plan["focus"]
            focus = f'<span class="fz">{E(attr_label(attr))} <b>{v}</b></span>'
            if plan["second"]:
                focus += f'<div class="acc nx">then {E(attr_label(plan["second"][0]))} ({plan["second"][1]})</div>'
        else:
            focus = '<span class="okk">Nothing at 13 or below — keep him on his role</span>'
        extra = ""
        if plan["untrain"]:
            extra = " " + "; ".join(f"{attr_label(k)} {v} can't really be trained — mentoring helps with Determination"
                                    if k == "determination" else f"{attr_label(k)} {v} is largely fixed"
                                    for v, k in plan["untrain"]) + "."
        xi = '<span class="xi">XI</span>' if plan["in_xi"] else ""
        xtra = "" if plan["in_xi"] else " xtra"
        folded += not plan["in_xi"]
        rows.append(f"""<tr class="{row_state(p)}{xtra}"><td class="nm">{E(short(p['name']))}{xi}</td><td>{E(plan['label'])}</td>
          <td><div>{E(plan['ip_role'])}</div><div class="acc">{E(plan['oop_role'])}</div></td><td class="pwc">{pw}</td>
          <td>{focus}</td><td class="whyc">{E(plan['why'] + extra)}</td></tr>""")
    ind_html = "".join(rows)

    prospects = sorted((p for p in R["players"] if p["where"] in ("squad", "loan_out") and p.get("potential")
                        and (p["potential"] >= 3.5)), key=lambda p: -p["potential"])[:12]
    prow = []
    for p in prospects:
        plan = individual_plan(R, p)
        if not plan:
            continue
        focus = (f'{E(attr_label(plan["focus"][0]))} <b>{plan["focus"][1]}</b>' if plan["focus"] else "—")
        where = "on loan — set it with his loan club in mind" if p["where"] == "loan_out" else (
            "U21/U18" if p["youth"] else "first team")
        prow.append(f"""<tr><td class="nm">{E(short(p['name']))}</td><td>{p['age'] or ''}</td><td>{E(plan['label'])}</td>
          <td>{E(plan['ip_role'])} / {E(plan['oop_role'])}</td><td>{focus}</td><td class="acc">{E(where)}</td></tr>""")
    prospects_html = "".join(prow)

    # mentoring: low determination youngsters + high determination senior pros
    low_det = [p for p in R["players"] if p["where"] == "squad" and (p["age"] or 99) <= 21 and (p["attrs"].get("determination") or 20) <= 11]
    high_det = sorted((p for p in R["players"] if p["where"] == "squad" and not p["youth"] and (p["age"] or 0) >= 26
                       and (p["attrs"].get("determination") or 0) >= 16), key=lambda p: -p["attrs"]["determination"])[:4]
    mentor = ""
    if low_det and high_det:
        mentor = f"""<section id="tr-mentor"><h2>Mentoring <span class="h2sub">Determination is part of {E(TACTICAL_STYLE.lower())} but can't be trained — mentoring is FM's way to shape it</span></h2>
  <div class="explain">Young players with low Determination: <b>{E(", ".join(f"{short(p['name'])} ({p['attrs']['determination']})" for p in low_det[:8]))}</b>.
  Senior pros with high Determination: <b>{E(", ".join(f"{short(p['name'])} ({p['attrs']['determination']})" for p in high_det))}</b>.
  Put them in a mentoring group together (Training → Mentoring → Create New Mentoring Group). Mentoring rubs personality off on
  the youngsters over months, and it costs nothing in training time.</div></section>"""

    cheat = [("Opponents pass through your press", "Out Of Possession weeks: Pressing Intensity, Pressing Trap, Out Of Possession Shape", "Anticipation, Work Rate, Aggression (only if you're not already giving away lots of fouls)"),
             ("Lots of shots, few clear-cut chances", "Chance Creation; Final Third as the pre-match session", "Vision, Passing, Off the Ball"),
             ("Not finishing chances (goals below xG)", "Mostly individual; Attacking Ball Work in one-match weeks", "Finishing, Composure"),
             ("Losing the ball / low pass completion", "Possession Ball Work, Passing Style, Build Up", "First Touch, Composure, Passing, Decisions"),
             ("Losing headers / set pieces", "Corners and Free Kicks as Match Preparation sessions", "Heading, Jumping Reach, Strength"),
             ("Being outrun late in games", "Conditioning, two days after a match, one-match weeks only", "Stamina (Natural Fitness can't really be trained)"),
             ("Conceding chances in behind", "Line of Engagement, Out Of Possession Shape; Defensive Positioning pre-match", "Positioning, Concentration, Pace")]
    cheat_html = "".join(f"<tr><td>{E(a)}</td><td>{E(b)}</td><td>{E(c)}</td></tr>" for a, b, c in cheat)
    jumps = [("tr-teams", "Training in place"), ("tr-change", "What to change"), ("tr-indiv", "Individual training")]
    if prospects_html:
        jumps.append(("tr-prospects", "Prospects"))
    if mentor:
        jumps.append(("tr-mentor", "Mentoring"))
    jumps.append(("tr-howto", "Doing it yourself"))
    nav = "".join(f'<button class="fchip" data-jump="{k}">{E(v)}</button>' for k, v in jumps)
    return f"""<div class="subnav"><span class="fl">Jump to</span>{nav}</div>
<section id="tr-teams"><h2>Training in place <span class="h2sub">read from your save's training calendars · the schedule name is exactly what your Training screen shows</span></h2>
  <div class="tteams">{teams_html}</div></section>
<section id="tr-change"><h2>What to change in the first team's schedule <span class="h2sub">each one from your own match numbers (Tactical fit → How it's going)</span></h2>
  <div class="trecs">{rec_html}</div>
  {f'<div class="insights"><b>Leave these alone</b><ul>{keep_html}</ul></div>' if keep_html else ''}</section>
<section id="tr-indiv"><h2>Individual training — first team <span class="h2sub">FM doesn't let other tools read what each player is set to now, so compare this with his card in Training → Individual Training</span></h2>
  <div class="explain">Set each player's <b>IP Role</b> and <b>OOP Role</b> to the roles he plays in your tactic, give him the
  <b>Individual Training Focus</b> shown, and use <b>Position/Role</b> or <b>Individual Out of Possession Training</b> for the
  position work. One focus at a time: change it once that attribute has gone up or after a couple of months. If FM doesn't list
  that exact attribute as a focus, pick the option that includes it (e.g. a speed focus for Pace or Acceleration). Drop the focus
  for anyone who's playing twice a week and starting to look tired.</div>
  <div class="ftable indiv clipped" id="indivT"><table><thead><tr><th>Player</th><th>Plays</th><th>IP / OOP role to train</th><th>Position work</th>
  <th>Focus</th><th>Why</th></tr></thead><tbody>{ind_html}</tbody></table></div>{more_btn("indivT", folded, "players outside your best XI") if folded else ""}</section>
{f'''<section id="tr-prospects"><h2>Prospects <span class="h2sub">players {POTENTIAL_MAX_AGE} and under with 3.5★+ potential</span></h2>
  <div class="ftable indiv"><table><thead><tr><th>Player</th><th>Age</th><th>Plays</th><th>Roles to train</th><th>Focus</th><th></th></tr></thead>
  <tbody>{prospects_html}</tbody></table></div></section>''' if prospects_html else ''}
{mentor}
<section id="tr-howto"><details class="fold"><summary><h2>Doing it yourself next time <span class="h2sub">how the advice above is worked out · seven steps and a cheat sheet</span></h2></summary>
  <div class="explain"><ol class="steps">
    <li><b>Find the problem in the numbers, not the attributes.</b> Tactical fit → How it's going lists what's in the bottom half of the league. That's what training should fix.</li>
    <li><b>Match it to a session</b> with the cheat sheet below. Team problems (shape, pressing, chance creation) are team sessions; player problems (finishing, heading) are individual focus.</li>
    <li><b>Swap, don't stack.</b> Every day already has three sessions. Replace a session of the same category, ideally one behind something you're already top of the league for. Adding load is how players get injured.</li>
    <li><b>Keep the match rhythm.</b> Recovery the day after a match, Match Preparation the day before, anything heavy two days after a match. No extra physical work in two-match weeks.</li>
    <li><b>Check FM's own warning.</b> Each schedule shows its effect on injury risk, fatigue and condition — if a change turns those red, undo it.</li>
    <li><b>Individual focus = the lowest trainable attribute that matters</b> for his role or your style, preferring one behind a weak number of his. One at a time.</li>
    <li><b>Re-check in a month.</b> Refresh this report and see if the number moved.</li></ol></div>
  <div class="ftable cheat"><table><thead><tr><th>If this isn't working</th><th>Team sessions</th><th>Individual focus</th></tr></thead><tbody>{cheat_html}</tbody></table></div></details></section>"""


def fit_page(R):
    F = R["fit"]
    mis = []
    for m in F["misfits"]:
        p = m["p"]
        if m["best"]:
            e, r = m["best"]
            row = r["row"]
            where = (f'Best fit: <b>{E(r["label"])}</b> · {E(ROLES["IP"][row[3]][0])} / '
                     f'{E(ROLES["OOP"][row[4]][0])} · {e["fit"]:.1f}')
            weak = "".join(f'<span class="wk">{E(attr_label(k))} {v}</span>' for v, k in e["weak"][:4])
            weak += "".join(f'<span class="wk st">{E(attr_label(k))} {v}</span>' for v, k in e["style_weak"][:3]
                            if (v, k) not in e["weak"])
        else:
            where, weak = "No slot in your tactic", ""
        mis.append(f"""<div class="mis {row_state(p)}"><div class="mtop"><b>{E(p['name'])}</b><span>{p['age'] or ''}</span></div>
          <div class="mwhere">{where}</div><div class="mwhy">{E(m['why'])}</div><div>{weak}</div></div>""")
    mis_html = "".join(mis) or '<div class="allgood">Everyone in your first team suits a role in this tactic. 🔥</div>'

    xi_by_row = [p for _, p in R["xi1"]]          # best XI, one player per FORMATION row
    xi_entry = [next((e for e in r["entries"] if e["p"] is xi_by_row[i]), None) if i < len(xi_by_row) else None
                for i, r in enumerate(F["rows"])]
    fits = [(e["fit"], i) for i, e in enumerate(xi_entry) if e]
    pick = min(fits)[1] if fits else 0           # open on the weakest fit in your best XI
    tabs = []
    for i, (r, e, (x, y)) in enumerate(zip(F["rows"], xi_entry, PITCH_XY)):
        cls = ("good" if e["fit"] >= 14 else "ok" if e["fit"] >= FIT_FLOOR else "bad") if e else "bad"
        val = f'{e["fit"]:.1f}' if e else "–"
        who = E(surname(e["p"]["name"])) if e else "nobody"
        on = i == pick
        tabs.append(f'<button type="button" role="tab" id="rtab-{i}" aria-controls="role-{i}" aria-selected="{"true" if on else "false"}" '
                    f'tabindex="{0 if on else -1}" class="rpk {cls}" style="--x:{x}%;--y:{y}%" title="{E(r["label"])}: {who} fits at {val}">'
                    f'<b>{E(r["label"])}</b><i>{val}</i><span>{who}</span></button>')
    cards = []
    for i, r in enumerate(F["rows"]):
        slot, _, _, ip_role, oop_role = r["row"]
        ip_keys, oop_keys = ROLES["IP"][ip_role][1], ROLES["OOP"][oop_role][1]
        keys = list(dict.fromkeys(ip_keys + oop_keys))
        tag = {k: ("both" if k in ip_keys and k in oop_keys else "ip" if k in ip_keys else "oop") for k in keys}
        chips = "".join(f'<span class="kc {tag[k]}">{E(attr_label(k))}</span>' for k in keys)
        head = "".join(f'<th class="ak {tag[k]}" title="{E(attr_label(k))}">{E(ATTR_ABBR.get(k, attr_label(k)[:3]))}</th>' for k in keys)
        head += f'<th class="ak sty" title="Average of your {E(TACTICAL_STYLE)} attributes">{E(TACTICAL_STYLE[:5])}</th>' 
        body = []
        for e in r["entries"][:FIT_ROWS_SHOWN]:
            p = e["p"]
            xi = '<span class="xi">XI</span>' if e["xi"] else ""
            body.append(f"""<tr class="{row_state(p)}"><td class="nm">{E(short(p['name']))}{xi}</td><td>{fit_bar(e['fit'])}</td>
              {''.join(attr_cell(p['attrs'].get(k)) for k in keys)}{attr_cell(round(e['style']) if e['style'] is not None else None)}</tr>""")
        if not body:
            body.append(f'<tr><td colspan="{len(keys) + 2}" class="acc">Nobody in your first team can play here.</td></tr>')
        cards.append(f"""<div class="fcard" id="role-{i}" role="tabpanel" aria-labelledby="rtab-{i}"{"" if i == pick else " hidden"}><div class="fhead"><span class="slot">{E(r['label'])}</span>
            <span class="roles"><b>{E(ROLES['IP'][ip_role][0])}</b> <em>in possession</em> · <b>{E(ROLES['OOP'][oop_role][0])}</b> <em>out of possession</em></span></div>
            <div class="look"><span class="lk">Look for</span>{chips}</div>
            <div class="ftable"><table><thead><tr><th>Player</th><th>Fit</th>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div></div>""")
    style_chips = "".join(f'<span class="kc sty">{E(attr_label(k))}</span>' for k in STYLE_KEYS)
    nav = "".join(f'<button class="fchip" data-jump="{k}">{E(v)}</button>' for k, v in
                  (("fit-perf", "How it's going"), ("fit-gegen", f"{TACTICAL_STYLE} breakdown"),
                   ("fit-mis", "Players who don't fit"), ("fit-roles", "Role by role")))
    return f"""<div class="subnav"><span class="fl">Jump to</span>{nav}
  <span class="stylechips"><b>{E(TACTICAL_STYLE)} asks for</b>{style_chips}</span></div>
{perf_section(R)}
{gegen_section(R)}
<section id="fit-mis"><h2>Players who don't fit the system <span class="h2sub">first team, judged on the key attributes of their best role in your tactic</span></h2>
  <div class="misgrid">{mis_html}</div></section>
<section id="fit-roles"><h2>Role by role <span class="h2sub">fit = role key attributes (in &amp; out of possession) blended with {E(TACTICAL_STYLE)} attributes · XI = in your best XI</span></h2>
  <div class="klegend"><span class="kc ip">In possession</span><span class="kc oop">Out of possession</span><span class="kc both">Both</span>
    <span class="scale"><i class="a1">≤{WEAK_ATTR - 2}</i><i class="a2">{WEAK_ATTR - 1}–{WEAK_ATTR}</i><i class="a3">11–12</i><i class="a4">13–15</i><i class="a5">16+</i></span></div>
  <div class="rolepick"><div><div class="rpitch" role="tablist" aria-label="Positions in your tactic">
    <i class="rl half"></i><i class="rl circ"></i><i class="rl box t"></i><i class="rl box b"></i>{''.join(tabs)}</div>
    <p class="rpcap">Pick a position. The number is how well your best XI player there fits the role (/20) · it opens on the weakest.</p></div>
    <div class="rpcards">{''.join(cards)}</div></div></section>"""


def stats_rows(entries):
    body = []
    most = max((s["apps"] for _, s, _ in entries), default=0) or 1
    for p, s, team in entries:
        avg = s["avg"]
        cls = "" if avg is None else ("hi" if avg >= HIGH_MATCH_RATING else ("lo" if avg < LOW_MATCH_RATING else ""))
        slot = p["best"][0] if p["best"] else "–"
        cs = str(s["cs"]) if slot in ("GK", "LB", "CB", "RB") else "–"
        team_td = f"<td>{E(team)}</td>" if team is not None else ""
        bar = f'<span class="abar" style="--w:{s["apps"] / most * 100:.0f}%" aria-hidden="true"></span>'
        body.append(f"""<tr class="{row_state(p)}"><td class="nm">{E(p['name'])}</td>{team_td}<td>{slot}</td><td class="r lo">{p['age'] or ''}</td>
          <td class="r">{bar}{s['apps']}</td><td class="r">{s['g']}</td><td class="r">{s['a']}</td>
          <td class="r avg {cls}">{'–' if avg is None else f'{avg:.2f}'}</td><td class="r lo">{cs}</td><td class="r lo">{s['y']} / {s['r']}</td></tr>""")
    return "".join(body)


def stat_leaders(R) -> str:
    """Season leaders as key figures: the leader, his number, and the next two behind him."""
    rows = [(p, p["stats"]) for p in R["players"] if p.get("stats") and p["stats"].get("apps")]
    if not rows:
        return ""
    most = max(s["apps"] for _, s in rows)
    floor = max(3, round(most / 3))
    keepers = [(p, s) for p, s in rows if p["best"] and p["best"][0] == "GK"]
    rated = [(p, s) for p, s in rows if s.get("avg") is not None and s["apps"] >= floor]

    def card(label, pool, key, fmt=str):
        ranked = sorted(pool, key=lambda e: -e[1][key])
        if not ranked or not ranked[0][1][key]:
            return (f'<div class="tile ldr"><div class="lbl">{label}</div><div class="val">–</div>'
                    f'<div class="who acc">Nobody yet</div></div>')
        top = ranked[0][1][key]
        leaders = [p for p, s in ranked if s[key] == top]
        who = E(leaders[0]["name"])
        if len(leaders) == 2:
            who = f"{E(surname(leaders[0]['name']))} &amp; {E(surname(leaders[1]['name']))}"
        elif len(leaders) > 2:
            who += f' <span class="acc">+{len(leaders) - 1} more</span>'
        nxt = [(p, s) for p, s in ranked if s[key] != top][:2]
        then = " · ".join(f"{E(surname(p['name']))} {fmt(s[key])}" for p, s in nxt)
        return (f'<div class="tile ldr"><div class="lbl">{label}</div><div class="val">{fmt(top)}</div>'
                f'<div class="who">{who}</div><div class="sub">{"then " + then if then else "&nbsp;"}</div></div>')

    cards = [card("Goals", rows, "g"), card("Assists", rows, "a"),
             card(f"Average rating · {floor}+ apps", rated, "avg", lambda v: f"{v:.2f}"),
             card("Appearances", rows, "apps"), card("Clean sheets · keepers", keepers, "cs")]
    return f"""<section><h2>Season leaders <span class="h2sub">first team, all competitions</span></h2>
  <div class="fin k5 ldrs">{''.join(cards)}</div></section>"""


def stats_table(R):
    head = ('<th class="r">Apps</th><th class="r">G</th><th class="r">A</th><th class="r">Avg</th>'
            '<th class="r lo">CS</th><th class="r lo">Y / R</th>')
    first = sorted(((p, p["stats"], None) for p in R["players"] if p.get("stats")), key=lambda e: -e[1]["apps"])
    names = R.get("team_names", {})
    youth = sorted(((p, s, names.get(s["team"], "Youth")) for p in R["players"] for s in p.get("ystats") or []),
                   key=lambda e: (e[2], -e[1]["apps"]))
    first_html = stats_rows(first) or '<tr><td colspan="9" class="acc">No first-team appearances yet this season.</td></tr>'
    youth_html = stats_rows(youth) or '<tr><td colspan="10" class="acc">No youth-team appearances yet this season.</td></tr>'
    return f"""{stat_leaders(R)}<section><h2>First team <span class="h2sub">all competitions this season · only appearances for the first team · tap a column to sort</span></h2>
  <table class="squad stats sortable sticky-h" data-default="3"><caption class="sr">First team stats, sortable by column</caption><thead><tr><th>Player</th><th>Pos</th><th class="r lo">Age</th>{head}</tr></thead><tbody>{first_html}</tbody></table></section>
<section><h2>Youth teams <span class="h2sub">appearances for your U21 and U18 sides</span></h2>
  <table class="squad stats sortable sticky-h" data-default="4"><caption class="sr">Youth team stats, sortable by column</caption><thead><tr><th>Player</th><th>Team</th><th>Pos</th><th class="r lo">Age</th>{head}</tr></thead><tbody>{youth_html}</tbody></table></section>"""


def sandbox_data(R) -> str:
    labels = row_labels()
    rows = [dict(slot=r[0], label=lab, ip=ROLES["IP"][r[3]][0], oop=ROLES["OOP"][r[4]][0],
                 prow=PITCH_ROW.get(r[0], 2), lr=LEFT_TO_RIGHT.index(r[0]) if r[0] in LEFT_TO_RIGHT else 5)
            for lab, r in zip(labels, FORMATION)]

    def entry(pid, p, st, note, target=False):
        chips = {}
        for i, (v, code) in p["rows"].items():
            lab = FORMATION[i][0]
            if lab not in chips or v > chips[lab][1]:
                chips[lab] = [lab, round(v, 2), code]
        return dict(id=pid, n=p["name"], s=short(p["name"]), a=p["age"], y=p["youth"], t=1 if target else 0,
                    pos=" ".join(p.get("fm_nat") or []), st=st, note=note,
                    best=round(p["best"][1][0], 2) if p["best"] else 0,
                    sl=sorted(chips.values(), key=lambda c: -c[1]),
                    r={str(k): [round(v[0], 2), v[1]] for k, v in p["orows"].items()})

    players = []
    for i, p in enumerate(R["players"]):
        if not p["orows"]:
            continue
        if p["where"] == "loan_out":
            st, note = "away", f"On loan at {p['loan_out'][0]}"
        elif "deal_out" in p or "loan_out_arr" in p:
            v = p.get("deal_out") or p.get("loan_out_arr")
            st, note = "left", f"Leaving for {v[0]} · {d(v[1])}"
        elif "inj" in p:
            st, note = "injured", f"Injured · {injury_text(p['inj'][0])} · back {d(p['inj'][2])}"
        elif "sus" in p:
            st, note = "suspended", "Suspended"
        else:
            st, note = "available", ""
        if p["where"] == "incoming":
            v = p.get("deal_in") or p.get("loan_in_arr")
            note = f"Arriving from {v[0]} · {d(v[1])}"
        e = entry(i, p, st, note)
        e["g"] = 2 if p["where"] == "loan_out" else 1 if p["where"] == "incoming" else 0   # fixed list group
        players.append(e)
    for j, p in enumerate(R.get("targets", [])):
        if p["orows"]:
            e = entry(10000 + j, p, "target", f"{p['club']} · from {p['source']}", target=True)
            e["uid"] = p["uid"]
            players.append(e)
    by_obj = {id(p): i for i, p in enumerate(R["players"])}
    xi = [by_obj.get(id(p)) if p else None for _, p in R["xi1"]]
    xi_stars = [round(p["rows"].get(i, p["slots"][s])[0], 2) if p else 0 for i, (s, p) in enumerate(R["xi1"])]
    data = dict(rows=rows, players=players, xi=xi, xiStars=xi_stars, xiLevel=round(R["xi_level"], 2),
                key=f"fm27sandbox2:{R['club']}:{R['save_name']}")
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def sandbox_page(R):
    return f"""<section><h2>Sandbox <span class="h2sub">mark players injured, gone or away, sign your scouting targets, then build an XI · ratings change with the position you put someone in</span></h2>
  <p class="ph-only ph-note">Everything works here, but building line-ups is quicker on a bigger screen.</p>
  <div class="sbtop">
    <div class="sbscore"><div class="lbl">Your XI</div><div class="val" id="sbAvg"></div><div class="sub" id="sbCmp"></div></div>
    <div class="sbwarn" id="sbWarn" aria-live="polite"></div>
    <div class="sbbtns"><span class="sbmode" id="sbMode"></span><button class="fchip on" id="sbAuto">Auto-pick best XI</button>
      <button class="fchip" id="sbReset">Reset all changes</button></div>
  </div>
  <div class="sbgrid">
    <div><div class="pitchcap">Your XI <span>pick anyone · <span class="fam N">N</span>natural <span class="fam A">A</span>accomplished <span class="fam C">C</span>can play, not ideal <span class="fam X">X</span>out of position</span></div>
      <div class="pitch sbpitch" id="sbPitch"></div></div>
    <div><div class="pitchcap">Best XI <span>everyone fit · gold border = different from yours</span></div><div class="pitch sbpitch cmp" id="sbBest"></div></div>
  </div>
  <div class="sblist">
    <div class="sbfilter"><input id="sbSearch" placeholder="Search players…"><label class="ytog"><input type="checkbox" id="sbYouth"> Youth teams</label>
      <span class="sblegend"><span class="dot available"></span>Available <span class="dot injured"></span>Injured
        <span class="dot suspended"></span>Suspended <span class="dot left"></span>Left club <span class="dot away"></span>Away on loan
        <span class="dot signed"></span>Signed target</span></div>
    <div class="sbsec">Your squad <span>stars by position — he's rated differently in every slot</span></div>
    <div id="sbPlayers" class="sbcols"></div>
    <div class="sbsec">Scouting targets <span>from your FM Squad Planner, or picked below · set to <b>Signed</b> to use them</span></div>
    <div id="sbAdd" class="sbadd"></div>
    <div id="sbTargets" class="sbcols"></div>
    <div class="fair">Targets are rated from their real attributes. To keep it fair, only add players your scouts have fully
      reported on — and potential is never shown for them.</div>
  </div>
  <script id="sbdata" type="application/json">{sandbox_data(R)}</script></section>"""


SANDBOX_JS = r"""
(function(){
const el=document.getElementById('sbdata'); if(!el) return;
const D=JSON.parse(el.textContent), P={}; D.players.forEach(p=>P[p.id]=p);
const ST_SQUAD=[['available','Available'],['injured','Injured'],['suspended','Suspended'],['left','Left club'],['away','Away on loan']];
const ST_TARGET=[['target','Not signed'],['signed','Signed']];
const GROUP={N:0,A:0,C:1,X:2}, GNAME=['Plays here','Can play here, not ideal','Out of position'];
function fresh(){const s={status:{},lineup:D.xi.slice(),auto:true};D.players.forEach(p=>s.status[p.id]=p.st);return s;}
let S=null;try{const v=JSON.parse(localStorage.getItem(D.key)||'null');if(v&&v.status&&v.lineup)S=v;}catch(e){}
if(!S)S=fresh();
D.players.forEach(p=>{const cur=S.status[p.id];if(cur==null||(p.t&&!['target','signed'].includes(cur))||(!p.t&&['target','signed'].includes(cur)))S.status[p.id]=p.st;});
S.lineup=D.rows.map((_,i)=>{const id=S.lineup[i];return id!=null&&P[id]?id:null;});
function save(){try{localStorage.setItem(D.key,JSON.stringify(S));}catch(e){}}
const avail=id=>S.status[id]==='available'||S.status[id]==='signed';
const half=x=>Math.round(x*2)/2;
function starHTML(r){const w=half(Math.max(0,Math.min(5,r)))/5*100;return `<span class="stars sm">★★★★★<span class="on" style="width:${w}%">★★★★★</span></span>`;}
function hungarian(c){const n=c.length,m=c[0].length,INF=1e18,u=Array(n+1).fill(0),v=Array(m+1).fill(0),p=Array(m+1).fill(0),way=Array(m+1).fill(0);
 for(let i=1;i<=n;i++){p[0]=i;let j0=0;const minv=Array(m+1).fill(INF),used=Array(m+1).fill(false);
  do{used[j0]=true;const i0=p[j0];let delta=INF,j1=0;for(let j=1;j<=m;j++)if(!used[j]){const cur=c[i0-1][j-1]-u[i0]-v[j];if(cur<minv[j]){minv[j]=cur;way[j]=j0;}if(minv[j]<delta){delta=minv[j];j1=j;}}
   for(let j=0;j<=m;j++){if(used[j]){u[p[j]]+=delta;v[j]-=delta;}else minv[j]-=delta;}j0=j1;}while(p[j0]!==0);
  do{const j1=way[j0];p[j0]=p[j1];j0=j1;}while(j0);}
 const res=Array(n).fill(-1);for(let j=1;j<=m;j++)if(p[j])res[p[j]-1]=j-1;return res;}
function autoPick(){const pool=D.players.filter(p=>avail(p.id)),n=D.rows.length;
 if(!pool.length){S.lineup=Array(n).fill(null);return;}
 const cost=D.rows.map((r,i)=>pool.map(p=>{const x=p.r[i];if(!x)return 1e6;return -x[0]+[0,4,8][GROUP[x[1]]]-(x[1]==='N'?0.01:0);}).concat(Array(n).fill(1e3)));
 const pick=hungarian(cost);S.lineup=pick.map((j,i)=>j>=0&&j<pool.length&&cost[i][j]<1e5?pool[j].id:null);}
function rowsByLine(){const rows={};D.rows.forEach((r,i)=>{(rows[r.prow]=rows[r.prow]||[]).push(i);});
 return Object.keys(rows).sort((a,b)=>a-b).map(k=>rows[k].sort((a,b)=>D.rows[a].lr-D.rows[b].lr||a-b));}
const LINES='<div class="lines"><i class="half"></i><i class="circle"></i><i class="box top"></i><i class="box bot"></i></div>';
function rating(i){const id=S.lineup[i];if(id==null)return null;const x=P[id].r[i];return x||null;}
function renderPitch(){const pitch=document.getElementById('sbPitch');let html=LINES;
 rowsByLine().forEach(idx=>{html+='<div class="prow">'+idx.map(i=>{const r=D.rows[i],id=S.lineup[i],x=rating(i);
   const groups=[[],[],[]];D.players.forEach(q=>{const y=q.r[i];if(avail(q.id)&&y)groups[GROUP[y[1]]].push(q);});
   let sel=`<select data-row="${i}"><option value="">— nobody —</option>`;
   groups.forEach((g,gi)=>{if(!g.length)return;g.sort((a,b)=>b.r[i][0]-a.r[i][0]);
     sel+=`<optgroup label="${GNAME[gi]}">`+g.map(q=>`<option value="${q.id}"${q.id===id?' selected':''}>${q.s} · ${half(q.r[i][0])}★${q.t?' · target':''}${q.y?' · youth':''}</option>`).join('')+'</optgroup>';});
   sel+='</select>';
   const best=D.xiStars[i]||0,mine=x?x[0]:0,dlt=half(mine)-half(best);
   const dh=`<span class="dl ${dlt>0?'up':dlt<0?'down':'eq'}" title="vs your best XI in this slot">${dlt>0?'+':dlt<0?'−':''}${dlt===0?'=':Math.abs(dlt)+'★'}</span>`;
   const bestSlot=id!=null&&P[id].sl.length&&P[id].sl[0][0]!==r.slot&&P[id].sl[0][1]-mine>=0.5?`<div class="bsn">best at ${P[id].sl[0][0]} · ${half(P[id].sl[0][1])}★</div>`:'';
   return `<div class="pchip sb ${id==null?'empty':''}" title="${r.ip} in possession · ${r.oop} out of possession"><span class="ps">${r.label}</span>${sel}
     <div class="pr">${x?starHTML(x[0])+`<span class="fam ${x[1]}">${x[1]}</span>`:'<b class="none">Empty</b>'}${dh}</div>${bestSlot}</div>`;}).join('')+'</div>';});
 pitch.innerHTML=html;
 pitch.querySelectorAll('select').forEach(s=>s.addEventListener('change',e=>{const i=+e.target.dataset.row,v=e.target.value===''?null:+e.target.value;
  if(v!=null){const other=S.lineup.indexOf(v);if(other>=0&&other!==i)S.lineup[other]=null;}S.lineup[i]=v;S.auto=false;save();render();}));}
function renderBest(){let html=LINES;
 rowsByLine().forEach(idx=>{html+='<div class="prow">'+idx.map(i=>{const r=D.rows[i],id=D.xi[i],p=id!=null?P[id]:null,x=p?p.r[i]:null;
   const same=S.lineup[i]===id;
   return `<div class="pchip cmp ${same?'same':''}"><span class="ps">${r.label}</span><b>${p?p.s:'—'}</b><div class="pr">${x?starHTML(x[0])+`<span class="fam ${x[1]}">${x[1]}</span>`:''}</div></div>`;}).join('')+'</div>';});
 document.getElementById('sbBest').innerHTML=html;}
function renderSummary(){let tot=0,empty=0,odd=[],changed=0;S.lineup.forEach((id,i)=>{const x=rating(i);if(id!==D.xi[i])changed++;if(!x){empty++;return;}tot+=x[0];if(x[1]==='C'||x[1]==='X')odd.push(P[id].s);});
 const avg=tot/D.rows.length;document.getElementById('sbAvg').innerHTML=starHTML(avg)+` <span class="of">${avg.toFixed(1)}</span>`;
 let diff=Math.round((avg-D.xiLevel)*10)/10;if(Object.is(diff,-0))diff=0;
 document.getElementById('sbCmp').innerHTML=`${diff>=0?'+':''}${diff.toFixed(1)}★ vs best XI (${D.xiLevel.toFixed(1)}) · ${changed} change${changed===1?'':'s'}`;
 const out=D.players.filter(p=>!p.t&&!avail(p.id)&&p.st==='available').map(p=>p.s), signed=D.players.filter(p=>p.t&&S.status[p.id]==='signed').map(p=>p.s);
 let w='';if(empty)w+=`<div class="bad">${empty} empty slot${empty>1?'s':''}</div>`;
 if(odd.length)w+=`<div>Playing out of position: ${odd.join(', ')}</div>`;if(out.length)w+=`<div>Ruled out: ${out.join(', ')}</div>`;
 if(signed.length)w+=`<div class="sg">Signed: ${signed.join(', ')}</div>`;
 if(!w)w='<div class="acc">Full-strength XI. Change someone\'s status below or pick your own players on the pitch.</div>';
 document.getElementById('sbWarn').innerHTML=w;document.getElementById('sbMode').textContent=S.auto?'auto-picking':'your own picks';
 const key=avg.toFixed(2);if(lastAvg!==null&&lastAvg!==key&&window.gsap&&!matchMedia('(prefers-reduced-motion: reduce)').matches)
  gsap.fromTo('#sbAvg',{scale:1.08,color:'#fff'},{scale:1,color:'',duration:.45,ease:'power2.out',transformOrigin:'0 50%',clearProps:'transform,color'});lastAvg=key;}
function card(p,inXI){const opts=(p.t?ST_TARGET:ST_SQUAD).map(([k,l])=>`<option value="${k}"${S.status[p.id]===k?' selected':''}>${l}</option>`).join('');
 const chips=p.sl.map(([lab,st,c])=>`<i class="${c}">${lab} ${half(st)}★</i>`).join('')||'<i class="X">no slot in your tactic</i>';
 const rm=p.t&&window.FM27_LIVE&&/scouting list/.test(p.note)?`<button class="rmx" data-rm="${p.n.replace(/"/g,'&quot;')}" title="Remove from scouting.txt">×</button>`:'';
 return `<div class="sbp ${S.status[p.id]}${inXI?' inxi':''}"><span class="dot ${S.status[p.id]}"></span>
   <div class="sbn"><b>${p.n}</b><span>${p.pos}${p.a?' · '+p.a:''}${p.note?' · '+p.note:''}</span><div class="sl">${chips}</div></div>
   <select data-p="${p.id}">${opts}</select>${rm}</div>`;}
let lastAvg=null,foldAway=true;
const norm=v=>v.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
function renderList(){const q=norm(document.getElementById('sbSearch').value||'').trim(),youth=document.getElementById('sbYouth').checked;
 const inXI=new Set(S.lineup.filter(x=>x!=null));const match=p=>!q||norm(p.n).includes(q);
 const squad=D.players.filter(p=>!p.t&&(youth||!p.y||inXI.has(p.id))&&match(p)).sort((a,b)=>b.best-a.best);
 const tg=D.players.filter(p=>p.t&&match(p)).sort((a,b)=>b.best-a.best);
 let html='';
 [0,1,2].forEach(g=>{const ps=squad.filter(p=>(p.g||0)===g);if(!ps.length)return;
  if(g===2){const open=!foldAway||!!q;html+=`<button type="button" class="sbg tog" id="sbAwayTog" aria-expanded="${open}">Away on loan <span>${ps.length}</span><em>${open?'set one to Available to try him in this XI':'tap to show'}</em></button>`;if(!open)return;}
  else if(g===1)html+=`<div class="sbg">Arriving <span>${ps.length}</span><em>already agreed, rated as if they're here</em></div>`;
  html+=ps.map(p=>card(p,inXI.has(p.id))).join('');});
 document.getElementById('sbPlayers').innerHTML=html||'<div class="acc">No players match your search.</div>';
 const tog=document.getElementById('sbAwayTog');if(tog)tog.addEventListener('click',()=>{foldAway=!foldAway;renderList();document.getElementById('sbAwayTog').focus();});
 document.getElementById('sbTargets').innerHTML=tg.map(p=>card(p,inXI.has(p.id))).join('')||'<div class="acc">No scouting targets yet.</div>';
 document.querySelectorAll('.sblist select[data-p]').forEach(s=>s.addEventListener('change',e=>{const id=+e.target.dataset.p;S.status[id]=e.target.value;
  if(S.auto)autoPick();else S.lineup=S.lineup.map(x=>x!=null&&!avail(x)?null:x);save();render();}));
 document.querySelectorAll('.sblist [data-rm]').forEach(b=>b.addEventListener('click',()=>scout('remove',b.dataset.rm)));}
function addForm(){const box=document.getElementById('sbAdd');
 if(!window.FM27_LIVE){box.innerHTML='<span class="acc">To add players, type their names into <b>scouting.txt</b> in your FM27 Squad Report folder (one per line). Anyone you put in FM\'s Squad Planner is added automatically.</span>';return;}
 const POS=['GK','LB','LWB','CB','RB','RWB','DM','CM','LM','RM','AM','LW','RW','ST'];
 box.className='pick';
 box.innerHTML=`<p class="pk-why">FM doesn't let other tools read your scouting shortlist, so find the players here: type part of a name or a club.
   Anyone in FM's Squad Planner shows up by itself.</p>
  <div class="pk-bar"><div class="pk-in"><input id="pkQ" type="search" role="combobox" aria-expanded="false" aria-controls="pkList" aria-autocomplete="list"
     autocomplete="off" spellcheck="false" placeholder="Name or club, e.g. Mrozek or Benfica" aria-label="Find a player by name or club"></div>
   <select id="pkPos" aria-label="Position"><option value="">Any position</option>${POS.map(p=>`<option>${p}</option>`).join('')}</select>
   <select id="pkAge" aria-label="Age"><option value="">Any age</option><option value="19">19 and under</option><option value="21">21 and under</option><option value="23">23 and under</option></select></div>
  <div class="pk-msg" id="pkMsg" role="status" aria-live="polite"></div>
  <ul class="pk-list" id="pkList" role="listbox" aria-multiselectable="true" aria-label="Players in your save" hidden></ul>
  <div class="pk-tray" id="pkTray" hidden></div>`;
 const q=document.getElementById('pkQ'),pos=document.getElementById('pkPos'),age=document.getElementById('pkAge'),
  list=document.getElementById('pkList'),msg=document.getElementById('pkMsg'),tray=document.getElementById('pkTray');
 const have=new Set(D.players.filter(p=>p.t&&p.uid).map(p=>p.uid)),picked=new Map();let items=[],active=-1,timer=0,seq=0;
 const esc=v=>String(v==null?'':v).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
 function draw(){list.innerHTML=items.map((p,i)=>{const on=picked.has(p.uid),old=have.has(p.uid);
   return `<li role="option" id="pk-${p.uid}" data-i="${i}" aria-selected="${on}"${old?' aria-disabled="true"':''} class="${i===active?'act':''}">
    <span class="pk-tick" aria-hidden="true"></span><span class="pk-n"><b>${esc(p.n)}</b><span>${p.a?esc(p.a)+' · ':''}${esc(p.p||'?')} · ${esc(p.c)}</span></span>
    ${old?'<em>already in the Sandbox</em>':''}</li>`;}).join('');
  list.hidden=!items.length;q.setAttribute('aria-expanded',items.length?'true':'false');
  if(active>=0&&items[active])q.setAttribute('aria-activedescendant','pk-'+items[active].uid);else q.removeAttribute('aria-activedescendant');}
 function drawTray(){if(!picked.size){tray.hidden=true;tray.innerHTML='';return;}tray.hidden=false;
  tray.innerHTML=`<span class="pk-tl">Picked</span>${[...picked.values()].map(p=>`<span class="pk-chip">${esc(p.n)}<button type="button" data-un="${p.uid}" aria-label="Unpick ${esc(p.n)}">×</button></span>`).join('')}
   <button type="button" class="fchip on" id="pkAdd">Add ${picked.size} to the Sandbox</button>`;}
 function toggle(i){const p=items[i];if(!p||have.has(p.uid))return;picked.has(p.uid)?picked.delete(p.uid):picked.set(p.uid,p);active=i;draw();drawTray();}
 async function search(){const v=q.value.trim(),my=++seq;
  if(v.replace(/\s/g,'').length<2){items=[];active=-1;draw();msg.textContent=v?'Keep typing: at least 2 letters.':'';return;}
  msg.textContent='Searching…';
  try{const r=await fetch(`/players?q=${encodeURIComponent(v)}&pos=${pos.value}&age=${age.value}`,{cache:'no-store'});const j=await r.json();if(my!==seq)return;
   if(!j.ready){items=[];draw();msg.textContent='Still reading your save, try again in a few seconds.';return;}
   items=j.items;active=items.length?0:-1;draw();
   msg.textContent=!j.total?`No players match “${v}”${pos.value||age.value?' with those filters':''} in your save.`:
    j.total>items.length?`Showing ${items.length} of ${j.total}. Add a club, position or age to narrow it down.`:`${j.total} player${j.total===1?'':'s'}`;}
  catch(e){if(my===seq)msg.textContent='Couldn\'t search right now. Is the Squad Report window still open?';}}
 const later=()=>{clearTimeout(timer);timer=setTimeout(search,180);};
 q.addEventListener('input',later);pos.addEventListener('change',search);age.addEventListener('change',search);
 q.addEventListener('keydown',e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){if(!items.length)return;e.preventDefault();
   active=(active+(e.key==='ArrowDown'?1:-1)+items.length)%items.length;draw();const el=document.getElementById('pk-'+items[active].uid);if(el)el.scrollIntoView({block:'nearest'});}
  else if(e.key==='Enter'&&active>=0){e.preventDefault();toggle(active);}
  else if(e.key==='Escape'){items=[];active=-1;draw();msg.textContent='';}});
 list.addEventListener('mousedown',e=>e.preventDefault());   // keep focus in the search box
 list.addEventListener('click',e=>{const li=e.target.closest('li[data-i]');if(li)toggle(+li.dataset.i);});
 tray.addEventListener('click',e=>{const un=e.target.closest('[data-un]');if(un){picked.delete(+un.dataset.un);draw();drawTray();return;}
  if(e.target.id==='pkAdd'){const n=picked.size;e.target.disabled=true;
   post({action:'add_uids',uids:[...picked.keys()]},`Adding ${n} player${n===1?'':'s'}… this page refreshes by itself in about 30 seconds.`,msg);}});}
async function post(body,okText,msg){
 try{const r=await fetch('/scouting',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json();if(!j.ok)throw new Error(j.error||'failed');
  if(msg)msg.textContent=okText;
  const start=window.FM27_LIVE;const t=setInterval(async()=>{try{const s=await (await fetch('/status',{cache:'no-store'})).json();if(s.version!==start&&!s.building){clearInterval(t);location.reload();}}catch(e){}},2000);}
 catch(e){if(msg)msg.textContent='Couldn\'t update scouting.txt: '+e.message;}}
function scout(action,name){post({action,name},(action==='add'?'Adding ':'Removing ')+name+'… this page refreshes by itself in about 30 seconds.',document.getElementById('pkMsg'));}
function render(){renderPitch();renderBest();renderSummary();renderList();}
document.getElementById('sbAuto').addEventListener('click',()=>{S.auto=true;autoPick();save();render();});
document.getElementById('sbReset').addEventListener('click',()=>{S=fresh();autoPick();save();render();});
document.getElementById('sbSearch').addEventListener('input',renderList);document.getElementById('sbYouth').addEventListener('change',renderList);
addForm();if(S.auto)autoPick();render();
})();
"""


FILTER_JS = r"""
(function(){
const t=document.getElementById('squadTable'); if(!t) return;
const rows=[...t.querySelectorAll('tbody tr:not(.grp)')], heads=[...t.querySelectorAll('tbody tr.grp')];
const F={st:'all',pos:new Set(),mode:'any',youth:false,q:''};
const fold=new Set(heads.filter(h=>h.querySelector('.gtog').getAttribute('aria-expanded')==='false').map(h=>h.dataset.gh));
const rmF=matchMedia('(prefers-reduced-motion: reduce)').matches;
const norm=v=>v.normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();
rows.forEach(r=>{r.dataset.q=norm(r.cells[0].textContent);});
const search=document.getElementById('sqSearch'),count=document.getElementById('fcount');
function match(tr){const st=tr.dataset.st.split(' '),pos=tr.dataset.pos.split(' ');let ok=F.st==='all'||st.includes(F.st);
 if(ok&&F.pos.size){const a=[...F.pos];ok=F.mode==='any'?a.some(x=>pos.includes(x)):a.every(x=>pos.includes(x));}
 if(ok&&F.q)ok=tr.dataset.q.includes(F.q);
 if(ok&&tr.dataset.youth==='1'&&!F.youth)ok=false;return ok;}
function apply(){const fs=(window.Flip&&!rmF&&t.offsetParent)?Flip.getState(rows):null;
 const filtering=F.st!=='all'||F.pos.size>0||F.q!=='';const per={};let n=0,folded=0;
 rows.forEach(tr=>{tr._ok=match(tr);if(tr._ok){n++;per[tr.dataset.g]=(per[tr.dataset.g]||0)+1;}});
 if(filtering)Object.keys(per).forEach(g=>fold.delete(g));   // a filter or search always shows what it found
 rows.forEach(tr=>{const show=tr._ok&&!fold.has(tr.dataset.g);if(tr._ok&&!show)folded++;tr.style.display=show?'':'none';});
 heads.forEach(h=>{const g=h.dataset.gh,b=h.querySelector('.gtog');h.style.display=per[g]?'':'none';
  b.setAttribute('aria-expanded',!fold.has(g));b.querySelector('.gn').textContent=per[g]||0;});
 let none=t.querySelector('tr.nomatch');if(!none){none=document.createElement('tr');none.className='nomatch';t.tBodies[0].appendChild(none);}
 const other=F.st!=='all'||F.pos.size>0,said=search.value.trim().replace(/[<>&"]/g,'');
 none.innerHTML='<td colspan="10">No players match '+(F.q?'“'+said+'”'+(other?' with these filters':''):'these filters')+'.'
  +(F.q&&!F.youth?' Youth-team players only show with “Include youth teams”.':'')+' <button class="fchip" type="button" data-clear>Clear filters</button></td>';
 none.style.display=n?'none':'';
 count.textContent=`${n} player${n===1?'':'s'}`+(folded?` · ${folded} folded away`:'');
 document.querySelectorAll('.sqk .tbtn').forEach(b=>b.setAttribute('aria-pressed',b.dataset.st===F.st));
 if(fs)Flip.from(fs,{duration:.4,ease:'power2.out',onEnter:e=>gsap.fromTo(e,{opacity:0},{opacity:1,duration:.3})});}
function setSt(k){F.st=k;document.querySelectorAll('.filters .fchip[data-st]').forEach(x=>x.classList.toggle('on',x.dataset.st===k));apply();}
function clear(){F.st='all';F.pos.clear();F.mode='any';F.youth=false;F.q='';search.value='';document.getElementById('incYouth').checked=false;
 document.querySelectorAll('.filters .fchip').forEach(x=>x.classList.toggle('on',x.dataset.st==='all'||x.dataset.mode==='any'));apply();}
document.querySelectorAll('.filters .fchip[data-st]').forEach(b=>b.addEventListener('click',()=>setSt(b.dataset.st)));
document.querySelectorAll('.sqk .tbtn').forEach(b=>b.addEventListener('click',()=>setSt(F.st===b.dataset.st?'all':b.dataset.st)));
document.querySelectorAll('.filters .fchip.pos').forEach(b=>b.addEventListener('click',()=>{const v=b.dataset.pos;F.pos.has(v)?F.pos.delete(v):F.pos.add(v);b.classList.toggle('on');apply();}));
document.querySelectorAll('.filters .fchip.mode').forEach(b=>b.addEventListener('click',()=>{F.mode=b.dataset.mode;document.querySelectorAll('.filters .fchip.mode').forEach(x=>x.classList.toggle('on',x===b));apply();}));
document.getElementById('incYouth').addEventListener('change',e=>{F.youth=e.target.checked;apply();});
search.addEventListener('input',()=>{F.q=norm(search.value.trim());apply();});
search.addEventListener('keydown',e=>{if(e.key==='Escape'&&search.value){search.value='';F.q='';apply();}});
heads.forEach(h=>h.querySelector('.gtog').addEventListener('click',()=>{const g=h.dataset.gh;fold.has(g)?fold.delete(g):fold.add(g);apply();}));
document.getElementById('fclear').addEventListener('click',clear);
t.addEventListener('click',e=>{if(e.target.closest('[data-clear]'))clear();});
apply();
})();
"""


CSS = r"""
:root{--bg:#0e1512;--bg2:#121a16;--panel:#16201b;--panel2:#1d2923;--line:#2a3a32;--line2:#1f2c26;--text:#eef1e8;--text2:#c3cbc0;--muted:#8d9a91;
--red:var(--kit);--kit:#C8102E;--kit-ink:#fff;--brand:#1C7F46;--brand-ink:#fff;--gold:#e9b949;--star:#e9b949;--star0:#34443b;
--loanin:#3b82f6;--loanout:#a855f7;--dealin:#22c55e;--dealout:#ec4899;--injs:#facc15;--injl:#ef4444;--sus:#94a3b8;
--vred:#ff5d5d;--vamber:#f59e0b;--vgreen:#10b981;--vgrey:#6b7a71;
--display:"Archivo","Arial Narrow",system-ui,sans-serif;--gutter:clamp(18px,3.4vw,80px)}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 "Archivo",system-ui,sans-serif;font-stretch:100%;
 font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased}
::selection{background:var(--kit);color:var(--kit-ink)}
:focus-visible{outline:2px solid var(--gold);outline-offset:2px;border-radius:3px}
.wrap{max-width:none;margin:0;padding:22px var(--gutter) 60px}
.mock{background:repeating-linear-gradient(135deg,#2a1d06,#2a1d06 10px,#241905 10px,#241905 20px);border:1px solid #6b4e12;color:#f5c542;
 font-size:12px;font-weight:600;padding:7px 12px;border-radius:4px;margin-bottom:18px}
/* masthead: the one loud thing — kit-red band, shirt-lettering wordmark */
header.top{position:relative;overflow:hidden;display:flex;justify-content:space-between;gap:32px;align-items:flex-end;
 padding:26px var(--gutter) 22px;background:var(--kit);color:#fff;
 background-image:linear-gradient(100deg,rgba(255,255,255,.07) 0 38%,transparent 38% 100%),linear-gradient(180deg,transparent 60%,rgba(0,0,0,.18))}
header.top::after{content:"";position:absolute;left:0;right:0;bottom:0;height:4px;background:var(--gold)}
.kicker{font-family:var(--display);font-stretch:75%;font-weight:600;font-size:15px;color:rgba(255,255,255,.82)}
.brand h1{font-family:var(--display);font-stretch:62%;font-weight:900;font-style:italic;text-transform:uppercase;
 font-size:clamp(56px,9vw,112px);line-height:.82;letter-spacing:-.01em;margin:4px 0 0;color:#fff7ea}
.meta{display:grid;grid-template-columns:repeat(2,auto);gap:10px 28px;margin:0 0 4px;font-size:13px}
.meta div{min-width:0}.meta dt{font-size:12px;color:rgba(255,255,255,.72)}
.meta dd{margin:0;font-family:var(--display);font-stretch:75%;font-weight:700;font-size:18px;line-height:1.15;color:#fff;white-space:nowrap}
.meta .date dd{font-size:26px;font-weight:800}
.meta .save dd{font-family:inherit;font-stretch:100%;font-weight:500;font-size:13px;white-space:normal;max-width:260px}
.sticky{position:sticky;top:0;z-index:20;background:var(--bg);padding:0 var(--gutter);border-bottom:1px solid var(--line);
 box-shadow:0 12px 20px -16px rgba(0,0,0,.9)}
.nav{display:flex;gap:4px;overflow-x:auto;scrollbar-width:none}
.nav a{position:relative;display:flex;align-items:center;gap:7px;padding:13px 12px 11px;color:var(--muted);text-decoration:none;white-space:nowrap;
 font-family:var(--display);font-stretch:75%;font-weight:700;font-size:17px;transition:color .15s}
.nav a::after{content:"";position:absolute;left:10px;right:10px;bottom:0;height:4px;background:var(--kit);transform:scaleX(0);transition:transform .2s}
.nav a:hover{color:var(--text)}
.nav a.active{color:var(--text)}.nav a.active::after{transform:scaleX(1)}
.nav .k{font-size:11px;font-weight:600;font-stretch:100%;color:var(--muted);opacity:.7}
.nav .count{font-family:"Archivo",sans-serif;font-stretch:100%;font-size:11px;font-weight:700;background:var(--panel2);border-radius:3px;padding:0 6px;color:var(--text2)}
.nav .count.warn{background:var(--kit);color:var(--kit-ink)}
.page{display:none}.page.active{display:block;animation:pagein .25s ease-out}
@keyframes pagein{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.page.active{animation:none}.nav a::after{transition:none}}
@media print{.page{display:block!important;break-before:page}.sticky{position:static}.nav{display:none}}
h1{margin:2px 0 0;font-size:30px}
.chip{background:var(--panel2);border:1px solid var(--line);padding:1px 8px;border-radius:4px}
.fin{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);border-radius:6px;overflow:hidden}
.tile{background:var(--panel);padding:14px 18px 16px;min-width:0}
.tile .lbl{color:var(--muted);font-size:13px}
.tile .val{font-family:var(--display);font-stretch:62%;font-weight:800;font-size:44px;line-height:1;margin-top:6px}
.tile .of{color:var(--muted);font-family:"Archivo",sans-serif;font-stretch:100%;font-size:14px;font-weight:500}
.tile .sub{color:var(--muted);font-size:12px;margin-top:2px}.bar{height:6px;background:var(--panel2);border-radius:4px;margin-top:8px;overflow:hidden}
.bar i{display:block;height:100%;background:linear-gradient(90deg,#22c55e,#f59e0b)}
.legend{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:14px 0 4px}
.nlegend{color:var(--muted);font-size:12px;margin-left:8px;display:flex;gap:6px;align-items:center}
section{margin-top:40px}
h2{font-family:var(--display);font-stretch:62%;font-weight:800;font-size:34px;line-height:1;margin:0 0 16px;display:flex;align-items:baseline;flex-wrap:wrap;gap:4px 12px}
h2 .h2sub,.h2sub{font-family:"Archivo",sans-serif;font-stretch:100%;color:var(--muted);font-size:13px;font-weight:400;margin-left:0}
h3,h4{font-family:var(--display);font-stretch:75%;font-weight:700}
.slot{font-family:var(--display);font-stretch:62%;font-style:italic;font-weight:900;letter-spacing:0}
.stars{position:relative;display:inline-block;font-size:16px;line-height:1;color:var(--star0)!important;white-space:nowrap;vertical-align:-1px}
.stars .on{position:absolute;left:0;top:0;overflow:hidden;color:var(--star);text-align:left}
.stars.sm{font-size:13px}
.trend{font-size:11px;font-weight:700;margin-left:6px;white-space:nowrap}.trend.up{color:#22c55e}.trend.down{color:#ef4444}
.fam{flex-shrink:0;display:inline-block;font-size:10px;font-weight:800;width:16px;height:16px;line-height:16px;text-align:center;border-radius:4px;margin:0 6px 0 4px;vertical-align:1px}
.fam.N{background:var(--text);color:var(--bg)}.fam.A{border:1px solid var(--muted);color:var(--text2)}
.fam.C{border:1px dashed #f59e0b;color:#fbbf24}.fam.X{border:1px dashed #ef4444;color:#fca5a5}
.badge{display:inline-flex;align-items:center;gap:5px;font-size:11.5px;padding:2px 8px;border-radius:999px;white-space:nowrap;margin:1px 4px 1px 0;
 border:1px solid transparent}
.badge b{font-weight:700}
.badge.loan-in{background:rgba(59,130,246,.18);color:#93c5fd;border-color:rgba(59,130,246,.55)}
.badge.loan-out{background:rgba(168,85,247,.18);color:#d8b4fe;border-color:rgba(168,85,247,.55)}
.badge.deal-in{background:rgba(34,197,94,.16);color:#86efac;border-color:rgba(34,197,94,.55)}
.badge.deal-out{background:rgba(236,72,153,.16);color:#f9a8d4;border-color:rgba(236,72,153,.55)}
.badge.inj-short{background:var(--injs);color:#221a00}
.badge.inj-long{background:var(--injl);color:#fff}
.badge.sus{background:#0a0a0a;color:var(--text);border-color:#94a3b8}
.badge.expiring{background:transparent;color:var(--text2);border:1px dashed #94a3b8}
/* verdicts */
.vgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.vcard{background:var(--panel);border:1px solid var(--line);border-left:5px solid var(--vgrey);border-radius:6px;padding:14px 16px}
.vcard.red{border-left-color:var(--vred);background:linear-gradient(90deg,rgba(239,68,68,.10),var(--panel) 45%)}
.vcard.amber{border-left-color:var(--vamber);background:linear-gradient(90deg,rgba(245,158,11,.09),var(--panel) 45%)}
.vhead{display:flex;align-items:center;gap:10px}.rank{width:22px;height:22px;border-radius:50%;background:var(--panel2);color:var(--muted);
 font-size:12px;font-weight:700;display:grid;place-items:center}
.slot{font-size:26px;line-height:1}.vtitle{font-weight:700;font-size:13px}
.vcard.red .vtitle{color:#fca5a5}.vcard.amber .vtitle{color:#fcd34d}
.vcard p{margin:8px 0 10px;color:var(--text2)}.who{font-size:12.5px;color:var(--muted);margin-top:4px}.who .wl{display:inline-block;width:64px;font-weight:600}
.who em.none{color:#fca5a5;font-style:normal;font-weight:600}
.okrow{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap}
.okchip{flex:1;min-width:230px;background:var(--panel);border:1px solid var(--line);border-left:5px solid var(--vgreen);border-radius:5px;padding:9px 12px;
 display:flex;gap:8px;align-items:baseline;font-size:12.5px}
.okchip .slot{font-size:15px}.okchip b{color:#6ee7b7;font-size:11px}.okchip span:last-child{color:var(--muted)}
.okchip.grey{border-left-color:var(--vgrey)}.okchip.grey b{color:var(--text2)}
/* pitches */
.pitches{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px}
.ptitle{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px}.ptitle h3{margin:0;font-size:15px}.ptitle span{color:var(--muted);font-size:12.5px}
.pitch{position:relative;border-radius:6px;padding:16px 12px;background:repeating-linear-gradient(180deg,#14361f 0 52px,#173d23 52px 104px);border:1px solid #24502f}
.lines{position:absolute;inset:8px;border:1.5px solid rgba(255,255,255,.18);border-radius:4px;pointer-events:none}
.lines .half{position:absolute;left:0;right:0;top:50%;border-top:1.5px solid rgba(255,255,255,.18)}
.lines .circle{position:absolute;left:50%;top:50%;width:90px;height:90px;margin:-45px;border:1.5px solid rgba(255,255,255,.18);border-radius:50%}
.lines .box{position:absolute;left:30%;right:30%;height:56px;border:1.5px solid rgba(255,255,255,.18)}.lines .top{top:-1.5px;border-top:0}.lines .bot{bottom:-1.5px;border-bottom:0}
.prow{position:relative;display:flex;justify-content:space-evenly;gap:8px;margin:10px 0}
.pchip{width:140px;min-width:0;background:rgba(14,21,18,.9);border:1px solid var(--line);border-radius:5px;padding:6px 8px;text-align:center;box-shadow:0 4px 14px rgba(0,0,0,.35)}
.pchip b{display:block;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pchip .ps{font-size:10px;font-weight:800;color:var(--muted)}
.pchip .pr{display:flex;justify-content:center;align-items:center;margin-top:1px}.pchip .pb{margin-top:3px;min-height:0}
.pchip .badge{font-size:10px;padding:1px 6px}
.pchip.empty{border:1.5px dashed #ef4444;background:rgba(239,68,68,.12)}.pchip.empty b{color:#fca5a5}
.pchip.inj-long{border-color:var(--injl)}.pchip.inj-short{border-color:var(--injs)}.pchip.sus{border-color:#94a3b8}
.pchip.deal-in{border-color:var(--dealin)}.pchip.loan-in{border-color:var(--loanin)}
/* position cards */
.pgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
.pcard{background:var(--panel);border:1px solid var(--line);border-top:4px solid var(--vgrey);border-radius:6px;overflow:hidden}
.pcard.red{border-top-color:var(--vred)}.pcard.amber{border-top-color:var(--vamber)}.pcard.green{border-top-color:var(--vgreen)}
.pch{display:flex;align-items:center;gap:8px;padding:9px 10px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.pch .slot{font-size:17px}.pname{color:var(--muted);font-size:12px;flex:1}
.pch .vtag{flex-basis:100%;text-align:center}.vtag{font-size:10px;font-weight:700;padding:2px 7px;border-radius:999px;background:var(--panel2);color:var(--text2)}
.vtag.red{background:rgba(239,68,68,.18);color:#fca5a5}.vtag.amber{background:rgba(245,158,11,.16);color:#fcd34d}.vtag.green{background:rgba(16,185,129,.16);color:#6ee7b7}
.plist{padding:4px 0}
.prow2{display:grid;grid-template-columns:1fr 26px;grid-template-areas:"nm ag" "st st" "bd bd";padding:6px 10px;border-left:3px solid transparent}
.prow2+.prow2{border-top:1px solid var(--line2)}
.prow2 .nm{grid-area:nm;font-weight:600;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.prow2 .ag{grid-area:ag;color:var(--muted);text-align:right;font-size:12px}.prow2 .st{grid-area:st;padding-left:26px}
.prow2 .bd{grid-area:bd;padding-left:26px}.prow2 .bd:empty{display:none}.prow2 .badge{font-size:10px;padding:0 6px}
.prow2 .fam{margin-left:0}.u21{font-size:9.5px;font-weight:700;color:#7dd3fc;border:1px solid #2b5672;border-radius:4px;padding:0 4px;margin-left:6px;vertical-align:1px}
.prow2.loan-out{opacity:.55}.prow2.deal-out .nm{text-decoration:line-through;text-decoration-color:rgba(236,72,153,.7)}
.prow2.loan-in,.squad tr.loan-in td:first-child{border-left-color:var(--loanin)}
.prow2.loan-out,.squad tr.loan-out td:first-child{border-left-color:var(--loanout)}
.prow2.deal-in,.squad tr.deal-in td:first-child{border-left-color:var(--dealin)}
.prow2.deal-out,.squad tr.deal-out td:first-child{border-left-color:var(--dealout)}
.prow2.inj-short,.squad tr.inj-short td:first-child{border-left-color:var(--injs)}
.prow2.inj-long,.squad tr.inj-long td:first-child{border-left-color:var(--injl)}
.prow2.sus,.squad tr.sus td:first-child{border-left-color:#94a3b8}
/* tables */
.squad{width:100%;border-collapse:separate;border-spacing:0;background:var(--panel);border:1px solid var(--line);border-radius:6px;overflow:hidden}
.squad th{text-align:left;font-size:11px;color:var(--muted);padding:10px 12px;background:var(--panel2);border-bottom:1px solid var(--line)}
.squad td{padding:8px 12px;border-bottom:1px solid var(--line2);vertical-align:middle}
.squad td:first-child{border-left:4px solid transparent}
.squad .r{text-align:right;font-variant-numeric:tabular-nums}.squad .nm{font-weight:600}
.squad tr.grp td{background:var(--bg2);color:var(--muted);font-size:11px;font-weight:700;padding:7px 12px}
.squad .acc{color:var(--muted)}.squad td.exp{color:var(--text2);text-decoration:underline dashed #94a3b8;text-underline-offset:3px}
.squad tr.loan-out td{color:#b8aecb}
.stats .avg.hi{color:#4ade80;font-weight:700}.stats .avg.lo{color:#fbbf24}
/* deals */
.deals{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.dcol{background:var(--panel);border:1px solid var(--line);border-radius:6px;overflow:hidden}
.dcol h3{margin:0;padding:10px 14px;font-size:14px;display:flex;justify-content:space-between;align-items:center}
.dcol h3 span{font-size:12px;border-radius:999px;padding:0 8px;background:rgba(255,255,255,.12)}
.dcol.deal-in h3{background:rgba(34,197,94,.18);color:#86efac}.dcol.deal-out h3{background:rgba(236,72,153,.18);color:#f9a8d4}
.dcol.loan-out h3{background:rgba(168,85,247,.18);color:#d8b4fe}.dcol.loan-in h3{background:rgba(59,130,246,.18);color:#93c5fd}
.dcol ul{list-style:none;margin:0;padding:4px 0}.dcol li{display:flex;justify-content:space-between;gap:10px;padding:9px 14px;border-top:1px solid var(--line2)}
.dcol li:first-child{border-top:0}.dcol li span{display:block;color:var(--muted);font-size:12px}.dcol .dd{text-align:right;font-size:12.5px;color:var(--text2)}
.dcol li.empty{color:var(--muted)}
footer{margin-top:34px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}

.bs{font-size:10px;font-weight:700;color:var(--muted);margin-left:6px}
.wp{font-size:9.5px;font-weight:700;color:#fcd34d;border:1px solid rgba(245,158,11,.45);border-radius:4px;padding:0 4px;margin-left:8px;vertical-align:1px}
.halfnote{font-size:11.5px;color:var(--text2);background:rgba(148,163,184,.08);border-top:1px solid var(--line);padding:8px 10px}
.allgood{background:var(--panel);border:1px solid var(--line);border-left:5px solid var(--vgreen);border-radius:6px;padding:16px;margin-bottom:12px}
.more{color:var(--muted);font-size:12px;padding:6px 10px 8px 36px}
.yt{font-size:9.5px;font-weight:700;color:#a5b4c3;border:1px solid var(--line);border-radius:4px;padding:0 4px;margin-left:6px;vertical-align:1px}
details.youth{margin-top:14px}details.youth summary{cursor:pointer;color:var(--muted);font-weight:600;padding:8px 2px}
details.youth[open] summary{margin-bottom:8px}
.notes{margin:0 0 10px;padding-left:18px;color:#fbbf24}
.livebar{position:fixed;right:18px;bottom:18px;z-index:50;display:none;align-items:center;gap:8px;background:var(--panel);border:1px solid var(--line);
 border-radius:5px;padding:9px 14px;font-size:13px;color:var(--text);box-shadow:0 8px 30px rgba(0,0,0,.45)}
.livebar.show{display:flex}.livebar.new{border-color:#22c55e}.livebar.new a{color:#4ade80;font-weight:700}.livebar.err{border-color:#ef4444;color:#fca5a5}
.livebar .spin{width:12px;height:12px;border:2px solid var(--line);border-top-color:#d0102e;border-radius:50%;animation:lvspin 1s linear infinite}
@keyframes lvspin{to{transform:rotate(360deg)}}
.explain{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px 16px;margin-top:22px;color:var(--text2);font-size:13px;line-height:1.7}
.pot{margin-left:8px;display:inline-flex;align-items:center;gap:4px;padding:0 5px;border:1px dashed rgba(59,130,246,.6);border-radius:5px}
.pot .stars .on{color:#93c5fd}.potl{font-size:9.5px;font-weight:800;color:#93c5fd}
.filters{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px 12px;margin-bottom:12px}
.frow{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:4px 0}.fl{font-size:11px;font-weight:700;color:var(--muted);width:70px}
.fchip{font:inherit;font-size:12px;font-weight:600;color:var(--text2);background:var(--panel2);border:1px solid var(--line);border-radius:999px;padding:3px 11px;cursor:pointer}
.fchip:hover{border-color:var(--muted)}.fchip.on{background:color-mix(in srgb,var(--kit) 22%,transparent);border-color:color-mix(in srgb,var(--kit) 70%,transparent);color:#fff}
.fchip.pos{border-radius:6px;padding:3px 8px}.mode{margin-left:10px;display:flex;gap:4px}.fchip.mode.on{background:rgba(148,163,184,.25);border-color:#94a3b8}
.squad tr.nomatch td{color:var(--muted);text-align:center;padding:18px}
.ytog{font-size:12.5px;color:var(--text2);display:flex;gap:6px;align-items:center;cursor:pointer}.fcount{color:var(--muted);font-size:12px;margin-left:auto}
.sbtop{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:12px}
.sbstats{display:flex;gap:14px;align-items:flex-start}.sbwarn{font-size:12.5px;color:var(--text2);line-height:1.7}.sbwarn .bad{color:#fca5a5;font-weight:600}
.sbbtns{display:flex;gap:8px;align-items:center}.sbmode{font-size:12px;color:var(--muted)}
.sbgrid{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr);gap:14px}
.pchip.sb{width:150px}.pchip.sb select{width:100%;margin:3px 0;background:var(--bg);color:var(--text);border:1px solid var(--line);border-radius:6px;font:inherit;font-size:11.5px;padding:3px 2px}
.pchip.sb b.none{color:#fca5a5;font-size:12px}
.sblist{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px 14px;margin-top:16px}
.sbfilter{display:flex;gap:10px;align-items:center;margin-bottom:8px}.sbfilter input#sbSearch{flex:1;background:var(--bg);border:1px solid var(--line);color:var(--text);border-radius:4px;padding:6px 10px;font:inherit}
.sblegend{font-size:11.5px;color:var(--muted);display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.sbp{display:grid;grid-template-columns:12px minmax(0,1fr) auto auto;gap:8px;align-items:center;padding:7px 4px;border-top:1px solid var(--line2)}
.sbp .sbn b{display:block;font-size:13px}.sbp .sbn span{font-size:11.5px;color:var(--muted)}.sbp.inxi .sbn b::after{content:" XI";font-size:9.5px;color:var(--bg);background:var(--gold);border-radius:4px;padding:0 4px;margin-left:6px}
.sbp select{background:var(--bg);color:var(--text);border:1px solid var(--line);border-radius:6px;font:inherit;font-size:12px;padding:3px}
.sbp.injured,.sbp.suspended,.sbp.left,.sbp.away{opacity:.65}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%}.dot.available{background:#22c55e}.dot.injured{background:#ef4444}
.dot.suspended{background:#94a3b8}.dot.left{background:#ec4899}.dot.away{background:#a855f7}
.tteams{display:grid;grid-template-columns:1.6fr 1fr 1fr;gap:12px}
.tcard{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:12px 14px;min-width:0}
.tch{display:flex;justify-content:space-between;align-items:baseline}.tch b{font-size:14px}.tch span{font-size:11px;color:var(--muted)}
.tnow{font-family:var(--display);font-stretch:75%;font-size:22px;font-weight:800;color:var(--text);margin:4px 0 10px}
.tcols{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px}.tl{font-size:10.5px;font-weight:800;color:var(--muted);margin-bottom:4px}
.tnext{list-style:none;margin:0;padding:0;font-size:12.5px}.tnext li{display:flex;gap:8px;padding:2px 0}.tnext span{color:var(--muted);width:48px;flex-shrink:0}
.rot{display:grid;grid-template-columns:1fr 50px 18px;gap:6px;align-items:center;font-size:11.5px;padding:1px 0}.rot span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rot i{height:6px;border-radius:3px;background:#d0102e;display:block}.rot b{text-align:right}
.tgrid table{width:100%;border-collapse:separate;border-spacing:3px;table-layout:fixed}.tgrid th{font-size:10.5px;color:var(--muted);font-weight:700;text-align:center}
.ses{font-size:10.5px;text-align:center;border-radius:6px;padding:5px 2px;line-height:1.2;color:var(--text)}
.ses.tac{background:#1e3a8a}.ses.prep{background:#5b21b6}.ses.dev{background:#166534}.ses.phys{background:#9a3412}.ses.rest{background:var(--line)}
.ses.match{background:#b91c1c;font-weight:800}.ses.extra{background:#27272a;color:var(--muted)}.tnote{font-size:11px;margin-top:4px}
.trecs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.trec{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--gold);border-radius:6px;padding:12px 14px}
.trec h4{margin:0 0 8px;font-size:14.5px}.tr1{display:grid;grid-template-columns:84px 1fr;gap:8px;margin-top:6px}.tr1 p{margin:0;font-size:13px;color:var(--text2);line-height:1.5}
.ftable.indiv td{vertical-align:top;text-align:left;white-space:normal}.ftable.indiv td.whyc{font-size:12px;color:var(--text2);max-width:380px}
.pw{font-size:12px}.fz{display:inline-block;background:rgba(245,197,66,.13);border:1px solid rgba(245,197,66,.45);border-radius:6px;padding:1px 8px;font-size:12.5px}
.nx{font-size:11px;margin-top:2px}.steps{margin:0;padding-left:20px;line-height:1.7}.ftable.cheat td{text-align:left;white-space:normal;font-size:12.5px}
.pitchcap{font-size:12.5px;font-weight:700;color:var(--text);margin:0 0 6px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pitchcap>span{font-weight:400;color:var(--muted);font-size:11.5px;display:flex;align-items:center;gap:2px;flex-wrap:wrap}.pitchcap .fam{margin:0 2px 0 8px}
.pchip.cmp{width:112px;padding:5px 6px}.pchip.cmp b{font-size:12px}.pchip.cmp.same{opacity:.62}.pchip.cmp:not(.same){border-color:var(--gold)}
.dl{font-size:10px;font-weight:800;border-radius:4px;padding:0 4px;margin-left:4px}.dl.up{background:rgba(34,197,94,.2);color:#4ade80}
.dl.down{background:rgba(239,68,68,.2);color:#fca5a5}.dl.eq{color:var(--muted)}.bsn{font-size:10px;color:#fbbf24;margin-top:1px}
.sbcols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 16px}
.sbsec{font-size:12px;font-weight:800;color:var(--text2);margin:14px 0 2px}
.sbsec span{font-weight:400;text-transform:none;letter-spacing:0;color:var(--muted);margin-left:8px}
.sbp .sl{display:flex;flex-wrap:wrap;gap:3px;margin-top:3px}.sbp .sl i{font-style:normal;font-size:10.5px;border-radius:4px;padding:0 4px;background:var(--panel2);color:var(--text2)}
.sbp .sl i.N{background:var(--line);color:#fff}.sbp .sl i.X{background:none;color:var(--muted)}
.dot.signed{background:var(--gold)}.dot.target{background:#475569}.sbp.target{opacity:.8}.sbwarn .sg{color:var(--gold)}
.rmx{background:none;border:1px solid var(--line);color:var(--muted);border-radius:6px;cursor:pointer;font:inherit;padding:0 6px}
.sbadd{display:flex;gap:8px;align-items:center;margin:4px 0 6px}
.pick{margin:6px 0 10px;max-width:880px}
.pk-why{margin:0 0 8px;font-size:12.5px;color:var(--text2);line-height:1.5}
.pk-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.pk-in{flex:1 1 320px;min-width:0}
.pk-in input{width:100%;box-sizing:border-box;background:var(--bg);border:1px solid var(--line);color:var(--text);border-radius:6px;padding:8px 11px;font:inherit;font-size:13.5px}
.pk-in input::placeholder{color:var(--muted)}
.pk-bar select{background:var(--bg);color:var(--text);border:1px solid var(--line);border-radius:6px;font:inherit;font-size:13px;padding:7px 8px}
.pk-msg{font-size:12px;color:var(--muted);min-height:18px;margin:6px 2px 2px}
.pk-list{list-style:none;margin:0;padding:4px;max-height:320px;overflow-y:auto;background:var(--bg);border:1px solid var(--line);border-radius:8px}
.pk-list li{display:flex;align-items:center;gap:10px;padding:7px 10px;border-radius:6px;cursor:pointer}
.pk-list li:hover,.pk-list li.act{background:var(--panel2)}
.pk-list li.act{box-shadow:inset 0 0 0 1px #46604f}
.pk-list li[aria-disabled="true"]{cursor:default;opacity:.6}
.pk-tick{flex:none;width:16px;height:16px;border-radius:4px;border:1.5px solid #46604f;display:grid;place-items:center}
.pk-list li[aria-selected="true"] .pk-tick{background:var(--gold);border-color:var(--gold)}
.pk-list li[aria-selected="true"] .pk-tick::after{content:"";width:8px;height:4px;border:2px solid #10170F;border-top:0;border-right:0;transform:rotate(-45deg) translate(1px,-1px)}
.pk-n{min-width:0;flex:1}.pk-n b{display:block;font-size:13.5px}.pk-n span{display:block;font-size:12px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pk-list em{flex:none;font-style:normal;font-size:11.5px;color:var(--muted)}
.pk-tray{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:10px;padding:10px 12px;background:var(--panel2);border:1px solid var(--line);border-radius:8px}
.pk-tl{font-family:var(--display);font-stretch:75%;font-weight:800;font-size:14px;color:var(--text2);margin-right:4px}
.pk-chip{display:inline-flex;align-items:center;gap:4px;font-size:12.5px;background:var(--bg);border:1px solid var(--line);border-radius:999px;padding:2px 4px 2px 10px}
.pk-chip button{all:unset;cursor:pointer;width:18px;height:18px;border-radius:50%;display:grid;place-items:center;color:var(--muted);font-size:14px}
.pk-chip button:hover{color:var(--text);background:var(--panel2)}.pk-chip button:focus-visible{outline:2px solid var(--gold)}
.pk-tray #pkAdd{margin-left:auto}.sbadd input{flex:1;max-width:520px;background:var(--bg);border:1px solid var(--line);color:var(--text);border-radius:4px;padding:6px 10px;font:inherit}
.sbadd .acc{font-size:12px}.fair{font-size:11.5px;color:var(--muted);margin-top:10px}
.prow2.main{background:rgba(34,197,94,.10)}.prow2.many{background:rgba(59,130,246,.14)}
.gp{font-size:9.5px;font-weight:700;color:#93c5fd;border:1px solid #2b4a72;border-radius:4px;padding:0 4px;margin-left:6px;vertical-align:1px}
.gp.lots{background:#1d3a66;color:#dbeafe}
.poslegend{font-size:12px;color:var(--text2);display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin:-4px 0 12px}
.sw{display:inline-block;width:14px;height:14px;border-radius:4px}.sw.main{background:rgba(34,197,94,.4)}.sw.many{background:rgba(59,130,246,.45);margin-left:10px}
.poslegend .gp{margin-left:10px}.also{font-size:10.5px;color:var(--muted);margin-top:1px}
.subnav{display:flex;flex-wrap:wrap;gap:6px;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px 12px;margin-top:22px}
.stylechips{margin-left:auto;display:flex;flex-wrap:wrap;gap:4px;align-items:center;font-size:11.5px}.stylechips b{color:var(--muted);font-weight:600;margin-right:4px}
.rec{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:0 0 12px;font-size:13px;color:var(--text2)}.rec .big{font-family:var(--display);font-stretch:62%;font-size:56px;line-height:.9;font-weight:900;font-style:italic;color:var(--text)}
.frm{width:22px;height:22px;border-radius:6px;display:inline-grid;place-items:center;font-size:11px;font-weight:800;color:#fff}
.frm.W{background:#15803d}.frm.D{background:var(--muted)}.frm.L{background:#b91c1c}
.wgrid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.wh{font-size:12.5px;margin:0 0 8px}.wh.ok{color:#4ade80}.wh.no{color:#fca5a5}
.wi{background:var(--panel);border:1px solid var(--line);border-left:3px solid;border-radius:5px;padding:8px 12px;margin-bottom:8px}
.wi.good{border-left-color:#22c55e}.wi.bad{border-left-color:#ef4444}
.wl{display:flex;justify-content:space-between;gap:10px}.wl b{font-size:13.5px}.wl span{font-weight:700;white-space:nowrap}
.wr{font-size:11.5px;color:var(--muted)}.wt{font-size:12.5px;color:var(--text2);margin-top:2px}
.insights{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px 16px;margin-top:6px;font-size:13px}
.insights ul{margin:6px 0 0;padding-left:18px;color:var(--text2);line-height:1.6}
.sub3{font-size:16px;margin:24px 0 10px}
.perfgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.perfcard{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:10px 12px}
.pctop{display:flex;justify-content:space-between;gap:8px;align-items:baseline;margin-bottom:4px}.pctop b{font-size:14px}.pctop span{font-size:11.5px;color:var(--muted);text-align:right}
.pcrow{display:flex;flex-wrap:wrap;gap:4px;align-items:center;margin-top:4px}.pcl{font-size:10px;font-weight:800;width:84px}
.pcl.ok{color:#4ade80}.pcl.no{color:#fca5a5}
.pc{font-size:11.5px;border-radius:6px;padding:2px 7px;display:inline-flex;gap:5px;align-items:center}
.pc.good{background:rgba(34,197,94,.13);border:1px solid rgba(34,197,94,.35)}.pc.bad{background:rgba(239,68,68,.12);border:1px solid rgba(239,68,68,.35)}
.pc i{font-style:normal;font-size:10px;color:var(--muted)}
.pc em,.presskey{font-style:normal;font-size:9px;font-weight:800;color:var(--bg);background:var(--gold);border-radius:3px;padding:0 3px}
.ftable.gegen td.back{text-align:left;white-space:normal}.okk{font-size:11.5px;color:#4ade80}.teamrow td{background:rgba(245,197,66,.07);font-weight:700}
.badge.arr{background:transparent!important;border-style:dashed!important;border-width:1.5px}
.nav .count.amber{background:rgba(245,158,11,.18);border-color:rgba(245,158,11,.5);color:#fcd34d}
.deals.two{grid-template-columns:repeat(2,1fr)}
.dgroup{font-size:13px;color:var(--text2);margin:18px 0 10px}
.dgroup span{text-transform:none;letter-spacing:0;color:var(--muted);font-weight:500;margin-left:8px}
.dcol.arr{border-style:dashed}.dcol.loan-in.arr h3{background:rgba(59,130,246,.08)}.dcol.loan-out.arr h3{background:rgba(168,85,247,.08)}
.misgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.mis{background:var(--panel);border:1px solid var(--line);border-left:5px solid var(--vamber);border-radius:6px;padding:12px 14px}
.mis .mtop{display:flex;justify-content:space-between;font-size:15px}.mis .mtop span{color:var(--muted)}
.mis .mwhere{color:var(--text2);font-size:12.5px;margin-top:4px}.mis .mwhy{color:#fcd34d;font-size:12.5px;margin:6px 0}
.wk{display:inline-block;font-size:11.5px;background:rgba(239,68,68,.16);border:1px solid rgba(239,68,68,.45);color:#fca5a5;border-radius:6px;padding:1px 7px;margin:2px 4px 0 0}
.klegend{display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
.kc{display:inline-block;font-size:11.5px;font-weight:600;border-radius:6px;padding:2px 8px;margin:2px 4px 2px 0;border:1px solid}
.kc.ip{color:#93c5fd;border-color:rgba(59,130,246,.5);background:rgba(59,130,246,.12)}
.kc.oop{color:#fca5a5;border-color:rgba(239,68,68,.45);background:rgba(239,68,68,.10)}
.kc.sty{color:#fde68a;border-color:rgba(245,158,11,.5);background:rgba(245,158,11,.12)}
.ftable th.ak.sty{color:#fcd34d}.wk.st{background:rgba(245,158,11,.14);border-color:rgba(245,158,11,.45);color:#fcd34d}
.look.big{border:0;padding:0}.stylebox h2{margin-bottom:8px}
.kc.both{color:#e9d5ff;border-color:rgba(168,85,247,.55);background:rgba(168,85,247,.14)}
.scale{margin-left:auto;display:flex;gap:3px;font-size:11px}.scale i{font-style:normal;padding:2px 7px;border-radius:4px}
.fgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.fcard{background:var(--panel);border:1px solid var(--line);border-radius:6px;overflow:hidden}
.fhead{display:flex;align-items:baseline;gap:10px;padding:10px 12px 4px}.fhead .slot{font-size:18px}
.fhead .roles{font-size:12.5px;color:var(--text2)}.fhead em{color:var(--muted);font-style:normal;font-size:11.5px}
.look{padding:2px 12px 8px;border-bottom:1px solid var(--line)}.look .lk{font-size:11px;font-weight:700;color:var(--muted);margin-right:8px}
.ftable{overflow-x:auto}.ftable table{width:100%;border-collapse:collapse;font-size:12.5px}
.ftable th{font-size:10.5px;color:var(--muted);font-weight:700;padding:6px 4px;text-align:center;border-bottom:1px solid var(--line)}
.ftable th:first-child{text-align:left;padding-left:12px}.ftable th.ak.ip{color:#93c5fd}.ftable th.ak.oop{color:#fca5a5}.ftable th.ak.both{color:#d8b4fe}
.ftable td{padding:5px 4px;border-bottom:1px solid var(--line2);text-align:center}
.ftable td.nm{text-align:left;padding-left:12px;font-weight:600;white-space:nowrap;border-left:3px solid transparent}
.ftable tr.loan-in td.nm{border-left-color:var(--loanin)}.ftable tr.deal-in td.nm{border-left-color:var(--dealin)}
.ftable tr.inj-long td.nm{border-left-color:var(--injl)}.ftable tr.inj-short td.nm{border-left-color:var(--injs)}.ftable tr.sus td.nm{border-left-color:#94a3b8}
.xi{font-size:9.5px;font-weight:800;color:var(--bg);background:var(--gold);border-radius:4px;padding:0 4px;margin-left:6px;vertical-align:1px}
.av{font-variant-numeric:tabular-nums;font-weight:600;min-width:26px}
.a1,.scale .a1{background:rgba(239,68,68,.35);color:#fee2e2}.a2,.scale .a2{background:rgba(245,158,11,.25);color:#fde68a}
.a3,.scale .a3{background:rgba(148,163,184,.12);color:var(--text2)}.a4,.scale .a4{background:rgba(34,197,94,.16);color:#bbf7d0}
.a5,.scale .a5{background:rgba(34,197,94,.38);color:#dcfce7}
.fitv{display:flex;align-items:center;gap:6px;justify-content:flex-start;min-width:84px}.fitv b{font-size:12.5px;width:30px;text-align:right}
.fitv i{flex:1;height:5px;border-radius:3px;background:var(--panel2);overflow:hidden}.fitv u{display:block;height:100%;text-decoration:none}
.fitv.good u{background:#22c55e}.fitv.ok u{background:#94a3b8}.fitv.bad u{background:#ef4444}.fitv.bad b{color:#fca5a5}
.vtitle,.squad th,.ftable th,.tch span,.tl,.wh,.pcl,.dgroup,.sbsec,.look .lk,.fl,.squad tr.grp td,.pchip .ps,.tile .lbl{
 font-family:var(--display);font-stretch:75%}
.vtitle{font-size:16px}.wh{font-size:20px;font-weight:800}.dgroup,.sbsec{font-size:19px;font-weight:800}
.squad th{font-size:13px;font-weight:700}.squad tr.grp td{font-size:14px;color:var(--text2)}
.pchip .ps{font-size:12px;font-style:italic}.pcl{font-size:13px}.tl,.look .lk,.fl{font-size:13px}
.slot+.vtitle,.vhead .vtitle{margin-left:2px}
/* responsive floor */
@media (max-width:1100px){.pgrid{grid-template-columns:repeat(3,1fr)}.vgrid,.misgrid{grid-template-columns:repeat(2,1fr)}.deals{grid-template-columns:repeat(2,1fr)}}
@media (max-width:760px){.wrap{padding:16px 14px 48px}header.top{flex-direction:column;align-items:flex-start;gap:14px}
 .fin{grid-template-columns:repeat(2,1fr)}.pgrid,.vgrid,.misgrid,.deals,.pitches,.wgrid,.fgrid,.trecs,.perfgrid,.sbgrid,.tteams{grid-template-columns:1fr}
 .legend{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;padding-bottom:10px}.legend>*{flex-shrink:0}
 .squad{display:block;overflow-x:auto}.sbtop{flex-direction:column}.pchip{width:auto;flex:1}}
"""




# =============================================================================================
# The site: a public home page (the same for everyone, demo data only), the launch loader and the app shell.
# Scripts and the crest live in assets/ so everything works offline. "../assets/" resolves to /assets/ on the
# live server and to the assets folder next to Reports/ when a report file is opened directly.

def asset(name: str) -> str:
    return f"../assets/{name}"


FONT_LINKS = """<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:ital,wdth,wght@0,62..125,100..900;1,62..125,100..900&display=swap" rel="stylesheet">"""

# Demo club for the home page: Liverpool's XI from 22 November 2026 (v Manchester United). Ratings are made up.
DEMO_XI = [("GK", "Alisson", 4.5), ("LB", "Kerkez", 4.0), ("CB", "van Dijk", 4.5), ("CB", "Jacquet", 3.5),
           ("RB", "Araújo", 4.0), ("DM", "Mac Allister", 4.5), ("DM", "Szoboszlai", 4.5), ("LW", "Ngumoha", 3.0),
           ("AM", "Wirtz", 5.0), ("RW", "Barcola", 4.0), ("ST", "Isak", 4.5)]
# where each FORMATION slot stands on a portrait pitch (x across, y down; your goal at the bottom)
PITCH_XY = [(50, 89), (14, 69), (37, 75), (63, 75), (86, 69), (36, 54), (64, 54), (16, 30), (50, 37), (84, 30), (50, 13)]


# ---------------------------------------------------------------------------------------------
# Brand (the app's own identity) and club identity (whoever you manage: colours + crest or initials badge)

APP_LOGO_SVG = ('<svg class="logo" viewBox="0 0 32 32" aria-hidden="true"><rect x="1" y="1" width="30" height="30" rx="8" fill="#1C7F46"/>'
                '<rect x="8.5" y="5" width="15" height="22" rx="1.5" fill="none" stroke="#F2F4EE" stroke-width="2"/>'
                '<path d="M8.5 16h15" stroke="#F2F4EE" stroke-width="2"/><circle cx="16" cy="9.6" r="1.9" fill="#F2F4EE"/>'
                '<circle cx="11.9" cy="12.9" r="1.9" fill="#F2F4EE"/><circle cx="20.1" cy="12.9" r="1.9" fill="#F2F4EE"/>'
                '<circle cx="12.4" cy="20.6" r="1.9" fill="#F2F4EE"/>'
                '<circle cx="19.6" cy="20.6" r="2.5" fill="none" stroke="#F2F4EE" stroke-width="1.7"/></svg>')
APP_NAME = "Squad Report"

# FM saves don't store club colours or crests, so: a table of well-known clubs, and a stable colour from the name otherwise
CLUB_COLOURS = {
    "liverpool": "#C8102E", "arsenal": "#EF0107", "aston villa": "#7B1A44", "bournemouth": "#DA291C", "brentford": "#E30613",
    "brighton": "#0057B8", "burnley": "#6C1D45", "chelsea": "#034694", "crystal palace": "#1B458F", "everton": "#1A4BB8",
    "fulham": "#CC0000", "ipswich": "#0044A9", "leeds": "#1D428A", "leicester": "#0B3FA8", "manchester city": "#6CABDD",
    "manchester united": "#DA291C", "newcastle": "#D9D9D9", "nottingham forest": "#DD0000", "southampton": "#D71920",
    "sunderland": "#EB172B", "tottenham": "#2B4FA3", "west ham": "#7A263A", "wolverhampton": "#FDB913", "wolves": "#FDB913",
    "real madrid": "#FEBE10", "barcelona": "#A50044", "atletico": "#CB3524", "bayern": "#DC052D", "dortmund": "#FDE100",
    "paris saint germain": "#1D4FA0", "juventus": "#D9D9D9", "inter": "#0068A8", "milan": "#FB090B", "napoli": "#12A0D7",
    "roma": "#8E1F2F", "ajax": "#D2122E", "benfica": "#E83030", "porto": "#1F5FB0", "celtic": "#018749", "rangers": "#1B458F",
}
CLUB_CRESTS = {"liverpool": ("liverbird-red.svg", "liverbird-white.svg")}   # (on dark, on club colour / pitch)
CLUB_FILE = APP_DIR / "data" / "club.json"   # last club read, so the loader can wear its colours before a save is read


def _norm_club(name: str) -> str:
    n = re.sub(r"[^a-z ]", " ", (name or "").lower().replace("&", " "))
    return " ".join(w for w in n.split() if w not in ("fc", "afc", "cf", "sc", "the", "and", "hove", "albion", "hotspur",
                                                         "wanderers", "town", "city", "united", "f", "c")) or n.strip()


def _lum(h: str) -> float:
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def _mix(h: str, other: str, t: float) -> str:
    a = [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


def _badge(initials: str, fill: str, ink: str, rim: str = "rgba(255,255,255,.35)") -> str:
    size = 15 if len(initials) <= 2 else 11.5
    return (f'<svg class="badge-crest" viewBox="0 0 40 48" aria-hidden="true"><path d="M20 1.5 38 7.5V24c0 11.5-7.6 18.6-18 22.5C9.6 42.6 2 35.5 2 24V7.5Z" '
            f'fill="{fill}" stroke="{rim}" stroke-width="2"/><text x="20" y="29.5" text-anchor="middle" font-family="Archivo,Arial Narrow,sans-serif" '
            f'font-stretch="62%" font-weight="900" font-style="italic" font-size="{size}" fill="{ink}">{E(initials)}</text></svg>')


def kit_on_light(kit: str) -> str:
    """The club colour darkened just enough to read on light paper and to carry white text."""
    for step in range(17):
        c = _mix(kit, "#000000", step * 0.05)
        if _lum(c) <= 0.16:
            return c
    return "#151512"


def club_identity(name: str) -> dict:
    """Colours and crest markup for a club: kit colour, readable ink on it, and crest HTML for dark, kit and pitch backgrounds."""
    key = _norm_club(name)
    full = re.sub(r"[^a-z ]", " ", (name or "").lower())
    kit = CLUB_COLOURS.get(key) or next((v for k, v in CLUB_COLOURS.items() if k in full), None)
    if not kit:
        hue = int(hashlib.md5((name or "club").encode()).hexdigest()[:6], 16) % 360
        r, g, b = colorsys.hls_to_rgb(hue / 360, 0.46, 0.62)
        kit = f"#{round(r * 255):02X}{round(g * 255):02X}{round(b * 255):02X}"
    if _lum(kit) < 0.04:
        kit = _mix(kit, "#FFFFFF", 0.3)        # keep very dark kits visible on the dark app background
    ink = "#111111" if _lum(kit) > 0.42 else "#FFFFFF"
    words = [w for w in re.split(r"[\s\-]+", name or "") if w and w.lower() not in ("fc", "afc", "cf", "sc", "the", "de", "&", "and", "of")]
    initials = "".join(w[0] for w in words[:3]).upper() or "FC"
    crest = next((v for k, v in CLUB_CRESTS.items() if k == key or k in full), None)
    if crest:
        dark, onkit = f'<img src="{asset(crest[0])}" alt="">', f'<img src="{asset(crest[1])}" alt="">'
        pitch = onkit
    else:
        dark = _badge(initials, kit, ink)
        onkit = _badge(initials, "rgba(255,255,255,.14)", ink, rim=ink)
        pitch = _badge(initials, "rgba(255,255,255,.16)", "#FFFFFF", rim="rgba(255,255,255,.7)")
    return dict(name=name, kit=kit, ink=ink, dark=dark, onkit=onkit, pitch=pitch, initials=initials)


def last_club() -> dict | None:
    try:
        name = json.loads(CLUB_FILE.read_text()).get("name")
        return club_identity(name) if name else None
    except (OSError, ValueError):
        return None


def pitch3d(cards, label: str, crest: str | None = None) -> str:
    """A fake-3D pitch: the pitch is tilted with CSS and every player card counter-rotates, so the cards stand
    up and face you whichever way the pitch is turned. cards = [(slot, name, stars, state class)] in FORMATION order."""
    players = "".join(
        f'<div class="p3-pl" style="--x:{x}%;--y:{y}%"><i class="p3-sh"></i><div class="p3-card {cls}">'
        f'<b>{E(slot)}</b><span class="nm">{E(name)}</span>{stars(r, True) if r else ""}</div></div>'
        for (slot, name, r, cls), (x, y) in zip(cards, PITCH_XY))
    crest_img = f'<span class="p3-crest">{crest}</span>' if crest else ""
    return f"""<div class="p3" data-p3 tabindex="0" role="group" aria-roledescription="3D pitch" aria-label="{E(label)}">
  <div class="p3-cam"><div class="p3-pitch"><i class="p3-l half"></i><i class="p3-l circ"></i><i class="p3-l box t"></i>
  <i class="p3-l box b"></i><i class="p3-l six t"></i><i class="p3-l six b"></i>{crest_img}{players}</div></div></div>"""


P3_CSS = r"""
.stars{position:relative;display:inline-block;white-space:nowrap;line-height:1;color:#34443b;letter-spacing:0}
.stars .on{position:absolute;left:0;top:0;overflow:hidden;color:#e9b949;text-align:left}
.p3{--rx:54deg;--rz:-14deg;--sc:1;--pw:380px;position:relative;perspective:1500px;perspective-origin:50% 35%;display:grid;place-items:center;
 touch-action:pan-y;user-select:none;-webkit-user-select:none;border-radius:12px;cursor:grab}
.p3:focus-visible{outline:2px solid #e9b949;outline-offset:6px}
.p3.grabbing{cursor:grabbing}
.p3-cam{transform-style:preserve-3d;transform:scale(var(--sc)) rotateX(var(--rx)) rotateZ(var(--rz))}
.p3-pitch{position:relative;width:var(--pw);aspect-ratio:68/105;transform-style:preserve-3d;
 background:repeating-linear-gradient(180deg,#22603a 0 10%,#1c5432 10% 20%);box-shadow:0 0 0 14px #184a2b,0 60px 90px -20px rgba(0,0,0,.7)}
.p3-pitch::before{content:"";position:absolute;inset:0;border:2px solid rgba(255,255,255,.5)}
.p3-l{position:absolute;border:2px solid rgba(255,255,255,.5);pointer-events:none}
.p3-l.half{left:0;right:0;top:50%;height:0;border-width:2px 0 0}
.p3-l.circ{left:50%;top:50%;width:27%;aspect-ratio:1;border-radius:50%;transform:translate(-50%,-50%)}
.p3-l.box{left:20%;right:20%;height:16%}.p3-l.six{left:36%;right:36%;height:5.5%}
.p3-l.t{top:0;border-top:0}.p3-l.b{bottom:0;border-bottom:0}
.p3-crest{position:absolute;left:50%;top:50%;width:8%;transform:translate(-50%,-50%);opacity:.5;line-height:0}
.p3-crest img,.p3-crest svg{width:100%;height:auto;display:block}
.p3-pl{position:absolute;left:var(--x);top:var(--y);width:0;height:0;transform-style:preserve-3d}
.p3-sh{position:absolute;width:64px;height:24px;left:-32px;top:-12px;border-radius:50%;background:radial-gradient(closest-side,rgba(0,0,0,.55),transparent)}
.p3-card{position:absolute;left:-38px;bottom:0;width:76px;transform-origin:50% 100%;
 transform:rotateZ(calc(var(--rz) * -1)) rotateX(calc(var(--rx) * -1));
 background:rgba(14,21,18,.95);border:1px solid #33463c;border-radius:6px;padding:0 6px 6px;text-align:center;
 box-shadow:0 14px 22px -10px rgba(0,0,0,.8);backface-visibility:hidden}
.p3-card b{display:block;margin:0 -6px 4px;background:var(--kit,#C8102E);color:var(--kit-ink,#fff);border-radius:5px 5px 0 0;
 font-family:"Archivo","Arial Narrow",sans-serif;font-stretch:62%;font-style:italic;font-weight:900;font-size:13px;line-height:19px}
.p3-card .nm{display:block;font-family:"Archivo","Arial Narrow",sans-serif;font-stretch:75%;font-weight:700;font-size:13px;line-height:1.15;
 color:#eef1e8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.p3-card .stars{font-size:10px;margin-top:2px;display:inline-block}
.p3-card.empty{border-style:dashed;border-color:#ff5d5d}.p3-card.empty b{background:#5a2a33}
.p3-card.inj-long{border-color:#ef4444}.p3-card.inj-short{border-color:#facc15}.p3-card.deal-in{border-color:#22c55e}.p3-card.loan-in{border-color:#3b82f6}
@media (max-width:700px){.p3{--pw:min(70vw,320px)}.p3-card{width:70px;left:-35px}.p3-card .nm{font-size:12px}}
"""

P3_JS = r"""
function initP3(el){
 if(!window.gsap||el.dataset.p3on)return; el.dataset.p3on=1;
 const rm=matchMedia('(prefers-reduced-motion: reduce)').matches;
 const read=n=>parseFloat(el.style.getPropertyValue(n)||getComputedStyle(el).getPropertyValue(n))||0;
 const base=read('--rz');
 let sway=rm?null:gsap.to(el,{'--rz':(base+9)+'deg',duration:5.5,ease:'sine.inOut',yoyo:true,repeat:-1});
 const stop=()=>{if(sway){sway.kill();sway=null;}};
 const set=(z,x,d)=>gsap.to(el,{'--rz':Math.max(-55,Math.min(55,z))+'deg','--rx':Math.max(24,Math.min(70,x))+'deg',
   duration:rm?0:(d==null?.55:d),ease:'power3.out',overwrite:'auto'});
 let drag=null;
 el.addEventListener('pointerdown',e=>{if(e.button)return;stop();drag={x:e.clientX,y:e.clientY,z:read('--rz'),r:read('--rx'),t:e.pointerType};
   el.setPointerCapture(e.pointerId);el.classList.add('grabbing');});
 el.addEventListener('pointermove',e=>{if(!drag)return;const dy=drag.t==='touch'?0:(e.clientY-drag.y);set(drag.z+(e.clientX-drag.x)*.3,drag.r-dy*.2,.4);});
 const end=()=>{drag=null;el.classList.remove('grabbing');};
 el.addEventListener('pointerup',end);el.addEventListener('pointercancel',end);
 el.addEventListener('keydown',e=>{const k={ArrowLeft:[-10,0],ArrowRight:[10,0],ArrowUp:[0,-6],ArrowDown:[0,6]}[e.key];
   if(!k)return;e.preventDefault();stop();set(read('--rz')+k[0],read('--rx')+k[1]);});
}
"""

# ---------------------------------------------------------------------------------------------
# Public home page


DEMO_TICKER = [("deal-in", "Signing", "New left back joins on 1 Jan"), ("inj-short", "Injured", "Winger back in 2 wks"),
               ("expiring", "Contract", "Keeper's deal ends Jun 2027"), ("loan-out", "Loan agreed", "U21 midfielder heads out on 1 Jan"),
               ("sus", "Suspended", "Holding midfielder misses 1 match")]
DEMO_XI2 = [("GK", "Mamardashvili", 3.5), ("LB", "Robertson", 3.0), ("CB", "Gomez", 3.0), ("CB", "Leoni", 2.5),
            ("RB", "Frimpong", 3.5), ("DM", "Gravenberch", 3.5), ("DM", "Endo", 3.0), ("LW", "Gakpo", 3.5),
            ("AM", "Jones", 3.0), ("RW", "Chiesa", 3.0), ("ST", "Ekitiké", 3.5)]
MINI_W, MINI_H = 1440, 945   # the previews are real app pages at this size, scaled down to fit the window on the home page


def _demo_p(name, slot, r):
    return {"name": name, "rows": {}, "slots": {slot: (r, "N")}, "trend": 0, "where": "squad", "youth": False}


def _demo_doc(route: str, body: str) -> str:
    """A static copy of one app page with demo data (no scripts), for an <iframe srcdoc> on the home page."""
    lfc = club_identity("Liverpool")
    head = header_html(lfc, {"home": (3, "warn"), "tactics": (2, "amber"), "transfers": (4, "")}, {"squad": (27, ""), "fit": (2, "amber")},
                       ticker_html([(c, t, x, "home") for c, t, x in DEMO_TICKER]), route)
    return (f'<!DOCTYPE html><html lang="en" style="--kit:{lfc["kit"]};--kit-ink:{lfc["ink"]};--kit-l:{kit_on_light(lfc["kit"])}"><head><meta charset="utf-8">{FONT_LINKS}'
            f'<style>{CSS}{P3_CSS}{APP_CSS}{MINI_CSS}</style></head><body class="app mini">{head}<main class="wrap">{body}</main></body></html>')


def _demo_rows(chip):
    """Group the 11 demo players into pitch rows the way pitch() does, rendering each with chip(i, slot, name, stars)."""
    rows: dict[int, list] = {}
    for i, (slot, name, r) in enumerate(DEMO_XI):
        rows.setdefault(PITCH_ROW.get(slot, 2), []).append((slot, name, r, i))
    out = []
    for k in sorted(rows):
        cells = sorted(rows[k], key=lambda c: (LEFT_TO_RIGHT.index(c[0]) if c[0] in LEFT_TO_RIGHT else 5, c[3]))
        out.append('<div class="prow">' + "".join(chip(i, slot, name, r) for slot, name, r, i in cells) + "</div>")
    return '<div class="lines"><i class="half"></i><i class="circle"></i><i class="box top"></i><i class="box bot"></i></div>' + "".join(out)


def _wi(label, value, rank, of, avg, note, good):
    return (f'<div class="wi {"good" if good else "bad"}"><div class="wl"><b>{label}</b><span>{value}</span></div>{rank_strip(rank, of)}'
            f'<div class="wr">{ordinal(rank)} of {of} · league avg {avg}</div><div class="wt">{note}</div></div>')


def demo_pages() -> list[str]:
    crest = club_identity("Liverpool")["pitch"]
    best = [(s, _demo_p(n, s, r)) for s, n, r in DEMO_XI]
    second = [(s, _demo_p(n, s, r)) for s, n, r in DEMO_XI2]
    xis_page = f"""<section><h2>Best XI &amp; second XI <span class="h2sub">4-2-3-1 · rated in both phases · every player used once</span></h2>
  <div class="xtools blur"><button class="seg" aria-pressed="true">3D</button><button class="seg" aria-pressed="false">Flat</button>
   <span class="xhint">3D: drag a pitch to turn it. Flat shows every badge.</span></div>
  <div class="pitches3d"><div class="focus">{pitch3d_card('Best XI', best, 'fully fit squad', crest)}</div>
   <div class="blur">{pitch3d_card('Second XI', second, "from who's left", crest)}</div></div></section>"""

    hero_cards = [(s, n, r, "") for s, n, r in DEMO_XI]
    form = "".join(f'<span class="frm {x}">{x}</span>' for x in "WWDWL")
    tiles = (f'<div class="tile"><div class="lbl">Transfer budget left</div><div class="val">£62m</div><div class="sub">as of Nov 2026 month-end</div></div>'
             f'<div class="tile"><div class="lbl">Wage bill / budget (p/w)</div><div class="val">£4.86m <span class="of">/ £5.40m</span></div>'
             f'<div class="bar"><i style="width:90%"></i></div><div class="sub">£540k/wk room</div></div>'
             f'<div class="tile"><div class="lbl">XI level</div><div class="val">{stars(4.4)} <span class="of">4.4</span></div><div class="sub">average of your best XI</div></div>'
             f'<div class="tile"><div class="lbl">Unavailable now</div><div class="val">2 <span class="of">players</span></div><div class="sub">1 injured · 1 suspended</div></div>')

    def who(label, name, r, fam="N"):
        return f'<div class="who"><span class="wl">{label}</span>{name} {stars(r, True)}<span class="fam {fam}">{fam}</span></div>'
    verdicts = (f'<div class="vcard red"><div class="vhead"><span class="rank">1</span><span class="slot">RB</span><span class="vtitle">Needs a better starter</span></div>'
                f'<p>Only one natural right back above 3★, and the cover drops a full star.</p>{who("Starter", "Araújo", 4.0)}{who("Backup", "Frimpong", 3.0)}</div>'
                f'<div class="vcard amber"><div class="vhead"><span class="rank">2</span><span class="slot">LB</span><span class="vtitle">Needs more depth</span></div>'
                f'<p>Backup is 1.5★ under your XI level.</p>{who("Starter", "Kerkez", 4.0)}{who("Backup", "Robertson", 2.5)}</div>'
                f'<div class="vcard amber"><div class="vhead"><span class="rank">3</span><span class="slot">CB</span><span class="vtitle">Ageing starter</span></div>'
                f'<p>Your best centre back is 35. The next best is a full star lower when he goes.</p>{who("Starters", "van Dijk", 4.5)}{who("Backups", "Gomez", 3.0)}</div>')
    ok = "".join(f'<div class="okchip"><span class="slot">{s}</span><b>Sorted</b><span>{t}</span></div>'
                 for s, t in (("GK", "4.5★ starter, 3.5★ cover"), ("DM", "two natural 4★+ starters"), ("ST", "starter and cover both natural")))
    home_page = f"""<div style="margin-top:-330px"><div class="blur"><section class="hband">
  <div class="hb-txt"><p class="hb-k">FM27 squad report</p><h1 class="hb-club">Liverpool</h1>
   <dl class="hb-meta"><div><dt>In-game date</dt><dd>22 Nov 2026</dd></div><div><dt>Tactic</dt><dd>4-2-3-1 Gegenpress</dd></div>
    <div><dt>Trends vs</dt><dd>15 Nov 2026</dd></div><div><dt>Save</dt><dd class="sv">Demo career</dd></div></dl>
   <div class="hb-rec"><span class="hb-pos">3rd</span><span class="hb-of">of 20<br>29 pts from 13</span><span class="hb-form">{form}</span></div>
   <a class="hb-btn">Open best XIs</a></div>
  <div class="hb-3d">{pitch3d(hero_cards, "Demo best XI", crest)}<p class="hb-hint">Your best XI. Drag to rotate.</p></div></section>
  <section><h2>Club snapshot</h2><div class="fin">{tiles}</div></section></div>
 <section><h2>Where the squad needs work <span class="h2sub">after arranged transfers &amp; loans go through · loaned-out players not counted</span></h2>
  <div class="vgrid focus">{verdicts}</div><div class="okrow blur">{ok}</div></section></div>"""

    chips = "".join(f'<button class="fchip">{x}</button>' for x in ("How it's going", "Gegenpress breakdown", "Players who don't fit", "Role by role"))
    style = "".join(f'<span class="kc sty">{x}</span>' for x in ("Work Rate", "Teamwork", "Determination", "Stamina", "Natural Fitness", "Aggression", "Anticipation", "Acceleration", "Pace"))
    good = (_wi("Shots", "16.2 per game", 2, 20, "12.1", "constant pressure on goal", True)
            + _wi("Possession won high", "9.1 per game", 1, 20, "6.4", "the press is biting", True)
            + _wi("Goals conceded", "0.85 per game", 3, 20, "1.31", "hard to score against", True))
    bad = (_wi("Clear-cut chances", "1.10 per game", 14, 20, "1.25", "lots of shots, few great ones", False)
           + _wi("Aerial duels won", "44%", 16, 20, "49%", "losing headers", False)
           + _wi("Pass completion", "82%", 13, 20, "84%", "a bit loose on the ball", False))
    fit_page_demo = f"""<div class="subnav blur"><span class="fl">Jump to</span>{chips}<div class="stylechips"><b>Gegenpress asks for</b>{style}</div></div>
 <section><h2>How the tactic is going <span class="h2sub">the league only · from the game's own match stats (12 of your matches have full reports) · ranked against all 20 teams</span></h2>
  <div class="focus" style="padding:6px 10px 2px"><div class="rec"><span class="big">3rd</span><span>of 20</span><span>P13 · W9 D2 L2 · 29 pts · 28–11 goals</span>{form}</div>
  <div class="wgrid"><div><h3 class="wh ok">What's working</h3>{good}</div><div><h3 class="wh no">What's not working</h3>{bad}</div></div></div>
  <div class="insights blur"><b>Putting it together</b><ul><li>You shoot a lot but from worse positions than most: work on chance quality.</li></ul></div></section>"""

    labels = row_labels()
    changed = {9: ("Gakpo", 3.5)}   # RW swapped in the sandbox

    def sb_chip(i, slot, name, r):
        nm, rr = changed.get(i, (name, r))
        d = rr - r
        dl = f'<span class="dl {"down" if d < 0 else "eq"}">{"−" + format(abs(d), "g") + "★" if d < 0 else "="}</span>'
        return (f'<div class="pchip sb"><span class="ps">{E(labels[i])}</span><select><option>{E(nm)} · {format(rr, "g")}★</option></select>'
                f'<div class="pr">{stars(rr, True)}<span class="fam N">N</span>{dl}</div></div>')

    def cmp_chip(i, slot, name, r):
        same = "" if i in changed else " same"
        return f'<div class="pchip cmp{same}"><span class="ps">{E(labels[i])}</span><b>{E(name)}</b><div class="pr">{stars(r, True)}<span class="fam N">N</span></div></div>'
    sandbox_demo = f"""<section><h2>Sandbox <span class="h2sub">mark players injured, gone or away, sign your scouting targets, then build an XI · ratings change with the position you put someone in</span></h2>
  <div class="sbtop"><div class="sbscore focus"><div class="lbl">Your XI</div><div class="val">{stars(4.3)} <span class="of">4.3</span></div>
    <div class="sub">−0.1★ vs best XI (4.4) · 1 change</div></div><div class="sbwarn focus" style="flex:0 1 auto"><span class="bad">Barcola</span> marked injured, so Gakpo comes in at RW.</div>
   <div class="sbbtns blur"><span class="sbmode">your own picks</span><button class="fchip on">Auto-pick best XI</button><button class="fchip">Reset all changes</button></div></div>
  <div class="sbgrid"><div class="focus" style="padding:6px"><div class="pitchcap">Your XI <span>pick anyone · <span class="fam N">N</span>natural <span class="fam A">A</span>accomplished</span></div>
    <div class="pitch sbpitch">{_demo_rows(sb_chip)}</div></div>
   <div class="blur"><div class="pitchcap">Best XI <span>everyone fit · gold border = different from yours</span></div><div class="pitch sbpitch cmp">{_demo_rows(cmp_chip)}</div></div></div>
  <div class="sblist blur"><div class="sbsec">Your squad <span>stars by position</span></div></div></section>"""
    return [_demo_doc("team/xis", xis_page), _demo_doc("home", home_page), _demo_doc("tactics/fit", fit_page_demo), _demo_doc("sandbox", sandbox_demo)]


MINI_CSS = r"""
html,body{height:945px;overflow:hidden;scrollbar-width:none}
body.mini{pointer-events:none;padding-bottom:0}
.mini .skip,.mini .keypop{display:none}
.mini .ah{position:relative;z-index:5}
.mini main.wrap{padding-top:26px}
.mini .blur{filter:blur(3px) saturate(.55);opacity:.38}
.mini .focus{position:relative;border-radius:12px;box-shadow:0 0 0 3px #4FC77F,0 0 0 16px rgba(79,199,127,.14),0 40px 90px -30px rgba(0,0,0,.9)}
.mini .tk-tr{animation-duration:80s}
"""


def landing_page() -> str:
    lfc = club_identity("Liverpool")
    hero_cards = [(s, n, r, "") for s, n, r in DEMO_XI]
    steps = [
        ("Best XIs", "Your strongest XI and a second XI from who's left, rated for your tactic in and out of possession."),
        ("Where it needs work", "Which positions need a better starter or more depth, counted after arranged transfers and loans go through."),
        ("How the tactic is going", "Your numbers against every other team in the league, straight from the game's own match stats."),
        ("Sandbox", "Mark players injured or sold, swap people in, and watch your best XI change before you do it for real."),
    ]
    step_html = "".join(f'<button class="st{" on" if i == 0 else ""}" data-i="{i}" type="button" aria-pressed="{"true" if i == 0 else "false"}">'
                        f'<b>{E(t)}</b><span>{E(x)}</span></button>' for i, (t, x) in enumerate(steps))
    screens = "".join(f'<div class="scr{" on" if i == 0 else ""}"><iframe title="Preview of the {E(t)} page" tabindex="-1" aria-hidden="true" '
                      f'srcdoc="{html.escape(doc, quote=True)}"></iframe></div>' for i, ((t, _), doc) in enumerate(zip(steps, demo_pages())))
    does = ["Reads your newest FM27 save by itself, read-only", "Rates every player from visible attributes, for your tactic and in general",
            "Picks a best XI and a second XI", "Flags positions that need a better starter or more depth",
            "Checks your tactic against the league from match stats", "Shows training, deals, loans and season stats",
            "Rebuilds itself every time you save"]
    wont = ["Change your save. It only ever reads it", "Show current ability, potential ability or hidden attributes",
            "Tell you who to sign. It points at positions, never players", "Send your save anywhere. It stays on your Mac",
            "Ask for an account or a subscription"]
    return f"""<!DOCTYPE html><html lang="en" style="--kit-l:#1C7F46"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<script>{LOOK_HEAD_JS}</script>
<title>FM27 {APP_NAME}</title><meta name="description" content="Turns your Football Manager 27 save into a squad report: best XIs, positions that need work and how your tactic is going.">
<link rel="icon" href="{asset('app-logo.svg')}">{FONT_LINKS}<style>{P3_CSS}{LANDING_CSS}{LOOK_CSS}</style>
<style id="looks-css">{theme_font_css()}{THEME_CSS}</style><style>{LANDING_THEME_CSS}</style></head>
<body class="landing">
<a class="skip" href="#top">Skip to content</a>
<header class="lnav"><a class="lbrand" href="#top">{APP_LOGO_SVG}<span>FM27 {APP_NAME}</span></a>
 <nav aria-label="Page"><a href="#inside">What's inside</a><a href="#wont">What it won't do</a><a href="#how">How it works</a></nav>
 <button class="look-btn ah-look" type="button" popovertarget="lookpop" aria-label="Change the look">Look<span class="lk-cur">: <b id="lookCur">Original</b></span></button>
 <a class="btn sm" href="/app" data-launch>Launch the app</a></header>
<main id="top">
<section class="hero">
 <div class="hero-txt"><p class="for">For Football Manager 27</p>
  <h1>Know your squad before you hit Continue.</h1>
  <p class="lede">{APP_NAME} reads your latest FM27 save and shows your best XIs, the positions that need work and how your
   tactic is going. Visible attributes only, so nothing gets spoiled.</p>
  <div class="ctas"><a class="btn" href="/app" data-launch>Launch the app</a><a class="tlink" href="#inside">See what's inside</a></div></div>
 <div class="hero-3d demo" style="--kit:{lfc['kit']};--kit-ink:{lfc['ink']};--kit-l:{kit_on_light(lfc['kit'])}">{pitch3d(hero_cards, "Demo: Liverpool's XI from 22 November 2026 on a 3D pitch. Drag or use the arrow keys to rotate it.", lfc['pitch'])}
  <p class="hint">Drag to rotate. Demo squad: Liverpool, 22 Nov 2026. Your own club appears when you launch.</p></div>
</section>
<section class="story" id="inside" aria-label="What's inside the app">
 <div class="story-in">
  <div class="story-txt"><h2>What's inside</h2><div class="steps">{step_html}</div></div>
  <div class="fwrap"><div class="frame">{screens}</div><p class="f-demo">The real pages, with demo data. Liverpool is the demo club; ratings are made up.</p></div>
 </div>
</section>
<section class="split" id="wont" aria-label="What it does and doesn't do">
 <h2>What it does, and what it won't</h2>
 <div class="cols"><div><h3>It does</h3><ul class="does">{''.join(f'<li class="rv">{E(x)}</li>' for x in does)}</ul></div>
  <div><h3>It won't</h3><ul class="wont">{''.join(f'<li class="rv">{E(x)}</li>' for x in wont)}</ul>
  <p class="aside rv">The one exception, if you want it: potential stars for players 23 and under, switched off with one setting.</p></div></div>
</section>
<section class="how" id="how" aria-label="How it works">
 <h2>How it works</h2>
 <ol><li class="rv"><b>1</b><h3>Save in FM27</h3><p>Play as normal with any club. The app watches for your newest save.</p></li>
  <li class="rv"><b>2</b><h3>It rebuilds itself</h3><p>About 30 seconds after you save, the report is ready.</p></li>
  <li class="rv"><b>3</b><h3>Refresh and read</h3><p>Open the app, or refresh it if it's already open.</p></li></ol>
</section>
<section class="cta"><h2>Your save is waiting.</h2><a class="btn inv" href="/app" data-launch>Launch the app</a>
 <p>Opens at localhost:8027/app on this Mac.</p></section>
</main>
<footer class="lfoot"><p>Fan-made tool. Not affiliated with Sports Interactive or SEGA, or with any club. The demo uses Liverpool's line-up from
 22 November 2026 with made-up star ratings.</p></footer>
{look_popover()}
<div class="launch" id="launch" aria-hidden="true">{APP_LOGO_SVG}</div>
<div class="cur" aria-hidden="true"><span>Drag</span></div>
<script src="{asset('gsap.min.js')}"></script><script src="{asset('ScrollTrigger.min.js')}"></script>
<script src="{asset('SplitText.min.js')}"></script><script src="{asset('lenis.min.js')}"></script>
<script>{P3_JS}{LANDING_JS}{LOOK_JS}</script></body></html>"""


LANDING_CSS = r"""
:root{--bg:#0e1512;--panel:#16201b;--panel2:#1d2923;--line:#2a3a32;--text:#eef1e8;--text2:#c3cbc0;--muted:#8d9a91;
 --brand:#1C7F46;--brand-ink:#fff;--brand-hi:#4FC77F;--kit:#1C7F46;--kit-ink:#fff;--gold:#e9b949;
 --display:"Archivo","Arial Narrow",system-ui,sans-serif;--gut:clamp(20px,5vw,72px)}
*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0;color:var(--text);font:17px/1.55 "Archivo",system-ui,sans-serif;-webkit-font-smoothing:antialiased;overflow-x:hidden}
a{color:inherit}
:focus-visible{outline:2px solid var(--brand-hi);outline-offset:3px;border-radius:4px}
::selection{background:var(--brand);color:var(--brand-ink)}
.skip{position:absolute;left:12px;top:-60px;z-index:100;background:var(--brand);color:var(--brand-ink);padding:8px 14px;border-radius:6px;font-weight:700}
.skip:focus{top:12px}
h1,h2,h3{font-family:var(--display);margin:0}
.btn{display:inline-flex;align-items:center;gap:10px;background:var(--brand);color:var(--brand-ink);text-decoration:none;font-family:var(--display);font-stretch:75%;
 font-weight:800;font-size:21px;line-height:1;padding:17px 26px;border-radius:7px;box-shadow:0 10px 30px -14px rgba(28,127,70,.7);
 transition:transform .2s ease,background-color .2s ease}
.btn:hover{background:#18703E;transform:translateY(-2px)}.btn:active{transform:scale(.97)}
.btn.sm{font-size:16px;padding:10px 16px;box-shadow:none}
.btn.inv{background:#10170F;color:#fff;box-shadow:0 14px 40px -14px rgba(0,0,0,.6)}.btn.inv:hover{background:#000}
.tlink{font-weight:600;text-underline-offset:5px;text-decoration-thickness:1px;color:var(--text2)}.tlink:hover{color:var(--text)}
.logo{display:block}
/* nav */
.lnav{position:fixed;inset:0 0 auto;z-index:40;display:flex;align-items:center;gap:28px;padding:14px var(--gut);transition:background-color .3s,box-shadow .3s}
.lnav.solid{background:rgba(14,21,18,.88);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);box-shadow:0 1px 0 var(--line)}
.lbrand{display:flex;align-items:center;gap:10px;text-decoration:none;font-family:var(--display);font-stretch:75%;font-weight:800;font-size:19px}
.lbrand .logo{width:30px;height:30px}
.lnav nav{display:flex;gap:24px;margin-left:auto}.lnav nav a{text-decoration:none;color:var(--text2);font-size:15px}.lnav nav a:hover{color:var(--text)}
.look-btn{font:inherit;font-size:14px;font-weight:600;color:var(--text2);background:transparent;border:1px solid var(--line);border-radius:999px;padding:8px 14px;cursor:pointer;white-space:nowrap}
.look-btn:hover{color:var(--text);border-color:var(--text2)}.look-btn b{font-weight:700;color:var(--text)}
.landing .lookpop{top:72px;right:var(--gut)}
.lnav .btn.sm{white-space:nowrap}
@media (max-width:480px){.lbrand span{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}}
/* hero */
.hero{min-height:100svh;display:grid;grid-template-columns:minmax(0,5fr) minmax(0,7fr);align-items:center;gap:20px;padding:110px var(--gut) 40px;
 background:radial-gradient(55% 65% at 72% 55%,rgba(46,140,82,.28),transparent 70%)}
.for{color:var(--brand-hi);font-family:var(--display);font-stretch:75%;font-weight:700;font-size:18px;margin:0 0 14px}
.hero h1{font-stretch:62%;font-weight:850;font-size:clamp(54px,6.8vw,112px);line-height:.9;letter-spacing:-.005em;max-width:12ch;text-wrap:balance}
.lede{color:var(--text2);font-size:clamp(17px,1.35vw,20px);max-width:44ch;margin:26px 0 34px;text-wrap:pretty}
.ctas{display:flex;align-items:center;gap:26px;flex-wrap:wrap}
.hero-3d{display:grid;justify-items:center;gap:10px}
.hero-3d .p3{width:100%;height:min(78vh,720px);--pw:min(430px,33vw)}
.hint{margin:0;color:var(--muted);font-size:13px;text-align:center}
/* story */
.story{position:relative}
.story-in{min-height:100vh;display:grid;grid-template-columns:minmax(0,4fr) minmax(0,8fr);gap:56px;align-items:center;padding:90px var(--gut) 60px}
.story h2{font-stretch:62%;font-weight:850;font-size:clamp(44px,5vw,76px);line-height:.95;margin-bottom:26px}
.steps{display:grid;gap:6px}
.st{all:unset;box-sizing:border-box;display:block;padding:14px 0 14px 18px;border-left:3px solid var(--line);cursor:pointer;color:var(--muted);
 transition:color .3s,border-color .3s}
.st b{display:block;font-family:var(--display);font-stretch:75%;font-size:24px;font-weight:800;line-height:1.1}
.st span{display:block;font-size:15px;margin-top:4px;max-width:40ch}
.st.on{color:var(--text);border-color:var(--brand-hi)}.st:hover{color:var(--text2)}.st:focus-visible{outline:2px solid var(--brand-hi);outline-offset:2px}
.fwrap{perspective:1800px}
.frame{position:relative;transform:rotateY(-16deg) rotateX(7deg);aspect-ratio:1440/945;background:#121a16;border:1px solid var(--line);
 border-radius:12px;overflow:hidden;box-shadow:40px 60px 100px -30px rgba(0,0,0,.8),0 0 0 1px rgba(255,255,255,.03) inset}
.scr{position:absolute;inset:0;background:#0e1512;opacity:0;visibility:hidden}
.scr.on{opacity:1;visibility:visible}
.scr iframe{position:absolute;left:0;top:0;width:1440px;height:945px;border:0;transform-origin:0 0;transform:scale(var(--k,.5));pointer-events:none;background:#0e1512}
.f-demo{margin:14px 0 0;font-size:12.5px;color:var(--muted);text-align:right}
/* does / won't */
.split,.how{padding:120px var(--gut)}
.split h2,.how h2{font-stretch:62%;font-weight:850;font-size:clamp(44px,5vw,76px);line-height:.95;margin-bottom:48px;max-width:16ch}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:0}
.cols>div{padding:0 48px 0 0}.cols>div+div{padding:0 0 0 48px;border-left:2px solid rgba(255,255,255,.14)}
.cols h3{font-stretch:75%;font-weight:800;font-size:26px;margin-bottom:12px}
.cols ul{list-style:none;margin:0;padding:0}
.cols li{position:relative;padding:14px 0 14px 34px;border-top:1px solid var(--line);font-size:18px}
.cols li::before{position:absolute;left:0;top:14px;font-weight:900;font-size:18px}
.does li::before{content:"✓";color:#4ade80}.wont li::before{content:"✕";color:#fca5a5}
.aside{color:var(--muted);font-size:14px;margin:18px 0 0;max-width:46ch}
.how ol{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(3,1fr);gap:28px}
.how li{border-top:2px solid var(--text);padding-top:18px}
.how li>b{display:block;font-family:var(--display);font-stretch:62%;font-style:italic;font-weight:900;font-size:84px;line-height:.85;color:var(--brand-hi)}
.how h3{font-stretch:75%;font-weight:800;font-size:28px;margin:14px 0 6px}.how p{margin:0;color:var(--text2);max-width:32ch}
.cta{background:var(--brand);color:var(--brand-ink);padding:120px var(--gut);display:grid;justify-items:start;gap:28px;
 background-image:linear-gradient(100deg,rgba(0,0,0,.14) 0 40%,transparent 40%)}
.cta h2{font-stretch:62%;font-style:italic;font-weight:900;font-size:clamp(60px,10vw,160px);line-height:.85}
.cta p{margin:0;color:rgba(255,255,255,.82);font-size:15px}
.lfoot{padding:28px var(--gut) 40px;color:var(--muted);font-size:13px}.lfoot p{margin:0;max-width:90ch}
/* launch + cursor */
.launch{position:fixed;inset:0;z-index:90;display:none;place-items:center;background:var(--brand);clip-path:circle(0% at 50% 50%)}
.launch .logo{width:min(140px,26vw);height:auto}
.cur{position:fixed;left:0;top:0;z-index:80;width:70px;height:70px;margin:-35px 0 0 -35px;border-radius:50%;border:1.5px solid var(--text);
 display:grid;place-items:center;pointer-events:none;opacity:0;font-family:var(--display);font-stretch:75%;font-weight:800;font-size:14px;color:var(--text);
 background:rgba(14,21,18,.35);backdrop-filter:blur(2px)}
.has-cur .p3{cursor:none}
@media (max-width:900px){
 .lnav nav{display:none}.lnav .look-btn{margin-left:auto}.lnav{gap:12px}
 .hero{grid-template-columns:1fr;padding-top:96px}.hero-3d .p3{height:62vh;--pw:min(300px,64vw)}
 .story-in{grid-template-columns:1fr;gap:28px}.steps{grid-template-columns:repeat(2,1fr)}.st span{display:none}
 .frame{transform:none}
 .cols{grid-template-columns:1fr}.cols>div,.cols>div+div{padding:0;border:0}.cols>div+div{margin-top:40px}
 .how ol{grid-template-columns:1fr}
}
@media (prefers-reduced-motion:reduce){.btn{transition:none}}
"""


LANDING_JS = r"""
(function(){
const rm=matchMedia('(prefers-reduced-motion: reduce)').matches, G=!!window.gsap;
if(G){gsap.registerPlugin(ScrollTrigger,SplitText);}
document.querySelectorAll('[data-p3]').forEach(initP3);
let lenis=null;
if(G&&window.Lenis&&!rm){lenis=new Lenis({lerp:.1});lenis.on('scroll',ScrollTrigger.update);gsap.ticker.add(t=>lenis.raf(t*1000));gsap.ticker.lagSmoothing(0);
 ScrollTrigger.addEventListener('refresh',()=>lenis.resize());}
const nav=document.querySelector('.lnav');const solid=()=>nav.classList.toggle('solid',scrollY>30);addEventListener('scroll',solid,{passive:true});solid();
document.querySelectorAll('a[href^="#"]').forEach(a=>a.addEventListener('click',e=>{const t=document.querySelector(a.getAttribute('href'));if(!t)return;
 e.preventDefault();if(lenis)lenis.scrollTo(t,{offset:a.getAttribute('href')==='#top'?0:-60});else t.scrollIntoView({behavior:rm?'auto':'smooth'});}));

// hero entrance: the one orchestrated moment on load
if(G&&!rm){
 gsap.set('.hero .lede,.hero .ctas,.hero .for,.hint',{opacity:0,y:20});
 document.fonts.ready.then(()=>{
  const split=new SplitText('.hero h1',{type:'lines',mask:'lines'});
  gsap.timeline({defaults:{ease:'power4.out'}})
   .from(split.lines,{yPercent:110,duration:1.05,stagger:.09,onComplete:()=>split.revert()})
   .to('.hero .for,.hero .lede,.hero .ctas',{opacity:1,y:0,duration:.8,stagger:.08},'-=.75')
   .from('.hero .p3',{'--rx':'84deg','--sc':.72,opacity:0,duration:1.7,ease:'expo.out'},'-=1.2')
   .to('.hint',{opacity:1,y:0,duration:.6},'-=.8');
 });
}

// "What's inside": pinned on wide screens, the scroll turns the app window and swaps screens; elsewhere the steps are buttons
const story=document.querySelector('.story'),screens=[...story.querySelectorAll('.scr')],steps=[...story.querySelectorAll('.st')],
 frame=story.querySelector('.frame');
// each preview is a real app page at 1440x945, scaled to the window
const fit=()=>frame.style.setProperty('--k',(frame.clientWidth/1440).toFixed(4));fit();
if(window.ResizeObserver)new ResizeObserver(fit).observe(frame);else addEventListener('resize',fit);
let curStep=-1,jumping=false,marks=[];
function activate(i){if(i===curStep)return;curStep=i;steps.forEach((s,k)=>{s.classList.toggle('on',k===i);s.setAttribute('aria-pressed',k===i);});}
let pinST=null;
if(G){
 const mm=gsap.matchMedia();
 mm.add('(min-width: 901px) and (prefers-reduced-motion: no-preference)',()=>{
  const poses=[[-16,7],[-5,3],[-20,9],[-9,5]];
  gsap.set(screens,{autoAlpha:0});gsap.set(screens[0],{autoAlpha:1});gsap.set(frame,{rotateY:poses[0][0],rotateX:poses[0][1]});
  const tl=gsap.timeline({defaults:{ease:'none'},scrollTrigger:{trigger:story,start:'top top',end:'+='+(screens.length*85)+'%',pin:story.querySelector('.story-in'),scrub:true,anticipatePin:1,
   onUpdate:self=>{if(jumping)return;const p=self.progress;let best=0;marks.forEach((m,k)=>{if(Math.abs(m-p)<Math.abs(marks[best]-p))best=k;});activate(best);}}});
  tl.addLabel('s0');
  // the next page fades in over the current one (explicit from/to values both ways, so scrolling back or jumping never leaves the window blank)
  for(let i=1;i<screens.length;i++){
   tl.to(frame,{rotateY:poses[i][0],rotateX:poses[i][1],duration:1})
     .fromTo(screens[i],{autoAlpha:0,yPercent:4},{autoAlpha:1,yPercent:0,duration:.45},'<+.25')
     .fromTo(screens[i-1],{autoAlpha:1},{autoAlpha:0,duration:.01,immediateRender:false})
     .addLabel('s'+i,'>+.1');
  }
  pinST=tl.scrollTrigger;marks=screens.map((_,k)=>tl.labels['s'+k]/tl.duration());
  return()=>{pinST=null;gsap.set(screens,{clearProps:'all'});screens.forEach((s,k)=>s.classList.toggle('on',k===curStep));};
 });
}
function showStatic(i){screens.forEach((s,k)=>s.classList.toggle('on',k===i));activate(i);}
steps.forEach((s,i)=>s.addEventListener('click',()=>{
 if(pinST){const y=pinST.start+(pinST.end-pinST.start)*marks[i];activate(i);jumping=true;
  const fw=story.querySelector('.fwrap');
  const jump=()=>{if(lenis)lenis.scrollTo(y,{immediate:true,force:true});else scrollTo({top:y,behavior:'instant'});ScrollTrigger.update();jumping=false;};
  if(G&&!rm){gsap.timeline().to(fw,{autoAlpha:0,scale:.985,duration:.14,ease:'power2.in'}).add(jump).to(fw,{autoAlpha:1,scale:1,duration:.3,ease:'power2.out'});}
  else jump();}
 else showStatic(i);}));
showStatic(0);

// gentle reveals for the lists below
if(G&&!rm){gsap.set('.rv',{opacity:0,y:22});
 ScrollTrigger.batch('.rv',{start:'top 88%',onEnter:b=>gsap.to(b,{opacity:1,y:0,duration:.7,ease:'power3.out',stagger:.07,overwrite:true})});}
// re-measure once fonts and the previews have loaded (never synchronously during setup)
if(window.ScrollTrigger){document.fonts&&document.fonts.ready.then(()=>ScrollTrigger.refresh());addEventListener('load',()=>ScrollTrigger.refresh(),{once:true});}

// custom cursor: only over the 3D pitch, only for a mouse, and it says what you can do there
const cur=document.querySelector('.cur');
if(G&&!rm&&matchMedia('(hover: hover) and (pointer: fine)').matches){
 document.documentElement.classList.add('has-cur');
 const qx=gsap.quickTo(cur,'x',{duration:.18,ease:'power3'}),qy=gsap.quickTo(cur,'y',{duration:.18,ease:'power3'});
 document.querySelectorAll('[data-p3]').forEach(el=>{
  el.addEventListener('pointerenter',()=>gsap.to(cur,{opacity:1,scale:1,duration:.25}));
  el.addEventListener('pointerleave',()=>gsap.to(cur,{opacity:0,scale:.6,duration:.25}));
  el.addEventListener('pointerdown',()=>gsap.to(cur,{scale:.82,backgroundColor:'color-mix(in srgb,var(--kit) 55%,transparent)',duration:.2}));
  addEventListener('pointerup',()=>{gsap.to(cur,{scale:1,duration:.2});gsap.set(cur,{clearProps:'backgroundColor'});});
 });
 addEventListener('pointermove',e=>{qx(e.clientX);qy(e.clientY);},{passive:true});
}

// launch: the camera dives into the pitch, the app's colour wipes in, then your club's loader picks it up
const ov=document.getElementById('launch');
document.querySelectorAll('[data-launch]').forEach(a=>a.addEventListener('click',e=>{
 if(e.metaKey||e.ctrlKey||e.shiftKey)return;
 e.preventDefault();const href=a.getAttribute('href');
 try{sessionStorage.setItem('fm27-launch',String(Date.now()));}catch(_){}
 if(!G||rm){location.href=href;return;}
 lenis&&lenis.stop();
 const p3=document.querySelector('.hero .p3'),inView=scrollY<innerHeight*.6;
 const x=e.clientX||innerWidth/2,y=e.clientY||innerHeight/2;
 const tl=gsap.timeline({onComplete:()=>{location.href=href;}});
 if(inView)tl.to(p3,{'--rx':'8deg','--rz':'0deg','--sc':2.6,duration:.75,ease:'power3.in'},0);
 tl.to('main>*:not(.hero),.lnav,.hero-txt,.lfoot',{opacity:0,duration:.35,ease:'power2.in'},0)
   .set(ov,{display:'grid'},inView?.35:0)
   .fromTo(ov,{clipPath:`circle(0% at ${x}px ${y}px)`},{clipPath:`circle(150% at ${x}px ${y}px)`,duration:.6,ease:'power3.in'},inView?.35:0)
   .from(ov.querySelector('.logo'),{scale:.4,opacity:0,duration:.35,ease:'back.out(2)'},'-=.2');
}));
// coming back with the back button: undo the launch state
addEventListener('pageshow',ev=>{if(ev.persisted){location.reload();}});
})();
"""

# ---------------------------------------------------------------------------------------------
# Loader: shown while a save is being read, and as the launch sequence when you open the app


def boot_html(club: dict | None = None) -> str:
    shapes = ('<rect x="1" y="1" width="66" height="103"/><line x1="1" y1="52.5" x2="67" y2="52.5"/><circle cx="34" cy="52.5" r="9.15"/>'
              '<rect x="13.8" y="1" width="40.4" height="16.5"/><rect x="13.8" y="87.5" width="40.4" height="16.5"/>'
              '<rect x="24.8" y="1" width="18.4" height="5.5"/><rect x="24.8" y="98.5" width="18.4" height="5.5"/>')
    shapes = shapes.replace("/>", ' pathLength="1"/>')
    steps = "".join(f'<li><i></i>{E(s)}</li>' for s in BUILD_STEPS)
    ticks = "<i></i>" * len(BUILD_STEPS)
    if club:
        panel = f'<div class="boot-red"><span class="boot-crest">{club["onkit"]}</span><b class="boot-club">{E(club["name"])}</b></div>'
        style, who = f' style="--kit:{club["kit"]};--kit-ink:{club["ink"]}"', f'<span>{E(club["name"])}</span>'
        ident = f'<div class="boot-id">{club["dark"]}<b>{E(club["name"])}</b></div>'
    else:
        panel = f'<div class="boot-red brand"><span class="boot-crest">{APP_LOGO_SVG}</span><b class="boot-club">FM27 {APP_NAME}</b></div>'
        style, who = ' style="--kit:#1C7F46;--kit-ink:#fff"', f"<span>FM27 {APP_NAME}</span>"
        ident = f'<div class="boot-id brand">{APP_LOGO_SVG}<b>FM27 {APP_NAME}</b></div>'
    return f"""<div id="boot" class="boot" role="status" aria-live="polite" aria-busy="true"{style}>
 {panel}
 <div class="boot-in"><i class="cm tl"></i><i class="cm tr"></i><i class="cm bl"></i><i class="cm br"></i>
  <div class="boot-pw"><svg class="boot-pitch" viewBox="0 0 68 105" aria-hidden="true">{shapes}</svg><i class="boot-scan"></i></div>
  <div class="boot-txt">{ident}<p class="boot-h" id="bootH">Reading your save</p><ol class="boot-steps">{steps}</ol>
   <div class="boot-bar">{ticks}</div><p class="boot-meta"><span id="bootPct">0%</span><span id="bootNote">Step 1 of {len(BUILD_STEPS)}</span></p>
   <p class="boot-err" id="bootErr" hidden></p></div>
  <p class="boot-foot">{who}<span>localhost:{LIVE_PORT}</span></p></div>
</div>"""


BOOT_CSS = r"""
.boot{position:fixed;inset:0;z-index:200;display:none;background:#0e1512;color:#eef1e8;font-family:"Archivo",system-ui,sans-serif}
.booting .boot,.boot.wait{display:block}
.booting body{overflow:hidden}
.boot-red{position:absolute;inset:0;z-index:2;display:grid;place-items:center;align-content:center;gap:18px;background:var(--kit,#C8102E);color:var(--kit-ink,#fff)}
.boot-crest{display:block;line-height:0}.boot-crest img,.boot-crest svg{height:min(190px,30vh);width:auto}
.boot-club{font-family:"Archivo","Arial Narrow",sans-serif;font-stretch:62%;font-style:italic;font-weight:900;font-size:clamp(34px,5vw,64px);text-transform:uppercase;line-height:.9}
.boot-red.brand{background:#1C7F46;color:#fff}
.boot-id{display:flex;align-items:center;gap:12px;margin:0 0 16px}
.boot-id img,.boot-id svg{height:46px;width:auto;flex:none}
.boot-id b{font-family:"Archivo","Arial Narrow",sans-serif;font-stretch:62%;font-style:italic;font-weight:900;font-size:28px;text-transform:uppercase;line-height:1;color:var(--kit,#1C7F46)}
.boot-id.brand b{color:#eef1e8;font-style:normal;font-stretch:75%;text-transform:none}
.boot.wait .boot-red{display:none}
.boot-in{position:absolute;inset:0;display:grid;grid-template-columns:auto minmax(0,440px);align-items:center;justify-content:center;gap:64px;padding:40px}
.cm{position:absolute;width:22px;height:22px;border:0 solid rgba(238,241,232,.4)}
.cm.tl{left:24px;top:24px;border-width:2px 0 0 2px}.cm.tr{right:24px;top:24px;border-width:2px 2px 0 0}
.cm.bl{left:24px;bottom:24px;border-width:0 0 2px 2px}.cm.br{right:24px;bottom:24px;border-width:0 2px 2px 0}
.boot-pw{position:relative;width:min(220px,34vw);overflow:hidden}
.boot-pitch{display:block;width:100%}
.boot-pitch *{fill:none;stroke:rgba(238,241,232,.6);stroke-width:.55;stroke-dasharray:1;stroke-dashoffset:1;animation:bdraw 1.1s cubic-bezier(.6,0,.2,1) forwards}
.boot-pitch *:nth-child(2){animation-delay:.12s}.boot-pitch *:nth-child(3){animation-delay:.22s}.boot-pitch *:nth-child(n+4){animation-delay:.32s}
@keyframes bdraw{to{stroke-dashoffset:0}}
.boot-scan{position:absolute;left:0;right:0;top:0;height:22%;background:linear-gradient(180deg,transparent,color-mix(in srgb,var(--kit) 28%,transparent) 70%,rgba(255,93,93,.9) 71%,transparent 73%);
 animation:bscan 2.2s cubic-bezier(.45,0,.55,1) infinite;opacity:0}
.boot.wait .boot-scan{opacity:1}
@keyframes bscan{0%{transform:translateY(-100%)}100%{transform:translateY(480%)}}
.boot-h{margin:0 0 18px;font-family:"Archivo","Arial Narrow",sans-serif;font-stretch:62%;font-weight:850;font-size:clamp(40px,5vw,64px);line-height:.95}
.boot-steps{list-style:none;margin:0 0 22px;padding:0;display:grid;gap:7px;font-size:15px;color:rgba(238,241,232,.38)}
.boot-steps li{display:flex;align-items:center;gap:10px;transition:color .3s}
.boot-steps i{width:14px;height:14px;border-radius:50%;border:1.5px solid currentColor;flex:none;position:relative}
.boot-steps li.act{color:#eef1e8}.boot-steps li.act i{border-color:var(--kit,#C8102E);border-top-color:transparent;animation:bspin .8s linear infinite}
.boot-steps li.done{color:#c3cbc0}.boot-steps li.done i{background:var(--kit,#C8102E);border-color:var(--kit,#C8102E)}
.boot-steps li.done i::after{content:"";position:absolute;left:4px;top:1px;width:3px;height:7px;border:solid #fff;border-width:0 1.5px 1.5px 0;transform:rotate(45deg)}
@keyframes bspin{to{transform:rotate(360deg)}}
.boot-bar{display:grid;grid-template-columns:repeat(8,1fr);gap:4px}
.boot-bar i{height:8px;border-radius:2px;background:#1d2923;transition:background-color .25s}.boot-bar i.on{background:var(--kit,#C8102E)}
.boot-meta{display:flex;justify-content:space-between;margin:10px 0 0;font-size:13px;color:#8d9a91;font-variant-numeric:tabular-nums}
.boot-err{margin:16px 0 0;padding:12px 14px;border-left:3px solid #ff5d5d;background:rgba(255,93,93,.08);color:#fca5a5;font-size:14px}
.boot-foot{position:absolute;left:56px;right:56px;bottom:22px;display:flex;justify-content:space-between;margin:0;font-size:12px;color:#8d9a91}
@media (max-width:700px){.boot-in{grid-template-columns:1fr;justify-items:center;gap:28px;align-content:center}.boot-pw{width:120px}.boot-txt{width:100%}}
@media (prefers-reduced-motion:reduce){.boot-pitch *{animation:none;stroke-dashoffset:0}.boot-scan{display:none}.boot-steps li.act i{animation:none}}
"""

BOOT_JS = r"""
window.FM27Boot=(function(){
const boot=document.getElementById('boot');if(!boot)return null;
const rm=matchMedia('(prefers-reduced-motion: reduce)').matches;
const lis=[...boot.querySelectorAll('.boot-steps li')],ticks=[...boot.querySelectorAll('.boot-bar i')],n=lis.length;
const pct=document.getElementById('bootPct'),note=document.getElementById('bootNote'),err=document.getElementById('bootErr');
function paint(step,done){lis.forEach((li,i)=>{li.classList.toggle('done',done||i<step);li.classList.toggle('act',!done&&i===step);});
 const k=done?n:Math.max(0,step);ticks.forEach((t,i)=>t.classList.toggle('on',i<k));
 pct.textContent=Math.round(k/n*100)+'%';note.textContent=done?'Ready':('Step '+(Math.max(0,step)+1)+' of '+n);}
function finish(){document.documentElement.classList.remove('booting');boot.remove();try{sessionStorage.removeItem('fm27-launch');}catch(_){}
 document.dispatchEvent(new Event('fm27:ready'));}
// launched from the home page with the report already built: tick through the finished steps, then lift the loader away
function play(){
 if(!window.gsap||rm){finish();return;}
 const red=boot.querySelector('.boot-red'),st={k:0};
 const tl=gsap.timeline({onComplete:finish});
 tl.to(red,{yPercent:-100,duration:.7,ease:'expo.inOut',delay:.15})
   .to(st,{k:n,duration:.9,ease:'power1.inOut',onUpdate:()=>paint(Math.floor(st.k),st.k>=n)},'-=.25')
   .to(boot,{yPercent:-100,duration:.8,ease:'expo.inOut'},'+=.25');
 const skip=()=>tl.progress(1);boot.addEventListener('click',skip);addEventListener('keydown',e=>{if(e.key==='Escape')skip();},{once:true});
}
// the report isn't built yet: follow the real rebuild through /status, then load the app
function wait(){
 boot.classList.add('wait');document.documentElement.classList.add('booting');let seen=false;
 async function poll(){
  try{const s=await (await fetch('/status',{cache:'no-store'})).json();
   if(s.ready&&!s.building){paint(n,true);try{sessionStorage.setItem('fm27-launch',String(Date.now()));}catch(_){}setTimeout(()=>location.reload(),rm?0:450);return;}
   if(s.building){seen=true;err.hidden=true;paint(Math.max(0,s.step),false);document.getElementById('bootH').textContent='Reading your save';}
   else if(s.error){err.hidden=false;err.textContent=s.error.startsWith('no FM27 save')?'No FM27 save found yet. Save your game in FM27 and this page carries on by itself.'
     :'Couldn\'t read your save ('+s.error+'). Save again in FM27 and this page tries again by itself.';}
  }catch(e){err.hidden=false;err.textContent='The app window is closed. Double-click Run Squad Report to start it again.';}
  setTimeout(poll,900);}
 poll();
}
return {play,wait,paint};
})();
"""

# ---------------------------------------------------------------------------------------------
# App shell: six sections in the navbar, the pages inside a section as tabs underneath, and a club news ticker

SECTIONS = [("home", "Home", [("overview", "Overview", "home")]),
            ("team", "Team", [("xis", "Best XIs", "team/xis"), ("positions", "Positions", "team/positions"), ("squad", "Squad list", "team/squad")]),
            ("tactics", "Tactics", [("fit", "Tactical fit", "tactics/fit"), ("training", "Training", "tactics/training")]),
            ("sandbox", "Sandbox", [("sandbox", "Sandbox", "sandbox")]),
            ("transfers", "Transfers", [("deals", "Deals & loans", "transfers")]),
            ("stats", "Stats", [("stats", "Season stats", "stats")])]
SECTION_NOTE = {"home": "Your squad at a glance", "sandbox": "Try line-ups before you make them",
                "transfers": "Arranged moves and current loans", "stats": "This season, first team and youth"}


def ticker_items(R) -> list[tuple[str, str, str, str]]:
    """(tag class, tag, text, route) for the club news ticker, from the save only."""
    deals, health, contracts = [], [], []
    for p in R["players"]:
        nm = p["name"]
        if "deal_in" in p:
            deals.append(("deal-in", "Signing", f"{nm} arrives from {p['deal_in'][0]}, {d(p['deal_in'][1])}", "transfers"))
        if "deal_out" in p:
            deals.append(("deal-out", "Leaving", f"{nm} joins {p['deal_out'][0]}, {d(p['deal_out'][1])}", "transfers"))
        if "loan_in_arr" in p:
            deals.append(("loan-in", "Loan agreed", f"{nm} arrives on loan from {p['loan_in_arr'][0]}, {d(p['loan_in_arr'][1])}", "transfers"))
        if "loan_out_arr" in p:
            deals.append(("loan-out", "Loan agreed", f"{nm} goes on loan to {p['loan_out_arr'][0]}, {d(p['loan_out_arr'][1])}", "transfers"))
        if p["where"] != "squad" or p["youth"]:
            continue
        if "inj" in p:
            days, what, back = p["inj"]
            health.append(("inj-long" if days >= LONG_INJURY_DAYS else "inj-short", "Injured", f"{nm}: {what}, back {d(back)}", "team/squad"))
        if "sus" in p:
            health.append(("sus", "Suspended", f"{nm} misses {p['sus']} match{'es' if p['sus'] > 1 else ''}", "team/squad"))
        if p.get("expiring") and "deal_out" not in p:
            contracts.append(("expiring", "Contract", f"{nm}'s deal ends {d(p['contract_end'], '%b %Y')}", "team/squad"))
    need = sum(1 for v in R["verdicts"] if v[1] in ("red", "amber"))
    head = [("warn", "Squad", f"{need} position{'s' if need != 1 else ''} need work", "home")] if need else []
    return (head + deals + health + contracts)[:20]


def ticker(R) -> str:
    return ticker_html(ticker_items(R))


def ticker_html(items) -> str:
    if not items:
        return ""

    def lis(hidden):
        tab = ' tabindex="-1"' if hidden else ""
        return "".join(f'<li><a href="#{r}"{tab}><span class="tag {c}">{E(t)}</span>{E(x)}</a></li>' for c, t, x, r in items)
    dur = max(28, sum(len(x) for _, _, x, _ in items) // 5)
    return f"""<div class="tk" id="tk"><button class="tk-btn" type="button" aria-pressed="false" aria-label="Pause club news" title="Pause club news">
  <svg viewBox="0 0 12 12" aria-hidden="true"><rect x="2" y="2" width="3" height="8"/><rect x="7" y="2" width="3" height="8"/></svg></button>
  <div class="tk-vp" aria-label="Club news"><div class="tk-tr" style="--dur:{dur}s"><ul>{lis(False)}</ul><ul aria-hidden="true">{lis(True)}</ul></div></div></div>"""


def app_header(R) -> str:
    need = sum(1 for v in R["verdicts"] if v[1] in ("red", "amber"))
    deals_n = sum(1 for p in R["players"] for k in STATUS_KEYS if k in p)
    squad_n = sum(1 for p in R["players"] if p["where"] == "squad" and not p["youth"])
    misfit_n = len(R["fit"]["misfits"])
    return header_html(club_identity(R["club"]), {"home": (need, "warn"), "tactics": (misfit_n, "amber"), "transfers": (deals_n, "")},
                       {"squad": (squad_n, ""), "fit": (misfit_n, "amber")}, ticker(R))


NAV_ICONS = {
    "home": '<path d="M3.5 10.5 12 3.5l8.5 7V20a1 1 0 0 1-1 1H15v-6H9v6H4.5a1 1 0 0 1-1-1z"/>',
    "team": '<path d="M8.5 3.5 3.5 6.5l1.8 4.3 2.2-1V20.5h9V9.8l2.2 1 1.8-4.3-5-3c-.6 1.5-2 2.4-3.5 2.4s-2.9-.9-3.5-2.4z"/>',
    "tactics": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M4 12h16"/><circle cx="12" cy="12" r="2.8"/><path d="M9 3v3.5h6V3M9 21v-3.5h6V21"/>',
    "sandbox": '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2.2"/><circle cx="9" cy="17" r="2.2"/>',
    "transfers": '<path d="M4 8.5h14.5M15 5l3.5 3.5L15 12M20 15.5H5.5M9 12l-3.5 3.5L9 19"/>',
    "stats": '<path d="M5 20.5v-8M12 20.5v-15M19 20.5v-11"/>',
    "more": '<circle cx="5.5" cy="12" r="1.7" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.7" fill="currentColor" stroke="none"/><circle cx="18.5" cy="12" r="1.7" fill="currentColor" stroke="none"/>',
    "look": '<circle cx="12" cy="12" r="8.5"/><path d="M12 3.5a8.5 8.5 0 0 0 0 17z" fill="currentColor" stroke="none"/>',
    "key": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.8v.4"/>',
    "about": '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
}


def nav_icon(name: str, cls: str = "ni") -> str:
    return (f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{NAV_ICONS[name]}</svg>')


def more_sheet() -> str:
    """The phone's More tab: the sections that don't get their own tab, then the look, the key and the home page."""
    blurb = {"stats": "Season leaders and every player's numbers", "sandbox": "Try line-ups. Easier on a bigger screen"}
    links = "".join(f'<a href="#{pages[0][2]}" data-sec="{sid}">{nav_icon(sid, "mi")}<span><b>{E(label)}</b><small>{blurb[sid]}</small></span></a>'
                    for sid, label, pages in SECTIONS if sid in blurb)
    return (f'<div id="morepop" class="keypop morepop" popover><p class="kp-h">More</p>'
            f'<nav class="mp-links" aria-label="More sections">{links}</nav>'
            f'<div class="mp-tools"><button type="button" popovertarget="lookpop">{nav_icon("look", "mi")}<span><b>Look</b>'
            f'<small id="lookCur2">Original</small></span></button>'
            f'<button type="button" popovertarget="keypop">{nav_icon("key", "mi")}<span><b>Key</b><small>What the badges and letters mean</small></span></button>'
            f'<a href="/">{nav_icon("about", "mi")}<span><b>About</b><small>The home page</small></span></a></div></div>')


def header_html(club: dict, sec_count: dict, sub_count: dict, ticker_markup: str, route: str | None = None) -> str:
    """The app's sticky header. route pre-selects a page (used by the static previews on the home page)."""
    sec_on = route.split("/")[0] if route else None

    def pill(c, label):
        return f'<span class="count {c[1]}" aria-label="{c[0]} {label}">{c[0]}</span>' if c and c[0] else ""
    links, subs = [], []
    for i, (sid, label, pages) in enumerate(SECTIONS, 1):
        cur = ' aria-current="true"' if sid == sec_on else ""
        links.append(f'<a href="#{pages[0][2]}" data-sec="{sid}"{cur}>{nav_icon(sid)}<span class="k" aria-hidden="true">{i}</span><span class="nl">{E(label)}</span>'
                     f'{pill(sec_count.get(sid), "to look at")}</a>')
        on = " on" if sid == sec_on else ""
        if len(pages) > 1:
            tabs = "".join(f'<a role="tab" href="#{r}" data-route="{r}" aria-controls="p-{pid}" tabindex="-1"'
                           f'{" aria-selected=\"true\"" if r == route else ""}>{E(t)}{pill(sub_count.get(pid), "")}</a>' for pid, t, r in pages)
            subs.append(f'<div class="ah-sub{on}" data-for="{sid}" role="tablist" aria-label="{E(label)} pages">{tabs}</div>')
        else:
            subs.append(f'<div class="ah-sub note{on}" data-for="{sid}"><span>{E(SECTION_NOTE.get(sid, ""))}</span></div>')
    legend = f"""<span class="badge deal-in"><b>Transfer in</b></span><span class="badge deal-out"><b>Transfer out</b></span>
    <span class="badge loan-in"><b>Loan in</b></span><span class="badge loan-out"><b>Loan out</b></span>
    <span class="badge loan-in arr"><b>Loan</b> arranged, not started</span>
    <span class="badge inj-short"><b>Injured</b> under {LONG_INJURY_DAYS // 7} wks</span><span class="badge inj-long"><b>Injured</b> {LONG_INJURY_DAYS // 7} wks +</span>
    <span class="badge sus"><b>Suspended</b></span><span class="badge expiring"><b>Contract</b> ends within 12 months</span>
    <span class="nlegend"><span class="fam N">N</span> natural <span class="fam A">A</span> accomplished <span class="fam C">C</span> can play <span class="fam X">X</span> out of position</span>"""
    return f"""<a class="skip" href="#main">Skip to content</a>
<header class="ah"><div class="ah-row">
  <a class="ah-brand" href="#home" aria-label="{APP_NAME} home">{APP_LOGO_SVG}<span><small>FM27</small>{APP_NAME}</span></a>
  <span class="ah-title" id="ahTitle" aria-hidden="true"></span>
  <nav class="ah-nav" aria-label="Sections">{''.join(links)}<button class="ah-more" type="button" popovertarget="morepop" aria-label="More: Stats, Sandbox, look and key">{nav_icon("more")}<span class="nl">More</span></button></nav>
  <div class="ah-tools"><span class="ah-club" title="The club in your save">{club['dark']}<b>{E(club['name'])}</b></span>
   <span class="ah-live" id="liveDot"><i></i><span id="liveTxt">Up to date</span></span>
   <button class="ah-btn ah-look" type="button" popovertarget="lookpop" aria-label="Change the look">Look<span class="lk-cur">: <b id="lookCur">Original</b></span></button>
   <button class="ah-btn" type="button" popovertarget="keypop">Key</button><a class="ah-btn ah-about" href="/">About</a></div>
 </div>{''.join(subs)}{ticker_markup}</header>
<div id="keypop" class="keypop" popover><p class="kp-h">Key</p><div class="kp-b">{legend}</div></div>{look_popover()}{more_sheet()}"""


def xi_cards(xi) -> list:
    """An XI as pitch3d() cards: (slot, surname, stars for that slot, status class)."""
    cards = []
    for i, (slot, p) in enumerate(xi):
        if p is None:
            cards.append((slot, "No option", 0, "empty"))
        else:
            cards.append((slot, surname(p["name"]), p["rows"].get(i, p["slots"][slot])[0], row_state(p)))
    return cards


def home_hero(R) -> str:
    rec = (R.get("perf") or {}).get("record")
    form = (R.get("perf") or {}).get("form", [])
    cards = xi_cards(R["xi1"])
    trend_txt = d(date.fromisoformat(R["last_run"])) if R["last_run"] else "start next run"
    rec_html = ""
    if rec:
        chips = "".join(f'<span class="frm {f["res"]}" title="{E(f["score"])} {"vs" if f["home"] else "at"} {E(f["opp"])}">{f["res"]}</span>' for f in form)
        rec_html = f"""<div class="hb-rec"><span class="hb-pos">{ordinal(rec['pos'])}</span><span class="hb-of">of {rec['of']}<br>
          {rec['pts']} pts from {rec['p']}</span><span class="hb-form" aria-label="Last {len(form)} league results">{chips}</span></div>"""
    return f"""<section class="hband">
 <div class="hb-txt"><p class="hb-k">FM27 squad report</p><h1 class="hb-club">{E(R['club'])}</h1>
  <dl class="hb-meta"><div><dt>In-game date</dt><dd>{E(d(R['game_date']))}</dd></div><div><dt>Tactic</dt><dd>{E(FORMATION_NAME)} {E(TACTICAL_STYLE)}</dd></div>
   <div><dt>Trends vs</dt><dd>{E(trend_txt)}</dd></div><div><dt>Save</dt><dd class="sv">{E(R['save_name'])}</dd></div></dl>
  {rec_html}<a class="hb-btn" href="#team/xis">Open best XIs</a></div>
 <div class="hb-3d">{pitch3d(cards, f"Your best XI on a 3D pitch, average {R['xi_level']:.1f} stars. Drag or use the arrow keys to rotate it.", club_identity(R['club'])['pitch'])}
  <p class="hb-hint">Your best XI. Drag to rotate.</p></div>
</section>"""


APP_CSS = r"""
html{scroll-padding-top:150px}
body.app{padding-bottom:40px}
.skip{position:absolute;left:12px;top:-60px;z-index:300;background:var(--gold);color:#0e1512;padding:8px 14px;border-radius:6px;font-weight:700}
.skip:focus{top:12px}
.ah{position:sticky;top:0;z-index:50;background:rgba(14,21,18,.94);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.ah-row{display:flex;align-items:center;gap:24px;padding:0 var(--gutter);height:60px}
.ah-brand{display:flex;align-items:center;gap:10px;text-decoration:none;color:var(--text);flex:none}
.ah-brand .logo{width:30px;height:30px;flex:none}
.ah-brand span{display:flex;flex-direction:column;font-family:var(--display);font-stretch:75%;font-weight:800;font-size:19px;line-height:1}
.ah-brand small{font-size:11px;font-weight:600;color:var(--muted);font-stretch:100%;font-family:"Archivo",sans-serif}
.ah-club{display:flex;align-items:center;gap:8px;padding:3px 10px 3px 6px;border:1px solid var(--line);border-radius:999px;font-size:13px}
.ah-club img,.ah-club svg{height:24px;width:auto}.ah-club b{font-family:var(--display);font-stretch:75%;font-weight:800;font-size:15px;text-transform:uppercase;font-style:italic}
.ah-nav{display:flex;gap:2px;height:100%}
.ah-nav a{position:relative;display:flex;align-items:center;gap:7px;padding:0 13px;color:var(--muted);text-decoration:none;
 font-family:var(--display);font-stretch:75%;font-weight:700;font-size:17px;transition:color .15s}
.ah-nav a::after{content:"";position:absolute;left:10px;right:10px;bottom:-1px;height:4px;background:var(--kit);transform:scaleX(0);transition:transform .22s}
.ah-nav a:hover{color:var(--text)}.ah-nav a[aria-current="true"]{color:var(--text)}.ah-nav a[aria-current="true"]::after{transform:scaleX(1)}
.ah-nav .k{font-size:11px;font-weight:600;font-stretch:100%;opacity:.55}
.count{font-family:"Archivo",sans-serif;font-stretch:100%;font-size:11px;font-weight:700;background:var(--panel2);border-radius:3px;padding:0 6px;color:var(--text2);line-height:17px}
.count.warn{background:var(--kit);color:var(--kit-ink)}.count.amber{background:rgba(245,158,11,.2);color:#fcd34d}
.ah-tools{margin-left:auto;display:flex;align-items:center;gap:10px}
.ah-live{display:flex;align-items:center;gap:7px;font-size:13px;color:var(--muted);white-space:nowrap}
.ah-live i{width:8px;height:8px;border-radius:50%;background:#22c55e;box-shadow:0 0 0 3px rgba(34,197,94,.18)}
.ah-live.busy i{background:#f59e0b;animation:lpulse 1.2s ease-in-out infinite}.ah-live.err i{background:#ff5d5d}.ah-live.new i{background:var(--gold)}
@keyframes lpulse{50%{box-shadow:0 0 0 6px rgba(245,158,11,.05)}}
.ah-btn{font:inherit;font-size:13px;font-weight:600;color:var(--text2);background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:5px 11px;cursor:pointer;text-decoration:none}
.ah-btn:hover{color:var(--text);border-color:#46604f}
.ah-sub{display:none;align-items:center;gap:4px;padding:0 var(--gutter);height:42px;border-top:1px solid var(--line2)}
.ah-sub.on{display:flex}
.ah-sub a{display:flex;align-items:center;gap:6px;padding:6px 12px;border-radius:6px;color:var(--muted);text-decoration:none;font-size:14px;font-weight:600}
.ah-sub a:hover{color:var(--text);background:var(--panel)}
.ah-sub a[aria-selected="true"]{color:var(--text);background:var(--panel2);box-shadow:inset 0 -2px 0 var(--kit)}
.ah-sub.note span{font-size:13px;color:var(--muted)}
.tk{display:flex;align-items:center;border-top:1px solid var(--line2);height:34px}
.tk-btn{flex:none;display:grid;place-items:center;width:calc(var(--gutter) + 8px);min-width:40px;height:100%;background:none;border:0;color:var(--muted);cursor:pointer}
.tk-btn svg{width:12px;height:12px;fill:currentColor}.tk-btn:hover{color:var(--text)}
.tk-btn[aria-pressed="true"] svg rect:last-child{display:none}.tk-btn[aria-pressed="true"] svg rect:first-child{width:7px}
.tk-vp{overflow:hidden;flex:1;-webkit-mask-image:linear-gradient(90deg,transparent,#000 3%,#000 97%,transparent);mask-image:linear-gradient(90deg,transparent,#000 3%,#000 97%,transparent)}
.tk-tr{display:flex;width:max-content;animation:tk var(--dur) linear infinite}
.tk:hover .tk-tr,.tk:focus-within .tk-tr,.tk.paused .tk-tr{animation-play-state:paused}
.tk ul{display:flex;gap:34px;margin:0;padding:0 34px 0 0;list-style:none;white-space:nowrap}
.tk a{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--text2);text-decoration:none}.tk a:hover{color:var(--text)}
.tk .tag{font-size:11px;font-weight:700;padding:1px 7px;border-radius:999px;border:1px solid transparent}
.tag.deal-in{background:rgba(34,197,94,.16);color:#86efac;border-color:rgba(34,197,94,.55)}
.tag.deal-out{background:rgba(236,72,153,.16);color:#f9a8d4;border-color:rgba(236,72,153,.55)}
.tag.loan-in{background:rgba(59,130,246,.18);color:#93c5fd;border-color:rgba(59,130,246,.55)}
.tag.loan-out{background:rgba(168,85,247,.18);color:#d8b4fe;border-color:rgba(168,85,247,.55)}
.tag.inj-short{background:#facc15;color:#221a00}.tag.inj-long{background:#ef4444;color:#fff}
.tag.sus{background:#0a0a0a;color:#e5e7eb;border-color:#94a3b8}.tag.expiring{color:#c3cbc0;border:1px dashed #94a3b8}.tag.warn{background:var(--kit);color:var(--kit-ink)}
@keyframes tk{to{transform:translateX(-50%)}}
.keypop{inset:auto;top:112px;right:var(--gutter);left:auto;margin:0;max-width:440px;background:var(--panel);color:var(--text);border:1px solid var(--line);
 border-radius:8px;padding:14px 16px;box-shadow:0 30px 60px -20px rgba(0,0,0,.8)}
.keypop::backdrop{background:transparent}
.kp-h{margin:0 0 8px;font-family:var(--display);font-stretch:75%;font-weight:800;font-size:18px}
.kp-b{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.kp-b .nlegend{margin:6px 0 0;width:100%}
main.wrap{padding-top:26px}
.page.active{animation:none}
/* home hero */
.hband{position:relative;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);align-items:center;gap:20px;min-height:clamp(520px,34vw,760px);
 background:var(--kit);border-radius:10px;overflow:hidden;color:var(--kit-ink);
 background-image:linear-gradient(100deg,rgba(255,255,255,.07) 0 42%,transparent 42%),linear-gradient(180deg,transparent 60%,rgba(0,0,0,.2))}
.hband::after{content:"";position:absolute;left:0;right:0;bottom:0;height:5px;background:var(--gold)}
.hb-txt{padding:40px 0 40px 44px;position:relative;z-index:1}
.hb-k{margin:0;font-family:var(--display);font-stretch:75%;font-weight:600;font-size:16px;color:color-mix(in srgb,var(--kit-ink) 82%,transparent)}
.hb-club{font-family:var(--display);font-stretch:62%;font-weight:900;font-style:italic;text-transform:uppercase;font-size:clamp(60px,7.4vw,168px);
 line-height:.82;margin:6px 0 22px;color:var(--kit-ink);display:block;letter-spacing:-.005em}
.hb-meta{display:grid;grid-template-columns:repeat(2,auto);justify-content:start;gap:10px 30px;margin:0 0 20px}
.hb-meta dt{font-size:12px;color:color-mix(in srgb,var(--kit-ink) 72%,transparent)}.hb-meta dd{margin:0;font-family:var(--display);font-stretch:75%;font-weight:700;font-size:19px}
.hb-meta dd.sv{font-family:inherit;font-stretch:100%;font-weight:500;font-size:13px;max-width:240px}
.hb-rec{display:flex;align-items:center;gap:14px;margin:0 0 22px}
.hb-pos{font-family:var(--display);font-stretch:62%;font-style:italic;font-weight:900;font-size:64px;line-height:.85}
.hb-of{font-size:13px;line-height:1.35;color:color-mix(in srgb,var(--kit-ink) 85%,transparent)}
.hb-form{display:flex;gap:4px}.hb-form .frm{width:24px;height:24px}
.hb-btn{display:inline-flex;background:var(--kit-ink);color:var(--kit);text-decoration:none;font-family:var(--display);font-stretch:75%;font-weight:800;font-size:18px;
 padding:12px 18px;border-radius:7px;transition:transform .2s}.hb-btn:hover{transform:translateY(-2px)}.hb-btn:active{transform:scale(.97)}
.hb-3d{position:relative;align-self:stretch;display:grid;align-content:center;justify-items:center;
 background:radial-gradient(70% 70% at 50% 55%,rgba(0,0,0,.28),transparent 70%)}
.hb-3d .p3{width:100%;height:clamp(500px,32vw,720px);--pw:clamp(300px,19vw,440px);--rx:52deg}
.hb-3d .p3:focus-visible{outline-color:var(--kit-ink)}
.hb-hint{margin:-26px 0 18px;font-size:12px;color:color-mix(in srgb,var(--kit-ink) 75%,transparent)}
/* best XIs: 2D / 3D */
.xtools{display:flex;gap:4px;margin:-4px 0 14px}
.seg{font:inherit;font-size:13px;font-weight:600;color:var(--muted);background:var(--panel);border:1px solid var(--line);padding:5px 12px;cursor:pointer}
.seg:first-child{border-radius:6px 0 0 6px}.seg:last-child{border-radius:0 6px 6px 0}
.seg[aria-pressed="true"]{color:var(--text);background:var(--panel2);border-color:#46604f}
.xhint{margin-left:12px;font-size:12.5px;color:var(--muted)}
.pitches3d{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.p3w{background:radial-gradient(70% 60% at 50% 55%,rgba(34,96,58,.22),transparent 70%),var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px 0;overflow:hidden}
.p3w .p3{height:600px;margin-top:-70px;--pw:min(340px,24vw);--rx:52deg;perspective-origin:50% 55%}
.pitches[hidden],.pitches3d[hidden]{display:none}
/* tilt-on-hover for cards */
.tilt{transform:perspective(900px) rotateX(var(--ty,0deg)) rotateY(var(--tx,0deg));transition:transform .25s ease-out;will-change:transform}
section[id],.page section{scroll-margin-top:150px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
/* positions laid out in the formation, on a pitch */
.pform{position:relative;display:grid;gap:12px 14px;padding:22px;border-radius:12px;align-items:start;
 grid-template-columns:repeat(3,minmax(0,1fr));
 grid-template-areas:"lw st rw" "dm am cm" "lb cb rb" ". gk .";
 background:repeating-linear-gradient(180deg,#1d5132 0 140px,#1a4a2d 140px 280px);border:1px solid #275a37}
.pform::before{content:"";position:absolute;inset:12px;border:2px solid rgba(255,255,255,.16);border-radius:6px;pointer-events:none}
.pf-box{position:absolute;left:34%;right:34%;height:70px;border:2px solid rgba(255,255,255,.16);pointer-events:none}
.pf-box.t{top:12px;border-top:0}.pf-box.b{bottom:12px;border-bottom:0}
.pform .pcard{position:relative;background:rgba(14,21,18,.95);box-shadow:0 18px 30px -18px rgba(0,0,0,.8)}
.pform .pch{padding:7px 10px;gap:6px}.pform .pch .slot{font-size:20px}.pform .pch .vtag{flex-basis:auto;margin-left:auto}
.prow2.c{display:flex;align-items:center;gap:6px;padding:3px 10px;min-height:27px;font-size:12.5px}
.prow2.c+.prow2.c{border-top:1px solid var(--line2)}
.prow2.c .fam{margin:0;flex:none}.prow2.c .nm{flex:1;min-width:0;font-weight:600;font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.prow2.c .st{flex:none;padding:0}.prow2.c .ag{flex:none;width:20px;text-align:right;color:var(--muted);font-size:11.5px}
.prow2.c .u21,.prow2.c .yt{margin:0;flex:none}
.gpc{flex:none;font-size:10px;font-weight:800;min-width:18px;text-align:center;border-radius:4px;padding:0 4px;color:#93c5fd;border:1px solid #2b4a72}
.gpc.lots{background:#1d3a66;color:#dbeafe}
.wpc{flex:none;width:15px;height:15px;border-radius:50%;display:inline-grid;place-items:center;font-size:10px;font-weight:900;background:rgba(245,158,11,.2);color:#fcd34d}
.potc{flex:none;font-size:10.5px;font-weight:700;color:#93c5fd}
.poslegend{gap:2px 4px;overflow-x:clip}
.poslegend .hint-b .gpc,.poslegend .hint-b .wpc,.poslegend .hint-b .potc,.poslegend .hint-b .u21,.poslegend .hint-b .yt,.poslegend .hint-b .fam,.poslegend .hint-b .sw{margin:0}
/* key items that explain themselves */
.hint{position:relative;display:inline-flex}
.hint-b{all:unset;display:inline-flex;align-items:center;gap:6px;cursor:help;padding:4px 9px;border-radius:999px;border:1px solid transparent;
 color:var(--text2);font-size:12px;transition:background .15s,border-color .15s}
.hint-b u{text-decoration:underline dotted color-mix(in srgb,var(--muted) 80%,transparent);text-underline-offset:3px}
.hint-b:hover,.hint.open .hint-b{background:var(--panel);border-color:var(--line);color:var(--text)}
.hint-b:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
.tip{position:absolute;left:0;top:calc(100% + 8px);z-index:40;width:max-content;max-width:min(320px,calc(100vw - 24px));background:#0b110e;color:var(--text2);
 border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:12.5px;line-height:1.55;box-shadow:0 22px 44px -18px rgba(0,0,0,.95);
 opacity:0;visibility:hidden;transform:translateY(-4px);transition:opacity .15s,transform .15s,visibility 0s linear .15s;pointer-events:none;white-space:normal}
.tip b{color:var(--text)}
.tip::before{content:"";position:absolute;left:var(--ax,18px);top:-6px;width:10px;height:10px;background:#0b110e;border-left:1px solid var(--line);border-top:1px solid var(--line);transform:rotate(45deg)}
.hint:hover .tip,.hint:focus-within .tip,.hint.open .tip{opacity:1;visibility:visible;transform:none;transition-delay:.08s,.08s,0s}
@media (prefers-reduced-motion:reduce){.tip{transition:none}}
.pexp{display:block;width:100%;font:inherit;font-size:12.5px;font-weight:600;color:var(--text2);background:none;border:0;border-top:1px solid var(--line2);padding:8px 10px;text-align:left;cursor:pointer}
.pexp:hover{color:var(--text);background:rgba(255,255,255,.03)}.pexp::after{content:" ▾"}.pexp[aria-expanded="true"]::after{content:" ▴"}
/* league-rank strip */
.rk{display:grid;grid-template-columns:repeat(var(--n),1fr);gap:2px;margin:8px 0 2px}
.rk i{height:7px;border-radius:2px;background:var(--panel2)}.rk i.top{background:rgba(34,197,94,.22)}.rk i.bot{background:rgba(239,68,68,.18)}
.wi.good .rk i.me{background:#22c55e;box-shadow:0 0 0 2px rgba(34,197,94,.35)}.wi.bad .rk i.me{background:#ef4444;box-shadow:0 0 0 2px rgba(239,68,68,.35)}
.rk-ends{display:flex;justify-content:space-between;font-size:10.5px;color:var(--muted);margin-bottom:2px}
/* sortable tables */
table.sortable th button{all:unset;cursor:pointer;display:inline-flex;align-items:center;gap:4px;border-radius:3px}
table.sortable th button:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
table.sortable th button::after{content:"↕";font-size:10px;opacity:.35}
table.sortable th[aria-sort="ascending"] button::after{content:"▲";opacity:1;color:var(--gold)}
table.sortable th[aria-sort="descending"] button::after{content:"▼";opacity:1;color:var(--gold)}
table.sortable th[aria-sort] {color:var(--text)}
/* show more / folded sections */
.clipped .xtra{display:none}
.morebtn{display:flex;align-items:center;justify-content:center;gap:6px;width:100%;margin-top:10px;font:inherit;font-size:13px;font-weight:600;color:var(--text2);
 background:var(--panel);border:1px dashed var(--line);border-radius:6px;padding:9px 12px;cursor:pointer;transition:color .15s,border-color .15s}
.morebtn:hover{color:var(--text);border-color:#46604f;border-style:solid}
.morebtn::after{content:"▾";font-size:11px}.morebtn[aria-expanded="true"]::after{content:"▴"}
details.fold>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:12px;border-radius:6px}
details.fold>summary::-webkit-details-marker{display:none}
details.fold>summary h2{margin:0}
details.fold>summary::after{content:"Show";margin-left:auto;flex:none;font-size:12.5px;font-weight:600;color:var(--text2);border:1px solid var(--line);border-radius:6px;padding:5px 12px;background:var(--panel)}
details.fold>summary:hover::after{color:var(--text);border-color:#46604f}
details.fold[open]>summary::after{content:"Hide"}details.fold[open]>summary{margin-bottom:16px}
/* key figures that filter a list */
.fin.k5{grid-template-columns:repeat(5,minmax(0,1fr));margin-bottom:12px}
button.tile{font:inherit;color:inherit;text-align:left;border:0;border-radius:0;cursor:pointer;position:relative;transition:background .15s}
button.tile:hover{background:var(--panel2)}
button.tile::after{content:"Filter";position:absolute;top:12px;right:14px;font-size:10.5px;font-weight:700;color:var(--muted);border:1px solid var(--line);border-radius:999px;padding:0 8px}
button.tile[aria-pressed="true"]{background:color-mix(in srgb,var(--kit) 14%,var(--panel));box-shadow:inset 0 -3px 0 var(--kit)}
button.tile[aria-pressed="true"]::after{content:"Showing";color:var(--text);border-color:var(--kit)}
.ldrs .who{color:var(--text);font-weight:700;font-size:14.5px;margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ldrs .val{font-variant-numeric:tabular-nums}
/* squad list: search, folding groups, sticky header */
.fsearch{flex:0 1 300px;min-width:0;background:var(--bg);border:1px solid var(--line);color:var(--text);border-radius:6px;padding:6px 10px;font:inherit;font-size:13px}
.fsearch::placeholder{color:var(--muted)}
.gtog{all:unset;cursor:pointer;display:inline-flex;align-items:center;gap:8px}
.gtog::before{content:"▾";font-family:"Archivo",sans-serif;font-stretch:100%;font-size:14px;line-height:1;color:var(--muted);transition:transform .2s}.gtog[aria-expanded="false"]::before{transform:rotate(-90deg)}
.gtog:focus-visible{outline:2px solid var(--gold);outline-offset:3px;border-radius:3px}
.gn{font-family:"Archivo",sans-serif;font-stretch:100%;font-size:11px;font-weight:700;background:var(--panel2);border-radius:3px;padding:0 6px;color:var(--text2)}
.squad.sticky-h{overflow:visible}
.squad.sticky-h thead th{position:sticky;top:var(--ahh,136px);z-index:3}
.squad.sticky-h thead th:first-child{border-top-left-radius:6px}.squad.sticky-h thead th:last-child{border-top-right-radius:6px}
.squad tr.nomatch td .fchip{margin-left:8px}
.abar{display:inline-block;width:44px;height:5px;border-radius:3px;margin-right:10px;vertical-align:middle;
 background:linear-gradient(90deg,var(--kit) var(--w),var(--panel2) var(--w))}
/* transfers: month-by-month timeline */
.tline{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:18px 14px;margin-bottom:6px}
.tlm{position:relative;padding-top:24px;min-width:0}
.tlm::before{content:"";position:absolute;left:0;right:-14px;top:6px;height:2px;background:var(--line)}
.tlm:last-child::before{right:0}
.tlm::after{content:"";position:absolute;left:0;top:1px;width:12px;height:12px;border-radius:50%;background:var(--kit);box-shadow:0 0 0 4px color-mix(in srgb,var(--kit) 22%,transparent)}
.tlh{display:flex;align-items:baseline;gap:8px;margin-bottom:8px}
.tlh b{font-family:var(--display);font-stretch:75%;font-weight:800;font-size:20px}.tlh span{font-size:12px;color:var(--muted)}
.tlm ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px}
.tlm li{display:flex;gap:9px;align-items:flex-start;background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:7px 10px}
.tlm .tag{flex:none;margin-top:1px;font-size:11px;font-weight:700;padding:1px 7px;border-radius:999px;white-space:nowrap}
.tlm li div{min-width:0}.tlm li.grp div span{line-height:1.5;margin-top:2px;color:var(--text2)}.tlm li b{display:block;font-size:13px}.tlm li div span{display:block;font-size:11.5px;color:var(--muted)}
.deals{align-items:start}
/* tactical fit: role picker */
.rolepick{display:grid;grid-template-columns:minmax(280px,360px) minmax(0,1fr);gap:18px;align-items:start}
.rpitch{position:relative;aspect-ratio:68/100;border-radius:10px;border:1px solid #275a37;
 background:repeating-linear-gradient(180deg,#1d5132 0 10%,#1a4a2d 10% 20%)}
.rpitch .rl{position:absolute;border:2px solid rgba(255,255,255,.14);pointer-events:none}
.rpitch .rl.half{left:4%;right:4%;top:50%;height:0;border-width:2px 0 0}
.rpitch .rl.circ{left:50%;top:50%;width:26%;aspect-ratio:1;border-radius:50%;transform:translate(-50%,-50%)}
.rpitch .rl.box{left:28%;right:28%;height:11%}.rpitch .rl.box.t{top:2.5%;border-top:0}.rpitch .rl.box.b{bottom:2.5%;border-bottom:0}
.rpk{position:absolute;left:var(--x);top:var(--y);transform:translate(-50%,-50%);width:21%;min-width:62px;display:grid;justify-items:center;gap:1px;
 font:inherit;color:var(--text);background:rgba(14,21,18,.94);border:1px solid var(--line);border-radius:7px;padding:5px 4px 6px;cursor:pointer;
 box-shadow:0 10px 20px -12px rgba(0,0,0,.8);transition:transform .15s,border-color .15s,box-shadow .15s}
.rpk b{font-family:var(--display);font-stretch:75%;font-weight:800;font-style:italic;font-size:13px;line-height:1;color:var(--muted)}
.rpk i{font-style:normal;font-weight:800;font-size:16px;line-height:1.15;font-variant-numeric:tabular-nums}
.rpk span{font-size:10.5px;color:var(--text2);max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rpk.good i{color:#4ade80}.rpk.bad i{color:#fca5a5}
.rpk:hover{border-color:#46604f;transform:translate(-50%,-50%) translateY(-2px)}
.rpk:active{transform:translate(-50%,-50%) scale(.96)}
.rpk[aria-selected="true"]{border-color:var(--gold);box-shadow:0 0 0 2px var(--gold),0 14px 24px -12px rgba(0,0,0,.9);z-index:2}
.rpk[aria-selected="true"] b{color:var(--gold)}
.rpcap{font-size:12px;color:var(--muted);margin:8px 2px 0;line-height:1.5}
.rpcards .fcard .ftable td{padding:7px 4px}
/* sandbox: one score bar that stays in view, grouped roster */
.sbtop{position:sticky;top:calc(var(--ahh,136px) + 8px);z-index:6;display:flex;align-items:center;gap:22px;background:var(--panel);
 border:1px solid var(--line);border-radius:8px;padding:10px 16px;margin-bottom:14px;box-shadow:0 18px 30px -24px rgba(0,0,0,.9)}
.sbscore{flex:none}.sbscore .lbl{font-family:var(--display);font-stretch:75%;font-size:13px;color:var(--muted)}
.sbscore .val{display:inline-block;font-family:var(--display);font-stretch:62%;font-weight:800;font-size:30px;line-height:1.05}
.sbscore .of{color:var(--muted);font-family:"Archivo",sans-serif;font-stretch:100%;font-size:14px;font-weight:500}
.sbscore .sub{color:var(--muted);font-size:12px}
.sbtop .sbwarn{flex:1;min-width:0;border-left:1px solid var(--line);padding-left:18px}
.sbtop .sbbtns{flex:none}
.sbg{grid-column:1/-1;display:flex;align-items:baseline;gap:8px;margin:14px 0 2px;font-family:var(--display);font-stretch:75%;font-weight:800;font-size:16px;color:var(--text2)}
.sbg span{font-family:"Archivo",sans-serif;font-stretch:100%;font-size:11px;font-weight:700;background:var(--panel2);border-radius:3px;padding:0 6px}
.sbg em{font-family:"Archivo",sans-serif;font-stretch:100%;font-style:normal;font-weight:400;font-size:12px;color:var(--muted)}
button.sbg{all:unset;grid-column:1/-1;display:flex;align-items:baseline;gap:8px;margin:14px 0 2px;padding:8px 0;cursor:pointer;border-top:1px solid var(--line2);
 font-family:var(--display);font-stretch:75%;font-weight:800;font-size:16px;color:var(--text2)}
button.sbg::before{content:"▾";font-size:11px;font-family:"Archivo",sans-serif;transition:transform .2s}
button.sbg[aria-expanded="false"]::before{transform:rotate(-90deg)}
button.sbg:hover{color:var(--text)}button.sbg:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
/* training: next weeks as a timeline */
.tnext li{position:relative;padding:3px 0 9px 20px}
.tnext li::before{content:"";position:absolute;left:3px;top:9px;width:8px;height:8px;border-radius:50%;background:var(--line);border:1px solid #46604f}
.tnext li:first-child::before{background:var(--kit);border-color:var(--kit);box-shadow:0 0 0 4px color-mix(in srgb,var(--kit) 22%,transparent)}
.tnext li::after{content:"";position:absolute;left:7px;top:19px;bottom:-3px;width:2px;background:var(--line)}
.tnext li:last-child::after{display:none}
@media (max-width:1180px){.pform{grid-template-columns:repeat(2,minmax(0,1fr));grid-template-areas:"st st" "lw rw" "am am" "dm cm" "lb rb" "cb cb" "gk gk"}.pf-box{display:none}}
@media (max-width:1100px){.ah-club b{display:none}.ah-nav .k{display:none}.ah-nav a{padding:0 9px}.ah-live span{display:none}}
@media (max-width:1100px){.fin.k5{grid-template-columns:repeat(6,minmax(0,1fr))}.fin.k5>*{grid-column:span 2}.fin.k5>:nth-child(n+4){grid-column:span 3}}
@media (max-width:760px){
 .fin.k5{grid-template-columns:repeat(2,minmax(0,1fr))}.fin.k5>*,.fin.k5>:nth-child(n+4){grid-column:auto}.fin.k5>:last-child{grid-column:1/-1}
 .squad.sq,.squad.stats{display:table}.squad .lo{display:none}.squad td,.squad th{padding:7px 6px}.abar{display:none}
 .frow.ftop{flex-wrap:wrap}.fsearch{flex:1 1 100%}
 .rolepick{grid-template-columns:minmax(0,1fr)}.rpitch{width:100%;max-width:420px;margin:0 auto}
 .squad td.bd .badge{white-space:normal;display:inline-block;max-width:100%}.squad td.bd{min-width:0}
 .sbtop{position:static;flex-wrap:wrap;gap:10px}.sbtop .sbwarn{border-left:0;padding-left:0;flex-basis:100%}
 details.fold>summary{align-items:flex-start}
}
@media (max-width:860px){
 .ah{backdrop-filter:none;-webkit-backdrop-filter:none;background:#0e1512}.ah-row{gap:12px}.ah-nav{position:fixed;left:0;right:0;bottom:0;height:58px;z-index:60;background:rgba(14,21,18,.97);border-top:1px solid var(--line);
  justify-content:space-around;padding-bottom:env(safe-area-inset-bottom)}
 .ah-nav a{flex-direction:column;justify-content:center;gap:0;font-size:13px;padding:0 4px}.ah-nav a::after{top:-1px;bottom:auto}
 .ah-nav .count{position:absolute;top:6px;right:0;font-size:10px;padding:0 4px;line-height:14px}
 body.app{padding-bottom:70px}.ah-sub{overflow-x:auto}
 .hband{grid-template-columns:1fr}.hb-txt{padding:28px 22px 0}.hb-3d .p3{height:400px;--pw:250px;--sc:.86}
 .keypop{top:100px;right:12px;left:12px;max-width:none}
 .pform{grid-template-columns:1fr;grid-template-areas:"st" "lw" "am" "rw" "dm" "cm" "lb" "cb" "rb" "gk";padding:16px}.pf-box{display:none}
 .pitches3d{grid-template-columns:1fr}.p3w .p3{height:460px;--pw:250px}.xhint{display:none}
 .ptitle{flex-wrap:wrap;gap:2px 10px}.sbgrid>*,.pitchwrap{min-width:0}
 .prow{gap:4px}.prow .pchip,.prow .pchip.sb,.prow .pchip.cmp{flex:1 1 0;min-width:0;width:auto;padding:5px 3px}.prow .pchip b{font-size:12px}
 .pchip.sb select{width:100%;min-width:0;max-width:100%;font-size:11px}
 .pitches .pchip .badge{display:none}
}
@media (prefers-reduced-motion:reduce){.tk-tr{animation:none}.tk-vp{overflow-x:auto}.tk ul[aria-hidden]{display:none}.tk-btn{display:none}.tilt{transition:none}}
/* phone-only parts (shown by PHONE_CSS) */
.ni,.ah-more,.ah-title,.ph-only{display:none}
.pkey-fold>summary{display:none}
"""

# ---------------------------------------------------------------------------------------------
# Looks: switchable themes from the design research. "orig" is the first design and needs no CSS.
# Each look is scoped to :root[data-theme="X"] by scope_css(); the choice lives in localStorage ("fm27-theme").
THEMES = [("orig", "Original", "The design you started with"),
          ("A", "Matchday programme", "Editorial: light paper, print rules, serif notes"),
          ("B", "Floodlit glass", "Frosted panels over a night pitch"),
          ("C", "Scoreboard", "Mono numbers, LED strips, one signal green"),
          ("D", "Sticker album", "Bold outlines, hard shadows, mown pitch"),
          ("E", "Glass + scoreboard", "Glass frame, scoreboard data (B and C)")]
THEME_KEYS = [k for k, _, _ in THEMES]

# (family, file, weight range, style, extra descriptors, latin-ext file or None)
THEME_FONTS = [("Newsreader", "font-newsreader", "200 800", "normal", "", "font-newsreader-ext"),
               ("Newsreader", "font-newsreader-italic", "200 800", "italic", "", None),
               ("Martian Mono", "font-martian-mono", "100 800", "normal", "font-stretch:75% 112.5%;", None),
               ("Bricolage Grotesque", "font-bricolage", "200 800", "normal", "", "font-bricolage-ext"),
               ("Hanken Grotesk", "font-hanken", "100 900", "normal", "", "font-hanken-ext"),
               ("JetBrains Mono", "font-jetbrains-mono", "100 800", "normal", "", None),
               ("Doto", "font-doto", "100 900", "normal", "", None),
               ("Geist", "font-geist", "100 900", "normal", "", "font-geist-ext"),
               ("Geist Mono", "font-geist-mono", "100 900", "normal", "", None),
               ("Big Shoulders", "font-big-shoulders", "100 900", "normal", "", "font-big-shoulders-ext"),
               ("Big Shoulders Stencil", "font-big-shoulders-stencil", "900", "normal", "", None),
               ("Schibsted Grotesk", "font-schibsted", "400 900", "normal", "", "font-schibsted-ext")]
LATIN = ("U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,"
         "U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD")
LATIN_EXT = ("U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,"
             "U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF")


def theme_font_css() -> str:
    """@font-face for the looks' fonts. Browsers only download a face once something on screen uses it."""
    out = []
    for fam, file, wght, style, extra, ext in THEME_FONTS:
        for f, rng in ((file, LATIN), (ext, LATIN_EXT)):
            if f:
                out.append(f'@font-face{{font-family:"{fam}";src:url({asset(f + ".woff2")}) format("woff2");font-weight:{wght};'
                           f'font-style:{style};font-display:swap;{extra}unicode-range:{rng}}}')
    return "".join(out)


def scope_css(css: str, key: str) -> str:
    """Prefix every selector with :root[data-theme="key"] (inside @media/@supports too)."""
    return prefix_css(css, f':root[data-theme="{key}"]')


def prefix_css(css: str, pre: str) -> str:
    """Prefix every selector with `pre`; :root/html selectors are joined onto it."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def one(sel: str) -> str:
        sel = sel.strip()
        if sel.startswith(":root"):
            return pre + sel[5:]
        if sel.startswith("html"):
            return pre + sel[4:]
        return f"{pre} {sel}"

    def split(head: str) -> list[str]:
        parts, depth, cur = [], 0, ""
        for ch in head:
            depth += ch == "("
            depth -= ch == ")"
            if ch == "," and depth == 0:
                parts.append(cur)
                cur = ""
            else:
                cur += ch
        return parts + [cur]

    def walk(s: str) -> str:
        res, i = [], 0
        while True:
            j = s.find("{", i)
            if j < 0:
                return "".join(res)
            head, depth, k = s[i:j].strip(), 1, j + 1
            while depth:
                depth += (s[k] == "{") - (s[k] == "}")
                k += 1
            body = s[j + 1:k - 1]
            if head.startswith(("@media", "@supports", "@container", "@starting-style")):
                res.append(f"{head}{{{walk(body)}}}")
            elif head.startswith("@"):
                res.append(f"{head}{{{body}}}")
            else:
                res.append(",".join(one(x) for x in split(head)) + "{" + body.strip() + "}")
            i = k
    return walk(css)


# shared by the two light looks (A, D): the dark-theme pastel text colours turned into readable inks
LIGHT_FIX = r"""
.badge.loan-in,.tag.loan-in{background:rgba(59,130,246,.12);color:#1d4ed8;border-color:rgba(59,130,246,.6)}
.badge.loan-out,.tag.loan-out{background:rgba(168,85,247,.12);color:#7e22ce;border-color:rgba(168,85,247,.6)}
.badge.deal-in,.tag.deal-in{background:rgba(34,197,94,.14);color:#15803d;border-color:rgba(34,197,94,.65)}
.badge.deal-out,.tag.deal-out{background:rgba(236,72,153,.12);color:#be185d;border-color:rgba(236,72,153,.6)}
.badge.sus,.tag.sus{background:#1f2937;color:#fff;border-color:#1f2937}
.badge.expiring,.tag.expiring{color:var(--text2);border-color:#6b7280}
.vcard.red .vtitle,.who em.none,.pchip.empty b,.sbwarn .bad,.pchip.sb b.none,.fitv.bad b,.wh.no,.pcl.no,.wk,.dl.down,.rpk.bad i,.fam.X,.trend.down{color:#b91c1c}
.vcard.amber .vtitle,.wp,.mis .mwhy,.wk.st,.count.amber,.wpc,.bsn,.fam.C,.stats .avg.lo,.notes,.ftable th.ak.sty,.kc.sty{color:#a16207}
.okchip b,.wh.ok,.pcl.ok,.okk,.stats .avg.hi,.dl.up,.rpk.good i,.trend.up{color:#15803d}
.u21,.gpc,.potc,.potl,.gp{color:#1d4ed8;border-color:rgba(29,78,216,.45)}
.gpc.lots,.gp.lots{background:#1d4ed8;color:#fff}
.pot .stars .on{color:#2563eb}.pot{border-color:rgba(37,99,235,.6)}
.vtag.red{background:rgba(239,68,68,.14);color:#b91c1c}.vtag.amber{background:rgba(245,158,11,.18);color:#92400e}
.vtag.green{background:rgba(16,185,129,.14);color:#047857}
.dcol.deal-in h3{color:#15803d}.dcol.deal-out h3{color:#be185d}.dcol.loan-out h3{color:#7e22ce}.dcol.loan-in h3{color:#1d4ed8}
.kc.ip,.ftable th.ak.ip{color:#1d4ed8}.kc.oop,.ftable th.ak.oop{color:#b91c1c}.kc.both,.ftable th.ak.both{color:#7e22ce}
.a1{background:rgba(239,68,68,.22);color:#7f1d1d}.a2{background:rgba(245,158,11,.24);color:#78350f}.a3{background:rgba(0,0,0,.05);color:var(--text2)}
.a4{background:rgba(34,197,94,.16);color:#14532d}.a5{background:rgba(34,197,94,.34);color:#14532d}
.squad tr.loan-out td{color:#6b5b86}
.ses{color:#fff}.ses.rest{background:#d4d4cc;color:var(--text)}.ses.extra{background:#e4e4de;color:var(--muted)}
.sbp .sl i.N{background:var(--text);color:var(--bg)}
.xi,.pc em,.presskey,.sbp.inxi .sbn b::after{color:#fff}
.fz{background:rgba(202,138,4,.12);border-color:rgba(202,138,4,.5)}
.teamrow td{background:rgba(0,0,0,.04)}
.pchip.empty{background:rgba(239,68,68,.08)}
.livebar{background:var(--panel);color:var(--text)}
.ah-live i{box-shadow:0 0 0 3px rgba(34,197,94,.2)}
"""

# A. Matchday programme: the report as a printed team sheet
THEME_A = r"""
:root{color-scheme:light;--bg:#F4F4F0;--bg2:#EAEAE4;--panel:#F4F4F0;--panel2:#E6E6DF;--line:#1A1A17;--line2:#D3D3CB;
 --text:#151512;--text2:#3D3D38;--muted:#66665E;--star:var(--kit-l);--star0:#CDCDC5;--gold:#151512;
 --display:"Archivo","Arial Narrow",system-ui,sans-serif;--serif:"Newsreader",Georgia,serif;--mono:"Martian Mono",ui-monospace,monospace}
body{background:var(--bg);color:var(--text)}
::selection{background:var(--text);color:var(--bg)}
.ah{background:var(--bg);backdrop-filter:none;-webkit-backdrop-filter:none;border-bottom:3px solid var(--line)}
.ah-brand span{font-stretch:125%;font-weight:800;font-size:17px;letter-spacing:-.01em}
.ah-brand small,.ah-nav .k{font-family:var(--mono);font-stretch:87.5%;font-size:10px}
.ah-nav a{font-stretch:100%;font-weight:600;font-size:15px}
.ah-nav a::after{bottom:-3px;height:3px;background:var(--kit-l)}
.ah-club,.ah-btn,.count,.hint-b,.lk-o{border-radius:0}
.ah-club{border-color:var(--line)}
.ah-btn{background:transparent;border-color:var(--line);color:var(--text)}
.ah-btn:hover{background:var(--text);color:var(--bg);border-color:var(--text)}
.ah-sub{border-top-color:var(--line2)}.ah-sub a{border-radius:0}.ah-sub a:hover{background:none}
.ah-sub a[aria-selected="true"]{background:none;box-shadow:inset 0 -2px 0 var(--text)}
.ah-sub.note span{font-family:var(--serif);font-style:italic;font-size:14.5px}
.tk{border-top-color:var(--line2)}
.count{font-family:var(--mono);background:var(--panel2)}
h2{font-stretch:125%;font-weight:800;font-size:clamp(30px,2.7vw,46px);letter-spacing:-.035em;line-height:.95}
h2 .h2sub,.h2sub{font-family:var(--serif);font-style:italic;font-size:15.5px;color:var(--text2);letter-spacing:0}
.page>section:not(.hband){border-top:3px solid var(--line);padding-top:16px}
p,.wt,.insights,.explain,.tr1 p,.sbwarn,.mwhere,.pk-why,.rpcap,footer,.tnote,.allgood,.halfnote,.fair{font-family:var(--serif)}
.vcard p,.wt,.tr1 p,.explain,.insights ul{font-size:15px;line-height:1.5}
.squad th,.ftable th,.tile .lbl,.wr,.rk-ends,.tl,.fl,.tlh span,.pctop span,.ah-live,.xhint,.fcount,.pitchcap>span,.look .lk,.tch span,.who .wl,.sbscore .lbl{
 font-family:var(--mono);font-stretch:87.5%;font-style:normal;font-weight:500;font-size:10.5px;letter-spacing:0}
.squad .r,.ftable td,.tile .of,.wl span,.sbscore .of,.rpk i,.av{font-family:var(--mono);font-stretch:87.5%}
.squad .r,.ftable td{font-size:12px}
.vcard,.okchip,.tile,.dcol,.filters,.sblist,.tcard,.trec,.wi,.insights,.perfcard,.mis,.fcard,.subnav,.explain,.allgood,.tlm li,.p3w,.sbtop,.morebtn{
 background:transparent;border-style:solid;border-width:1px 0 0;border-top-color:var(--line);border-radius:0;box-shadow:none}
.vcard,.okchip,.mis,.allgood,.wi,.trec{border-left-width:4px;padding-left:14px}
.vcard.red,.vcard.amber{background:transparent}
.sbtop{background:var(--bg);border-bottom:1px solid var(--line)}
.fin{background:transparent;border:0;border-top:1px solid var(--line);border-radius:0;gap:0}
.tile{border-width:0 0 0 1px;border-left-color:var(--line2)}.tile:first-child{border-left-width:0}
.tile .val{font-style:italic;font-weight:900;font-size:52px}
button.tile:hover{background:var(--panel2)}button.tile[aria-pressed="true"]{background:var(--panel2);box-shadow:inset 0 -3px 0 var(--text)}
button.tile::after{border-radius:0;font-family:var(--mono);border-color:var(--line)}
button.tile[aria-pressed="true"]::after{border-color:var(--text)}
.pcard{background:transparent;border-style:solid;border-width:4px 0 0;border-radius:0}
.squad{background:transparent;border:0;border-top:2px solid var(--line);border-radius:0}
.squad th{background:var(--bg);border-bottom:1px solid var(--line)}
.squad.sticky-h thead th:first-child,.squad.sticky-h thead th:last-child{border-radius:0}
.squad tr.grp td{background:var(--bg2);font-stretch:100%}
.dcol h3{border-bottom:1px solid var(--line2)}
.fchip,.seg,.rmx,details.fold>summary::after,.morebtn{border-radius:0;background:transparent;border-color:var(--line);color:var(--text)}
.fchip.on,.seg[aria-pressed="true"],.fchip.mode.on{background:var(--text);color:var(--bg);border-color:var(--text)}
input,select,.fsearch,.pk-list,.pk-tray,.pk-chip{background:#fff;color:var(--text);border-color:var(--line);border-radius:0}
.badge,.tag,.vtag,.kc,.wk,.pc,.fz{border-radius:2px}
.frm{border-radius:0;font-family:var(--mono);font-size:10px}
.frm.W{background:var(--text)}.frm.D{background:#9a9a90}.frm.L{background:var(--kit-l)}
.rec .big{color:var(--kit-l);font-size:84px}
.sbscore .val{font-style:italic;font-weight:900}
.rk{gap:3px}.rk i{height:9px;border-radius:0;background:transparent;box-shadow:inset 0 0 0 1px var(--line)}
.rk i.top,.rk i.bot{background:transparent}
.wi.good .rk i.me{background:var(--text);box-shadow:none}.wi.bad .rk i.me{background:var(--kit-l);box-shadow:none}
.pitch,.pform,.rpitch{background:var(--bg);border:1px solid var(--line);border-radius:0}
.lines,.lines .half,.lines .circle,.lines .box,.pform::before,.pf-box,.rpitch .rl{border-color:rgba(21,21,18,.5)}
.pchip,.rpk,.pform .pcard{background:var(--bg);border:1px solid var(--line);border-radius:0;box-shadow:none}
.pform .pcard{border-top-width:4px}
.pchip .ps,.rpk b{color:var(--text2);font-family:var(--mono);font-style:normal;font-size:10px;font-stretch:87.5%}
.rpk[aria-selected="true"]{box-shadow:0 0 0 2px var(--text);border-color:var(--text)}.rpk[aria-selected="true"] b{color:var(--text)}
.p3-pitch{background:#E7E7E0;box-shadow:0 0 0 14px #DCDCD4,0 50px 80px -30px rgba(0,0,0,.25)}
.p3-pitch::before,.p3-l{border-color:rgba(21,21,18,.55)}
.p3-card{background:var(--bg);border:1px solid var(--line);border-radius:0;box-shadow:0 10px 18px -12px rgba(0,0,0,.4)}
.p3-card b{border-radius:0;background:var(--kit-l);color:#fff}
.p3-card .nm{color:var(--text)}
.p3-sh{opacity:.3}
.hband{border-radius:0}.hband::after{background:var(--line);height:4px}
.hb-btn{border-radius:0}
.tip{background:var(--bg);color:var(--text2);border-color:var(--line);border-radius:0;box-shadow:6px 6px 0 rgba(0,0,0,.08)}
.tip::before{background:var(--bg);border-color:var(--line)}
.keypop,.lookpop{background:var(--bg);border:1px solid var(--line);border-radius:0;box-shadow:8px 8px 0 rgba(0,0,0,.1)}
.tlm::before{background:var(--line)}.tlm::after{background:var(--kit-l);box-shadow:none;border-radius:0}
.tnext li:first-child::before{background:var(--text);border-color:var(--text);box-shadow:none}
.abar{background:linear-gradient(90deg,var(--text) var(--w),var(--panel2) var(--w))}
.rot i{background:var(--text)}
.ses{border-radius:0}
.fam{border-radius:0}
.dot{border-radius:0}
@media (max-width:860px){.ah-nav{background:var(--bg);border-top:3px solid var(--line)}.ah-nav a::after{top:-3px}}
"""

# B. Floodlit glass. Frame = page light, header, popovers and hero; data = cards, tables, chips; pitch = the night pitch.
B_FRAME = r"""
:root{color-scheme:dark}
html{background:var(--bg)}
body{background:transparent;font-family:var(--body);font-stretch:100%}
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background:
 radial-gradient(60% 50% at 6% -12%,rgba(255,255,255,.13),transparent 70%),
 radial-gradient(46% 52% at 98% -6%,color-mix(in srgb,var(--kit) 36%,transparent),transparent 70%),
 radial-gradient(80% 60% at 50% 122%,rgba(28,127,70,.42),transparent 70%),
 repeating-linear-gradient(90deg,rgba(255,255,255,.02) 0 110px,transparent 110px 220px),var(--bg)}
body::after{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:.06;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")}
.ah{background:rgba(8,20,14,.58);backdrop-filter:blur(20px) saturate(1.4);-webkit-backdrop-filter:blur(20px) saturate(1.4);border-bottom:1px solid var(--line)}
.ah-brand span{font-family:var(--display);font-stretch:100%;font-weight:700;font-size:17px;letter-spacing:-.01em}
.ah-brand small{font-family:var(--body)}
.ah-nav a{font-family:var(--body);font-stretch:100%;font-weight:600;font-size:15px}
.ah-nav a::after{height:3px;border-radius:3px;box-shadow:0 0 14px var(--kit)}
.ah-sub{border-top-color:var(--line2)}
.ah-sub a{border-radius:999px}.ah-sub a:hover{background:rgba(255,255,255,.06)}
.ah-sub a[aria-selected="true"]{background:rgba(255,255,255,.11);box-shadow:inset 0 1px 0 rgba(255,255,255,.16)}
.ah-btn{background:rgba(255,255,255,.06);border-color:var(--line);border-radius:999px;box-shadow:inset 0 1px 0 rgba(255,255,255,.12)}
.ah-btn:hover{border-color:rgba(255,255,255,.3)}
.ah-club{background:color-mix(in srgb,var(--kit) 18%,transparent);border-color:color-mix(in srgb,var(--kit) 50%,transparent)}
.count{border-radius:999px}
.tk{border-top-color:var(--line2)}
.keypop,.lookpop{background:rgba(12,26,19,.74);backdrop-filter:blur(24px) saturate(1.5);-webkit-backdrop-filter:blur(24px) saturate(1.5);
 border:1px solid var(--line);border-radius:18px;box-shadow:inset 0 1px 0 rgba(255,255,255,.14),0 40px 80px -30px #000}
.tip{background:rgba(12,26,19,.9);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border-color:var(--line);border-radius:12px}
.tip::before{background:rgb(14,28,21)}
h2{font-family:var(--display);font-stretch:100%;font-weight:700;font-size:clamp(24px,2vw,32px);letter-spacing:-.025em}
h3,h4,.kp-h{font-family:var(--display);font-stretch:100%}
.h2sub{font-family:var(--body)}
.hband{color:var(--text);background-color:transparent;border:1px solid var(--line);border-radius:26px;
 background-image:radial-gradient(70% 90% at 0% 0%,color-mix(in srgb,var(--kit) 50%,transparent),transparent 70%),
  linear-gradient(180deg,rgba(255,255,255,.08),rgba(255,255,255,.02));
 box-shadow:inset 0 1px 0 rgba(255,255,255,.18),0 50px 90px -50px #000}
.hband::after{display:none}
.hb-k,.hb-meta dt,.hb-of,.hb-hint{color:var(--text2)}
.hb-club{color:var(--text);font-family:var(--display);font-style:normal;font-stretch:100%;font-weight:800;letter-spacing:-.045em;text-transform:none}
.hb-meta dd{font-family:var(--body);font-stretch:100%;font-weight:600}
.hb-pos{font-family:var(--num);font-style:normal;font-stretch:100%;letter-spacing:-.04em}
.hb-btn{background:var(--text);color:#06120C;border-radius:999px;font-family:var(--body);font-stretch:100%;font-weight:700;font-size:16px}
.hb-3d .p3:focus-visible{outline-color:var(--gold)}
.sbtop{background:rgba(10,24,17,.62);backdrop-filter:blur(20px) saturate(1.4);-webkit-backdrop-filter:blur(20px) saturate(1.4);
 border-color:var(--line);border-radius:18px;box-shadow:inset 0 1px 0 rgba(255,255,255,.12),0 20px 40px -26px #000}
.squad th{background:#0d1e15}
.livebar{background:rgba(12,26,19,.85);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border-radius:12px}
@media (max-width:860px){.ah{background:rgba(8,20,14,.96);backdrop-filter:none;-webkit-backdrop-filter:none}
 .ah-nav{background:rgba(8,20,14,.84);backdrop-filter:blur(18px) saturate(1.4);-webkit-backdrop-filter:blur(18px) saturate(1.4)}}
"""
B_DATA = r"""
.vtitle,.squad th,.ftable th,.tch span,.tl,.wh,.pcl,.dgroup,.sbsec,.look .lk,.fl,.squad tr.grp td,.pchip .ps,.tile .lbl{font-family:var(--body);font-stretch:100%}
.vtitle,.wh,.dgroup,.sbsec{font-family:var(--display);font-weight:700;letter-spacing:-.01em}
.squad th,.ftable th,.tile .lbl{font-weight:600;font-size:12px}
.squad .r,.ftable td,.wl span,.av,.rpk i{font-family:var(--mono)}
.vcard,.okchip,.tile,.pcard,.dcol,.filters,.sblist,.tcard,.trec,.wi,.insights,.perfcard,.mis,.fcard,.subnav,.explain,.allgood,.tlm li,.p3w,.morebtn,.squad{
 background:linear-gradient(180deg,rgba(255,255,255,.075),rgba(255,255,255,.028));border-color:var(--line);border-radius:18px;
 box-shadow:inset 0 1px 0 rgba(255,255,255,.1),0 24px 48px -34px rgba(0,0,0,.9)}
.wi,.tlm li,.okchip{border-radius:14px}
.vcard.red{background:linear-gradient(100deg,rgba(239,68,68,.16),transparent 55%),linear-gradient(180deg,rgba(255,255,255,.07),rgba(255,255,255,.025))}
.vcard.amber{background:linear-gradient(100deg,rgba(245,158,11,.14),transparent 55%),linear-gradient(180deg,rgba(255,255,255,.07),rgba(255,255,255,.025))}
.fin{background:transparent;border:0;gap:12px;overflow:visible;border-radius:0}
.tile .val{font-family:var(--num);font-stretch:100%;font-weight:700;letter-spacing:-.035em}
button.tile:hover{background:rgba(255,255,255,.1)}
button.tile[aria-pressed="true"]{background:color-mix(in srgb,var(--kit) 20%,rgba(255,255,255,.05));box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--kit) 60%,transparent),0 0 30px -10px var(--kit)}
button.tile::after{border-radius:999px}
.squad tr.grp td{background:rgba(255,255,255,.035)}
.squad.sticky-h thead th:first-child{border-top-left-radius:18px}.squad.sticky-h thead th:last-child{border-top-right-radius:18px}
.fchip{border-radius:999px;background:rgba(255,255,255,.06);border-color:var(--line)}
.fchip.on{background:color-mix(in srgb,var(--kit) 30%,transparent);border-color:color-mix(in srgb,var(--kit) 70%,transparent);box-shadow:0 0 16px -4px color-mix(in srgb,var(--kit) 70%,transparent)}
.seg{background:rgba(255,255,255,.05);border-color:var(--line)}.seg:first-child{border-radius:999px 0 0 999px}.seg:last-child{border-radius:0 999px 999px 0}
.seg[aria-pressed="true"]{background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.3)}
details.fold>summary::after{border-radius:999px;background:rgba(255,255,255,.06)}
input,select,.fsearch,.pk-list{background:rgba(0,0,0,.28);border-color:var(--line);border-radius:12px}
.frm{border-radius:999px}
.rec .big{font-family:var(--num);font-style:normal;font-stretch:100%;letter-spacing:-.04em;text-shadow:0 0 40px rgba(255,255,255,.2)}
.sbscore .val{font-family:var(--num);font-stretch:100%;letter-spacing:-.03em}
.rk{gap:3px}.rk i{height:8px;border-radius:999px;background:rgba(255,255,255,.08)}
.rk i.top{background:rgba(79,199,127,.2)}.rk i.bot{background:rgba(239,68,68,.17)}
.wi.good .rk i.me{background:#4FC77F;box-shadow:0 0 12px #4FC77F}.wi.bad .rk i.me{background:#ff5a5a;box-shadow:0 0 12px #ff5a5a}
.tlm::after{box-shadow:0 0 14px var(--kit)}
.tip,.hint-b{border-radius:12px}.hint-b:hover,.hint.open .hint-b{background:rgba(255,255,255,.07)}
.ses{border-radius:10px}
"""
B_PITCH = r"""
.pitch,.pform,.rpitch{background:radial-gradient(55% 45% at 50% 50%,rgba(79,199,127,.16),transparent 70%),
 repeating-linear-gradient(180deg,#0f2b1b 0 52px,#123220 52px 104px);border:1px solid rgba(255,255,255,.1);border-radius:22px}
.rpitch{background:radial-gradient(55% 45% at 50% 50%,rgba(79,199,127,.16),transparent 70%),repeating-linear-gradient(180deg,#0f2b1b 0 10%,#123220 10% 20%)}
.lines,.lines .half,.lines .circle,.lines .box,.pform::before,.pf-box,.rpitch .rl{border-color:rgba(255,255,255,.16)}
.pchip,.rpk,.pform .pcard{background:rgba(9,22,15,.8);border-color:rgba(255,255,255,.14);border-radius:14px;
 box-shadow:inset 0 1px 0 rgba(255,255,255,.12),0 16px 30px -18px #000}
.pform .pcard{border-top-width:3px}
.rpk[aria-selected="true"]{border-color:var(--gold);box-shadow:0 0 0 1px var(--gold),0 0 24px -4px var(--gold)}
.p3w{background:radial-gradient(70% 60% at 50% 55%,rgba(79,199,127,.18),transparent 70%),linear-gradient(180deg,rgba(255,255,255,.06),rgba(255,255,255,.02))}
.p3-pitch{background:repeating-linear-gradient(180deg,#1a4c2f 0 10%,#164229 10% 20%);
 box-shadow:0 0 0 14px #113522,0 0 90px rgba(79,199,127,.18),0 60px 90px -20px rgba(0,0,0,.75)}
.p3-pitch::before,.p3-l{border-color:rgba(255,255,255,.42)}
.p3-card{background:rgba(9,22,15,.9);border-color:rgba(255,255,255,.18);border-radius:10px;box-shadow:inset 0 1px 0 rgba(255,255,255,.14),0 14px 22px -10px rgba(0,0,0,.8)}
.p3-card b{border-radius:9px 9px 0 0;box-shadow:0 0 14px -2px var(--kit)}
"""
THEME_B_TOKENS = r"""
:root{--bg:#06120C;--bg2:rgba(255,255,255,.03);--panel:rgba(255,255,255,.055);--panel2:rgba(255,255,255,.09);--line:rgba(255,255,255,.12);
 --line2:rgba(255,255,255,.07);--text:#F3F5F1;--text2:rgba(243,245,241,.78);--muted:rgba(243,245,241,.56);--star:#F4C95D;--star0:rgba(255,255,255,.18);
 --gold:#7CE0A6;--display:"Bricolage Grotesque",system-ui,sans-serif;--body:"Hanken Grotesk",system-ui,sans-serif;
 --mono:"JetBrains Mono",ui-monospace,monospace;--num:"Bricolage Grotesque",system-ui,sans-serif}
"""

# C. Scoreboard: technical monochrome
C_FRAME = r"""
:root{color-scheme:dark}
body{font-family:var(--body);font-stretch:100%;font-size:13.5px}
.ah{background:rgba(10,11,10,.94);backdrop-filter:none;-webkit-backdrop-filter:none}
.ah-row{height:54px}
.ah-brand span{font-family:var(--body);font-stretch:100%;font-weight:600;font-size:15px;letter-spacing:-.01em}
.ah-brand small{font-family:var(--mono)}
.ah-nav a{font-family:var(--body);font-stretch:100%;font-weight:500;font-size:14px}
@media (min-width:861px){.ah-nav a{padding:0 10px}}
@media (min-width:1101px){.ah-nav .k{display:inline-grid;place-items:center;width:17px;height:17px;border:1px solid var(--line);border-radius:3px;font-family:var(--mono);font-size:10px;opacity:1;color:var(--muted)}}
.ah-nav a[aria-current="true"] .k{border-color:var(--gold);color:var(--gold)}
.ah-nav a::after{height:2px;background:var(--gold)}
.ah-sub a{border-radius:3px;font-size:13px;font-weight:500}
.ah-sub a[aria-selected="true"]{background:var(--panel2);box-shadow:inset 0 -2px 0 var(--gold)}
.ah-btn,.ah-club{border-radius:4px}.count{font-family:var(--mono);border-radius:2px}
.ah-live{font-family:var(--mono);font-size:11.5px}
h2{font-family:var(--body);font-stretch:100%;font-weight:600;font-size:21px;letter-spacing:-.02em}
.h2sub{font-family:var(--mono);font-size:11.5px}
h3,h4,.kp-h{font-family:var(--body);font-stretch:100%;font-weight:600}
.keypop,.lookpop{background:var(--panel);border-radius:6px}
.tip,.tip::before{background:#0d0f0e}.tip{border-radius:4px}
.hband{color:var(--text);background:var(--panel);border:1px solid var(--line);border-radius:6px;
 background-image:linear-gradient(90deg,var(--kit) 0 6px,transparent 6px),repeating-linear-gradient(0deg,rgba(255,255,255,.018) 0 1px,transparent 1px 4px)}
.hband::after{display:none}
.hb-k,.hb-meta dt{font-family:var(--mono);font-stretch:100%;font-size:11.5px;color:var(--muted)}
.hb-club{font-family:var(--num);font-style:normal;font-stretch:100%;font-weight:800;letter-spacing:.01em;color:var(--text);
 font-size:clamp(46px,5.2vw,118px);font-variation-settings:"ROND" 100}
.hb-meta dd{font-family:var(--body);font-stretch:100%;font-weight:600;font-size:17px}
.hb-pos{font-family:var(--num);font-style:normal;font-stretch:100%;color:var(--gold);font-variation-settings:"ROND" 100;text-shadow:0 0 18px rgba(79,199,127,.4)}
.hb-of,.hb-hint{color:var(--muted)}
.hb-btn{background:var(--gold);color:#06120C;border-radius:4px;font-family:var(--body);font-stretch:100%;font-weight:600;font-size:15px}
.hb-3d{background:radial-gradient(70% 70% at 50% 55%,rgba(79,199,127,.07),transparent 70%)}
.hb-3d .p3:focus-visible{outline-color:var(--gold)}
"""
C_DATA = r"""
.vtitle,.wh,.dgroup,.sbsec,.tlh b,.tnow,.pk-tl,.sbg,button.sbg{font-family:var(--body);font-stretch:100%;font-weight:600;letter-spacing:-.01em}
.squad th,.ftable th,.tile .lbl,.tl,.fl,.look .lk,.pchip .ps,.tch span,.rk-ends,.wr,.tlh span,.pctop span,.pcl,.squad tr.grp td,.sbscore .lbl,.who .wl{
 font-family:var(--mono);font-stretch:100%;font-style:normal;font-weight:500;font-size:11px;letter-spacing:0}
.squad .r,.ftable td,.wl span,.av,.tile .of,.sbscore .of,.rpk i,.fitv b,.dcol .dd,.tlm li div span,.who{font-family:var(--mono)}
.ftable td.nm{font-family:var(--body)}
.vcard,.okchip,.tile,.pcard,.dcol,.filters,.sblist,.tcard,.trec,.wi,.insights,.perfcard,.mis,.fcard,.subnav,.explain,.allgood,.tlm li,.p3w,.morebtn,.squad,.sbtop{
 background:var(--panel);border-color:var(--line);border-radius:4px;box-shadow:none}
.vcard,.okchip,.mis,.allgood,.wi{border-left-width:3px}
.vcard.red,.vcard.amber{background:var(--panel)}
.fin{gap:1px;background:var(--line);border-color:var(--line);border-radius:4px}
.tile{border:0;border-radius:0}
.tile .val{font-family:var(--num);font-stretch:100%;font-weight:700;font-size:40px;font-variation-settings:"ROND" 100;letter-spacing:.01em}
.tile .val .stars{font-size:18px}
button.tile[aria-pressed="true"]{background:color-mix(in srgb,var(--gold) 10%,var(--panel));box-shadow:inset 0 -2px 0 var(--gold)}
button.tile[aria-pressed="true"]::after{border-color:var(--gold)}
button.tile::after{border-radius:2px;font-family:var(--mono)}
.squad th{background:var(--panel2)}
.squad.sticky-h thead th:first-child{border-top-left-radius:4px}.squad.sticky-h thead th:last-child{border-top-right-radius:4px}
.squad tr.grp td{background:var(--bg2)}
.squad td:first-child{border-left-width:3px}
.badge,.tag{gap:6px;background:transparent;border:1px solid var(--line);color:var(--text);border-radius:3px;font-weight:500}
.tag{display:inline-flex;align-items:center}
.badge::before,.tag::before{content:"";flex:none;width:7px;height:7px;border-radius:1px;background:var(--c,#6b7280);box-shadow:0 0 6px var(--c,transparent)}
.badge.loan-in,.tag.loan-in{--c:#3b82f6}.badge.loan-out,.tag.loan-out{--c:#a855f7}.badge.deal-in,.tag.deal-in{--c:#22c55e}
.badge.deal-out,.tag.deal-out{--c:#ec4899}.badge.inj-short,.tag.inj-short{--c:#facc15}.badge.inj-long,.tag.inj-long{--c:#ef4444}
.badge.sus,.tag.sus{--c:#94a3b8}.tag.warn{--c:var(--kit)}
.badge.expiring,.tag.expiring{--c:transparent;border-style:dashed}
.badge.arr{border-style:dashed}
.vtag,.kc,.wk,.pc,.fz,.gpc,.u21,.yt,.wp,.gp{border-radius:2px}
.vtag{font-family:var(--mono);font-weight:500}
.fchip,.rmx{border-radius:3px;background:var(--panel2);border-color:var(--line)}
.fchip.on{background:rgba(79,199,127,.12);border-color:rgba(79,199,127,.55);color:var(--text)}
.seg:first-child{border-radius:4px 0 0 4px}.seg:last-child{border-radius:0 4px 4px 0}
.seg[aria-pressed="true"]{border-color:var(--gold)}
details.fold>summary::after{border-radius:4px}
input,select,.fsearch,.pk-list,.pk-tray{border-radius:4px}
.frm{border-radius:2px;font-family:var(--mono);font-size:10px;font-weight:600;background:var(--panel2);color:var(--muted)}
.frm.W{background:rgba(79,199,127,.16);color:var(--gold)}.frm.D{background:var(--panel2);color:var(--muted)}.frm.L{background:rgba(255,77,94,.16);color:#ff7a88}
.rec .big{font-family:var(--num);font-style:normal;font-stretch:100%;color:var(--gold);font-variation-settings:"ROND" 100;text-shadow:0 0 16px rgba(79,199,127,.4)}
.sbscore .val{font-family:var(--num);font-stretch:100%;font-variation-settings:"ROND" 100}
.rk{gap:2px}.rk i{height:12px;border-radius:1px;background:#1A1F1C}.rk i.top{background:#1C2A21}.rk i.bot{background:#2A1D20}
.wi.good .rk i.me{background:var(--gold);box-shadow:0 0 8px rgba(79,199,127,.7)}.wi.bad .rk i.me{background:#ff4d5e;box-shadow:0 0 8px rgba(255,77,94,.65)}
.slot{font-family:var(--mono);font-style:normal;font-weight:600;letter-spacing:.02em}
.vhead .slot{font-size:20px}
.fam{border-radius:2px;font-family:var(--mono);font-weight:600}
.ses{border-radius:3px;font-family:var(--body)}
.dot{border-radius:2px}
.tlm::after{border-radius:2px;background:var(--gold);box-shadow:0 0 10px rgba(79,199,127,.6)}
.tnext li:first-child::before{background:var(--gold);border-color:var(--gold);box-shadow:0 0 8px rgba(79,199,127,.6)}
.abar{background:linear-gradient(90deg,var(--gold) var(--w),var(--panel2) var(--w))}
.rot i{background:var(--gold)}
.hint-b{border-radius:4px}
.pitch,.pform,.rpitch{background-color:#0C100E;border:1px solid var(--line);border-radius:4px;
 background-image:linear-gradient(rgba(255,255,255,.03) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.03) 1px,transparent 1px);background-size:24px 24px}
.lines,.lines .half,.lines .circle,.lines .box,.pform::before,.pf-box,.rpitch .rl{border-color:rgba(79,199,127,.24)}
.pchip,.rpk,.pform .pcard{background:var(--panel2);border:1px solid var(--line);border-radius:3px;box-shadow:none}
.pform .pcard{border-top-width:3px}
.rpk[aria-selected="true"]{border-color:var(--gold);box-shadow:0 0 0 1px var(--gold)}
.p3w{background:radial-gradient(70% 60% at 50% 55%,rgba(79,199,127,.06),transparent 70%),var(--panel)}
.p3-pitch{background-color:#0E1411;background-image:linear-gradient(rgba(79,199,127,.06) 1px,transparent 1px),linear-gradient(90deg,rgba(79,199,127,.06) 1px,transparent 1px);
 background-size:10% 6.5%;box-shadow:0 0 0 14px #0B0F0D,0 0 0 15px #232825,0 60px 90px -20px rgba(0,0,0,.8)}
.p3-pitch::before,.p3-l{border-color:rgba(79,199,127,.5)}
.p3-card{background:#141816;border-color:#2A302C;border-radius:3px}
.p3-card b{border-radius:2px 2px 0 0;font-family:var(--mono);font-style:normal;font-stretch:100%;font-weight:600;font-size:11px;letter-spacing:.05em}
.p3-card .nm{font-family:var(--body);font-stretch:100%;font-weight:500}
"""
THEME_C_TOKENS = r"""
:root{--bg:#0A0B0A;--bg2:#0E100F;--panel:#101211;--panel2:#171A18;--line:#232825;--line2:#1A1E1B;--text:#E7EAE5;--text2:#B5BCB6;
 --muted:#7F8781;--star:#4FC77F;--star0:#2A302C;--gold:#4FC77F;--display:"Geist",system-ui,sans-serif;--body:"Geist",system-ui,sans-serif;
 --mono:"Geist Mono",ui-monospace,monospace;--num:"Doto","Geist Mono",monospace}
"""

# D. Sticker album: bold outlines, hard shadows, club colour as the one loud accent on a mown pitch
THEME_D = r"""
:root{color-scheme:light;--bg:#1C7F46;--bg2:#EFEFEA;--panel:#FFFFFF;--panel2:#F1F1EC;--line:#111111;--line2:#E2E2DB;--text:#111111;--text2:#333330;
 --muted:#5E5E57;--star:#111111;--star0:#D2D2CA;--gold:#111111;--display:"Big Shoulders","Arial Narrow",sans-serif;
 --body:"Schibsted Grotesk",system-ui,sans-serif;--stencil:"Big Shoulders Stencil","Big Shoulders",sans-serif}
html{background:#1C7F46}
body{background:transparent;font-family:var(--body);font-stretch:100%;color:var(--text);font-variant-numeric:normal}
.squad td,.ftable td,.tile .val,.sbscore .val,.rec .big,.hb-pos,.count,.gn{font-variant-numeric:tabular-nums}
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background:repeating-linear-gradient(90deg,#1C7F46 0 96px,#1A7541 96px 192px)}
::selection{background:var(--kit-l);color:#fff}
:focus-visible{outline:3px solid #111;outline-offset:3px}
.ah{background:#fff;backdrop-filter:none;-webkit-backdrop-filter:none;border-bottom:3px solid #111}
.ah-brand span{font-family:var(--display);font-stretch:100%;font-weight:900;font-size:22px;text-transform:uppercase;letter-spacing:.01em}
.ah-brand small{font-family:var(--body);font-weight:700;color:var(--muted)}
.ah-nav a{font-family:var(--body);font-stretch:100%;font-weight:800;font-size:14.5px;color:#333}
.ah-nav .k{opacity:.6}
@media (min-width:861px){.ah-nav{align-items:center;gap:4px}.ah-nav a{height:38px;border:2px solid transparent;border-radius:999px;padding:0 14px}
 .ah-nav a::after{display:none}.ah-nav a:hover{border-color:#111}
 .ah-nav a[aria-current="true"]{background:var(--kit-l);color:#fff;border-color:#111;box-shadow:3px 3px 0 #111}}
.ah-sub{background:#fff;border-top:2px solid #111}
.ah-sub a{border-radius:999px;font-weight:800;color:#333;border:2px solid transparent}
.ah-sub a:hover{background:none;border-color:#111}
.ah-sub a[aria-selected="true"]{background:#111;color:#fff;box-shadow:none}
.ah-sub.note span{font-weight:600;color:var(--muted)}
.tk{background:#111;border-top:0}.tk a{color:#e8e8e2}.tk a:hover{color:#fff}.tk-btn{color:#bbb}.tk-btn:hover{color:#fff}
.ah-btn{background:#fff;border:2px solid #111;border-radius:999px;color:#111;font-weight:800;box-shadow:2px 2px 0 #111;transition:transform .12s,box-shadow .12s}
.ah-btn:hover{transform:translate(-1px,-1px);box-shadow:3px 3px 0 #111;color:#111;border-color:#111}
.ah-btn:active{transform:translate(2px,2px);box-shadow:0 0 0 #111}
.ah-club{border:2px solid #111;background:#fff}
.count{border-radius:999px;background:#111;color:#fff}.count.warn{background:var(--kit-l);color:#fff}.count.amber{background:#F59E0B;color:#111}
.page>section:not(.hband),.page>.subnav,.page>.explain{background:#fff;border:3px solid #111;border-radius:16px;box-shadow:8px 8px 0 #111;padding:20px 22px 22px}
.page>section{margin-top:30px}
h2{font-family:var(--display);font-stretch:100%;font-weight:900;text-transform:uppercase;font-size:clamp(34px,3.1vw,54px);line-height:.88;letter-spacing:.004em}
h2 .h2sub,.h2sub{font-family:var(--body);text-transform:none;font-size:13px;font-weight:600;color:var(--muted);letter-spacing:0}
h3,h4,.vtitle,.wh,.dgroup,.sbsec,.tlh b,.kp-h,.tnow,.pk-tl,.sbg,button.sbg{font-family:var(--display);font-stretch:100%;font-weight:900;text-transform:uppercase;letter-spacing:.01em}
.squad th,.ftable th,.tile .lbl,.tl,.fl,.look .lk,.tch span,.pcl,.squad tr.grp td,.sbscore .lbl{font-family:var(--body);font-stretch:100%;font-style:normal;font-weight:800;font-size:12px}
.vcard,.okchip,.mis,.allgood,.wi,.trec,.pcard{border-style:solid;border-width:2px 2px 2px 7px;border-top-color:#111;border-right-color:#111;border-bottom-color:#111;
 border-radius:12px;box-shadow:4px 4px 0 #111;background:#fff}
.pcard{border-width:6px 2px 2px 2px;border-left-color:#111}
.vcard.red,.vcard.amber{background:#fff}
.dcol,.filters,.sblist,.tcard,.insights,.perfcard,.fcard,.tlm li,.p3w,.squad,.sbtop,.subnav{background:#fff;border:2px solid #111;border-radius:12px;box-shadow:4px 4px 0 #111}
.page>.subnav,.page>.explain{border-width:3px;box-shadow:8px 8px 0 #111}
.sbtop{border-width:3px;box-shadow:6px 6px 0 #111}
.fin{background:transparent;border:0;gap:14px;overflow:visible;border-radius:0}
.tile{background:#fff;border:2px solid #111;border-radius:12px;box-shadow:4px 4px 0 #111}
.tile .val{font-family:var(--display);font-stretch:100%;font-weight:900;font-size:clamp(34px,2.4vw + 16px,54px)}
button.tile{transition:transform .12s,box-shadow .12s}
button.tile:hover{background:#fff;transform:translate(-1px,-1px);box-shadow:5px 5px 0 #111}
button.tile[aria-pressed="true"]{background:var(--kit-l);color:#fff;box-shadow:4px 4px 0 #111}
button.tile[aria-pressed="true"] .lbl,button.tile[aria-pressed="true"] .sub,button.tile[aria-pressed="true"] .of{color:rgba(255,255,255,.85)}
button.tile::after{border:2px solid #111;border-radius:999px;color:#111;background:#fff}
.squad{overflow:hidden}.squad th{background:#111;color:#fff;border-bottom:0}
.squad.sticky-h{overflow:visible}.squad.sticky-h thead th:first-child{border-top-left-radius:10px}.squad.sticky-h thead th:last-child{border-top-right-radius:10px}
.squad td{border-bottom-color:var(--line2)}
.squad tr.grp td{background:var(--bg2);color:#111}
.dcol h3{border-bottom:2px solid #111}
.fchip,.seg,.rmx,.morebtn,details.fold>summary::after,.hb-btn{background:#fff;color:#111;border:2px solid #111;border-radius:999px;font-weight:800;box-shadow:2px 2px 0 #111}
.fchip:active,.seg:active,.morebtn:active{transform:translate(2px,2px);box-shadow:none}
.fchip.on,.seg[aria-pressed="true"],.fchip.mode.on{background:var(--kit-l);color:#fff;border-color:#111}
.seg:first-child,.seg:last-child{border-radius:999px}.xtools{gap:8px}
.morebtn:hover,details.fold>summary:hover::after{border-style:solid;border-color:#111;color:#111}
input,select,.fsearch,.pk-list{background:#fff;color:#111;border:2px solid #111;border-radius:10px}
.fsearch{border-radius:999px}
.badge,.tag{border:2px solid #111;font-weight:800;color:#111}
.badge.loan-in,.tag.loan-in{background:#BFDBFE;color:#111;border-color:#111}.badge.loan-out,.tag.loan-out{background:#E9D5FF;color:#111;border-color:#111}
.badge.deal-in,.tag.deal-in{background:#BBF7D0;color:#111;border-color:#111}.badge.deal-out,.tag.deal-out{background:#FBCFE8;color:#111;border-color:#111}
.badge.inj-short,.tag.inj-short{background:#FDE047;color:#111}.badge.inj-long,.tag.inj-long{background:#EF4444;color:#fff}
.badge.sus,.tag.sus{background:#111;color:#fff}.badge.expiring,.tag.expiring{background:#fff;border-style:dashed}
.tag.warn{background:var(--kit-l);color:#fff}
.badge.arr{border-style:dashed!important}
.frm{border:2px solid #111;border-radius:6px;font-family:var(--display);font-weight:900;font-size:13px;color:#111}
.frm.W{background:#4FC77F}.frm.D{background:#fff}.frm.L{background:var(--kit-l);color:#fff}
.rec .big,.hb-pos{font-family:var(--display);font-style:normal;font-stretch:100%;font-weight:900;text-transform:uppercase;
 -webkit-text-stroke:2px #111;paint-order:stroke fill;text-shadow:4px 4px 0 #111}
.rec .big{color:var(--kit-l);font-size:84px}
.sbscore .val{font-family:var(--display);font-stretch:100%;font-weight:900}
.slot{font-family:var(--display);font-style:normal;font-stretch:100%;font-weight:900}
.rk{gap:3px}.rk i{height:13px;border-radius:3px;background:#fff;border:2px solid #111}
.rk i.top{background:#DCFCE7}.rk i.bot{background:#FEE2E2}
.wi.good .rk i.me{background:#22C55E;box-shadow:none}.wi.bad .rk i.me{background:var(--kit-l);box-shadow:none}
.pitch,.pform,.rpitch{background:repeating-linear-gradient(180deg,#26A258 0 52px,#22924F 52px 104px);border:3px solid #111;border-radius:14px}
.rpitch{background:repeating-linear-gradient(180deg,#26A258 0 10%,#22924F 10% 20%)}
.lines,.lines .half,.lines .circle,.lines .box,.pform::before,.pf-box,.rpitch .rl{border-color:rgba(255,255,255,.5)}
.pchip,.rpk,.pform .pcard{background:#fff;color:#111;border:2px solid #111;border-radius:9px;box-shadow:3px 3px 0 #111}
.pform .pcard{border-top-width:6px}
.pitches .prow .pchip:nth-child(odd){rotate:-1.5deg}.pitches .prow .pchip:nth-child(even){rotate:1.2deg}
.pitches .pchip .ps{display:block;margin:-6px -8px 4px;background:var(--kit-l);color:#fff;font-family:var(--stencil);font-style:normal;font-size:15px;border-bottom:2px solid #111;padding:3px 0 2px;border-radius:7px 7px 0 0}
.pchip .ps,.rpk b{font-family:var(--stencil);font-style:normal;color:#111}
.rpk[aria-selected="true"]{background:var(--kit-l);color:#fff;box-shadow:3px 3px 0 #111;border-color:#111}.rpk[aria-selected="true"] b,.rpk[aria-selected="true"] span{color:#fff}
.p3w{background:#fff}
.p3-pitch{background:repeating-linear-gradient(180deg,#26A258 0 10%,#22924F 10% 20%);box-shadow:0 0 0 12px #1D7F44,0 0 0 15px #111,0 50px 80px -20px rgba(0,0,0,.45)}
.p3-pitch::before,.p3-l{border-color:rgba(255,255,255,.7)}
.p3-card{background:#fff;border:2px solid #111;border-radius:7px;box-shadow:3px 3px 0 #111;padding:0 6px 5px}
.p3-card b{font-family:var(--stencil);font-style:normal;font-weight:900;font-size:14px;border-bottom:2px solid #111;border-radius:5px 5px 0 0;background:var(--kit-l);color:#fff}
.p3-card .nm{color:#111;font-family:var(--body);font-stretch:100%;font-weight:800}
.p3-sh{opacity:.5}
.hband{border:3px solid #111;border-radius:18px;box-shadow:8px 8px 0 #111}
.hband::after{display:none}
.hb-club{font-family:var(--display);font-stretch:100%;font-style:normal;font-weight:900;-webkit-text-stroke:3px #111;paint-order:stroke fill;text-shadow:6px 6px 0 #111}
.hb-pos{color:var(--kit-ink)}
.hb-btn{font-family:var(--body);font-stretch:100%;font-size:16px;box-shadow:4px 4px 0 #111}
.hb-btn:hover{transform:translate(-2px,-2px);box-shadow:6px 6px 0 #111}
.keypop,.lookpop{background:#fff;border:3px solid #111;border-radius:16px;box-shadow:8px 8px 0 #111}
.tip,.tip::before{background:#fff;border-color:#111}.tip{border-width:2px;border-radius:10px;box-shadow:4px 4px 0 #111;color:#333}
.hint-b:hover,.hint.open .hint-b{background:#fff;border-color:#111}
.tlm::before{background:#111;height:3px}.tlm::after{background:var(--kit-l);border:2px solid #111;box-shadow:none}
.tnext li:first-child::before{background:var(--kit-l);border:2px solid #111;box-shadow:none}
.abar{background:linear-gradient(90deg,#111 var(--w),#e4e4dc var(--w))}
.rot i{background:#111}
.ses{border:2px solid #111}
.fam.N{background:#111;color:#fff}
footer{color:rgba(255,255,255,.88);border-top-color:rgba(255,255,255,.35)}
.notes{color:#fde68a}
.livebar{border:2px solid #111;box-shadow:4px 4px 0 #111}
@media (max-width:860px){.ah-nav{background:#fff;border-top:3px solid #111}.ah-nav a[aria-current="true"]{color:var(--kit-l)}
 .page>section:not(.hband),.page>.subnav,.page>.explain{padding:14px;box-shadow:5px 5px 0 #111}}
@media (prefers-reduced-motion:reduce){.ah-btn,button.tile{transition:none}}
"""

# E. Glass + scoreboard: B's frame and night pitch, C's data layer, lighter glass on the cards
THEME_E_TOKENS = r"""
:root{--bg:#06110C;--bg2:rgba(255,255,255,.03);--panel:rgba(255,255,255,.05);--panel2:rgba(255,255,255,.085);--line:rgba(255,255,255,.11);
 --line2:rgba(255,255,255,.065);--text:#EEF2EC;--text2:rgba(238,242,236,.76);--muted:rgba(238,242,236,.54);--star:#4FC77F;--star0:rgba(255,255,255,.16);
 --gold:#4FC77F;--display:"Bricolage Grotesque",system-ui,sans-serif;--body:"Geist",system-ui,sans-serif;
 --mono:"Geist Mono",ui-monospace,monospace;--num:"Doto","Geist Mono",monospace}
"""
E_GLASS = r"""
.vcard,.okchip,.tile,.pcard,.dcol,.filters,.sblist,.tcard,.trec,.wi,.insights,.perfcard,.mis,.fcard,.subnav,.explain,.allgood,.tlm li,.p3w,.morebtn,.squad{
 background:linear-gradient(180deg,rgba(255,255,255,.06),rgba(255,255,255,.022));border-radius:12px;box-shadow:inset 0 1px 0 rgba(255,255,255,.08)}
.vcard.red,.vcard.amber{background:linear-gradient(180deg,rgba(255,255,255,.06),rgba(255,255,255,.022))}
.fin{background:transparent;border:0;gap:10px;border-radius:0;overflow:visible}
.tile{border:1px solid var(--line);border-radius:12px}
.squad th{background:#0c1c14}
.squad.sticky-h thead th:first-child{border-top-left-radius:12px}.squad.sticky-h thead th:last-child{border-top-right-radius:12px}
.sbtop{border-radius:14px}
h2{font-weight:700}
.hb-pos{font-family:var(--num);color:var(--gold);font-variation-settings:"ROND" 100;letter-spacing:0;text-shadow:0 0 22px rgba(79,199,127,.45)}
.hb-club{letter-spacing:-.04em}
.pchip,.rpk,.pform .pcard{border-radius:10px}
.p3-card{border-radius:8px}
.p3-card b{border-radius:7px 7px 0 0}
"""


# every look: wider faces than Archivo, so keep the short table cells on one line
LOOK_COMMON = r"""
button.tile .lbl{padding-right:50px}
@media (min-width:1281px){.squad td.nm,.squad td.exp,.squad td.r,.squad td:nth-child(3),.squad td:has(>.stars){white-space:nowrap}}
.stars .on{color:var(--star)}
"""

# the Look switch itself (not scoped: it follows whichever look is on through the tokens)
LOOK_CSS = r"""
.lookpop{inset:auto;top:112px;right:var(--gutter);left:auto;margin:0;width:min(380px,calc(100vw - 24px));background:var(--panel);color:var(--text);
 border:1px solid var(--line);border-radius:8px;padding:14px 14px 10px;box-shadow:0 30px 60px -20px rgba(0,0,0,.8)}
.lookpop::backdrop{background:transparent}
.lk-sub{margin:-4px 0 10px;font-size:12.5px;color:var(--muted)}
.lk-list{display:grid;gap:4px;border:0;margin:0;padding:0}
.lk-list>legend{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.lk-o{display:grid;grid-template-columns:44px minmax(0,1fr);gap:12px;align-items:center;padding:7px 8px;border-radius:8px;cursor:pointer;border:1px solid transparent}
.lk-o:hover{background:var(--panel2)}
.lk-o input{position:absolute;opacity:0;pointer-events:none}
.lk-o:has(input:checked){border-color:var(--gold);background:var(--panel2)}
.lk-o:has(input:focus-visible){outline:2px solid var(--gold);outline-offset:2px}
.lk-o b{display:block;font-size:13.5px;line-height:1.25}.lk-o small{display:block;font-size:12px;color:var(--muted);line-height:1.35}
.lk-sw{width:44px;height:32px;border-radius:6px;display:grid;place-items:center;font-size:15px;line-height:1;overflow:hidden;box-shadow:0 0 0 1px rgba(127,127,127,.35)}
.lk-sw[data-k="orig"]{background:linear-gradient(135deg,#0e1512 55%,#C8102E 55%);color:#eef1e8;font:italic 900 15px "Archivo",sans-serif;font-stretch:62%}
.lk-sw[data-k="A"]{background:#F4F4F0;color:#151512;font:800 15px "Archivo",sans-serif;font-stretch:125%;box-shadow:inset 0 -4px 0 #C8102E,0 0 0 1px #151512}
.lk-sw[data-k="B"]{background:radial-gradient(80% 90% at 85% 0%,rgba(200,16,46,.6),transparent 60%),#0a1d13;color:#fff;font:700 15px "Bricolage Grotesque",sans-serif}
.lk-sw[data-k="C"]{background:#0A0B0A;color:#4FC77F;font:800 16px "Doto",monospace;font-variation-settings:"ROND" 100;text-shadow:0 0 8px rgba(79,199,127,.6)}
.lk-sw[data-k="D"]{background:repeating-linear-gradient(90deg,#1C7F46 0 8px,#1A7541 8px 16px);color:#111;font:900 15px "Big Shoulders",sans-serif}
.lk-sw[data-k="D"] i{font-style:normal;background:#fff;border:2px solid #111;border-radius:4px;box-shadow:2px 2px 0 #111;padding:0 4px}
.lk-sw[data-k="E"]{background:radial-gradient(80% 90% at 85% 0%,rgba(200,16,46,.55),transparent 60%),#0a1d13;color:#4FC77F;font:800 16px "Doto",monospace;font-variation-settings:"ROND" 100}
.lk-foot{margin:8px 2px 0;font-size:11.5px;color:var(--muted)}
.lk-foot kbd{font:inherit;font-size:11px;border:1px solid var(--line);border-radius:4px;padding:0 5px}
.ah-look b{font-weight:700}
@media (max-width:1100px){.ah-look .lk-cur{display:none}}
@media (max-width:860px){.lookpop{top:100px;right:12px;left:12px;width:auto}}
::view-transition-old(root),::view-transition-new(root){animation-duration:.32s}
"""

THEME_CSS = "".join(scope_css(LOOK_COMMON + css, k) for k, css in (
    ("A", LIGHT_FIX + THEME_A), ("B", THEME_B_TOKENS + B_FRAME + B_DATA + B_PITCH), ("C", THEME_C_TOKENS + C_FRAME + C_DATA),
    ("D", LIGHT_FIX + THEME_D), ("E", THEME_E_TOKENS + B_FRAME + C_DATA + B_PITCH + E_GLASS)))

LOOK_HEAD_JS = ("try{var t=localStorage.getItem('fm27-theme');if(/^[A-E]$/.test(t))document.documentElement.dataset.theme=t;}catch(e){}")

LOOK_JS = r"""
(function(){
const NAMES=__NAMES__,KEYS=Object.keys(NAMES),root=document.documentElement,pop=document.getElementById('lookpop');
const cur=document.getElementById('lookCur'),cur2=document.getElementById('lookCur2');
function now(){return root.dataset.theme||'orig';}
// the home page's previews are real app pages in srcdoc frames: give them the look CSS once, then the same look
function dress(f){let d;try{d=f.contentDocument;}catch(_){return;}if(!d||!d.body||!d.body.classList.contains('mini'))return;
 const css=document.getElementById('looks-css');
 if(css&&!d.getElementById('looks-css')){const st=d.createElement('style');st.id='looks-css';st.textContent=css.textContent;d.head.appendChild(st);}
 const k=now();if(k==='orig')delete d.documentElement.dataset.theme;else d.documentElement.dataset.theme=k;
 const c=d.getElementById('lookCur');if(c)c.textContent=NAMES[k];}
const frames=[...document.querySelectorAll('iframe[srcdoc]')];
frames.forEach(f=>{f.addEventListener('load',()=>dress(f));dress(f);});
function apply(k,save){
 const set=()=>{if(k==='orig')delete root.dataset.theme;else root.dataset.theme=k;
  if(cur)cur.textContent=NAMES[k];if(cur2)cur2.textContent=NAMES[k];
  document.querySelectorAll('.lk-o input').forEach(i=>{i.checked=i.value===k;});frames.forEach(dress);};
 const calm=matchMedia('(prefers-reduced-motion: reduce)').matches;
 if(save&&document.startViewTransition&&!calm)document.startViewTransition(set);else set();
 if(save){try{if(k==='orig')localStorage.removeItem('fm27-theme');else localStorage.setItem('fm27-theme',k);}catch(e){}}
}
apply(now(),false);
document.querySelectorAll('.lk-o input').forEach(i=>i.addEventListener('change',()=>{if(i.checked)apply(i.value,true);}));
addEventListener('keydown',e=>{
 if(e.metaKey||e.ctrlKey||e.altKey||(e.target.closest&&e.target.closest('input,select,textarea,[contenteditable]')))return;
 if(e.key==='l'||e.key==='L'){const i=KEYS.indexOf(now());apply(KEYS[(i+(e.shiftKey?-1:1)+KEYS.length)%KEYS.length],true);}
});
})();
""".replace("__NAMES__", json.dumps({k: n for k, n, _ in THEMES}))


def look_popover() -> str:
    opts = "".join(f'<label class="lk-o"><input type="radio" name="look" value="{k}"{" checked" if k == "orig" else ""}>'
                   f'<span class="lk-sw" data-k="{k}" aria-hidden="true">{"<i>Aa</i>" if k == "D" else "3rd" if k in ("C", "E") else "Aa"}</span>'
                   f'<span><b>{E(n)}</b><small>{E(d)}</small></span></label>' for k, n, d in THEMES)
    return (f'<div id="lookpop" class="lookpop" popover><p class="kp-h">Look</p>'
            f'<p class="lk-sub">Try the redesign ideas. Your choice is saved in this browser.</p>'
            f'<fieldset class="lk-list"><legend class="sr">Look</legend>{opts}</fieldset>'
            f'<p class="lk-foot">Press <kbd>L</kbd> to flick through them.</p></div>')


# The home page in each look. THEME_CSS supplies the tokens, fonts, body background and the 3D pitch;
# these rules handle the page's own parts (nav, hero, story, lists, call to action, launch wipe, cursor).
# The home page is club-neutral, so its accent is the app's pitch green, not a club colour.
LAND_A = r"""
body.landing{font-family:"Archivo",system-ui,sans-serif}
.lnav.solid{background:var(--bg);backdrop-filter:none;-webkit-backdrop-filter:none;box-shadow:0 3px 0 var(--line)}
.lbrand{font-stretch:125%;font-size:17px;letter-spacing:-.01em}
.lnav nav a{color:var(--text2);font-weight:600}
.look-btn,.btn,.btn.sm{border-radius:0}
.btn{background:var(--text);color:var(--bg);box-shadow:none;font-stretch:100%;font-size:19px}
.btn:hover{background:#1C7F46;color:#fff}
.btn.inv{background:var(--bg);color:var(--text)}.btn.inv:hover{background:#fff;color:var(--text)}
.hero{background:none;border-bottom:3px solid var(--line)}
.for{color:#1C7F46;font-family:"Martian Mono",monospace;font-stretch:87.5%;font-weight:500;font-size:13px}
.hero h1{font-stretch:125%;font-weight:800;font-size:clamp(44px,5.4vw,94px);line-height:.92;letter-spacing:-.045em;max-width:13ch}
.lede{font-family:var(--serif);font-size:clamp(18px,1.45vw,22px);line-height:1.5;color:var(--text2)}
.tlink{color:var(--text);text-decoration-thickness:2px}
.hint,.f-demo{font-family:"Martian Mono",monospace;font-stretch:87.5%;font-size:11px}
.story h2,.split h2,.how h2{font-stretch:125%;font-weight:800;font-size:clamp(36px,4.2vw,68px);letter-spacing:-.045em;line-height:.95}
.story-in{border-bottom:3px solid var(--line)}
.st{border-left-color:var(--line2);color:var(--muted)}.st.on{color:var(--text);border-left-color:var(--text)}
.st b{font-stretch:100%;font-weight:700}.st span{font-family:var(--serif);font-size:16px}
.frame{background:var(--bg);border:1px solid var(--line);border-radius:0;box-shadow:14px 14px 0 rgba(21,21,18,.12)}
.scr,.scr iframe{background:var(--bg)}
.cols>div+div{border-left:1px solid var(--line)}
.cols h3{font-stretch:100%;font-weight:800}
.cols li{border-top-color:var(--line2);font-family:var(--serif);font-size:19px}
.does li::before{color:#1C7F46}.wont li::before{color:#b91c1c}
.aside{font-family:var(--serif);font-style:italic;font-size:16px}
.how li{border-top:3px solid var(--line)}
.how li>b{color:#1C7F46}
.how h3{font-stretch:100%}.how p{font-family:var(--serif);font-size:17px}
.cta{background:var(--text);color:var(--bg);background-image:none}
.cta h2{font-stretch:125%;font-style:normal;font-weight:800;letter-spacing:-.05em;font-size:clamp(48px,7.4vw,128px)}
.cta p{color:rgba(244,244,240,.75);font-family:"Martian Mono",monospace;font-stretch:87.5%;font-size:12.5px}
.lfoot{font-family:var(--serif);font-style:italic;font-size:14px;border-top:1px solid var(--line)}
.launch{background:#151512}
.cur{border-color:var(--text);color:var(--text);background:rgba(244,244,240,.6);border-radius:0;backdrop-filter:none}
.skip{background:var(--text);color:var(--bg);border-radius:0}
:focus-visible{outline-color:var(--text)}
"""
# B: floodlit glass on the home page (E reuses it)
LAND_B = r"""
.lnav.solid{background:rgba(8,20,14,.55);backdrop-filter:blur(20px) saturate(1.4);-webkit-backdrop-filter:blur(20px) saturate(1.4);box-shadow:0 1px 0 var(--line)}
.lbrand{font-family:var(--display);font-stretch:100%;font-weight:700;font-size:18px;letter-spacing:-.01em}
.lnav nav a{font-weight:500}
.look-btn{background:rgba(255,255,255,.06);box-shadow:inset 0 1px 0 rgba(255,255,255,.12)}
.btn{background:#F3F5F1;color:#06120C;border-radius:999px;font-family:var(--body);font-stretch:100%;font-weight:700;font-size:18px;
 box-shadow:0 0 0 1px rgba(255,255,255,.4),0 14px 40px -14px rgba(79,199,127,.55)}
.btn:hover{background:#fff}
.btn.inv{background:#F3F5F1;color:#06120C}
.hero{background:radial-gradient(50% 60% at 72% 55%,rgba(79,199,127,.2),transparent 70%)}
.for{color:var(--gold);font-family:var(--body);font-stretch:100%;font-weight:600;font-size:16px}
.hero h1{font-family:var(--display);font-stretch:100%;font-weight:800;font-size:clamp(48px,5.8vw,100px);line-height:.92;letter-spacing:-.05em}
.story h2,.split h2,.how h2{font-family:var(--display);font-stretch:100%;font-weight:700;font-size:clamp(36px,4.2vw,66px);letter-spacing:-.04em;line-height:.98}
.st{border-left-width:2px}.st.on{border-left-color:var(--gold);box-shadow:-10px 0 22px -16px var(--gold)}
.st b{font-family:var(--display);font-stretch:100%;font-weight:700;letter-spacing:-.02em}
.frame{background:rgba(10,24,17,.6);border:1px solid rgba(255,255,255,.14);border-radius:22px;
 box-shadow:inset 0 1px 0 rgba(255,255,255,.16),40px 60px 100px -30px rgba(0,0,0,.85),0 0 80px -30px rgba(79,199,127,.35)}
.cols{gap:20px}
.cols>div,.cols>div+div{padding:28px 30px;border:1px solid var(--line);border-radius:24px;
 background:linear-gradient(180deg,rgba(255,255,255,.07),rgba(255,255,255,.025));box-shadow:inset 0 1px 0 rgba(255,255,255,.1)}
.cols h3{font-family:var(--display);font-stretch:100%;font-weight:700}
.cols li{border-top-color:var(--line2)}
.how ol{gap:18px}
.how li{border:1px solid var(--line);border-radius:22px;padding:24px;background:linear-gradient(180deg,rgba(255,255,255,.07),rgba(255,255,255,.02));
 box-shadow:inset 0 1px 0 rgba(255,255,255,.1)}
.how li>b{font-family:var(--display);font-style:normal;font-stretch:100%;font-weight:800;color:var(--gold);text-shadow:0 0 30px rgba(79,199,127,.45)}
.how h3{font-family:var(--display);font-stretch:100%;font-weight:700}
.cta{margin:20px var(--gut) 60px;border:1px solid var(--line);border-radius:30px;color:var(--text);
 background:radial-gradient(70% 120% at 0% 0%,rgba(28,127,70,.55),transparent 62%),linear-gradient(180deg,rgba(255,255,255,.08),rgba(255,255,255,.02));
 box-shadow:inset 0 1px 0 rgba(255,255,255,.16),0 50px 90px -50px #000}
.cta h2{font-family:var(--display);font-style:normal;font-stretch:100%;font-weight:800;letter-spacing:-.055em;font-size:clamp(48px,7.4vw,124px)}
.cta p{color:var(--text2)}
.launch{background:radial-gradient(60% 60% at 50% 40%,rgba(28,127,70,.55),transparent 70%),#06120C}
.cur{border-color:rgba(255,255,255,.55);background:rgba(255,255,255,.08);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);
 font-family:var(--body);font-stretch:100%;font-weight:700}
.skip{border-radius:999px}
"""
LAND_C = r"""
body.landing{font-size:16px}
.lnav.solid{background:rgba(10,11,10,.94);backdrop-filter:none;-webkit-backdrop-filter:none;box-shadow:0 1px 0 var(--line)}
.lbrand{font-family:var(--body);font-stretch:100%;font-weight:600;font-size:16px}
.lnav nav a{font-family:var(--mono);font-size:13px}
.look-btn,.btn,.btn.sm{border-radius:4px}
.btn{background:var(--gold);color:#06120C;font-family:var(--body);font-stretch:100%;font-weight:600;font-size:17px;box-shadow:0 0 24px -6px rgba(79,199,127,.55)}
.btn:hover{background:#6BD996}
.btn.inv{background:var(--gold);color:#06120C}
.hero{background-color:transparent;background-image:radial-gradient(45% 55% at 72% 55%,rgba(79,199,127,.08),transparent 70%),
 linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);
 background-size:auto,48px 48px,48px 48px}
.for{color:var(--gold);font-family:var(--mono);font-stretch:100%;font-weight:500;font-size:13px}
.hero h1{font-family:var(--body);font-stretch:100%;font-weight:600;font-size:clamp(44px,5vw,88px);line-height:.98;letter-spacing:-.045em}
.lede{font-size:18px}
.hint,.f-demo,.aside{font-family:var(--mono);font-size:12px}
.story h2,.split h2,.how h2{font-family:var(--body);font-stretch:100%;font-weight:600;font-size:clamp(34px,3.8vw,60px);letter-spacing:-.04em;line-height:1}
.st{border-left-width:2px}.st.on{border-left-color:var(--gold)}
.st b{font-family:var(--body);font-stretch:100%;font-weight:600;font-size:20px;letter-spacing:-.01em}.st span{font-size:14px}
.frame{background:var(--panel);border:1px solid var(--line);border-radius:6px;box-shadow:30px 50px 90px -30px rgba(0,0,0,.9)}
.scr,.scr iframe{background:var(--bg)}
.cols>div+div{border-left:1px solid var(--line)}
.cols h3{font-family:var(--body);font-stretch:100%;font-weight:600}
.cols li{border-top-color:var(--line);font-size:16.5px}
.cols li::before{font-family:var(--mono);font-weight:600}
.does li::before{color:var(--gold)}.wont li::before{color:#ff7a88}
.how li{border-top:1px solid var(--line)}
.how li>b{font-family:var(--num);font-style:normal;font-stretch:100%;font-weight:800;font-variation-settings:"ROND" 100;color:var(--gold);
 text-shadow:0 0 18px rgba(79,199,127,.45)}
.how h3{font-family:var(--body);font-stretch:100%;font-weight:600;font-size:22px}
.cta{color:var(--text);background:var(--panel);border-top:1px solid var(--line);border-bottom:1px solid var(--line);
 background-image:linear-gradient(90deg,#1C7F46 0 6px,transparent 6px),repeating-linear-gradient(0deg,rgba(255,255,255,.018) 0 1px,transparent 1px 4px)}
.cta h2{font-family:var(--num);font-style:normal;font-stretch:100%;font-weight:800;font-variation-settings:"ROND" 100;color:var(--gold);
 font-size:clamp(40px,6.4vw,112px);line-height:1;letter-spacing:0;text-shadow:0 0 26px rgba(79,199,127,.4)}
.cta p{color:var(--muted);font-family:var(--mono);font-size:13px}
.lfoot{font-family:var(--mono);font-size:12px}
.launch{background:#0A0B0A}
.cur{border-radius:6px;border-color:var(--gold);color:var(--gold);background:rgba(10,11,10,.5);font-family:var(--mono);font-stretch:100%;font-weight:500;font-size:12px}
.skip{border-radius:4px;background:var(--gold);color:#06120C}
"""
LAND_D = r"""
.lnav,.lnav.solid{background:#fff;backdrop-filter:none;-webkit-backdrop-filter:none;box-shadow:0 3px 0 #111}
.lbrand{font-family:var(--display);font-stretch:100%;font-weight:900;font-size:24px;text-transform:uppercase}
.lnav nav a{color:#333;font-weight:800}
.look-btn{background:#fff;color:#111;border:2px solid #111;font-weight:800;box-shadow:2px 2px 0 #111}
.look-btn b{color:#111}
.btn{background:#fff;color:#111;border:3px solid #111;border-radius:999px;font-family:var(--body);font-stretch:100%;font-weight:800;font-size:19px;
 box-shadow:5px 5px 0 #111;transition:transform .12s,box-shadow .12s}
.btn:hover{background:#fff;transform:translate(-2px,-2px);box-shadow:7px 7px 0 #111}
.btn:active{transform:translate(3px,3px);box-shadow:0 0 0 #111}
.btn.sm{border-width:2px;font-size:15px;box-shadow:3px 3px 0 #111}
.btn.inv{background:#111;color:#fff;box-shadow:5px 5px 0 #1C7F46}
.hero{background:none}
.hero-txt>*{position:relative}
.for{display:inline-block;background:#111;color:#fff;font-family:var(--body);font-stretch:100%;font-weight:800;font-size:14px;padding:7px 14px;border-radius:999px}
.hero h1{font-family:var(--display);font-stretch:100%;font-weight:900;text-transform:uppercase;color:#fff;font-size:clamp(52px,6.8vw,120px);line-height:.86;
 letter-spacing:.004em;-webkit-text-stroke:3px #111;paint-order:stroke fill;text-shadow:6px 6px 0 #111}
.lede{color:#fff;font-weight:600;font-size:clamp(17px,1.35vw,20px)}
.tlink{color:#fff;font-weight:800;text-decoration-thickness:2px}
.hint{color:rgba(255,255,255,.9);font-weight:700}
.story-txt{background:#fff;border:3px solid #111;border-radius:18px;box-shadow:8px 8px 0 #111;padding:26px 24px}
.story h2,.split h2,.how h2,.cta h2{font-family:var(--display);font-stretch:100%;font-weight:900;text-transform:uppercase;font-style:normal;letter-spacing:.004em}
.story h2,.split h2,.how h2{font-size:clamp(40px,4.6vw,78px);line-height:.88}
.st{border-left:4px solid #E2E2DB;color:#5E5E57}.st.on{color:#111;border-left-color:#1C7F46}
.st b{font-family:var(--display);font-stretch:100%;font-weight:900;text-transform:uppercase;font-size:26px}
.frame{background:#fff;border:3px solid #111;border-radius:16px;box-shadow:12px 12px 0 #111}
.scr,.scr iframe{background:#1C7F46}
.f-demo{color:#fff;font-weight:700}
.split,.how{background:#fff;border:3px solid #111;border-radius:20px;box-shadow:10px 10px 0 #111;margin:40px var(--gut);padding:56px clamp(20px,4vw,56px)}
.cols>div+div{border-left:3px solid #111}
.cols h3{font-family:var(--display);font-stretch:100%;font-weight:900;text-transform:uppercase;font-size:30px}
.cols li{border-top:2px solid #E2E2DB;font-weight:600}
.does li::before{color:#15803d}.wont li::before{color:#b91c1c}
.how li{border-top:3px solid #111}
.how li>b{font-family:var(--display);font-style:normal;font-stretch:100%;font-weight:900;color:#1C7F46;-webkit-text-stroke:3px #111;paint-order:stroke fill;
 text-shadow:5px 5px 0 #111;font-size:96px}
.how h3{font-family:var(--display);font-stretch:100%;font-weight:900;text-transform:uppercase;font-size:30px}
.cta{background:#fff;color:#111;border:3px solid #111;border-radius:20px;box-shadow:10px 10px 0 #111;margin:40px var(--gut) 60px;background-image:none}
.cta h2{font-size:clamp(56px,9vw,150px);line-height:.84}
.cta p{color:#5E5E57;font-weight:600}
.lfoot{color:rgba(255,255,255,.9);font-weight:600}
.launch{background:#1C7F46}
.cur{border:3px solid #111;background:#fff;color:#111;box-shadow:3px 3px 0 #111;font-family:var(--display);font-stretch:100%;font-weight:900;text-transform:uppercase;backdrop-filter:none}
.skip{background:#111;color:#fff;border-radius:999px}
@media (max-width:900px){.split,.how,.cta{margin:24px 14px;box-shadow:6px 6px 0 #111}.cols>div+div{border-left:0;border-top:3px solid #111;padding-top:28px}}
@media (prefers-reduced-motion:reduce){.btn{transition:none}}
"""
LAND_E = r"""
body.landing{font-size:16.5px}
.for,.hint,.f-demo{font-family:var(--mono);font-size:13px}
.hint,.f-demo{font-size:12px}
.lnav nav a{font-family:var(--body)}
.btn{font-family:var(--body)}
.how li>b{font-family:var(--num);font-variation-settings:"ROND" 100;text-shadow:0 0 22px rgba(79,199,127,.5)}
.cols li::before{font-family:var(--mono);font-weight:600}
.does li::before{color:var(--gold)}.wont li::before{color:#ff7a88}
.cta p{font-family:var(--mono);font-size:13px}
.cur{font-family:var(--mono);font-weight:500;font-size:12px}
"""
LANDING_THEME_CSS = "".join(scope_css(css, k) for k, css in (("A", LAND_A), ("B", LAND_B), ("C", LAND_C), ("D", LAND_D), ("E", LAND_B + LAND_E)))


# ---------------------------------------------------------------------------------------------
# Phones: not the desktop squeezed, but its own layout. The shell (tab bar, header, sheets) and the page layouts
# start at 860px (phones and small tablets in portrait). Prefixed with html:not(#_) so layout wins over every look's CSS, while the looks
# keep their colours and type (these rules avoid colours wherever they can).
PHONE_CSS_RAW = r"""
:root{--nav-on:var(--kit)}
:root[data-theme="A"],:root[data-theme="D"]{--nav-on:var(--kit-l)}
:root[data-theme="C"]{--nav-on:var(--gold)}
:root[data-theme="D"]{--seg-on:#111111}
:root[data-theme="B"],:root[data-theme="E"]{--nav-on:#ffffff;--sticky-bg:#0c1b14}
/* narrow desktop windows: a tighter header so the wider looks still fit on one line */
@media (min-width:861px) and (max-width:1280px){
 .ah-row{gap:16px}
 .ah-nav a{padding-left:9px;padding-right:9px}
 .ah-nav .k,.ah-club b,.ah-live span,.ah-look .lk-cur{display:none}
}
@media (min-width:861px) and (max-width:1024px){
 .ah-brand span{display:none}
 .ah-nav{gap:0}
 .ah-nav a{padding-left:7px;padding-right:7px}
}
@media (max-width:860px){
 html{-webkit-tap-highlight-color:transparent}
 body.app{padding-bottom:calc(78px + env(safe-area-inset-bottom))}
 .ah{padding-top:env(safe-area-inset-top)}
 .ah-row{height:54px;gap:10px;padding:0 16px}
 .ah-brand span{display:none}
 .ah-brand .logo{width:28px;height:28px}
 .ah-title{display:block;flex:1 1 auto;min-width:0;font-family:var(--display);font-stretch:75%;font-weight:800;font-size:25px;line-height:1.05;
  letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .ah-tools{gap:8px;margin-left:0}
 .ah-tools .ah-btn{display:none}
 .ah-club{padding:2px;border:0;background:none}.ah-club b{display:none}
 .ah-live span{display:none}
 /* the bottom tab bar: four sections and More */
 .ah-nav{height:calc(64px + env(safe-area-inset-bottom));padding:0 4px env(safe-area-inset-bottom);justify-content:space-around;align-items:stretch;gap:0}
 .ah-nav a[data-sec="sandbox"],.ah-nav a[data-sec="stats"]{display:none}
 .ah-nav a,.ah-more{position:relative;flex:1 1 0;min-width:0;height:auto;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;
  padding:7px 2px 5px;margin:0;border:0;border-radius:0;background:none;box-shadow:none;color:var(--muted);text-decoration:none;cursor:pointer;
  font:inherit;touch-action:manipulation}
 .ah-nav a::after{display:none}
 .ah-nav .k{display:none}
 .ah-nav .nl{font-family:inherit;font-stretch:100%;font-style:normal;font-size:11px;font-weight:600;line-height:1.1;letter-spacing:.01em;text-transform:none}
 .ni{display:block;width:46px;height:30px;padding:4px 12px;border-radius:999px;transition:background-color .2s}
 .ah-more{display:flex}
 .ah-nav a[aria-current="true"],.ah-more[data-on]{color:var(--text)}
 .ah-nav a[aria-current="true"] .ni,.ah-more[data-on] .ni{color:var(--nav-on);background:color-mix(in srgb,var(--nav-on) 17%,transparent)}
 .ah-nav a:active .ni,.ah-more:active .ni{background:color-mix(in srgb,var(--text) 10%,transparent)}
 .ah-nav .count{position:absolute;top:5px;left:calc(50% + 8px);right:auto;font-size:10px;line-height:15px;padding:0 5px;min-width:16px;text-align:center}
 /* pages inside a section: a segmented control */
 .ah-sub{height:auto;border-top:0;padding:0}
 .ah-sub[role="tablist"].on{display:flex;gap:2px;margin:0 16px 10px;padding:3px;border-radius:11px;background:var(--panel2)}
 .ah-sub[role="tablist"] a{flex:1 1 0;justify-content:center;min-height:34px;padding:6px 8px;border-radius:9px;font-size:13.5px;white-space:nowrap}
 .ah-sub[role="tablist"] a[aria-selected="true"]{background:var(--seg-on,var(--panel));box-shadow:0 1px 3px rgba(0,0,0,.3)}
 .ah-sub.note.on{display:none}
 /* Key, Look and More slide up from the bottom */
 .keypop,.lookpop{position:fixed;inset:auto 0 0 0;top:auto;left:0;right:0;width:100%;max-width:none;margin:0;max-height:min(84vh,680px);overflow:auto;
  overscroll-behavior:contain;border-radius:22px 22px 0 0;border-bottom-width:0;padding:8px 18px calc(20px + env(safe-area-inset-bottom));
  translate:0 0;transition:translate .36s cubic-bezier(.2,.8,.2,1),display .36s allow-discrete,overlay .36s allow-discrete}
 .keypop:not(:popover-open),.lookpop:not(:popover-open){translate:0 100%}
 @starting-style{.keypop:popover-open,.lookpop:popover-open{translate:0 100%}}
 .keypop::before,.lookpop::before{content:"";display:block;width:38px;height:5px;border-radius:3px;background:var(--muted);opacity:.45;margin:0 auto 12px}
 .keypop::backdrop,.lookpop::backdrop{background:rgba(0,0,0,.5)}
 :root[data-theme="A"] .keypop,:root[data-theme="A"] .lookpop{border-radius:0}
 .kp-h{font-size:20px}
 .lk-o{padding:10px 8px;min-height:56px}
 .mp-links,.mp-tools{display:grid;gap:2px;margin:2px 0 6px}
 .mp-tools{border-top:1px solid var(--line2);padding-top:8px;margin-top:6px}
 .mp-links a,.mp-tools a,.mp-tools button{all:unset;box-sizing:border-box;display:flex;align-items:center;gap:14px;min-height:58px;padding:10px;border-radius:12px;
  color:var(--text);cursor:pointer;-webkit-tap-highlight-color:transparent}
 .mp-links a:active,.mp-tools a:active,.mp-tools button:active,.mp-links a[aria-current="true"]{background:var(--panel2)}
 .mp-links a:focus-visible,.mp-tools a:focus-visible,.mp-tools button:focus-visible{outline:2px solid var(--gold);outline-offset:-2px}
 .mi{flex:none;width:26px;height:26px;color:var(--text2)}
 .mp-links a[aria-current="true"] .mi{color:var(--nav-on)}
 .mp-links b,.mp-tools b{display:block;font-size:16px;font-weight:700;line-height:1.2}
 .mp-links small,.mp-tools small{display:block;font-size:12.5px;line-height:1.35;color:var(--muted);margin-top:2px}
}
@media (max-width:860px) and (prefers-reduced-motion:reduce){.keypop,.lookpop{transition:none}.ni{transition:none}}
/* narrow desktop windows: the squad list drops its widest extra columns instead of scrolling sideways
   (FM positions, then ability and potential, then value and wage) */
@media (min-width:861px) and (max-width:1180px){.squad.sq td:nth-child(2),.squad.sq th:nth-child(2){display:none}}
@media (min-width:1181px) and (max-width:1280px){:root[data-theme] .squad.sq td:nth-child(2),:root[data-theme] .squad.sq th:nth-child(2){display:none}}
@media (min-width:1101px) and (max-width:1180px){:root[data-theme] .squad.sq td:nth-child(5),:root[data-theme] .squad.sq th:nth-child(5),
 :root[data-theme] .squad.sq td:nth-child(6),:root[data-theme] .squad.sq th:nth-child(6){display:none}}
@media (min-width:861px) and (max-width:1100px){.squad.sq td:nth-child(5),.squad.sq th:nth-child(5),.squad.sq td:nth-child(6),.squad.sq th:nth-child(6){display:none}}
@media (min-width:861px) and (max-width:980px){.squad.sq td:nth-child(7),.squad.sq th:nth-child(7),.squad.sq td:nth-child(8),.squad.sq th:nth-child(8){display:none}}
@media (max-width:860px){
 .ph-only{display:block}
 .tk{display:none}
 main.wrap{padding:12px 16px 24px}
 section,.page section{margin-top:30px}
 .page>:first-child{margin-top:6px}
 h2{font-size:27px;line-height:1;gap:4px 10px;margin-bottom:12px}
 h2 .h2sub,.h2sub{flex-basis:100%;font-size:12.5px;line-height:1.4}
 .ph-note{margin:-2px 0 12px;padding:10px 12px;border-radius:10px;font-size:13px;line-height:1.45;color:var(--text2);background:var(--panel);border:1px solid var(--line)}
 /* chip rows swipe sideways instead of wrapping onto four lines */
 .filters .frow:not(.ftop),.subnav,.okrow{flex-wrap:nowrap;overflow-x:auto;overscroll-behavior-x:contain;scrollbar-width:none;
  -webkit-mask-image:linear-gradient(90deg,#000 calc(100% - 28px),transparent);mask-image:linear-gradient(90deg,#000 calc(100% - 28px),transparent)}
 .filters .frow:not(.ftop)::-webkit-scrollbar,.subnav::-webkit-scrollbar,.okrow::-webkit-scrollbar{display:none}
 .filters .frow>*,.subnav>*,.okrow>*{flex:none}
 .filters .frow:not(.ftop){padding-right:28px}
 .fchip{min-height:34px;padding:6px 13px;font-size:13px}
 .fl{width:auto;margin-right:4px}
 .subnav{margin-top:4px;padding:10px 12px;gap:8px}
 .subnav .stylechips{display:none}
 .okrow{gap:10px;padding-right:28px}
 .okchip{width:auto;min-width:250px}
 .morebtn,details.fold>summary::after{min-height:40px}
 /* home: a compact cover, then the news */
 .hband{min-height:0;border-radius:18px}
 .hb-txt{padding:22px 20px 2px}
 .hb-club{font-size:clamp(44px,13vw,62px);margin:4px 0 16px}
 .hb-meta{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 18px;margin-bottom:16px}
 .hb-meta dd{font-size:16px}
 .hb-rec{gap:12px;margin-bottom:18px;flex-wrap:wrap}
 .hb-pos{font-size:54px}
 .hb-btn{display:flex;justify-content:center;width:100%;padding:14px 18px;font-size:17px}
 .hb-3d{padding-bottom:6px}
 .hb-3d .p3{height:320px;--pw:min(230px,58vw);--sc:.92}
 .hb-hint{margin:-16px 0 12px}
 .ph-news .news{list-style:none;margin:0;padding:0;border:1px solid var(--line);border-radius:14px;background:var(--panel);overflow:hidden}
 .ph-news li+li{border-top:1px solid var(--line2)}
 .ph-news a{display:flex;align-items:center;gap:10px;min-height:50px;padding:11px 14px;color:var(--text);text-decoration:none;font-size:14px;line-height:1.35}
 .ph-news a:active{background:var(--panel2)}
 .ph-news a::after{content:"›";margin-left:auto;padding-left:6px;color:var(--muted);font-size:20px;line-height:1}
 .ph-news .tag{flex:none;font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;border:1px solid transparent;white-space:nowrap}
 .fin{grid-template-columns:repeat(2,minmax(0,1fr))}
 .tile{padding:12px 14px 14px}
 .tile .val{font-size:34px}
 .vgrid{gap:10px}
 .vcard{padding:12px 14px}
 /* best XIs: one XI at a time */
 .xtools{flex-wrap:wrap;align-items:center;gap:8px 4px;margin:0 0 12px}
 .xiseg.ph-only{display:inline-flex;margin-left:auto}
 .xtools .seg{min-height:36px;padding:6px 14px}
 section[data-xi="1"] .pitches3d>:nth-child(2),section[data-xi="1"] .pitches>:nth-child(2),
 section[data-xi="2"] .pitches3d>:nth-child(1),section[data-xi="2"] .pitches>:nth-child(1){display:none}
 .p3w{padding:12px 12px 0}
 .p3w .p3{height:430px;margin-top:-56px;--pw:min(250px,64vw)}
 /* positions: the key folds away, the positions that need work come first */
 .pkey-fold>summary{display:flex;align-items:center;gap:8px;min-height:44px;padding:10px 14px;margin-bottom:12px;list-style:none;cursor:pointer;font-size:13.5px;
  font-weight:600;color:var(--text2);border:1px solid var(--line);border-radius:12px;background:var(--panel)}
 .pkey-fold>summary::-webkit-details-marker{display:none}
 .pkey-fold>summary::after{content:"Show";margin-left:auto;font-size:12.5px;color:var(--muted)}
 .pkey-fold[open]>summary::after{content:"Hide"}
 .pform{display:flex;flex-direction:column;gap:12px;padding:12px}
 .pform .pcard.red{order:-2}.pform .pcard.amber{order:-1}
 .prow2.c{min-height:40px;padding:6px 12px}
 /* squad list: one card per player */
 .fin.k5 .tile{padding:12px}
 .squad.sq{display:block;border-radius:14px;overflow:hidden}
 .squad.sq thead{display:none}
 .squad.sq tbody{display:block}
 .squad.sq tr{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:3px 12px;padding:11px 14px;border-left:4px solid transparent;
  border-bottom:1px solid var(--line2)}
 .squad.sq td,.squad.sq td:first-child{display:block;padding:0;border:0;min-width:0}
 .squad.sq td.nm{grid-column:1;grid-row:1;font-size:15.5px;white-space:normal}
 .squad.sq td:nth-child(4){grid-column:2;grid-row:1/span 2;justify-self:end;text-align:right}
 .squad.sq td:nth-child(3){grid-column:1;grid-row:2;font-size:12.5px;color:var(--muted)}
 .squad.sq td:nth-child(3)::before{content:"Age "}
 .squad.sq td.bd{grid-column:1/-1;grid-row:3;padding-top:4px}
 .squad.sq td.bd:empty,.squad.sq td.lo{display:none}
 .squad.sq tr.grp,.squad.sq tr.nomatch{display:block;padding:0;border-left:0}
 .squad.sq tr.grp td,.squad.sq tr.nomatch td{display:block;padding:10px 14px}
 .squad.sq tr.loan-in{border-left-color:var(--loanin)}.squad.sq tr.loan-out{border-left-color:var(--loanout)}
 .squad.sq tr.deal-in{border-left-color:var(--dealin)}.squad.sq tr.deal-out{border-left-color:var(--dealout)}
 .squad.sq tr.inj-short{border-left-color:var(--injs)}.squad.sq tr.inj-long{border-left-color:var(--injl)}.squad.sq tr.sus{border-left-color:#94a3b8}
 .filters{padding:10px 12px}
 .fsearch{min-height:42px;font-size:16px}
 /* tactics */
 .rec{gap:8px 12px}
 .wi{padding:10px 12px}
 .ftable{margin:0 -12px;padding:0 12px}
 .ftable th:first-child,.ftable td.nm{position:sticky;left:0;z-index:1;background:var(--sticky-bg,var(--panel))}
 .rpk{min-width:56px}
 /* training: the week scrolls sideways, everything else stacks */
 .tgrid{overflow-x:auto;overscroll-behavior-x:contain;margin:0 -12px;padding:0 12px}
 .tgrid table{min-width:620px}
 .tcols{grid-template-columns:1fr}
 /* transfers: a vertical timeline */
 .tline{grid-template-columns:1fr;gap:0}
 .tlm{padding:0 0 22px 26px;min-width:0}
 .tlm::before{left:5px;right:auto;top:16px;bottom:0;width:2px;height:auto}
 .tlm:last-child::before{display:none}
 .tlm::after{left:0;top:3px}
 .tlm li{padding:9px 11px}
 /* sandbox: the roster is one column on a phone */
 .sbcols{grid-template-columns:minmax(0,1fr)}
 .pchip.sb select{min-width:0;max-width:100%}
 .sbfilter,.sblegend{flex-wrap:wrap}
 .pform,.pform .pcard{min-width:0;max-width:100%}
 /* stats */
 .ldrs .who{white-space:normal}
 .squad.stats{max-width:100%}
 .squad.stats th,.squad.stats td{padding-left:5px;padding-right:5px}
}
"""
PHONE_CSS_RAW += r"""
@media (max-width:400px){.squad.stats th,.squad.stats td{padding-left:4px;padding-right:4px;font-size:12.5px}}
"""
PHONE_CSS = prefix_css(PHONE_CSS_RAW, "html:not(#_)")


APP_JS = r"""
(function(){
const rm=matchMedia('(prefers-reduced-motion: reduce)').matches, G=!!window.gsap;
if(G&&window.Flip)gsap.registerPlugin(Flip);
// header height, for sticky table headers and bars under it
const ahEl=document.querySelector('.ah');
if(ahEl){const setH=()=>document.documentElement.style.setProperty('--ahh',ahEl.offsetHeight+'px');setH();
 if(window.ResizeObserver)new ResizeObserver(setH).observe(ahEl);}
const ROUTE_PAGE={'home':'overview','team/xis':'xis','team/positions':'positions','team/squad':'squad','tactics/fit':'fit','tactics/training':'training',
 'sandbox':'sandbox','transfers':'deals','stats':'stats'};
const DEFAULT={team:'team/xis',tactics:'tactics/fit'};
const LEGACY={overview:'home',xis:'team/xis',positions:'team/positions',squad:'team/squad',fit:'tactics/fit',training:'tactics/training',deals:'transfers'};
const SECS=['home','team','tactics','sandbox','transfers','stats'];
const last={};
function norm(h){h=(h||'').replace(/^#/,'');if(LEGACY[h])h=LEGACY[h];if(DEFAULT[h])h=last[h]||DEFAULT[h];return ROUTE_PAGE[h]?h:'home';}
const pages=[...document.querySelectorAll('.page')];
let current=null;
function show(route,animate){
 const sec=route.split('/')[0],pid=ROUTE_PAGE[route];last[sec]=route;
 pages.forEach(p=>{const on=p.id==='p-'+pid;p.classList.toggle('active',on);p.hidden=!on;});
 document.querySelectorAll('.ah-nav a,.mp-links a').forEach(a=>a.setAttribute('aria-current',a.dataset.sec===sec?'true':'false'));
 const moreB=document.querySelector('.ah-more');if(moreB)moreB.toggleAttribute('data-on',sec==='stats'||sec==='sandbox');
 document.querySelectorAll('.ah-sub').forEach(s=>s.classList.toggle('on',s.dataset.for===sec));
 document.querySelectorAll('.ah-sub [role="tab"]').forEach(t=>{const on=t.dataset.route===route;t.setAttribute('aria-selected',on);t.tabIndex=on?0:-1;});
 const navA=document.querySelector('.ah-nav a[data-sec="'+sec+'"]');if(navA)navA.setAttribute('href','#'+route);
 const tab=document.querySelector('.ah-sub [role="tab"][data-route="'+route+'"]'),name=tab?tab.textContent.replace(/\d+$/,''):(navA?navA.textContent.replace(/^\d/,'').replace(/\d+$/,''):'');
 document.title=name.trim()+' · '+document.body.dataset.club+' · FM27 Squad Report';
 const secName=document.querySelector('.ah-nav a[data-sec="'+sec+'"] .nl'),tt=document.getElementById('ahTitle');if(tt&&secName)tt.textContent=secName.textContent;
 const page=document.getElementById('p-'+pid);
 if(current!==route){window.scrollTo(0,0);
  if(animate&&G&&!rm&&page)gsap.fromTo(page,{y:14,autoAlpha:0},{y:0,autoAlpha:1,duration:.38,ease:'power2.out',clearProps:'transform,opacity,visibility'});}
 current=route;
 if(page)page.dispatchEvent(new Event('fm27:shown'));
}
function go(route){if(location.hash.slice(1)!==route)location.hash=route;else show(route,true);}
addEventListener('hashchange',()=>{const r=norm(location.hash);if(r!==location.hash.slice(1))history.replaceState(null,'','#'+r);show(r,true);});
const start=norm(location.hash);if(start!==location.hash.slice(1))history.replaceState(null,'','#'+start);show(start,false);
// phone: the More sheet closes when you pick something, and its Look/Key buttons swap to that sheet
const mp=document.getElementById('morepop');
if(mp){mp.querySelectorAll('a[href^="#"]').forEach(a=>a.addEventListener('click',()=>{try{mp.hidePopover();}catch(_){}}));
 mp.querySelectorAll('[popovertarget]').forEach(b=>b.addEventListener('click',e=>{const t=document.getElementById(b.getAttribute('popovertarget'));if(!t||!t.showPopover)return;
  e.preventDefault();try{mp.hidePopover();t.showPopover();}catch(_){}}));}
// phone: Best XI or Second XI, one at a time
document.querySelectorAll('.xiseg').forEach(g=>{const sec=g.closest('section');sec.dataset.xi='1';
 g.querySelectorAll('[data-xi]').forEach(b=>b.addEventListener('click',()=>{sec.dataset.xi=b.dataset.xi;g.querySelectorAll('[data-xi]').forEach(x=>x.setAttribute('aria-pressed',x===b));}));});
// phone: the positions key starts folded
if(matchMedia('(max-width: 860px)').matches)document.querySelectorAll('details.pkey-fold').forEach(d=>{d.open=false;});
// keys: 1-6 sections, [ and ] for the pages inside a section
addEventListener('keydown',e=>{
 if(e.metaKey||e.ctrlKey||e.altKey||(e.target.closest&&e.target.closest('input,select,textarea,[contenteditable]')))return;
 const n=parseInt(e.key,10);
 if(n>=1&&n<=SECS.length){go(norm(SECS[n-1]));return;}
 if(e.key==='['||e.key===']'){const sub=document.querySelector('.ah-sub.on[role="tablist"]');if(!sub)return;
  const tabs=[...sub.querySelectorAll('[role="tab"]')],i=tabs.findIndex(t=>t.getAttribute('aria-selected')==='true');
  const j=(i+(e.key===']'?1:-1)+tabs.length)%tabs.length;go(tabs[j].dataset.route);}
});
// tab keyboard pattern for the page tabs
document.querySelectorAll('.ah-sub[role="tablist"]').forEach(list=>list.addEventListener('keydown',e=>{
 const tabs=[...list.querySelectorAll('[role="tab"]')],i=tabs.indexOf(document.activeElement);if(i<0)return;
 let j=null;if(e.key==='ArrowRight')j=(i+1)%tabs.length;else if(e.key==='ArrowLeft')j=(i-1+tabs.length)%tabs.length;
 else if(e.key==='Home')j=0;else if(e.key==='End')j=tabs.length-1;
 if(j==null)return;e.preventDefault();tabs[j].focus();go(tabs[j].dataset.route);}));
// club news ticker: pause button for anyone who wants it still
const tk=document.getElementById('tk');
if(tk){const b=tk.querySelector('.tk-btn');b.addEventListener('click',()=>{const p=tk.classList.toggle('paused');b.setAttribute('aria-pressed',p);
 b.setAttribute('aria-label',p?'Play club news':'Pause club news');b.title=b.getAttribute('aria-label');});}
// "About" goes to the public home page, which only exists on the live server
if(location.protocol==='file:')document.querySelectorAll('.ah-about').forEach(a=>a.remove());
// 3D pitches
document.querySelectorAll('[data-p3]').forEach(el=>window.initP3&&initP3(el));
// best XIs: flat or 3D, remembered
const flat=document.querySelector('.pitches'),deep=document.querySelector('.pitches3d'),segs=[...document.querySelectorAll('.xtools .seg')];
function view(v,anim){if(!flat||!deep)return;segs.forEach(s=>s.setAttribute('aria-pressed',s.dataset.view===v));
 const show3d=v==='3d';flat.hidden=show3d;deep.hidden=!show3d;
 if(G&&anim&&!rm){if(show3d){gsap.fromTo(deep.querySelectorAll('.p3'),{'--rx':'0deg','--sc':.82},{'--rx':'52deg','--sc':1,duration:1.1,ease:'expo.out',stagger:.08});}
  else gsap.fromTo(flat,{autoAlpha:0,y:12},{autoAlpha:1,y:0,duration:.4,ease:'power2.out',clearProps:'all'});}
 if(anim){try{localStorage.setItem('fm27-xi-view',v);}catch(_){}}}
segs.forEach(s=>s.addEventListener('click',()=>view(s.dataset.view,true)));
let saved='3d';try{saved=localStorage.getItem('fm27-xi-view')||'3d';}catch(_){}
view(innerWidth<700?'2d':saved,false);
// cards lean towards the pointer a little
if(!rm&&matchMedia('(hover: hover) and (pointer: fine)').matches){
 document.querySelectorAll('.vcard,.mis').forEach(c=>{c.classList.add('tilt');
  c.addEventListener('pointermove',e=>{const r=c.getBoundingClientRect(),x=(e.clientX-r.left)/r.width-.5,y=(e.clientY-r.top)/r.height-.5;
   c.style.setProperty('--tx',(x*7).toFixed(2)+'deg');c.style.setProperty('--ty',(-y*7).toFixed(2)+'deg');});
  c.addEventListener('pointerleave',()=>{c.style.setProperty('--tx','0deg');c.style.setProperty('--ty','0deg');});});
}
// positions: show all / show fewer per card
document.querySelectorAll('.pexp').forEach(b=>b.addEventListener('click',()=>{const box=document.getElementById(b.getAttribute('aria-controls'));
 const open=b.getAttribute('aria-expanded')!=='true';box.hidden=!open;b.setAttribute('aria-expanded',open);
 b.textContent=open?'Show fewer':'Show all '+b.dataset.n;
 if(open&&G&&!rm)gsap.from(box.children,{opacity:0,y:-6,duration:.25,stagger:.02,ease:'power2.out'});}));
// sortable tables: click a header; direction shown and announced via aria-sort
document.querySelectorAll('table.sortable').forEach(t=>{
 const ths=[...t.tHead.rows[0].cells],body=t.tBodies[0];
 const val=(tr,i)=>{const c=tr.cells[i];if(!c)return null;const s=c.textContent.trim();
  const n=parseFloat(s.replace(/[^0-9.\-]/g,''));return /^[–—-]?$/.test(s)?null:(isNaN(n)?s.toLowerCase():n);};
 function sortBy(i,dir){const rows=[...body.rows].filter(r=>r.cells.length>1);
  rows.sort((a,b)=>{const x=val(a,i),y=val(b,i);if(x===y)return 0;if(x===null)return 1;if(y===null)return -1;
   return (x<y?-1:1)*(dir==='ascending'?1:-1);});rows.forEach(r=>body.appendChild(r));
  ths.forEach((h,k)=>{if(k===i)h.setAttribute('aria-sort',dir);else h.removeAttribute('aria-sort');});}
 ths.forEach((th,i)=>{const b=document.createElement('button');b.type='button';b.textContent=th.textContent;th.textContent='';th.appendChild(b);
  b.addEventListener('click',()=>{const cur=th.getAttribute('aria-sort');const text=i<3&&!th.classList.contains('r');
   sortBy(i,cur?(cur==='descending'?'ascending':'descending'):(text?'ascending':'descending'));});});
 const d=+t.dataset.default;if(ths[d])ths[d].setAttribute('aria-sort','descending');
});
// key items: keep the tooltip on screen; tap (or click) pins it open, Escape or a tap elsewhere closes it
function placeTip(h){const tip=h.querySelector('.tip');if(!tip)return;tip.style.left='0px';tip.style.removeProperty('--ax');
 const box=h.closest('.poslegend'),lim=Math.min(innerWidth-12,box?box.getBoundingClientRect().right:innerWidth);
 const r=tip.getBoundingClientRect(),over=r.right-lim;if(over>0){const sh=Math.min(over,r.left-12);tip.style.left=-sh+'px';tip.style.setProperty('--ax',(18+sh)+'px');}}
document.querySelectorAll('.hint').forEach(h=>{h.addEventListener('pointerenter',()=>placeTip(h));h.addEventListener('focusin',()=>placeTip(h));
 h.querySelector('.hint-b').addEventListener('click',()=>{const was=h.classList.contains('open');document.querySelectorAll('.hint.open').forEach(x=>x.classList.remove('open'));
  if(!was){h.classList.add('open');placeTip(h);}});});
document.addEventListener('click',e=>{if(!e.target.closest('.hint'))document.querySelectorAll('.hint.open').forEach(x=>x.classList.remove('open'));});
document.addEventListener('keydown',e=>{if(e.key==='Escape')document.querySelectorAll('.hint.open').forEach(x=>{x.classList.remove('open');});});
// "show N more": containers with .clipped hide their .xtra items until asked
document.querySelectorAll('.morebtn').forEach(b=>b.addEventListener('click',()=>{const box=document.getElementById(b.getAttribute('aria-controls'));if(!box)return;
 const open=b.getAttribute('aria-expanded')!=='true';box.classList.toggle('clipped',!open);b.setAttribute('aria-expanded',open);b.textContent=open?'Show fewer':b.dataset.more;
 if(open&&G&&!rm)gsap.fromTo(box.querySelectorAll('.xtra'),{opacity:0},{opacity:1,duration:.3,stagger:.012,ease:'power1.out',clearProps:'opacity'});
 if(!open){const r=b.getBoundingClientRect();if(r.top<0||r.bottom>innerHeight)b.scrollIntoView({block:'center'});}}));
// jump links inside a page
document.querySelectorAll('[data-jump]').forEach(b=>b.addEventListener('click',()=>{const t=document.getElementById(b.dataset.jump);
 if(t)t.scrollIntoView({behavior:rm?'auto':'smooth',block:'start'});}));
// role by role: a position picker on a pitch (tabs), one role card at a time
document.querySelectorAll('.rpitch[role="tablist"]').forEach(list=>{const tabs=[...list.querySelectorAll('[role="tab"]')];
 function pick(t,focus){tabs.forEach(x=>{const on=x===t;x.setAttribute('aria-selected',on);x.tabIndex=on?0:-1;
   const p=document.getElementById(x.getAttribute('aria-controls'));if(p)p.hidden=!on;});
  if(focus)t.focus();const p=document.getElementById(t.getAttribute('aria-controls'));if(!p)return;
  if(G&&!rm)gsap.fromTo(p,{autoAlpha:0,x:12},{autoAlpha:1,x:0,duration:.3,ease:'power2.out',clearProps:'all'});
  if(innerWidth<=760){const r=p.getBoundingClientRect();if(r.top>innerHeight-120)p.scrollIntoView({behavior:rm?'auto':'smooth',block:'nearest'});}}
 tabs.forEach(t=>t.addEventListener('click',()=>pick(t)));
 list.addEventListener('keydown',e=>{const i=tabs.indexOf(document.activeElement);if(i<0)return;let j=null;
  if(e.key==='ArrowRight'||e.key==='ArrowDown')j=(i+1)%tabs.length;else if(e.key==='ArrowLeft'||e.key==='ArrowUp')j=(i-1+tabs.length)%tabs.length;
  else if(e.key==='Home')j=0;else if(e.key==='End')j=tabs.length-1;if(j==null)return;e.preventDefault();pick(tabs[j],true);});});
// loader: only when you've just launched the app from the home page
if(document.documentElement.classList.contains('booting')&&window.FM27Boot)FM27Boot.play();
})();
"""


def render(R) -> str:
    def page(pid, body):
        return f'<div class="page" id="p-{pid}" role="tabpanel" hidden>{body}</div>'
    notes = "".join(f"<li>{E(n)}</li>" for n in R["notes"])
    notes_html = f'<ul class="notes">{notes}</ul>' if notes else ""
    club = club_identity(R["club"])
    return f"""<!DOCTYPE html><html lang="en" style="--kit:{club['kit']};--kit-ink:{club['ink']};--kit-l:{kit_on_light(club['kit'])}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>{E(R['club'])} · FM27 Squad Report</title>
<link rel="icon" href="{asset('app-logo.svg')}">
<script>try{{if(Date.now()-(+sessionStorage.getItem('fm27-launch')||0)<60000)document.documentElement.classList.add('booting');}}catch(e){{}}{LOOK_HEAD_JS}</script>
{FONT_LINKS}<style>{CSS}{P3_CSS}{APP_CSS}{BOOT_CSS}{theme_font_css()}{LOOK_CSS}{THEME_CSS}{PHONE_CSS}</style></head><body class="app" data-club="{E(R['club'])}">
{boot_html(club)}{app_header(R)}<main id="main" class="wrap">
{page('overview', overview(R))}{page('xis', xis(R))}{page('positions', position_cards(R))}{page('squad', squad_table(R))}
{page('fit', fit_page(R))}{page('training', training_page(R))}{page('sandbox', sandbox_page(R))}{page('deals', deals(R))}{page('stats', stats_table(R))}
<footer>{notes_html}Read-only: your save is never changed. System and ability stars use visible attributes only (no CA or
hidden attributes), rated against every player in your save and scaled to your squad in half-star steps, so they're this tool's
own stars and can differ a little from FM's. {"Potential stars come from FM's hidden potential (turn off with SHOW_POTENTIAL)." if SHOW_POTENTIAL else ""}
Press 1 to 6 to jump between sections, and [ or ] for the pages inside one.</footer>
</main><script src="{asset('gsap.min.js')}"></script><script src="{asset('Flip.min.js')}"></script>
<script>{P3_JS}{BOOT_JS}{APP_JS}{SANDBOX_JS}{FILTER_JS}{LOOK_JS}</script></body></html>"""


# =============================================================================================
def make_report(save_path: Path) -> tuple[Path, str]:
    """Read a save and write the report. Returns (report file, html)."""
    print(f"Reading {save_path.name} (saved {datetime.fromtimestamp(save_path.stat().st_mtime):%d %b %Y %H:%M}) …")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        progress(0)
        save, tmp = open_save(save_path)
        try:
            report = build(save, save_path)
        finally:
            try:
                save.close()
            except Exception:  # noqa: BLE001
                pass
            shutil.rmtree(tmp.parent, ignore_errors=True)
    progress(7)
    try:
        CLUB_FILE.parent.mkdir(parents=True, exist_ok=True)
        CLUB_FILE.write_text(json.dumps({"name": report["club"]}))
    except OSError:
        pass
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"{report['club']} {report['game_date']:%Y-%m-%d}.html"
    page = render(report)
    out.write_text(page, encoding="utf-8")
    shutil.copyfile(out, REPORT_DIR / "latest.html")
    print(f"Done → {out.name}")
    return out, page


def _line_name(line: str) -> str:
    return norm_name(re.sub(r"\[\d+\]\s*$", "", line).replace("|", ",").split(",")[0])


def update_scouting_file(action: str, name: str) -> None:
    """Add a line to scouting.txt ("Name", "Name, Club" or "Name, Club [id]"), or remove the line(s) for that name."""
    try:
        lines = SCOUTING_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = SCOUTING_HELP.rstrip("\n").splitlines()
    target = _line_name(name)
    if action == "add":
        tag = re.search(r"\[\d+\]\s*$", name)
        dup = (any(tag.group(0).strip() in l for l in lines if not l.startswith("#")) if tag else
               any(_line_name(l) == target for l in lines if not l.startswith("#")))
        if not dup:
            lines.append(name)
    else:
        lines = [l for l in lines if l.startswith("#") or _line_name(l) != target]
    SCOUTING_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


LIVE_JS = r"""
(function(){const v=window.FM27_LIVE;if(!v)return;const el=document.createElement('div');el.className='livebar';el.setAttribute('role','status');document.body.appendChild(el);
const dot=document.getElementById('liveDot'),txt=document.getElementById('liveTxt');
function state(c,t){if(dot){dot.className='ah-live '+c;txt.textContent=t;dot.title=t;}}
function show(cls,h){el.className='livebar show '+cls;el.innerHTML=h;}
async function tick(){try{const r=await fetch('/status',{cache:'no-store'});const s=await r.json();
 if(s.building){const i=Math.max(0,s.step);show('busy','<span class="spin"></span>Reading your latest save: '+(s.steps[i]||'')+' ('+(i+1)+' of '+s.steps.length+')');state('busy','Reading save');}
 else if(s.version!==v){show('new','New report ready. <a href="" id="lvR">Refresh</a>');state('new','New report ready');}
 else if(s.error){show('err','Couldn\'t read your latest save: '+s.error);state('err','Last save unreadable');}
 else{el.className='livebar';state('','Up to date');}
 const a=document.getElementById('lvR');if(a)a.onclick=e=>{e.preventDefault();location.reload();};}
 catch(e){show('err','The app window is closed. Double-click Run Squad Report to start it again.');state('err','Offline');}}
setInterval(tick,3000);tick();})();
"""

def loader_page() -> str:
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reading your save · FM27 Squad Report</title><link rel="icon" href="{asset('app-logo.svg')}">{FONT_LINKS}
<style>body{{margin:0;background:#0e1512}}{BOOT_CSS}</style></head><body>{boot_html(last_club())}<script>{BOOT_JS}FM27Boot&&FM27Boot.wait();</script></body></html>"""


ASSET_TYPES = {".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml", ".css": "text/css; charset=utf-8", ".woff2": "font/woff2"}


def serve_live(argv: list[str]) -> None:
    """Keep a small report server running on this Mac only. Refresh the browser to see the latest save;
    when a new save appears it rebuilds by itself, and if this script is updated it restarts with the new version."""
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    fixed = pick_save(argv) if argv else None
    url = f"http://localhost:{LIVE_PORT}/"
    script = Path(__file__).resolve()
    script_mtime = script.stat().st_mtime
    state = {"html": None, "version": "", "building": False, "error": "", "built": None, "n": 0, "step": -1}
    lock = threading.Lock()
    landing = landing_page()

    def follow(i: int) -> None:
        with lock:
            state["step"] = i
    globals()["PROGRESS_HOOK"] = follow

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the window quiet
            pass

        def send(self, body, ctype="text/html; charset=utf-8", code=200, cache="no-store"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            path = self.path.split("?")[0]
            with lock:
                snap = dict(state)
            if path == "/status":
                self.send(json.dumps({"version": snap["version"], "building": snap["building"], "error": snap["error"],
                                      "step": snap["step"], "steps": BUILD_STEPS, "ready": snap["html"] is not None}),
                          "application/json")
            elif path in ("/", "/index.html"):
                self.send(landing)
            elif path in ("/app", "/app/"):
                if snap["html"] is None:
                    self.send(loader_page())
                else:
                    flag = f'<script>window.FM27_LIVE={json.dumps(snap["version"])};</script></head>'
                    page = snap["html"].replace("</head>", flag, 1).replace("</body>", f"<script>{LIVE_JS}</script></body>", 1)
                    self.send(page)
            elif path == "/players":
                from urllib.parse import parse_qsl
                qs = dict(parse_qsl(self.path.partition("?")[2]))
                self.send(json.dumps(search_players(qs.get("q", "")[:60], qs.get("pos", "")[:4].upper(), qs.get("age", "")[:2])),
                          "application/json")
            elif path.startswith("/assets/"):
                name = path[len("/assets/"):]
                f = APP_DIR / "assets" / name
                if re.fullmatch(r"[A-Za-z0-9._-]+", name) and f.suffix in ASSET_TYPES and f.is_file():
                    self.send(f.read_bytes(), ASSET_TYPES[f.suffix], cache="max-age=3600")
                else:
                    self.send("Not found", "text/plain", 404)
            else:
                self.send("Not found", "text/plain", 404)

        def do_POST(self):  # noqa: N802
            if self.path.split("?")[0] != "/scouting":
                return self.send("Not found", "text/plain", 404)
            try:
                body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 10_000)) or b"{}")
                action, name = body.get("action"), " ".join(str(body.get("name", "")).split())[:120]
                if action == "add_uids":   # picked in the Sandbox: write "Name, Club [id]" from the save, not from the page
                    wanted = {int(u) for u in body.get("uids", [])[:20] if str(u).isdigit()}
                    rows = [r for r in PLAYER_INDEX if r[0] in wanted]
                    if not rows:
                        raise ValueError("couldn't find those players in your save")
                    for uid, pname, club, *_ in rows:
                        update_scouting_file("add", f"{pname}, {club} [{uid}]")
                else:
                    if action not in ("add", "remove") or not name:
                        raise ValueError("needs a name")
                    update_scouting_file(action, name)
                with lock:
                    state["force"] = True
                self.send(json.dumps({"ok": True}), "application/json")
            except Exception as exc:  # noqa: BLE001
                self.send(json.dumps({"ok": False, "error": str(exc)}), "application/json", 400)

    try:
        server = ThreadingHTTPServer(("127.0.0.1", LIVE_PORT), Handler)
    except OSError:
        print(f"\n  It's already running — opening {url}")
        webbrowser.open(url)
        return

    def newest() -> Path | None:
        if fixed:
            return fixed if fixed.is_file() else None
        saves = candidate_saves()
        return saves[0] if saves else None

    def watch():
        nonlocal script_mtime
        attempted = None
        while True:
            # a new version of this tool? restart into it (only once the file is complete and valid)
            try:
                m = script.stat().st_mtime
                if m != script_mtime and time.time() - m > 2:
                    compile(script.read_text(encoding="utf-8"), str(script), "exec")
                    print("\n  The tool was updated — restarting with the new version …")
                    sys.stdout.flush()
                    server.server_close()
                    os.environ["FM27_NO_OPEN"] = "1"
                    os.execv(sys.executable, [sys.executable, str(script), *argv])
            except SyntaxError:
                script_mtime = script.stat().st_mtime   # half-written or broken update: keep the old version
                print("  An update to the tool looks incomplete — still running the previous version.")
            except OSError:
                pass
            # a newer save? rebuild once FM has finished writing it
            try:
                save = newest()
                if save:
                    st = save.stat()
                    key = (str(save), st.st_mtime, st.st_size)
                    forced = state.pop("force", False)
                    if forced or (key != attempted and time.time() - st.st_mtime > LIVE_SETTLE_SECONDS):
                        attempted = key
                        with lock:
                            state["building"] = True
                            state["step"] = 0
                        try:
                            _, page = make_report(save)
                            with lock:
                                state["n"] += 1
                                state.update(html=page, error="", built=key,
                                             version=f"{st.st_mtime:.0f}-{script_mtime:.0f}-{state['n']}")
                            print(f"  Refresh {url} to see it.")
                        except (Exception, SystemExit) as exc:  # noqa: BLE001
                            with lock:
                                state["error"] = str(exc).splitlines()[0][:200] if str(exc) else exc.__class__.__name__
                            print(f"  Couldn't read that save: {state['error']}")
                        finally:
                            with lock:
                                state["building"] = False
                                state["step"] = -1
                elif state["html"] is None and not state["error"]:
                    with lock:
                        state["error"] = "no FM27 save found yet — save your game in FM27"
            except OSError:
                pass
            time.sleep(LIVE_POLL_SECONDS)

    threading.Thread(target=watch, daemon=True).start()
    print(f"\n  Your report lives at {url}  (the app itself is at {url}app)")
    print("  Leave this window open (minimise it if you like). Save in FM, then refresh the page in your browser.")
    print("  Close this window when you're done.\n")
    if not os.environ.get("FM27_NO_OPEN"):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")


def main(argv: list[str]) -> None:
    if "--once" in argv:
        out, _ = make_report(pick_save([a for a in argv if a != "--once"]))
        webbrowser.open(out.as_uri())
    else:
        serve_live(argv)


if __name__ == "__main__":
    main(sys.argv[1:])
