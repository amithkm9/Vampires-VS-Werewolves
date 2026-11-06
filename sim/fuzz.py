"""Protocol fuzzing: many full games through the byte-exact fake server with real clients.

    uv run --no-project python -m sim.fuzz --games 40

Every game runs two `main.py` client processes (the exact tournament setup, pondering on)
over TCP. Any "cheated" verdict, timeout, client crash or hang is a failure.
"""

from __future__ import annotations

import argparse
import random
import subprocess
import sys
import threading
import time
from collections import Counter

from .fake_server import FakeServer
from .maps import load_map, random_map


def one_game(spec, budget: float, seed: int, max_plays: int) -> dict:
    srv = FakeServer(
        spec,
        port=0,
        move_time=2.0,
        max_plays=max_plays,
        end_sleep=0.02,
        seed=seed,
        log=lambda *_: None,
    )
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    cmd = [sys.executable, "main.py", "--name", f"fuzz{seed}", "--budget", str(budget)]
    cmd += ["--max-plays", str(max_plays), "127.0.0.1", str(srv.port)]
    clients = []
    for _ in range(2):
        clients.append(subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE))
        time.sleep(0.05)
    th.join(max_plays * 4.5 + 30)
    errors, hung = [], th.is_alive()
    for c in clients:  # a client crash is a tournament failure
        try:
            _, err = c.communicate(timeout=10)
            if c.returncode != 0:
                errors.append(err.decode(errors="replace")[-500:])
        except subprocess.TimeoutExpired:
            hung = True
            c.kill()
    res = dict(srv.result) if srv.result else {"reason": "server hung"}
    res["client_errors"] = errors
    res["hung"] = hung
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=30)
    p.add_argument("--budget", type=float, default=0.05)
    p.add_argument("--max-plays", type=int, default=200)
    p.add_argument("--seed", type=int, default=99)
    args = p.parse_args()
    rng = random.Random(args.seed)
    specs = [load_map("sim/maps/testmap2.xml"), load_map("sim/maps/thetrap.xml")]
    specs += [random_map(rng, f"fz{i}") for i in range(args.games - len(specs))]
    reasons = Counter()
    failures = 0
    for i, spec in enumerate(specs):
        r = one_game(spec, args.budget, 1000 + i, args.max_plays)
        bad = (
            "cheated" in r["reason"]
            or r.get("timeouts", [0, 0]) != [0, 0]
            or r["client_errors"]
            or r["hung"]
        )
        failures += bool(bad)
        reasons[r["reason"].split(":")[0]] += 1
        if bad:
            print(f"FAIL {spec.name}: {r}")
    print(f"games={len(specs)} failures={failures} outcomes={dict(reasons)}")


if __name__ == "__main__":
    main()
