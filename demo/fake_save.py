"""A made-up FM27 save with the same shape fmsave gives, so the real build() + render() can run without Nitish's save.

Liverpool (club 1) has a squad that exercises every status the report shows. 19 other clubs make up the league.
"""
import hashlib
import random
from datetime import date, timedelta
from types import SimpleNamespace as NS

TODAY = date(2026, 11, 22)
SEASON = date(2026, 7, 1)
rng = random.Random(27)


def h(*parts) -> float:
    """Stable 0..1 number from any key, so every run builds the same save."""
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


class Stats:
    """A stats row: named fields as given, any other numeric field made up from its name."""
    def __init__(self, seed, scale=1.0, **kw):
        self.__dict__.update(kw)
        self._seed, self._scale = seed, scale

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return round((0.5 + h(self._seed, name)) * 4 * self._scale, 2)


GK_ATTRS = ["aerial_reach", "command_of_area", "communication", "eccentricity", "handling", "kicking", "one_on_ones",
            "punching", "reflexes", "rushing_out", "throwing"]
OUT_ATTRS = ["corners", "crossing", "dribbling", "finishing", "first_touch", "free_kick_taking", "heading", "long_shots",
             "long_throws", "marking", "passing", "penalty_taking", "tackling", "technique", "aggression", "anticipation",
             "bravery", "composure", "concentration", "decisions", "determination", "flair", "leadership", "off_the_ball",
             "positioning", "teamwork", "vision", "work_rate", "acceleration", "agility", "balance", "jumping_reach",
             "natural_fitness", "pace", "stamina", "strength"]
KEY = {"GK": GK_ATTRS + ["decisions", "positioning", "concentration"],
       "DC": ["heading", "marking", "tackling", "positioning", "jumping_reach", "strength", "anticipation", "decisions"],
       "DL": ["crossing", "tackling", "pace", "stamina", "work_rate", "marking", "acceleration"],
       "DM": ["tackling", "passing", "anticipation", "positioning", "decisions", "teamwork", "work_rate", "stamina"],
       "MC": ["passing", "vision", "decisions", "first_touch", "technique", "stamina", "work_rate"],
       "AMC": ["passing", "vision", "technique", "first_touch", "dribbling", "flair", "off_the_ball", "decisions"],
       "AML": ["dribbling", "crossing", "pace", "acceleration", "technique", "flair", "off_the_ball", "agility"],
       "STC": ["finishing", "off_the_ball", "composure", "first_touch", "heading", "pace", "acceleration", "anticipation"]}
KEY["DR"], KEY["WBL"], KEY["WBR"], KEY["AMR"], KEY["MR"], KEY["ML"] = KEY["DL"], KEY["DL"], KEY["DL"], KEY["AML"], KEY["AML"], KEY["AML"]
NEAR = {"GK": [], "DC": ["DM"], "DL": ["WBL", "ML"], "DR": ["WBR", "MR"], "DM": ["MC", "DC"], "MC": ["DM", "AMC"],
        "AMC": ["MC", "AML", "AMR"], "AML": ["ML", "AMR", "STC"], "AMR": ["MR", "AML", "STC"], "STC": ["AMC"],
        "WBL": ["DL", "ML"], "WBR": ["DR", "MR"], "ML": ["AML", "DL"], "MR": ["AMR", "DR"]}
POS_FIELDS = ["gk", "sw", "dl", "dc", "dr", "wbl", "wbr", "dm", "ml", "mc", "mr", "aml", "amc", "amr", "stc"]


def make_player(uid, name, age, club, natural, accomplished=(), level=12.0, slot=0, **extra):
    seed = f"p{uid}"
    attrs = {}
    keys = {k for c in natural for k in KEY.get(c, [])}
    for a in OUT_ATTRS + GK_ATTRS:
        base = level + (3.2 if a in keys else -1.5) + (h(seed, a) - 0.5) * 5
        if a in GK_ATTRS and "GK" not in natural:
            base = 2 + h(seed, a) * 4
        if "GK" in natural and a in ("finishing", "dribbling", "crossing", "marking", "tackling", "heading", "long_shots"):
            base = 2 + h(seed, a) * 5
        attrs[a] = int(max(1, min(20, round(base))))
    fam = {f: 1 for f in POS_FIELDS}
    for c in natural:
        for n in NEAR.get(c, []):
            fam[n.lower()] = max(fam[n.lower()], 9 + int(h(seed, n) * 5))
    for c in accomplished:
        fam[c.lower()] = 16
    for c in natural:
        fam[c.lower()] = 20
    ca = int(60 + level * 8 + (h(seed, "ca") - .5) * 20)
    p = NS(uid=uid, name=name, age=age, club_uid=club.uid, club_name=club.name, team_slot=slot,
           natural_positions=list(natural), accomplished_positions=list(accomplished),
           positions=NS(**fam), attributes=NS(**attrs), ability=NS(current=ca, potential=min(200, ca + (max(0, 24 - age) * 6))),
           contract=NS(wage=int(20000 + level * 9000 * (0.6 + h(seed, "w"))), end=date(2027 + int(h(seed, "c") * 4), 6, 30)),
           transfer_value=int(level ** 3 * 9000 * (0.5 + h(seed, "v"))), transfer_value_state="ok",
           on_loan=False, loan_parent_club_uid=None, loan_parent_club_name=None, loan_end=None, suspensions=[])
    p.__dict__.update(extra)
    return p


CLUB_NAMES = ["Liverpool", "Arsenal", "Manchester City", "Chelsea", "Newcastle", "Aston Villa", "Tottenham", "Manchester United",
              "Brighton", "Nottingham Forest", "Bournemouth", "Brentford", "Fulham", "Crystal Palace", "West Ham", "Everton",
              "Wolverhampton", "Leeds", "Sunderland", "Burnley"]
STRENGTH = {n: 15.5 - i * 0.35 for i, n in enumerate(CLUB_NAMES)}
STRENGTH["Arsenal"], STRENGTH["Manchester City"], STRENGTH["Liverpool"] = 15.8, 15.6, 15.3


def build_world():
    clubs = []
    for i, n in enumerate(CLUB_NAMES, 1):
        teams = [NS(team_id=i * 10 + s, slot=s) for s in range(3)]
        clubs.append(NS(uid=i, name=n, short_name=n.replace("Manchester ", "Man ").replace("Wolverhampton", "Wolves")
                        .replace("Nottingham Forest", "Nott'm Forest"), teams=teams))
    by = {c.name: c for c in clubs}
    lfc = by["Liverpool"]
    players, contracts, injuries = [], [], []
    uid = 1000

    def add(name, age, natural, acc=(), level=12.5, slot=0, club=lfc, **extra):
        nonlocal uid
        uid += 1
        p = make_player(uid, name, age, club, natural, acc, level, slot, **extra)
        players.append(p)
        return p

    # --- Liverpool first team ---
    sq = {}
    for name, age, nat, acc, lv in [
        ("Alisson Becker", 34, ["GK"], [], 15.6), ("Giorgi Mamardashvili", 26, ["GK"], [], 14.2), ("Freddie Woodman", 29, ["GK"], [], 10.5),
        ("Milos Kerkez", 23, ["DL"], ["WBL"], 14.6), ("Andrew Robertson", 32, ["DL"], ["WBL"], 13.0),
        ("Virgil van Dijk", 35, ["DC"], [], 16.0), ("Jérémy Jacquet", 21, ["DC"], [], 13.6), ("Joe Gomez", 29, ["DC"], ["DR", "DL"], 13.2),
        ("Giovanni Leoni", 19, ["DC"], [], 12.4), ("Ronald Araújo", 27, ["DR"], ["DC"], 14.6), ("Jeremie Frimpong", 25, ["DR", "WBR"], ["AMR"], 13.0),
        ("Conor Bradley", 23, ["DR"], [], 12.6),
        ("Alexis Mac Allister", 27, ["DM", "MC"], [], 15.6), ("Dominik Szoboszlai", 26, ["MC", "AMC"], ["DM"], 15.4),
        ("Ryan Gravenberch", 24, ["DM", "MC"], [], 15.0), ("Wataru Endo", 33, ["DM"], ["DC"], 12.6), ("Curtis Jones", 25, ["MC"], ["DM"], 13.2),
        ("Florian Wirtz", 23, ["AMC"], ["AML"], 16.6), ("Rio Ngumoha", 18, ["AML"], [], 12.8), ("Cody Gakpo", 27, ["AML", "STC"], [], 14.4),
        ("Bradley Barcola", 24, ["AMR", "AML"], [], 14.8), ("Federico Chiesa", 29, ["AMR"], ["AML"], 13.4),
        ("Alexander Isak", 27, ["STC"], [], 16.0), ("Hugo Ekitiké", 24, ["STC"], ["AML"], 14.6)]:
        sq[name] = add(name, age, nat, acc, lv)
    # youth (U21 slot 1, U18 slot 2)
    for name, age, nat, lv, slot in [("Trey Nyoni", 19, ["MC"], 11.4, 1), ("Jayden Danns", 20, ["STC"], 11.0, 1), ("Amara Nallo", 19, ["DC"], 10.6, 1),
                                     ("Kieran Morrison", 18, ["AMR"], 10.2, 1), ("Ranel Young", 17, ["AMC"], 9.6, 2), ("Josh Davidson", 17, ["DL"], 9.2, 2)]:
        sq[name] = add(name, age, nat, (), lv, slot)
    sq["Jeremie Frimpong"].on_loan = False
    # statuses
    sq["Andrew Robertson"].contract.end = date(2027, 6, 30)
    sq["Alisson Becker"].contract.end = date(2027, 6, 30)
    sq["Wataru Endo"].suspensions = [NS(issued_date=TODAY - timedelta(days=6))]
    injuries += [NS(kind="typed", player_uid=sq["Joe Gomez"].uid, date=TODAY + timedelta(days=13), type_name="Hamstring strain"),
                 NS(kind="typed", player_uid=sq["Federico Chiesa"].uid, date=TODAY + timedelta(days=52), type_name="Torn knee ligaments")]
    # loan in: a keeper borrowed from Brentford
    loanee = add("Hákon Valdimarsson", 25, ["GK"], (), 11.2, on_loan=True, loan_parent_club_uid=by["Brentford"].uid,
                 loan_parent_club_name="Brentford", loan_end=date(2027, 6, 30))
    # out on loan
    for name, age, nat, lv, to in [("Harvey Elliott", 23, ["AMC", "AMR"], 13.6, "Aston Villa"), ("Tyler Morton", 23, ["DM"], 12.4, "Everton"),
                                   ("Ben Doak", 21, ["AMR"], 12.6, "Bournemouth")]:
        add(name, age, nat, (), lv, club=by[to], on_loan=True, loan_parent_club_uid=lfc.uid, loan_parent_club_name="Liverpool",
            loan_end=date(2027, 6, 30))
    # arranged moves (future contract entries)
    def move(p, to_club, start, terms):
        contracts.append(NS(player_uid=p.uid, club_uid=p.club_uid, club_name=p.club_name,
                            chain=[NS(start=start, has_terms=terms, club_uid=to_club.uid, club_name=to_club.name)]))
    move(sq["Curtis Jones"], by["Tottenham"], date(2027, 1, 2), True)        # transfer out in January
    move(sq["Trey Nyoni"], by["Sunderland"], date(2027, 1, 2), False)        # loan out in January
    # --- the rest of the league ---
    for c in clubs[1:]:
        lv = STRENGTH[c.name] - 2.2
        shape = ["GK", "GK", "DL", "DL", "DC", "DC", "DC", "DC", "DR", "DR", "DM", "DM", "MC", "MC", "MC", "AMC", "AMC",
                 "AML", "AML", "AMR", "AMR", "STC", "STC", "STC"]
        for k, pos in enumerate(shape):
            add(f"{c.short_name.split()[0][:3]} Player {k + 1}", 19 + int(h(c.uid, k) * 14), [pos], (), lv + (h(c.uid, k, "l") - .5) * 3, club=c)
    # incoming: transfer from Chelsea and a loan from Newcastle, both from January
    tin = next(p for p in players if p.club_name == "Chelsea" and "DR" in p.natural_positions)
    tin.name, tin.age = "Malo Gusto", 23
    move(tin, lfc, date(2027, 1, 2), True)
    lin = next(p for p in players if p.club_name == "Newcastle" and "DC" in p.natural_positions)
    lin.name = "Sven Botman"
    move(lin, lfc, date(2027, 1, 2), False)
    # a scouting target pool exists by virtue of the other clubs
    return clubs, players, contracts, injuries


def league_season(clubs, players):
    """13 played rounds of a double round robin, plus team and player match rows."""
    teams = [c.teams[0].team_id for c in clubs]
    strength = {c.teams[0].team_id: STRENGTH[c.name] for c in clubs}
    order = teams[:]
    fixtures, tms, pms, season_rows = [], [], [], []
    d0 = date(2026, 8, 16)
    for rnd in range(13):
        day = d0 + timedelta(days=7 * rnd + (14 if rnd >= 3 else 0))
        pairs = [(order[i], order[-1 - i]) for i in range(10)]
        order = [order[0]] + [order[-1]] + order[1:-1]
        for k, (a, b) in enumerate(pairs):
            home, away = (a, b) if (rnd + k) % 2 == 0 else (b, a)
            edge = (strength[home] - strength[away]) * 0.35 + 0.25
            hg = max(0, int(round(1.4 + edge + (h("g", rnd, home) - .5) * 3)))
            ag = max(0, int(round(1.1 - edge + (h("g", rnd, away) - .5) * 3)))
            f = NS(competition_id=1, home_team_id=home, away_team_id=away, date=day, played=True, home_goals=hg, away_goals=ag)
            fixtures.append(f)
            for tid, opp, is_home in ((home, away, True), (away, home, False)):
                s = strength[tid] - strength[opp]
                seed = f"t{rnd}{tid}"
                tms.append(Stats(seed, 1.0, competition_id=1, date=day, home_team_id=home, away_team_id=away, team_id=tid,
                                 is_home=is_home, expected_goals=round(1.3 + s * 0.12 + (h(seed, "xg") - .5), 2),
                                 shots=int(13 + s * 1.2 + (h(seed, "s") - .5) * 8), clear_cut_chances=round(1.3 + s * .1 + (h(seed, "c") - .5), 1),
                                 possession_percent=50 + s * 2 + (h(seed, "p") - .5) * 10, progressive_passes=int(40 + s * 3 + h(seed, "pp") * 10),
                                 final_third_passes=int(90 + s * 6 + h(seed, "f3") * 25), distance_km=round(110 + h(seed, "d") * 6, 1),
                                 fouls_made=int(9 + h(seed, "fo") * 6), passes_completed=int(420 + s * 25 + h(seed, "pc") * 60),
                                 passes_attempted=int(510 + s * 22 + h(seed, "pa") * 60), tackles_completed=int(12 + h(seed, "tc") * 6),
                                 tackles_attempted=int(19 + h(seed, "ta") * 6), headers_won=int(12 + h(seed, "hw") * 8),
                                 aerial_challenges_attempted=int(26 + h(seed, "ac") * 8), crosses_completed=int(4 + h(seed, "cc") * 5),
                                 crosses_attempted=int(17 + h(seed, "ca") * 8)))
    # league table
    rows = {t: dict(team_id=t, played=0, won=0, drawn=0, lost=0, goals_for=0, goals_against=0, points=0) for t in teams}
    for f in fixtures:
        for t, gf, ga in ((f.home_team_id, f.home_goals, f.away_goals), (f.away_team_id, f.away_goals, f.home_goals)):
            r = rows[t]
            r["played"] += 1; r["goals_for"] += gf; r["goals_against"] += ga
            r["won" if gf > ga else "drawn" if gf == ga else "lost"] += 1
            r["points"] += 3 if gf > ga else 1 if gf == ga else 0
    ranked = sorted(rows.values(), key=lambda r: (-r["points"], -(r["goals_for"] - r["goals_against"]), -r["goals_for"]))
    table = NS(competition_id=1, rows=[NS(position=i + 1, **r) for i, r in enumerate(ranked)])
    # player match rows (positions played) and season stats
    code_bit = {"GK": 0, "DR": 2, "DL": 3, "DC": 4, "WBR": 5, "WBL": 6, "DM": 7, "MR": 8, "ML": 9, "MC": 10, "AMR": 11, "AML": 12, "AMC": 13, "STC": 14}
    by_club = {}
    for p in players:
        by_club.setdefault(p.club_uid, []).append(p)
    for c in clubs:
        squad = [p for p in by_club.get(c.uid, []) if p.team_slot == 0 and not (p.on_loan and p.loan_parent_club_uid == 1 and c.uid != 1)]
        squad.sort(key=lambda p: -p.ability.current)
        for i, p in enumerate(squad):
            apps = 13 if i < 11 else max(0, 9 - i)
            if apps == 0:
                continue
            mins = apps * (85 if i < 11 else 30)
            if c.uid == 1:
                for rnd in range(apps):
                    pms.append(NS(player_uid=p.uid, has_stats=True, date=d0 + timedelta(days=7 * rnd),
                                  position=NS(raw=1 << code_bit.get(p.natural_positions[0], 10))))
            for kind in ("league", "overall"):
                season_rows.append(Stats(f"s{p.uid}", mins / 900, kind=kind, club_uid=c.uid, player_uid=p.uid, team_slot=0,
                                         minutes=mins, starts=min(apps, 13 if i < 11 else 0), substitute_appearances=0 if i < 11 else apps,
                                         goals=int(h(p.uid, "g") * (9 if "STC" in p.natural_positions else 3)),
                                         assists=int(h(p.uid, "a") * 6), average_rating=round(6.6 + h(p.uid, "r") * 0.9, 2),
                                         clean_sheets=int(h(p.uid, "cs") * 6), yellow_cards=int(h(p.uid, "y") * 4), red_cards=0,
                                         saves_held=None, saves_parried=None, saves_tipped=None, blocks=None, headers_won=None,
                                         penalties_scored=0))
    return fixtures, tms, pms, season_rows, table


def training_weeks():
    names = ["Match Preview", "Balanced", "Pressing Focus", "Attacking Focus", "Recovery Week"]
    out = []
    for slot in (0, 1):
        weeks = []
        wk = date(2026, 7, 6)
        while wk <= date(2026, 12, 21):
            n = names[int(h(slot, wk) * len(names))]
            days = [NS(day=wk + timedelta(days=d), sessions=[NS(raw=r) for r in ([5, 6, 300] if d % 3 == 0 else [0, 1, 2] if d % 3 == 1 else [500, 301, 402])])
                    for d in range(7)]
            weeks.append(NS(week_start=wk, schedule_name=n, days=days))
            wk += timedelta(days=7)
        out.append(NS(team_slot=slot, weeks=weeks))
    return out


class FakeSave:
    def __init__(self):
        self.clubs_, self.players_, self.contracts_, self.injuries_ = build_world()
        self.fixtures_, self.tms_, self.pms_, self.season_, self.table_ = league_season(self.clubs_, self.players_)
        self.info = NS(game_date=TODAY, save_name="Demo career", known_build=True, build="27.0.0")

    def managed_clubs(self): return [NS(club_uid=1, club_name="Liverpool", manager_name="Demo Manager")]
    def players(self): return iter(self.players_)
    def contracts(self): return iter(self.contracts_)
    def injuries(self): return iter(self.injuries_)
    def player_season_stats(self): return iter(self.season_)
    def finances(self): return [NS(club_uid=1, month=date(2026, 11, 1), transfer_budget_remaining=62_000_000,
                                   wage_budget_weekly=5_400_000, wage_payroll_weekly=4_860_000)]
    def clubs(self): return iter(self.clubs_)
    def player_match_stats(self): return iter(self.pms_)
    def training(self): return iter(training_weeks())
    def fixtures(self): return iter(self.fixtures_)
    def league_tables(self): return [self.table_]
    def team_match_stats(self): return iter(self.tms_)
    def competitions(self): return [NS(id=1, name="Premier League")]
    def squad_planner(self): return []
    def close(self): pass
