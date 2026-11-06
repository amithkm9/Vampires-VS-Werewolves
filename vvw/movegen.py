"""Strategic move generation.

Enumerating every split of every group is hopeless (the branching factor
explodes). Instead each group gets a handful of *purposeful* options:
  - step toward a human cell it can convert,
  - step toward an enemy group it can kill (>= 1.5x),
  - flee from an enemy group that can kill it,
  - step toward an allied group (merge),
  - attack adjacent cells with a random battle (only kept when it's not hopeless),
  - split: two or three parts for two or three human cells, or a detachment of
    exactly the force one human cell needs while the main body does something else,
  - stay put (only when another group moves).
Joint turns are built from the best option per group plus single and pairwise
deviations, then filtered for Rule 5 and the server's byte limits.
"""

from __future__ import annotations

from itertools import product
from typing import Dict, List, Tuple

from .rules import MAX_CELL, attack_ev
from .state import Board, Move, State

GroupOption = Tuple[float, List[Move]]

GAMMA = 0.8
MAX_GROUP_OPTIONS = 5
ROOT_GROUP_OPTIONS = 7  # wider at the root: each root move is searched anyway
MAX_SPLIT_OPTIONS = 3  # split options kept on top of the best single-cell options
MAX_GROUPS_FOR_SPLIT = 4  # don't split further once we have this many groups


def _danger(board: Board, q: int, n: int, theirs: Dict[int, int], exclude: int = -1) -> float:
    """Expected loss if a group of n creatures on q gets attacked by the best adjacent enemy
    on its next move (0.0 when no adjacent enemy is bigger)."""
    worst = 0.0
    for ep in board.nbrs[q]:
        e = theirs.get(ep)
        if e is not None and ep != exclude and e > n:
            v = attack_ev(e, n)
            if v > worst:
                worst = v
    return worst


def group_options(
    board: Board,
    state: State,
    side: int,
    gp: int,
    n: int,
    can_stay: bool,
    max_opts: int = 5,
) -> List[GroupOption]:
    mine = state.g[side]
    theirs = state.g[1 - side]
    hum = state.h
    D = board.D
    Dg = D[gp]
    steps_toward = board.steps_toward
    nbrs = board.nbrs[gp]
    dest: Dict[int, float] = {}
    gambles = set()  # cells where a random battle is a deliberate option

    def add(q: int, s: float) -> None:
        if s > dest.get(q, -1e18):
            dest[q] = s

    # Convertible humans.
    targets = []
    for hp, c in hum.items():
        if c <= n:
            d = Dg[hp]
            val = c * GAMMA ** (d - 1)
            targets.append((val, hp, c))
            for q in steps_toward(gp, hp):
                add(q, val)
    # Enemies: hunt, flee, or gamble.
    for ep, e in theirs.items():
        d = Dg[ep]
        if n >= 1.5 * e:  # deterministic kill
            val = 1.2 * e * GAMMA ** (d - 1)
            for q in steps_toward(gp, ep):
                add(q, val)
        elif n > e:  # positive-EV random battle: approach / attack
            val = attack_ev(n, e) * GAMMA ** (d - 1)
            if d == 1:
                gambles.add(ep)
            for q in steps_toward(gp, ep):
                add(q, val)
            if d <= 2:  # ...or keep away: a leader may prefer no battle at all
                De = D[ep]
                for q in nbrs:
                    if De[q] > d:
                        add(q, 0.1 * e)
        else:
            if e > n and d <= 3:  # they have a positive-EV attack on us: get away
                De = D[ep]
                flee = 0.6 * attack_ev(e, n)
                for q in nbrs:
                    if De[q] > d:
                        add(q, flee)
            if d == 1:  # desperate or even gamble; the search decides
                gambles.add(ep)
                add(ep, -attack_ev(e, n) if e > n else 0.0)
    # Merge with allies.
    for ap, a in mine.items():
        if ap != gp:
            d = Dg[ap]
            val = 0.25 * min(n, a) * GAMMA ** (d - 1)
            for q in steps_toward(gp, ap):
                add(q, val)
    # Random battle against adjacent humans we can't convert outright (only if decent odds).
    for q in nbrs:
        c = hum.get(q)
        if c is not None and c > n and n / (2.0 * c) >= 0.4:
            p = n / (2.0 * c)
            gambles.add(q)
            add(q, p * p * (n + c) - n)

    opts: List[GroupOption] = []
    for q, s in dest.items():
        c = hum.get(q)
        e = theirs.get(q)
        # Never stumble into a battle while routing toward something else.
        if q not in gambles and ((c is not None and c > n) or (e is not None and n < 1.5 * e)):
            continue
        if q in mine and mine[q] + n > MAX_CELL:
            continue
        if c is not None and c <= n and n + c > MAX_CELL:
            continue
        # Stepping next to a bigger enemy hands it a positive-EV attack; rank such steps down.
        s -= 2.0 * _danger(board, q, n + (c if c is not None and c <= n else 0), theirs, exclude=q)
        opts.append((s, [(gp, n, q)]))

    # Always keep at least two quiet (no battle) moves, so a gamble is never forced on the search.
    quiet = sum(1 for _, mv in opts if mv[0][2] not in gambles)
    if quiet < 2:
        have = {mv[0][2] for _, mv in opts}
        # Prefer drifting toward the nearest big human cell (we may grow into it) and away from danger.
        anchor = min(hum, key=lambda hp: Dg[hp]) if hum else None
        extra = []
        for q in nbrs:
            if (
                q in have
                or q in theirs
                or (q in hum and hum[q] > n)
                or (q in mine and mine[q] + n > MAX_CELL)
            ):
                continue
            s = -2.0 * _danger(board, q, n, theirs) - 0.5
            if anchor is not None:
                s -= 0.05 * D[anchor][q]
            extra.append((s, [(gp, n, q)]))
        extra.sort(key=lambda o: o[0], reverse=True)
        opts.extend(extra[: 2 - quiet])

    opts.sort(key=lambda o: o[0], reverse=True)
    splits = _split_options(board, state, side, gp, n, targets, opts)
    # Attacks on adjacent enemy groups are always kept, whatever their heuristic rank: a
    # desperate gamble by the opponent is exactly what the search must not overlook.
    attacks = [o for o in opts[max_opts:] if len(o[1]) == 1 and o[1][0][2] in theirs]
    opts = opts[:max_opts] + attacks + splits
    if can_stay:
        opts.append((-2.0 * _danger(board, gp, n, theirs), []))
        opts.sort(key=lambda o: o[0], reverse=True)
    return opts


def _part_ok(board: Board, state: State, side: int, k: int, q: int) -> bool:
    """A split part of k creatures can safely land on q (no battle, no byte overflow,
    not handed to a bigger adjacent enemy)."""
    theirs = state.g[1 - side]
    if q in theirs:
        return False
    mine = state.g[side]
    if q in mine and mine[q] + k > MAX_CELL:
        return False
    c = state.h.get(q, 0)
    if c > k or k + c > MAX_CELL:
        return False
    return _danger(board, q, k + c, theirs) <= 0.25 * k


def _place(board: Board, state: State, side: int, gp: int, parts) -> List[Move]:
    """One step for each (count, target) part, on pairwise distinct safe cells ([] if none)."""
    choices = [
        [q for q in board.steps_toward(gp, h) if _part_ok(board, state, side, k, q)]
        for k, h in parts
    ]
    # At most 3 parts x 3 cells each. No recursive closure here: it would be a reference
    # cycle, never freed while the cyclic GC is disabled (vvw/search.py).
    for cells in product(*choices):
        if len(set(cells)) == len(cells):
            return [(gp, k, q) for (k, _), q in zip(parts, cells)]
    return []


def _split_options(
    board: Board,
    state: State,
    side: int,
    gp: int,
    n: int,
    targets: List[Tuple[float, int, int]],
    singles: List[GroupOption],
) -> List[GroupOption]:
    """Split moves for one group (best first, at most MAX_SPLIT_OPTIONS):
    - two parts for two human cells (exact force to the smaller one, the rest to the other),
    - three parts for three human cells,
    - a detachment of exactly c creatures toward a human cell while the main body stays or
      takes its best single-cell option (collect far humans without abandoning the front).
    """
    groups = len(state.g[side])
    if groups >= MAX_GROUPS_FOR_SPLIT or not targets:
        return []
    top = sorted(targets, reverse=True)[:5]
    out: List[GroupOption] = []
    for i in range(len(top)):
        for j in range(i + 1, len(top)):
            v1, h1, c1 = top[i]
            v2, h2, c2 = top[j]
            if c1 + c2 > n:
                continue
            parts = [(c1, h1), (n - c1, h2)] if c1 <= c2 else [(n - c2, h1), (c2, h2)]
            mv = _place(board, state, side, gp, parts)
            if mv:
                out.append((v1 + v2 - 0.5, mv))
    if groups + 2 <= MAX_GROUPS_FOR_SPLIT:
        for i in range(min(4, len(top))):
            for j in range(i + 1, min(4, len(top))):
                for k in range(j + 1, min(4, len(top))):
                    trio = sorted((top[i], top[j], top[k]), key=lambda t: t[2])
                    (va, ha, ca), (vb, hb, cb), (vc, hc, _) = trio
                    rest = n - ca - cb
                    if rest < trio[2][2]:
                        continue
                    mv = _place(board, state, side, gp, [(ca, ha), (cb, hb), (rest, hc)])
                    if mv:
                        out.append((va + vb + vc - 1.0, mv))
    stay_score = None
    for v, h, c in top[:3]:
        rest = n - c
        if rest < c:
            continue  # the main body keeps the majority
        det = _place(board, state, side, gp, [(c, h)])
        if not det:
            continue
        a = det[0][2]
        if stay_score is None:
            stay_score = -2.0 * _danger(board, gp, rest, state.g[1 - side])
        out.append((v + stay_score - 0.5, det))
        for s_main, mv in singles[:2]:
            if len(mv) != 1:
                continue
            q = mv[0][2]
            if q != a and q not in state.h and _part_ok(board, state, side, rest, q):
                out.append((v + s_main - 0.5, det + [(gp, rest, q)]))
    out.sort(key=lambda o: o[0], reverse=True)
    return out[:MAX_SPLIT_OPTIONS]


def _joint_ok(moves: List[Move], state: State, side: int) -> bool:
    if not moves:
        return False
    srcs = set()
    arrive: Dict[int, int] = {}
    for src, cnt, dst in moves:
        srcs.add(src)
        arrive[dst] = arrive.get(dst, 0) + cnt
    if not srcs.isdisjoint(arrive):
        return False
    mine = state.g[side]
    hum = state.h
    for dst, a in arrive.items():
        if a > MAX_CELL or mine.get(dst, 0) + a > MAX_CELL:
            return False
        c = hum.get(dst)
        if c is not None and a >= c and a + c > MAX_CELL:
            return False
    return True


def generate_moves(board: Board, state: State, side: int, limit: int = 30) -> List[List[Move]]:
    """Candidate joint turns for `side`, best-first by heuristic score."""
    mine = state.g[side]
    groups = sorted(mine.items(), key=lambda kv: -kv[1])
    if not groups:
        return []
    can_stay = len(groups) > 1
    max_opts = ROOT_GROUP_OPTIONS if limit >= 20 else MAX_GROUP_OPTIONS
    opts = [group_options(board, state, side, gp, n, can_stay, max_opts) for gp, n in groups]
    opts = [o for o in opts if o]
    if not opts:
        return []

    seen = set()
    scored: List[Tuple[float, List[Move]]] = []

    def push(choice: List[int]) -> None:
        key = tuple(choice)
        if key in seen:
            return
        seen.add(key)
        moves: List[Move] = []
        score = 0.0
        for gi, oi in enumerate(choice):
            s, mv = opts[gi][oi]
            score += s
            moves.extend(mv)
        if _joint_ok(moves, state, side):
            scored.append((score, moves))

    base = [0] * len(opts)
    push(base)
    for gi in range(len(opts)):
        for oi in range(1, len(opts[gi])):
            c = list(base)
            c[gi] = oi
            push(c)
    if len(opts) <= 4:
        width = 3 if limit >= 20 else 2  # wider coordination at the root, cheaper inside the tree
        for gi in range(len(opts)):
            for gk in range(gi + 1, len(opts)):
                for oi in range(min(width, len(opts[gi]))):
                    for ok in range(min(width, len(opts[gk]))):
                        c = list(base)
                        c[gi] = oi
                        c[gk] = ok
                        push(c)
    # Everyone moves to their 2nd choice (diversity).
    push([min(1, len(o) - 1) for o in opts])

    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:limit]]
