import random
import unittest

from sim.referee import perform_moves
from vvw.rules import battle_outcomes, win_probability
from vvw.state import Board, State, apply_moves, validate


class WinProbability(unittest.TestCase):
    """Board.GetProba from the server binary."""

    def test_equal(self):
        self.assertEqual(win_probability(5, 5, False), 0.5)
        self.assertEqual(win_probability(5, 5, True), 0.5)

    def test_weaker_attacker(self):
        self.assertAlmostEqual(win_probability(3, 10, False), 3 / 20)
        self.assertAlmostEqual(win_probability(3, 10, True), 3 / 20)

    def test_stronger_attacker_vs_monsters(self):
        self.assertAlmostEqual(win_probability(12, 10, False), 12 / 10 - 0.5)
        self.assertEqual(win_probability(15, 10, False), 1.0)  # 1.5x inclusive

    def test_defender_at_1_5x_is_not_automatic(self):
        # The PDF says the attackers all die; the server just runs a random battle.
        self.assertAlmostEqual(win_probability(10, 15, False), 10 / 30)

    def test_humans_threshold_is_1(self):
        self.assertEqual(win_probability(11, 10, True), 1.0)


class Outcomes(unittest.TestCase):
    def test_conversion_is_deterministic(self):
        self.assertEqual(battle_outcomes(4, 4, True), [(1.0, True, 8)])

    def test_kill_is_inclusive(self):
        self.assertEqual(battle_outcomes(15, 10, False), [(1.0, True, 15)])
        self.assertEqual(len(battle_outcomes(14, 10, False)), 2)

    def test_random_battle_probabilities_sum_to_one(self):
        outs = battle_outcomes(7, 10, False)
        self.assertAlmostEqual(sum(p for p, _, _ in outs), 1.0)


class Validation(unittest.TestCase):
    """Mirror of Board.CheckMoves (+ crash cases)."""

    def setUp(self):
        self.b = Board(5, 5)
        P = self.b.pos
        self.P = P
        self.s = State({P(1, 1): 10, P(3, 3): 4}, {P(4, 0): 5}, {P(0, 4): 3})

    def test_ok(self):
        P = self.P
        self.assertIsNone(validate(self.b, self.s, 0, [(P(1, 1), 10, P(2, 2))]))
        self.assertIsNone(
            validate(self.b, self.s, 0, [(P(1, 1), 4, P(2, 2)), (P(1, 1), 6, P(0, 0))])
        )

    def test_empty_is_static_cheat(self):
        self.assertIsNotNone(validate(self.b, self.s, 0, []))

    def test_zero_count(self):
        P = self.P
        self.assertIsNotNone(validate(self.b, self.s, 0, [(P(1, 1), 0, P(2, 2))]))

    def test_rule5_source_and_target(self):
        P = self.P
        moves = [
            (P(1, 1), 5, P(2, 2)),
            (P(3, 3), 4, P(1, 1) + 0),
        ]  # (3,3)->(1,1) not adjacent anyway
        self.assertIsNotNone(validate(self.b, self.s, 0, moves))
        chain = [(P(1, 1), 5, P(2, 2)), (P(2, 2), 1, P(3, 3))]
        self.assertIsNotNone(validate(self.b, self.s, 0, chain))

    def test_not_ours(self):
        P = self.P
        self.assertIsNotNone(validate(self.b, self.s, 0, [(P(4, 0), 5, P(3, 0))]))

    def test_too_many_summed(self):
        P = self.P
        moves = [(P(1, 1), 6, P(2, 2)), (P(1, 1), 6, P(0, 0))]
        self.assertIsNotNone(validate(self.b, self.s, 0, moves))

    def test_not_adjacent(self):
        P = self.P
        self.assertIsNotNone(validate(self.b, self.s, 0, [(P(1, 1), 3, P(3, 1))]))

    def test_stay_in_place_is_rejected(self):
        P = self.P
        self.assertIsNotNone(validate(self.b, self.s, 0, [(P(1, 1), 3, P(1, 1))]))

    def test_byte_overflow(self):
        P = self.P
        s = State({P(1, 1): 200, P(2, 2): 100}, {P(4, 4): 1}, {})
        self.assertIsNotNone(validate(self.b, s, 0, [(P(1, 1), 200, P(2, 2))]))


class Transition(unittest.TestCase):
    def setUp(self):
        self.b = Board(5, 5)
        self.P = self.b.pos

    def test_merge_convert_kill(self):
        P = self.P
        s = State({P(0, 0): 6, P(2, 0): 9}, {P(3, 1): 6}, {P(0, 1): 6})
        out = apply_moves(s, 0, [(P(0, 0), 6, P(0, 1)), (P(2, 0), 9, P(3, 1))])
        self.assertEqual(len(out), 1)
        st = out[0][1]
        self.assertEqual(st.g[0], {P(0, 1): 12, P(3, 1): 9})
        self.assertEqual(st.g[1], {})
        self.assertEqual(st.h, {})

    def test_moves_into_same_target_are_summed(self):
        P = self.P
        s = State({P(0, 0): 3, P(2, 0): 3}, {}, {P(1, 0): 6})
        st = apply_moves(s, 0, [(P(0, 0), 3, P(1, 0)), (P(2, 0), 3, P(1, 0))])[0][1]
        self.assertEqual(st.g[0], {P(1, 0): 12})

    def test_random_battle_branches(self):
        P = self.P
        s = State({P(0, 0): 4}, {}, {P(1, 0): 8})
        out = apply_moves(s, 0, [(P(0, 0), 4, P(1, 0))])
        self.assertEqual(len(out), 2)
        self.assertAlmostEqual(sum(p for p, _ in out), 1.0)

    def test_referee_matches_model_on_deterministic_moves(self):
        P = self.P
        s = State({P(0, 0): 6, P(2, 0): 9}, {P(3, 1): 6}, {P(0, 1): 6})
        model = apply_moves(s, 0, [(P(0, 0), 6, P(0, 1)), (P(2, 0), 9, P(3, 1))])[0][1]
        real = s.copy()
        perform_moves(real, 0, [(P(0, 0), 6, P(0, 1)), (P(2, 0), 9, P(3, 1))], random.Random(0))
        self.assertEqual((model.g, model.h), (real.g, real.h))

    def test_referee_random_battle_statistics(self):
        """Empirical win rate of the referee's dice matches GetProba."""
        P = self.P
        rng = random.Random(1)
        wins = 0
        n = 4000
        for _ in range(n):
            s = State({P(0, 0): 6}, {P(1, 0): 10}, {})
            perform_moves(s, 0, [(P(0, 0), 6, P(1, 0))], rng)
            wins += P(1, 0) in s.g[0] or (not s.g[1])
        self.assertAlmostEqual(wins / n, 6 / 20, delta=0.03)


if __name__ == "__main__":
    unittest.main()
