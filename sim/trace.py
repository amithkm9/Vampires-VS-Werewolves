"""Print a game ply by ply: python -m sim.trace <map.xml> <botV> <botW> [seed] [max_lines]"""

from __future__ import annotations

import sys

from vvw.state import Board

from .bots import make_bot
from .maps import load_map
from .referee import play_game


def main(argv):
    spec = load_map(argv[0])
    seed = int(argv[3]) if len(argv) > 3 else 1
    limit = int(argv[4]) if len(argv) > 4 else 400
    b = Board(spec.rows, spec.cols)
    bots = [make_bot(argv[1]), make_bot(argv[2])]
    r = play_game(spec, bots, seed=seed, record=True)

    def fmt(cells):
        return " ".join(f"({b.xs[p]},{b.ys[p]}):{n}" for p, n in sorted(cells.items()))

    for i, (side, mv, st) in enumerate(r.history[:limit]):
        moves = " ".join(f"({b.xs[s]},{b.ys[s]})-{n}->({b.xs[d]},{b.ys[d]})" for s, n, d in mv)
        print(
            f"{i:3d} {'VW'[side]} {moves:40s} | V {fmt(st.g[0])} | W {fmt(st.g[1])} | H {fmt(st.h)}"
        )
    print("result:", r.winner, r.reason, r.plies, r.totals)


if __name__ == "__main__":
    main(sys.argv[1:])
