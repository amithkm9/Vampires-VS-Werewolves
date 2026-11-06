"""Static evaluation of a position, from one player's point of view.

Everything is measured on ONE scale, so heuristic scores and game-ending
outcomes are comparable:

    value = raw + G * tanh(raw / k)

- raw  : expected final material margin (material + human race + combat terms)
- G    : what winning the game is worth, in creatures (fixed for a whole search)
- k    : how uncertain the final result still is. Large while many humans are
         left, small in the endgame (a 2-creature lead with nothing left to
         convert is almost a sure win).

So (value - raw) / G ~ 2*P(win) - 1, an estimate of the win probability.
Terminal positions are worth +-1.5*G + margin. Expectimax over this value is
risk-aware for free: when ahead, a coin-flip battle throws away a likely win;
when clearly behind, the same gamble is the best hope.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .rules import attack_ev
from .state import Board, State

TERMINAL = 1.5  # terminal outcomes are worth TERMINAL * G (above any heuristic value)
DRAW = -0.25  # value of a draw at the ply limit, in units of G


@dataclass
class Weights:
    gamma: float = 0.82  # per-step discount on future captures
    human: float = 0.85  # weight of human-race claims
    chain_len: int = 4  # max captures per greedy tour
    threat_adj_killer_moves: float = 0.95  # attacker adjacent and moves next
    threat_adj_victim_moves: float = 0.25  # attacker adjacent, but victim moves first (may flee)
    threat_far: float = 0.30  # attacker at distance d>=2: threat_far * gamma^(d-2)
    threat_range: int = 8
    exposure: float = 0.5  # endgame: nudge per contact with a non-killable enemy
    behind_close: float = 0.15  # endgame when behind: reward closing distance
    split_penalty: float = 0.4  # per extra group (fragmentation)
    risk: float = 0.15  # search: penalty per unit of mean absolute deviation of OUR gambles
    tempo: float = 0.8  # search: bonus per creature won, discounted per ply (x root slope)
    tempo_decay: float = 0.8
    k_end: float = 2.5  # outcome uncertainty (creatures) with no humans left
    k_human: float = 0.4  # extra uncertainty per remaining human
    k_time: int = 30  # uncertainty shrinks over the last k_time plies


DEFAULT_WEIGHTS = Weights()


def win_value(state: State) -> float:
    """G: how much winning is worth, in creatures. Fixed once per search."""
    return max(20.0, 2.0 * (state.total(0) + state.total(1) + sum(state.h.values())))


def _tours(D, groups, hum, moves_left: int, gamma: float, chain_len: int):
    """Greedy capture tour for every group: repeatedly go for the most valuable
    (discounted) human cell it is big enough to convert, growing as it goes.
    Returns {human_cell: earliest arrival time} for this side."""
    arrival = {}
    for gp, n in groups.items():
        pos, size, t = gp, n, 0
        taken = set()
        for _ in range(chain_len):
            Dp = D[pos]
            best_v, best = 0.0, None
            for hp, c in hum.items():
                if c <= size and hp not in taken:
                    tt = t + Dp[hp]
                    if tt <= moves_left:
                        v = c * gamma**tt
                        if v > best_v:
                            best_v, best = v, (hp, c, tt)
            if best is None:
                break
            hp, c, tt = best
            taken.add(hp)
            if tt < arrival.get(hp, 1_000):
                arrival[hp] = tt
            pos, size, t = hp, size + c, tt
    return arrival


def terminal_value(state: State, me: int, plies_left: int, depth_from_root: int, G: float):
    """Value of a finished game (None if not finished). Faster wins / slower losses preferred."""
    u = state.total(me)
    t = state.total(1 - me)
    if t == 0 and u > 0:
        return TERMINAL * G + u - 0.01 * depth_from_root
    if u == 0:
        return -TERMINAL * G - t + 0.01 * depth_from_root
    if plies_left <= 0:
        if u > t:
            return TERMINAL * G + (u - t)
        if u < t:
            return -TERMINAL * G + (u - t)
        return DRAW * G  # a draw wins nothing: slightly worse than a fair gamble at the very end
    return None


def utility_k(hum_total: int, plies_left: int, w: Weights) -> float:
    k = w.k_end + w.k_human * hum_total
    if plies_left < w.k_time:
        k *= max(0.25, plies_left / w.k_time)
    return k


def evaluate(
    board: Board,
    state: State,
    me: int,
    to_move: int,
    plies_left: int,
    w: Weights,
    G: float,
) -> float:
    op = 1 - me
    mine = state.g[me]
    theirs = state.g[op]
    hum = state.h
    u = sum(mine.values())
    t = sum(theirs.values())
    raw = float(u - t)
    D = board.D
    gamma = w.gamma

    # Moves each side still gets before the game ends.
    if to_move == me:
        my_moves = (plies_left + 1) // 2
        op_moves = plies_left // 2
    else:
        my_moves = plies_left // 2
        op_moves = (plies_left + 1) // 2

    # ---- Human race: greedy capture tours; each human cell goes to whoever arrives first
    # (ties to the side that moves next).
    hum_total = 0
    if hum:
        arr_m = _tours(D, mine, hum, my_moves, gamma, w.chain_len)
        arr_o = _tours(D, theirs, hum, op_moves, gamma, w.chain_len)
        me_first = 0.5 if to_move == me else 0.0
        op_first = 0.5 - me_first
        for hp, c in hum.items():
            hum_total += c
            tm = arr_m.get(hp)
            to = arr_o.get(hp)
            if tm is None and to is None:
                continue
            if to is None or (tm is not None and tm - me_first < to - op_first):
                raw += w.human * c * gamma**tm
            else:
                raw -= w.human * c * gamma**to

    # ---- Combat: any bigger enemy group threatens a group, by the expected material swing
    # of its attack (deterministic kill at >= 1.5x, positive-EV random battle above 1x).
    # One term per victim (max over attackers), so threat and hunt aren't double counted.
    for victims, attackers, sign, side in ((mine, theirs, 1.0, me), (theirs, mine, -1.0, op)):
        victim_moves_next = to_move == side
        for gp, n in victims.items():
            worst = 0.0
            Dg = D[gp]
            for ep, e in attackers.items():
                if e > n:
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
                    v = f * attack_ev(e, n)
                    if v > worst:
                        worst = v
            if worst:
                raw -= sign * worst

    # ---- Fragmentation: many small groups are easy prey.
    raw -= w.split_penalty * (len(mine) - 1)
    raw += w.split_penalty * (len(theirs) - 1)

    # ---- Endgame (nothing left to convert): the leader avoids contact, the trailer seeks it.
    if not hum and mine and theirs and u != t:
        if u < t:
            raw -= w.behind_close * min(D[a][b] for a in mine for b in theirs)
        # A nudge, never big enough to flip who is ahead (the search handles actual attacks).
        contact = 0.0
        for gp, n in mine.items():
            Dg = D[gp]
            for ep, e in theirs.items():
                if e < 1.5 * n and n < 1.5 * e:  # neither side kills outright: a gamble is possible
                    d = Dg[ep]
                    if d <= 2:
                        contact += w.exposure * (1.0 if d == 1 else 0.5)
        contact = min(contact, 0.5 * abs(u - t))
        raw += -contact if u > t else contact

    # ---- Win-probability utility (see module docstring).
    k = utility_k(hum_total, plies_left, w)
    return raw + G * math.tanh(raw / k)


def root_slope(state: State, me: int, plies_left: int, w: Weights, G: float) -> float:
    """d(value)/d(raw) around the root's material margin: scales the tempo bonus so it stays
    meaningful relative to the utility curve."""
    raw = state.total(me) - state.total(1 - me)
    k = utility_k(sum(state.h.values()), plies_left, w)
    c = math.cosh(max(-20.0, min(20.0, raw / k)))
    return 1.0 + G / (k * c * c)
