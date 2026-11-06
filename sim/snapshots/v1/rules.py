"""Game rules exactly as the server (v3.2.1) implements them. See RULES.md for the evidence."""

from __future__ import annotations

KILL_RATIO = 1.5  # attacker >= 1.5 * defender kills (inclusive)  -- Board.PerformMoves
MAX_CELL = 255  # counts are bytes server-side; above this the server wraps or throws


def win_probability(e1: int, e2: int, vs_humans: bool) -> float:
    """Board.GetProba: probability that e1 attackers beat e2 defenders."""
    if e1 == e2:
        return 0.5
    c = 1.0 if vs_humans else KILL_RATIO
    if e1 >= c * e2:
        return 1.0
    if e1 < e2:
        return e1 / (2.0 * e2)
    return e1 / e2 - 0.5


def converts(attackers: int, humans: int) -> bool:
    return attackers >= humans


def kills(attackers: int, enemies: int) -> bool:
    return attackers >= KILL_RATIO * enemies


def battle_outcomes(attackers: int, defenders: int, vs_humans: bool):
    """Outcomes of an attack, as a list of (probability, attacker_wins, survivors).

    Deterministic cases return a single outcome. A random battle returns two
    outcomes whose survivors are the expected (rounded) counts:
      win  -> each attacker (and each human, vs humans) survives with prob P
      loss -> each defender survives with prob 1-P
    """
    if vs_humans:
        if attackers >= defenders:
            return [(1.0, True, attackers + defenders)]
    elif attackers >= KILL_RATIO * defenders:
        return [(1.0, True, attackers)]
    p = win_probability(attackers, defenders, vs_humans)
    pool = attackers + defenders if vs_humans else attackers
    out = []
    if p > 0.0:
        out.append((p, True, int(round(p * pool))))
    if p < 1.0:
        out.append((1.0 - p, False, int(round((1.0 - p) * defenders))))
    return out
