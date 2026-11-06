"""Coordinate-descent tuning of evaluation weights by self-play.

    uv run --no-project python -m sim.tune --rounds 2

Objective: mean score (win=1, draw=.5) of a fixed-depth AI with candidate weights
against a ladder of opponents, on many maps, both sides. Fixed depth makes every
game deterministic given the dice seed, so comparisons are not polluted by timing.
A change is kept only if it beats the incumbent by more than `--min-gain`.
Validate the result on a different map seed before adopting it.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace

from vvw.evaluate import DEFAULT_WEIGHTS

from .tournament import build_maps, run_match

GRID = {
    "risk": [0.05, 0.1, 0.15, 0.25, 0.4],
    "tempo": [0.3, 0.6, 0.8, 1.2, 2.0],
    "human": [0.6, 0.75, 0.85, 1.0, 1.2],
    "gamma": [0.75, 0.82, 0.88, 0.92],
    "threat_far": [0.1, 0.2, 0.3, 0.45],
    "threat_adj_victim_moves": [0.1, 0.25, 0.4],
    "k_end": [1.5, 2.5, 4.0, 6.0],
    "k_human": [0.2, 0.4, 0.7, 1.0],
    "split_penalty": [0.0, 0.2, 0.4, 0.8],
    "tempo_decay": [0.6, 0.8, 0.9],
}


def score(weights: dict, maps, opponents, depth: int) -> float:
    wj = json.dumps(weights)
    total = 0.0
    for opp in opponents:
        s, _ = run_match(f"aid:{depth}", opp, maps, aw=wj, verbose=False)
        total += s["score"] + 0.001 * s["avg_margin"]
    return total / len(opponents)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rounds", type=int, default=1)
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--random-maps", type=int, default=80)
    p.add_argument("--map-seed", type=int, default=11)
    p.add_argument("--min-gain", type=float, default=0.004)
    p.add_argument("--opponents", default="greedy,aggressive,snapd:v2:3")
    p.add_argument("--params", default=",".join(GRID))
    p.add_argument("--start", default="{}", help="JSON weights to start from")
    p.add_argument("--grid", default="{}", help="JSON overrides of GRID entries")
    args = p.parse_args()
    GRID.update(json.loads(args.grid))
    maps = build_maps("sim/maps/*.xml", args.random_maps, args.map_seed)
    opponents = args.opponents.split(",")
    best = json.loads(args.start)
    best_score = score(best, maps, opponents, args.depth)
    print(f"baseline {best_score:.4f}", flush=True)
    for rnd in range(args.rounds):
        improved = False
        for name in args.params.split(","):
            current = asdict(replace(DEFAULT_WEIGHTS, **best))[name]
            for v in GRID[name]:
                if v == current:
                    continue
                cand = dict(best, **{name: v})
                sc = score(cand, maps, opponents, args.depth)
                mark = ""
                if sc > best_score + args.min_gain:
                    best, best_score, improved, mark = cand, sc, True, "  <== keep"
                print(f"round {rnd} {name}={v}: {sc:.4f}{mark}", flush=True)
        print(f"after round {rnd}: {best_score:.4f} {json.dumps(best)}", flush=True)
        if not improved:
            break
    print("BEST", json.dumps(best))


if __name__ == "__main__":
    main()
