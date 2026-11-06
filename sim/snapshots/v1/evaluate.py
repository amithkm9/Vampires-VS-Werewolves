"""Static evaluation of a position, from one player's point of view.

score = utility( material + human_race + combat ) where utility is a squashed
(tanh) curve: concave when ahead (avoid gambles) and convex when behind
(gambles become attractive). Expectimax over this utility gives risk-aware play.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .state import Board, State

WIN = 1_000_000.0


@dataclass
class Weights:
    gamma: float = 0.82  # per-step discount on future captures
    human: float = 0.85  # weight of human-race claims
    second_claim: float = 0.55  # multiplier on a group's k-th claim (it can't be everywhere)
    threat_adj_killer_moves: float = 0.95  # killer is adjacent and moves next: almost dead
    threat_adj_victim_moves: float = 0.25  # killer adjacent, but victim moves first (may flee)
    threat_far: float = 0.30  # killer at distance d>=2: threat_far * gamma^(d-2)
    threat_range: int = 8
    tempo: float = 0.8  # search: bonus per unit of material won, discounted per ply
    tempo_decay: float = 0.8
    behind_close: float = 0.15  # when behind with no humans: reward closing distance
    split_penalty: float = 0.4  # per extra group (fragmentation)
    utility_scale: float = 0.30  # tanh width as a fraction of creatures on board
    utility_gain: float = 0.6  # extra slope of the utility around a level score


DEFAULT_WEIGHTS = Weights()


def terminal_value(state: State, me: int, plies_left: int, depth_from_root: int):
    """Return a value if the game is over, else None."""
    u = state.total(me)
    t = state.total(1 - me)
    if t == 0 and u > 0:
        return WIN - depth_from_root + u
    if u == 0:
        return -WIN + depth_from_root - t
    if plies_left <= 0:
        if u > t:
            return WIN / 2 + (u - t)
        if u < t:
            return -WIN / 2 + (u - t)
        return 0.0
    return None


def evaluate(
    board: Board,
    state: State,
    me: int,
    to_move: int,
    plies_left: int,
    w: Weights = DEFAULT_WEIGHTS,
) -> float:
    op = 1 - me
    mine = state.g[me]
    theirs = state.g[op]
    hum = state.h
    u = sum(mine.values())
    t = sum(theirs.values())
    raw = float(u - t)
    dist = board.dist
    D = board.D
    gamma = w.gamma

    # Moves each side still gets before the game ends.
    if to_move == me:
        my_moves = (plies_left + 1) // 2
        op_moves = plies_left // 2
    else:
        my_moves = plies_left // 2
        op_moves = (plies_left + 1) // 2

    # ---- Human race: who reaches each human cell first with enough creatures.
    if hum:
        my_claims = {}
        op_claims = {}
        for hp, c in hum.items():
            Dh = D[hp]
            best_m, gm = 999, -1
            for gp, n in mine.items():
                if n >= c:
                    d = Dh[gp]
                    if d < best_m:
                        best_m, gm = d, gp
            best_o, go = 999, -1
            for gp, n in theirs.items():
                if n >= c:
                    d = Dh[gp]
                    if d < best_o:
                        best_o, go = d, gp
            if best_m > my_moves:
                best_m = 999
            if best_o > op_moves:
                best_o = 999
            if best_m == 999 and best_o == 999:
                continue
            # Ties go to the side that moves next.
            em = best_m - (0.5 if to_move == me else 0.0)
            eo = best_o - (0.5 if to_move == op else 0.0)
            if em < eo:
                my_claims.setdefault(gm, []).append(c * gamma**best_m)
            else:
                op_claims.setdefault(go, []).append(c * gamma**best_o)
        for claims, sign in ((my_claims, 1.0), (op_claims, -1.0)):
            for vals in claims.values():
                vals.sort(reverse=True)
                f = 1.0
                for v in vals:
                    raw += sign * w.human * f * v
                    f *= w.second_claim

    # ---- Combat: every group the other side can kill (>= 1.5x) is at risk.
    # One term per victim (max over killers), so threat and hunt aren't double counted.
    for victims, killers, sign, side in ((mine, theirs, 1.0, me), (theirs, mine, -1.0, op)):
        victim_moves_next = to_move == side
        for gp, n in victims.items():
            worst = 0.0
            Dg = D[gp]
            for ep, e in killers.items():
                if e >= 1.5 * n:
                    d = Dg[ep]
                    if d == 1:
                        f = (
                            w.threat_adj_victim_moves
                            if victim_moves_next
                            else w.threat_adj_killer_moves
                        )
                    elif d <= w.threat_range:
                        f = w.threat_far * gamma ** (d - 2)
                    else:
                        continue
                    if f > worst:
                        worst = f
            if worst:
                raw -= sign * worst * n

    # ---- Fragmentation: many small groups are easy prey.
    raw -= w.split_penalty * (len(mine) - 1)
    raw += w.split_penalty * (len(theirs) - 1)

    # ---- Endgame when behind and nothing left to convert: close the distance.
    if not hum and u < t and mine and theirs:
        dmin = min(dist(a, b) for a in mine for b in theirs)
        raw -= w.behind_close * dmin

    # ---- Risk-aware utility: slope (1 + gain) near a level score, 1 far from it.
    # Concave when ahead (gambles cost more than they gain), convex when behind.
    k = max(4.0, w.utility_scale * (u + t))
    return raw + w.utility_gain * k * math.tanh(raw / k)
