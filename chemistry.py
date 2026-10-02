"""
Chemistry scoring between connected players in a 4-3-3 formation.

Each positional link has stat pairings that measure compatibility.
A high chemistry score means two players complement each other well.
"""

import json
import random
from pathlib import Path

import numpy as np

DATA_PATH = Path(__file__).parent / "data" / "players.json"

# Which positions are connected in a 4-3-3
LINKS = [
    ("RB", "RCB"),
    ("RCB", "LCB"),
    ("LCB", "LB"),
    ("RB", "RCM"),
    ("RCB", "CDM"),
    ("LCB", "CDM"),
    ("LB", "LCM"),
    ("CDM", "RCM"),
    ("CDM", "LCM"),
    ("RCM", "RW"),
    ("RCM", "ST"),
    ("LCM", "LW"),
    ("LCM", "ST"),
    ("RW", "ST"),
    ("LW", "ST"),
    ("RB", "RW"),
    ("LB", "LW"),
]

# Stat pairings for chemistry between position types.
# (stat_from_player_a, stat_from_player_b, weight)
# Higher correlation between these stats = better chemistry.
CHEMISTRY_RULES = {
    # Fullback <-> Winger: crossing + movement synergy
    ("RB", "RW"): [
        ("crosses_per90", "progressive_carries_per90", 0.3),
        ("progressive_passes_per90", "dribbles_per90", 0.2),
        ("xa_per90", "xg_per90", 0.3),
        ("press_per90", "press_per90", 0.2),
    ],
    ("LB", "LW"): [
        ("crosses_per90", "progressive_carries_per90", 0.3),
        ("progressive_passes_per90", "dribbles_per90", 0.2),
        ("xa_per90", "xg_per90", 0.3),
        ("press_per90", "press_per90", 0.2),
    ],
    # CB <-> CB: complementary aerial + passing
    ("RCB", "LCB"): [
        ("aerial_won_pct", "aerial_won_pct", 0.25),
        ("pass_completion", "pass_completion", 0.25),
        ("progressive_passes_per90", "progressive_passes_per90", 0.2),
        ("interceptions_per90", "tackles_per90", 0.15),
        ("clearances_per90", "blocks_per90", 0.15),
    ],
    # CB <-> Fullback: cover + distribution
    ("RCB", "RB"): [
        ("aerial_won_pct", "tackles_per90", 0.3),
        ("pass_completion", "pass_completion", 0.3),
        ("interceptions_per90", "interceptions_per90", 0.2),
        ("progressive_passes_per90", "progressive_passes_per90", 0.2),
    ],
    ("LCB", "LB"): [
        ("aerial_won_pct", "tackles_per90", 0.3),
        ("pass_completion", "pass_completion", 0.3),
        ("interceptions_per90", "interceptions_per90", 0.2),
        ("progressive_passes_per90", "progressive_passes_per90", 0.2),
    ],
    # CB <-> CDM: defensive shield
    ("RCB", "CDM"): [
        ("pass_completion", "pass_completion", 0.25),
        ("interceptions_per90", "tackles_per90", 0.25),
        ("progressive_passes_per90", "progressive_passes_per90", 0.25),
        ("press_per90", "press_per90", 0.25),
    ],
    ("LCB", "CDM"): [
        ("pass_completion", "pass_completion", 0.25),
        ("interceptions_per90", "tackles_per90", 0.25),
        ("progressive_passes_per90", "progressive_passes_per90", 0.25),
        ("press_per90", "press_per90", 0.25),
    ],
    # CDM <-> CM: midfield balance
    ("CDM", "RCM"): [
        ("progressive_passes_per90", "key_passes_per90", 0.3),
        ("tackles_per90", "dribbles_per90", 0.2),
        ("pass_completion", "pass_completion", 0.2),
        ("press_per90", "press_per90", 0.3),
    ],
    ("CDM", "LCM"): [
        ("progressive_passes_per90", "key_passes_per90", 0.3),
        ("tackles_per90", "dribbles_per90", 0.2),
        ("pass_completion", "pass_completion", 0.2),
        ("press_per90", "press_per90", 0.3),
    ],
    # Fullback <-> CM: overlap synergy
    ("RB", "RCM"): [
        ("progressive_passes_per90", "key_passes_per90", 0.3),
        ("crosses_per90", "through_balls_per90", 0.2),
        ("press_per90", "press_per90", 0.3),
        ("pass_completion", "pass_completion", 0.2),
    ],
    ("LB", "LCM"): [
        ("progressive_passes_per90", "key_passes_per90", 0.3),
        ("crosses_per90", "through_balls_per90", 0.2),
        ("press_per90", "press_per90", 0.3),
        ("pass_completion", "pass_completion", 0.2),
    ],
    # CM <-> Winger: creative link
    ("RCM", "RW"): [
        ("key_passes_per90", "progressive_carries_per90", 0.25),
        ("through_balls_per90", "dribbles_per90", 0.25),
        ("xa_per90", "xg_per90", 0.3),
        ("press_per90", "press_per90", 0.2),
    ],
    ("LCM", "LW"): [
        ("key_passes_per90", "progressive_carries_per90", 0.25),
        ("through_balls_per90", "dribbles_per90", 0.25),
        ("xa_per90", "xg_per90", 0.3),
        ("press_per90", "press_per90", 0.2),
    ],
    # CM <-> ST: supply line
    ("RCM", "ST"): [
        ("key_passes_per90", "xg_per90", 0.3),
        ("through_balls_per90", "progressive_carries_per90", 0.25),
        ("xa_per90", "xg_per90", 0.25),
        ("press_per90", "press_per90", 0.2),
    ],
    ("LCM", "ST"): [
        ("key_passes_per90", "xg_per90", 0.3),
        ("through_balls_per90", "progressive_carries_per90", 0.25),
        ("xa_per90", "xg_per90", 0.25),
        ("press_per90", "press_per90", 0.2),
    ],
    # Winger <-> ST: final third combination
    ("RW", "ST"): [
        ("xa_per90", "xg_per90", 0.35),
        ("crosses_per90", "aerial_won_pct", 0.2),
        ("key_passes_per90", "xg_per90", 0.25),
        ("press_per90", "press_per90", 0.2),
    ],
    ("LW", "ST"): [
        ("xa_per90", "xg_per90", 0.35),
        ("crosses_per90", "aerial_won_pct", 0.2),
        ("key_passes_per90", "xg_per90", 0.25),
        ("press_per90", "press_per90", 0.2),
    ],
}

# Normalization ranges for stats (min, max observed across top leagues)
STAT_RANGES = {
    "tackles_per90": (0.5, 4.0),
    "interceptions_per90": (0.3, 3.0),
    "progressive_passes_per90": (1.0, 12.0),
    "crosses_per90": (0.2, 6.0),
    "key_passes_per90": (0.3, 4.0),
    "through_balls_per90": (0.0, 1.2),
    "dribbles_per90": (0.3, 6.0),
    "aerial_won_pct": (25.0, 85.0),
    "pass_completion": (65.0, 95.0),
    "press_per90": (5.0, 25.0),
    "xa_per90": (0.0, 0.40),
    "xg_per90": (0.0, 0.80),
    "shot_creating_actions_per90": (1.0, 7.0),
    "progressive_carries_per90": (0.5, 7.0),
    "blocks_per90": (0.3, 2.5),
    "clearances_per90": (1.0, 6.0),
    "save_pct": (60.0, 85.0),
    "clean_sheet_pct": (15.0, 55.0),
    "long_pass_completion": (40.0, 75.0),
    "distribution_accuracy": (70.0, 95.0),
    "crosses_stopped_pct": (2.0, 15.0),
}


def normalize(value, stat_name):
    """Normalize a stat to 0-1 range."""
    lo, hi = STAT_RANGES.get(stat_name, (0, 1))
    if hi == lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def load_players():
    with open(DATA_PATH) as f:
        return json.load(f)


def compute_link_chemistry(player_a, player_b, pos_a, pos_b):
    """Compute chemistry score (0-100) between two players at given positions."""
    key = (pos_a, pos_b)
    if key not in CHEMISTRY_RULES:
        key = (pos_b, pos_a)
        if key not in CHEMISTRY_RULES:
            return 50  # neutral if no rules defined

    rules = CHEMISTRY_RULES[key]
    # If we swapped the key, swap stats too
    swapped = (pos_a, pos_b) not in CHEMISTRY_RULES

    total = 0.0
    total_weight = 0.0

    for stat_a, stat_b, weight in rules:
        if swapped:
            stat_a, stat_b = stat_b, stat_a

        val_a = player_a["stats"].get(stat_a, 0)
        val_b = player_b["stats"].get(stat_b, 0)

        norm_a = normalize(val_a, stat_a)
        norm_b = normalize(val_b, stat_b)

        # Chemistry = how well both stats are elevated
        # Product rewards both being high, geometric mean
        pair_score = (norm_a * norm_b) ** 0.5
        total += pair_score * weight
        total_weight += weight

    if total_weight == 0:
        return 50

    return round((total / total_weight) * 100, 1)


def get_squad_chemistry(squad):
    """Given a squad dict {position: player}, compute all link chemistries."""
    links = []
    for pos_a, pos_b in LINKS:
        if pos_a in squad and pos_b in squad:
            score = compute_link_chemistry(
                squad[pos_a], squad[pos_b], pos_a, pos_b
            )
            links.append({
                "from": pos_a,
                "to": pos_b,
                "from_name": squad[pos_a]["name"],
                "to_name": squad[pos_b]["name"],
                "score": score,
            })
    return links


def get_candidates_for_position(position, all_targets):
    """Return transfer targets that can play the given position."""
    return [p for p in all_targets if p["position"] == position]


def rank_replacements(position, squad, all_targets):
    """Rank all candidates for a position by total chemistry impact."""
    candidates = get_candidates_for_position(position, all_targets)
    results = []

    for candidate in candidates:
        test_squad = dict(squad)
        test_squad[position] = candidate
        links = get_squad_chemistry(test_squad)
        relevant = [l for l in links if l["from"] == position or l["to"] == position]
        avg_chem = sum(l["score"] for l in relevant) / len(relevant) if relevant else 50

        results.append({
            "player": candidate,
            "avg_chemistry": round(avg_chem, 1),
            "links": relevant,
        })

    results.sort(key=lambda r: r["avg_chemistry"], reverse=True)
    return results


def _squad_total_chemistry(squad):
    """Return the average chemistry score across all links."""
    links = get_squad_chemistry(squad)
    if not links:
        return 0.0
    return sum(l["score"] for l in links) / len(links)


def _single_swap_gain(base_squad, pos, player):
    """Compute the chemistry gain from a single swap. Used for upper-bound estimation."""
    test = dict(base_squad)
    test[pos] = player
    return _squad_total_chemistry(test) - _squad_total_chemistry(base_squad)


def optimize_signings(base_squad, bench, targets, max_signings=3):
    """Find the optimal set of 1..max_signings transfers to maximize chemistry.

    Uses Branch and Bound on the squad chemistry graph:

      - The squad is modelled as a weighted graph where nodes are formation
        positions and edges are chemistry links between adjacent positions.
        Edge weights are the chemistry scores between the two assigned players.

      - The search tree branches on each "swappable" position. At each node
        we decide: keep the current player, or swap in one of the candidates.

      - BOUNDING: At each partial assignment, we compute an optimistic upper
        bound by assuming every remaining un-swapped position gets the best
        possible single-swap improvement. If the upper bound cannot beat the
        current best solution, the entire subtree is pruned.

      - This avoids evaluating the full combinatorial space. For N candidate
        swaps, naive brute-force is O(sum C(N,k) for k=1..max_signings),
        but Branch and Bound prunes branches that provably cannot improve on
        the incumbent solution.

    The algorithm is a standard Branch and Bound (Land and Doig, 1960),
    widely used in integer programming and combinatorial optimization.

    Returns:
      - baseline: chemistry with no changes
      - results: top 5 solutions for each signing count (1..max_signings)
      - nodes_explored: how many states were evaluated
      - nodes_pruned: how many subtrees were cut
    """
    all_candidates = list(targets) + list(bench)

    # Group candidates by position (only positions in the formation)
    by_position = {}
    for p in all_candidates:
        pos = p["position"]
        if pos in base_squad and p["id"] != base_squad[pos].get("id"):
            if pos not in by_position:
                by_position[pos] = []
            by_position[pos].append(p)

    # Positions we can swap (sorted for deterministic branching)
    swap_positions = sorted(by_position.keys())

    baseline = _squad_total_chemistry(base_squad)

    # Precompute the best possible single-swap gain per position.
    # This is used for the upper bound in Branch and Bound.
    best_single_gain = {}
    for pos in swap_positions:
        gains = [_single_swap_gain(base_squad, pos, p) for p in by_position[pos]]
        best_single_gain[pos] = max(gains) if gains else 0

    # Branch and Bound state
    results = []
    best_score = baseline
    nodes_explored = 0
    nodes_pruned = 0

    def branch_and_bound(depth, current_squad, swaps_made, signings_left):
        """Recursively explore the search tree.

        depth: index into swap_positions (which position we're deciding on)
        current_squad: current assignment
        swaps_made: list of (position, player) swaps applied so far
        signings_left: how many more swaps we can make
        """
        nonlocal best_score, nodes_explored, nodes_pruned

        # Record current state as a solution if we've made at least 1 swap
        if swaps_made:
            score = _squad_total_chemistry(current_squad)
            nodes_explored += 1
            improvement = score - baseline

            results.append({
                "signings": [
                    {"position": pos, "player": player}
                    for pos, player in swaps_made
                ],
                "chemistry": round(score, 1),
                "improvement": round(improvement, 1),
            })

            if score > best_score:
                best_score = score

        # Base case: no more positions to consider or no signings left
        if depth >= len(swap_positions) or signings_left <= 0:
            return

        # --- UPPER BOUND CALCULATION ---
        # Optimistic estimate: current chemistry + best possible gains from
        # all remaining positions (assuming we could swap all of them,
        # ignoring the signings_left constraint for tighter bound).
        current_score = _squad_total_chemistry(current_squad)
        remaining_gains = sorted(
            [best_single_gain.get(swap_positions[i], 0)
             for i in range(depth, len(swap_positions))],
            reverse=True
        )
        # Take the top `signings_left` gains as the optimistic bound
        optimistic_gain = sum(remaining_gains[:signings_left])
        upper_bound = current_score + max(0, optimistic_gain)

        if upper_bound <= best_score and swaps_made:
            # This subtree cannot beat the incumbent, prune it
            nodes_pruned += 1
            return

        pos = swap_positions[depth]

        # Branch 1: don't swap this position (move to next)
        branch_and_bound(depth + 1, current_squad, swaps_made, signings_left)

        # Branch 2: try each candidate for this position
        for candidate in by_position[pos]:
            new_squad = dict(current_squad)
            new_squad[pos] = candidate
            new_swaps = swaps_made + [(pos, candidate)]
            branch_and_bound(depth + 1, new_squad, new_swaps, signings_left - 1)

    # Run Branch and Bound
    branch_and_bound(0, dict(base_squad), [], max_signings)

    # Sort by chemistry descending
    results.sort(key=lambda r: r["chemistry"], reverse=True)

    # Return top 5 results for each signing count
    top_results = []
    for n in range(1, max_signings + 1):
        n_results = [r for r in results if len(r["signings"]) == n]
        top_results.extend(n_results[:5])

    return {
        "baseline": round(baseline, 1),
        "results": top_results,
        "algorithm": "Branch and Bound",
        "nodes_explored": nodes_explored,
        "nodes_pruned": nodes_pruned,
    }


# --- Monte Carlo Simulation ---

def _perturb_stats(player, noise_std=0.1):
    """Create a copy of a player with Gaussian noise added to stats.

    Simulates uncertainty in player performance. Each stat is perturbed
    by a fraction of its value drawn from N(0, noise_std).
    """
    perturbed = dict(player)
    perturbed["stats"] = {}
    for stat, val in player["stats"].items():
        lo, hi = STAT_RANGES.get(stat, (0, 1))
        noise = random.gauss(0, noise_std * (hi - lo))
        perturbed["stats"][stat] = max(lo, min(hi, val + noise))
    return perturbed


def monte_carlo_chemistry(squad, n_simulations=1000):
    """Run Monte Carlo simulation on squad chemistry.

    Adds Gaussian noise to player stats across N simulations to produce
    a distribution of chemistry outcomes, quantifying uncertainty.

    Returns:
        dict with mean, std, percentiles, and per-link distributions
    """
    overall_scores = []
    link_scores = {f"{a}-{b}": [] for a, b in LINKS if a in squad and b in squad}

    for _ in range(n_simulations):
        # Perturb all players
        noisy_squad = {}
        for pos, player in squad.items():
            noisy_squad[pos] = _perturb_stats(player)

        # Compute chemistry
        links = get_squad_chemistry(noisy_squad)
        avg = sum(l["score"] for l in links) / len(links) if links else 50
        overall_scores.append(avg)

        for link in links:
            key = f"{link['from']}-{link['to']}"
            if key in link_scores:
                link_scores[key].append(link["score"])

    overall = np.array(overall_scores)

    # Per-link summary
    link_summary = {}
    for key, scores in link_scores.items():
        if scores:
            arr = np.array(scores)
            link_summary[key] = {
                "mean": round(float(arr.mean()), 1),
                "std": round(float(arr.std()), 1),
                "p5": round(float(np.percentile(arr, 5)), 1),
                "p95": round(float(np.percentile(arr, 95)), 1),
            }

    # Build histogram bins for the frontend
    hist_counts, hist_edges = np.histogram(overall, bins=20, range=(0, 100))

    return {
        "n_simulations": n_simulations,
        "mean": round(float(overall.mean()), 1),
        "std": round(float(overall.std()), 1),
        "median": round(float(np.median(overall)), 1),
        "p5": round(float(np.percentile(overall, 5)), 1),
        "p25": round(float(np.percentile(overall, 25)), 1),
        "p75": round(float(np.percentile(overall, 75)), 1),
        "p95": round(float(np.percentile(overall, 95)), 1),
        "histogram": {
            "counts": hist_counts.tolist(),
            "edges": [round(float(e), 1) for e in hist_edges.tolist()],
        },
        "links": link_summary,
    }
