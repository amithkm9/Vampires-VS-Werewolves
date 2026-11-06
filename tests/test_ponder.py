import time
import unittest

from vvw.ponder import Ponderer
from vvw.search import Searcher
from vvw.state import Board, State, apply_moves


def _position():
    b = Board(10, 14)
    P = b.pos
    st = State(
        {P(2, 2): 9, P(3, 7): 4},
        {P(11, 7): 9, P(10, 2): 4},
        {P(6, 1): 3, P(7, 8): 3, P(5, 5): 6, P(8, 4): 6, P(1, 9): 2, P(12, 0): 2},
    )
    return b, st


def _after(state, side, mv):
    return max(apply_moves(state, side, mv), key=lambda br: br[0])[1]


class Ponder(unittest.TestCase):
    def test_hit_continues_deeper_and_matches_fresh_search(self):
        """Pondering the actual position is pure head start: same answer as a fresh search
        of the same depth, reached with the pondered depth already done."""
        b, st = _position()
        me, opp = 0, 1
        s = Searcher(b, me, max_depth=3)
        mv, _ = s.choose(st, 120, time.perf_counter() + 30)
        child, hint = s.expected_reply(st, mv, 120)
        s.forget()
        assert hint is not None
        Ponderer(s).ponder(
            child, 119, stop=lambda: False, deadline=time.perf_counter() + 30, hint=hint
        )
        actual = _after(child, opp, list(hint))
        self.assertIn((actual.key(), 118), s.contexts)
        mv_p, info_p = s.choose(actual, 118, time.perf_counter() + 30)
        self.assertEqual(info_p.pondered, 3)

        fresh = Searcher(b, me, max_depth=3)
        mv_f, info_f = fresh.choose(actual, 118, time.perf_counter() + 30)
        self.assertEqual(mv_p, mv_f)
        self.assertAlmostEqual(info_p.value, info_f.value, places=6)

    def test_stops_promptly(self):
        b, st = _position()
        s = Searcher(b, 0)
        t_stop = time.perf_counter() + 0.05
        t0 = time.perf_counter()
        noticed = Ponderer(s).ponder(st, 119, stop=lambda: time.perf_counter() > t_stop)
        self.assertLess(time.perf_counter() - t0, 0.15)
        assert noticed is not None
        self.assertLess(noticed - t_stop, 0.05)

    def test_miss_is_a_normal_search(self):
        b, st = _position()
        s = Searcher(b, 0, max_depth=2)
        Ponderer(s).ponder(st, 119, stop=lambda: False, deadline=time.perf_counter() + 0.3)
        other = State(dict(st.g[0]), {b.pos(13, 9): 9, b.pos(10, 2): 4}, dict(st.h))
        mv, info = s.choose(other, 118, time.perf_counter() + 30)
        self.assertEqual(info.pondered, 0)
        self.assertTrue(mv)


if __name__ == "__main__":
    unittest.main()
