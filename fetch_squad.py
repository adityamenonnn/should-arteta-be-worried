"""
Fetches Arsenal's current squad from the FPL API and rebuilds data/players.json.
Maps players to 4-3-3 formation positions based on minutes played.
"""

import json
from pathlib import Path

import requests

FPL_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
OUT_PATH = Path(__file__).parent / "data" / "players.json"

# FPL position types
POS_MAP = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

# Manual mapping of known players to their actual 4-3-3 positions.
# FPL lumps everyone into GK/DEF/MID/FWD, so we need to be specific.
POSITION_OVERRIDES = {
    "David Raya": "GK",
    "Benjamin White": "RB",
    "William Saliba": "RCB",
    "Gabriel dos Santos Magalhães": "LCB",
    "Riccardo Calafiori": "LB",
    "Jurriën Timber": "LB",
    "Cristhian Mosquera": "RCB",
    "Ezri Konsa": "RCB",
    "Piero Hincapié": "LCB",
    "Declan Rice": "CDM",
    "Martin Ødegaard": "RCM",
    "Mikel Merino": "LCM",
    "Martín Zubimendi": "CDM",
    "Bruno Guimarães": "CDM",
    "Eberechi Eze": "RCM",
    "Bukayo Saka": "RW",
    "Noni Madueke": "RW",
    "Gabriel Martinelli": "LW",
    "Myles Lewis-Skelly": "LW",
    "Christos Tzolis": "LW",
    "Ethan Nwaneri": "RCM",
    "Kai Havertz": "ST",
    "Viktor Gyökeres": "ST",
    "Gabriel Fernando de Jesus": "ST",
}

# Players to skip (youth/loans/not first team)
SKIP_PLAYERS = {"Dowman", "Reiss Nelson", "Ferreira Vieira", "Kepa", "Meslier"}


def match_override(full_name):
    """Match a full FPL name to our override keys (partial match)."""
    for key in POSITION_OVERRIDES:
        if key.lower() in full_name.lower():
            return POSITION_OVERRIDES[key]
    return None


def build_stats(p):
    """Build a stats dict from FPL element data. These are simplified
    but proportional to real performance."""
    pos = POS_MAP[p["element_type"]]
    mins = max(p.get("minutes", 0), 1)
    per90 = 90.0 / mins if mins > 0 else 0

    goals = p.get("goals_scored", 0)
    assists = p.get("assists", 0)
    cs = p.get("clean_sheets", 0)
    creativity = p.get("creativity", "0")
    influence = p.get("influence", "0")
    threat = p.get("threat", "0")
    ict = p.get("ict_index", "0")

    creativity = float(creativity)
    influence = float(influence)
    threat = float(threat)

    # Derive approximate per-90 stats from FPL metrics
    stats = {}

    if pos == "GK":
        stats = {
            "save_pct": 70 + cs * 2,
            "clean_sheet_pct": round(cs / max(mins / 90, 1) * 100, 1),
            "pass_completion": 85.0,
            "long_pass_completion": 58.0,
            "distribution_accuracy": 82.0,
        }
    elif pos == "DEF":
        stats = {
            "tackles_per90": round(1.5 + influence * per90 * 0.02, 2),
            "interceptions_per90": round(1.2 + influence * per90 * 0.015, 2),
            "progressive_passes_per90": round(3.0 + creativity * per90 * 0.03, 2),
            "aerial_won_pct": 62.0,
            "pass_completion": 88.0,
            "press_per90": round(10.0 + influence * per90 * 0.02, 2),
            "blocks_per90": 1.3,
            "clearances_per90": 3.0,
            "crosses_per90": round(0.5 + creativity * per90 * 0.02, 2),
            "key_passes_per90": round(0.4 + creativity * per90 * 0.02, 2),
            "xa_per90": round(assists * per90 * 0.08, 3),
            "dribbles_per90": round(0.5 + creativity * per90 * 0.01, 2),
            "progressive_carries_per90": round(0.8 + creativity * per90 * 0.02, 2),
        }
    elif pos == "MID":
        stats = {
            "tackles_per90": round(1.0 + influence * per90 * 0.015, 2),
            "interceptions_per90": round(0.8 + influence * per90 * 0.01, 2),
            "progressive_passes_per90": round(4.0 + creativity * per90 * 0.05, 2),
            "key_passes_per90": round(1.0 + creativity * per90 * 0.04, 2),
            "through_balls_per90": round(0.1 + creativity * per90 * 0.005, 2),
            "pass_completion": 84.0,
            "press_per90": round(12.0 + influence * per90 * 0.02, 2),
            "dribbles_per90": round(1.0 + creativity * per90 * 0.03, 2),
            "xa_per90": round(assists * per90 * 0.1, 3),
            "xg_per90": round(goals * per90 * 0.12, 3),
            "shot_creating_actions_per90": round(2.0 + creativity * per90 * 0.04, 2),
            "progressive_carries_per90": round(2.0 + creativity * per90 * 0.03, 2),
            "crosses_per90": round(0.8 + creativity * per90 * 0.02, 2),
            "aerial_won_pct": 50.0,
        }
    else:  # FWD
        stats = {
            "xg_per90": round(goals * per90 * 0.15, 3),
            "xa_per90": round(assists * per90 * 0.08, 3),
            "aerial_won_pct": 52.0,
            "key_passes_per90": round(0.6 + creativity * per90 * 0.03, 2),
            "dribbles_per90": round(1.0 + threat * per90 * 0.01, 2),
            "press_per90": round(15.0 + influence * per90 * 0.02, 2),
            "shot_creating_actions_per90": round(2.0 + creativity * per90 * 0.03, 2),
            "progressive_carries_per90": round(2.0 + threat * per90 * 0.02, 2),
            "through_balls_per90": round(0.1 + creativity * per90 * 0.003, 2),
            "pass_completion": 78.0,
        }

    return stats


def main():
    print("Fetching FPL data...")
    resp = requests.get(FPL_URL)
    resp.raise_for_status()
    data = resp.json()

    teams = {t["id"]: t["name"] for t in data["teams"]}
    arsenal_id = next(tid for tid, name in teams.items() if name == "Arsenal")

    players = [p for p in data["elements"] if p["team"] == arsenal_id]
    players.sort(key=lambda x: (x["element_type"], -x.get("minutes", 0)))

    arsenal_squad = []
    # Track which formation positions are filled for the starting XI
    filled_positions = set()

    for p in players:
        full_name = f"{p['first_name']} {p['second_name']}"
        short_name = p["web_name"]
        fpl_pos = POS_MAP[p["element_type"]]
        formation_pos = match_override(full_name) or fpl_pos

        # Skip youth/loans/non-first-team
        if any(skip.lower() in full_name.lower() for skip in SKIP_PLAYERS):
            continue

        # Skip reserves/youth with 0 minutes for a cleaner squad
        if p.get("minutes", 0) == 0 and formation_pos in filled_positions:
            continue

        player_entry = {
            "id": p["second_name"].lower().replace(" ", "_").replace("á", "a")
                  .replace("é", "e").replace("í", "i").replace("ö", "o")
                  .replace("ø", "o").replace("ã", "a").replace("ü", "u"),
            "name": short_name,
            "full_name": full_name,
            "position": formation_pos,
            "nation": "",  # FPL doesn't provide nationality easily
            "age": 0,
            "minutes": p.get("minutes", 0),
            "stats": build_stats(p),
        }

        arsenal_squad.append(player_entry)
        filled_positions.add(formation_pos)

    # Pick the starting XI: highest minutes per position
    starting = {}
    bench = []
    for player in arsenal_squad:
        pos = player["position"]
        if pos not in starting or player["minutes"] > starting[pos]["minutes"]:
            if pos in starting:
                bench.append(starting[pos])
            starting[pos] = player
        else:
            bench.append(player)

    starting_list = list(starting.values())
    bench_list = bench

    # Build output
    output = {
        "arsenal": starting_list,
        "bench": bench_list,
        "targets": []  # User can add transfer targets separately
    }

    OUT_PATH.parent.mkdir(exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(starting_list)} starters + {len(bench_list)} bench to {OUT_PATH}")
    print("\nStarting XI:")
    for p in sorted(starting_list, key=lambda x: ["GK","RB","RCB","LCB","LB","CDM","RCM","LCM","RW","ST","LW"].index(x["position"]) if x["position"] in ["GK","RB","RCB","LCB","LB","CDM","RCM","LCM","RW","ST","LW"] else 99):
        print(f"  {p['position']:4s} {p['name']}")


if __name__ == "__main__":
    main()
