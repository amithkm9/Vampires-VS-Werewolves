import random
import time
import unittest

from vvw.evaluate import DEFAULT_WEIGHTS
from vvw.movegen import generate_moves
from vvw.safety import ensure_legal, fallback_move
from vvw.search import Searcher
from vvw.state import Board, State, validate


def random_state(rng: random.Random, board: Board) -> State:
    cells = rng.sample(range(board.size), min(board.size, rng.randint(3, 14)))
    v, w, h = {}, {}, {}
    for i, p in enumerate(cells):
        n = rng.choice([1, 2, 3, 5, 8, 12, 20, 40, 120, 200, 250])
        (v, w, h)[i % 3][p] = n
    if not v:
        v[cells[0]] = 5
    if not w:
        w[cells[1]] = 5
    return State(v, w, h)


class MoveGeneration(unittest.TestCase):
    def test_every_generated_turn_is_legal(self):
        """Property test: the generator never proposes a move the server would reject."""
        rng = random.Random(42)
        checked = 0
        for _ in range(400):
            board = Board(rng.randint(2, 12), rng.randint(2, 12))
            st = random_state(rng, board)
            for side in (0, 1):
                for mv in generate_moves(board, st, side, limit=40):
                    self.assertIsNone(validate(board, st, side, mv), (mv, st.g, st.h))
                    checked += 1
        self.assertGreater(checked, 1000)

    def test_fallback_is_always_legal(self):
        rng = random.Random(7)
        for _ in range(500):
            board = Board(rng.randint(1, 6), rng.randint(2, 6))
            st = random_state(rng, board)
            for side in (0, 1):
                self.assertIsNone(validate(board, st, side, fallback_move(board, st, side)))

    def test_ensure_legal_replaces_garbage(self):
        board = Board(4, 4)
        st = State({0: 5}, {15: 5}, {})
        for bad in ([], [(0, 0, 1)], [(0, 9, 1)], [(15, 5, 14)], [(0, 5, 10)]):
            self.assertIsNone(validate(board, st, 0, ensure_legal(board, st, 0, bad)))


class Search(unittest.TestCase):
    def test_respects_deadline(self):
        rng = random.Random(3)
        board = Board(20, 20)
        st = random_state(rng, board)
        s = Searcher(board, 0)
        t0 = time.perf_counter()
        s.choose(st, 150, t0 + 0.2)
        self.assertLess(time.perf_counter() - t0, 0.35)

    def test_takes_free_humans_now(self):
        """The tempo bonus stops the search from postponing a free conversion."""
        b = Board(15, 29)
        P = b.pos
        st = State(
            {P(27, 1): 4, P(18, 10): 6},
            {P(12, 4): 14},
            {P(28, 0): 2, P(14, 7): 20, P(18, 11): 4, P(0, 14): 2},
        )
        mv, _ = Searcher(b, 0, DEFAULT_WEIGHTS, max_depth=6).choose(
            st, 150, time.perf_counter() + 30
        )
        dsts = {d for _, _, d in mv}
        self.assertIn(P(18, 11), dsts)
        self.assertIn(P(28, 0), dsts)

    def test_leader_does_not_gamble(self):
        """Ahead 124-120 with nothing left to convert: never start a coin-flip battle."""
        b = Board(10, 20)
        P = b.pos
        st = State({P(5, 5): 120}, {P(6, 5): 124}, {})
        mv, _ = Searcher(b, 1, max_depth=3).choose(st, 100, time.perf_counter() + 30)
        self.assertNotIn(P(5, 5), {d for _, _, d in mv})

    def test_tie_takes_the_gamble_on_the_last_ply(self):
        """Tied on the last ply: a draw wins nothing, a 50/50 battle wins half the time."""
        b = Board(5, 5)
        P = b.pos
        st = State({P(2, 2): 12}, {P(2, 3): 12}, {})
        mv, _ = Searcher(b, 0, max_depth=2).choose(st, 1, time.perf_counter() + 30)
        self.assertEqual(mv, [(P(2, 2), 12, P(2, 3))])

    def test_tie_does_not_gamble_early(self):
        """Tied with most of the game left: keep playing, the opponent may still blunder."""
        b = Board(10, 10)
        P = b.pos
        st = State({P(4, 4): 12}, {P(5, 4): 12}, {})
        mv, _ = Searcher(b, 0, max_depth=3).choose(st, 150, time.perf_counter() + 30)
        self.assertNotIn(P(5, 4), {d for _, _, d in mv})

    def test_trailer_takes_the_gamble_at_the_end(self):
        """Behind with 1 ply left: the only way to win is to attack."""
        b = Board(5, 5)
        P = b.pos
        st = State({P(2, 2): 10}, {P(2, 3): 12}, {})
        mv, _ = Searcher(b, 0, max_depth=2).choose(st, 1, time.perf_counter() + 30)
        self.assertEqual(mv, [(P(2, 2), 10, P(2, 3))])


if __name__ == "__main__":
    unittest.main()
