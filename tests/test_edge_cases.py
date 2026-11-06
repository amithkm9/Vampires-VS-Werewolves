"""Strange-but-legal situations the tournament could throw at us.

For each one: the AI must return a legal move (per the server's own checks), on time,
for both species, over a whole game.
"""

import random
import time
import unittest

from sim.bots import make_bot
from sim.maps import MapSpec
from sim.referee import play_game
from vvw.safety import ensure_legal
from vvw.search import Searcher
from vvw.state import Board, State, validate


def spec(name, rows, cols, humans, v, w):
    return MapSpec(name, rows, cols, dict(humans), v, w)


EDGE_MAPS = [
    spec("1x2 corridor", 1, 2, {}, (0, 0, 5), (1, 0, 5)),
    spec("1x5 corridor", 1, 5, {(2, 0): 3}, (0, 0, 4), (4, 0, 4)),
    spec("5x1 column", 5, 1, {(0, 2): 3}, (0, 0, 4), (0, 4, 4)),
    spec("2x2 all full", 2, 2, {(1, 0): 2, (0, 1): 2}, (0, 0, 3), (1, 1, 3)),
    spec("no humans", 6, 6, {}, (0, 0, 10), (5, 5, 10)),
    spec("adjacent start", 4, 4, {(3, 3): 2}, (1, 1, 5), (2, 2, 5)),
    spec("adjacent, killable", 4, 4, {}, (1, 1, 15), (2, 2, 10)),
    spec("huge armies near byte limit", 6, 6, {(2, 2): 50, (3, 3): 50}, (0, 0, 200), (5, 5, 200)),
    spec("humans would overflow 255", 5, 5, {(1, 1): 100, (3, 3): 100}, (0, 0, 200), (4, 4, 200)),
    spec("one creature each", 5, 5, {(2, 2): 1}, (0, 0, 1), (4, 4, 1)),
    spec("unconvertible humans", 6, 6, {(2, 2): 50, (3, 3): 50}, (0, 0, 5), (5, 5, 5)),
    spec("very unequal", 8, 8, {(4, 4): 3}, (0, 0, 2), (7, 7, 40)),
    spec(
        "many tiny humans",
        8,
        8,
        {
            (x, y): 1
            for x in range(8)
            for y in range(8)
            if (x + y) % 3 == 0 and (x, y) not in ((0, 0), (7, 7))
        },
        (0, 0, 3),
        (7, 7, 3),
    ),
    spec("max-ish board", 60, 60, {(30, 30): 5, (10, 50): 3}, (0, 0, 8), (59, 59, 8)),
]


class EdgeMaps(unittest.TestCase):
    def test_whole_games_never_forfeit(self):
        for m in EDGE_MAPS:
            for bots in (("ai:0.05", "greedy"), ("greedy", "ai:0.05"), ("ai:0.05", "ai:0.05")):
                with self.subTest(map=m.name, bots=bots):
                    r = play_game(
                        m, [make_bot(b) for b in bots], seed=3, max_plays=60, move_time_limit=2.0
                    )
                    self.assertNotIn("bad move", r.reason)
                    self.assertNotIn("crashed", r.reason)
                    self.assertEqual(r.timeouts, [0, 0])


class EdgeStates(unittest.TestCase):
    def test_boxed_in_group_still_moves_legally(self):
        """Every neighbour holds a bigger enemy or humans: we must still send something legal."""
        b = Board(3, 3)
        P = b.pos
        st = State(
            {P(1, 1): 2},
            {P(0, 0): 50, P(1, 0): 50, P(2, 0): 50, P(0, 1): 50},
            {P(2, 1): 40, P(0, 2): 40, P(1, 2): 40, P(2, 2): 40},
        )
        mv, _ = Searcher(b, 0).choose(st, 50, time.perf_counter() + 0.2)
        self.assertIsNone(validate(b, st, 0, ensure_legal(b, st, 0, mv)))

    def test_all_neighbours_full_of_own_255(self):
        b = Board(2, 2)
        st = State({0: 255, 1: 255, 2: 255, 3: 255}, {}, {})
        st.g[1][3] = 1  # (not physically possible, but must not crash)
        del st.g[0][3]
        mv = ensure_legal(b, st, 0, [])
        self.assertTrue(mv)

    def test_random_states_always_legal_after_search(self):
        rng = random.Random(11)
        for _ in range(60):
            b = Board(rng.randint(1, 7), rng.randint(2, 7))
            cells = rng.sample(range(b.size), min(b.size, rng.randint(2, 8)))
            v, w, h = {cells[0]: rng.randint(1, 255)}, {cells[1]: rng.randint(1, 255)}, {}
            for p in cells[2:]:
                rng.choice((v, w, h))[p] = rng.randint(1, 255)
            st = State(v, w, h)
            for side in (0, 1):
                mv, _ = Searcher(b, side).choose(
                    st, rng.randint(1, 200), time.perf_counter() + 0.05
                )
                self.assertIsNone(validate(b, st, side, ensure_legal(b, st, side, mv)))


if __name__ == "__main__":
    unittest.main()
