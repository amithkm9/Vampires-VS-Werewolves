"""Head-to-head matches on many maps, both sides, fixed seeds, in parallel.

uv run --no-project python -m sim.tournament --a ai:0.3 --b greedy --random-maps 20
uv run --no-project python -m sim.tournament --a ai:0.3 --b ai:0.3 --b-weights '{"tempo": 0.0}'
"""

from __future__ import annotations

import argparse
import glob
import json
import multiprocessing as mp
import random
import statistics
import time
from dataclasses import replace

from vvw.evaluate import DEFAULT_WEIGHTS

from .bots import AIBot, make_bot
from .maps import load_map, random_map
from .referee import play_game


def _build(spec: str, weights_json: str, seed: int):
    bot = make_bot(spec, seed)
    if weights_json and isinstance(bot, AIBot):
        bot.weights = replace(DEFAULT_WEIGHTS, **json.loads(weights_json))
    return bot


def _run(job):
    mapspec, a, aw, b, bw, a_side, seed, max_plays = job
    bot_a = _build(a, aw, seed)
    bot_b = _build(b, bw, seed + 1)
    bots = [bot_a, bot_b] if a_side == 0 else [bot_b, bot_a]
    r = play_game(mapspec, bots, seed=seed, max_plays=max_plays)
    a_total = r.totals[a_side]
    b_total = r.totals[1 - a_side]
    outcome = "draw" if r.winner is None else ("win" if r.winner == a_side else "loss")
    return {
        "map": mapspec.name,
        "a_side": a_side,
        "outcome": outcome,
        "reason": r.reason,
        "margin": a_total - b_total,
        "plies": r.plies,
        "a_timeouts": r.timeouts[a_side],
        "a_max_t": max(r.move_times[a_side], default=0.0),
        "a_times": r.move_times[a_side],
        "forfeit": ("bad move" in r.reason or "crashed" in r.reason),
    }


def build_maps(map_glob: str, n_random: int, seed: int):
    maps = [load_map(p) for p in sorted(glob.glob(map_glob))] if map_glob else []
    rng = random.Random(seed)
    maps += [random_map(rng, f"rand{i:02d}") for i in range(n_random)]
    return maps


def run_match(a, b, maps, seeds=1, aw="", bw="", workers=None, max_plays=200, verbose=True):
    jobs = []
    for mi, m in enumerate(maps):
        for s in range(seeds):
            for a_side in (0, 1):
                jobs.append((m, a, aw, b, bw, a_side, 1000 * mi + 17 * s + 1, max_plays))
    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(workers or max(1, mp.cpu_count() - 1)) as pool:
        results = pool.map(_run, jobs, chunksize=1)
    summary = summarize(results)
    summary["wall_s"] = round(time.time() - t0, 1)
    if verbose:
        for r in results:
            if r["outcome"] != "win" or r["forfeit"]:
                print(
                    f"  {r['map']:<14} A as {'VW'[r['a_side']]}: {r['outcome']:<5} margin={r['margin']:+d} ({r['reason']})"
                )
        print(json.dumps(summary))
    return summary, results


def summarize(results):
    n = len(results)
    wins = sum(r["outcome"] == "win" for r in results)
    draws = sum(r["outcome"] == "draw" for r in results)
    times = sorted(t for r in results for t in r["a_times"])
    return {
        "games": n,
        "win": wins,
        "draw": draws,
        "loss": n - wins - draws,
        "score": round((wins + 0.5 * draws) / n, 3) if n else 0.0,
        "avg_margin": round(statistics.mean(r["margin"] for r in results), 2) if n else 0.0,
        "a_forfeits": sum(r["forfeit"] and r["outcome"] == "loss" for r in results),
        "a_timeouts": sum(r["a_timeouts"] for r in results),
        "a_p50_ms": round(1000 * times[len(times) // 2], 1) if times else 0,
        "a_p99_ms": round(1000 * times[int(len(times) * 0.99)], 1) if times else 0,
        "a_max_ms": round(1000 * times[-1], 1) if times else 0,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--a", default="ai:0.3")
    p.add_argument("--b", default="greedy")
    p.add_argument("--a-weights", default="")
    p.add_argument("--b-weights", default="")
    p.add_argument("--maps", default="sim/maps/*.xml")
    p.add_argument("--random-maps", type=int, default=10)
    p.add_argument("--map-seed", type=int, default=7)
    p.add_argument("--seeds", type=int, default=1)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--max-plays", type=int, default=200)
    args = p.parse_args()
    maps = build_maps(args.maps, args.random_maps, args.map_seed)
    run_match(
        args.a,
        args.b,
        maps,
        args.seeds,
        args.a_weights,
        args.b_weights,
        args.workers,
        args.max_plays,
    )


if __name__ == "__main__":
    main()
