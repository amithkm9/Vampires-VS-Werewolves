"""Strategic move generation.

Enumerating every split of every group is hopeless (the branching factor
explodes). Instead each group gets a handful of *purposeful* options:
  - step toward a human cell it can convert,
  - step toward an enemy group it can kill (>= 1.5x),
  - flee from an enemy group that can kill it,
  - step toward an allied group (merge),
  - attack adjacent cells with a random battle (only kept when it's not hopeless),
  - split in two to grab two human cells at once,
  - stay put (only when another group moves).
Joint turns are built from the best option per group plus single and pairwise
deviations, then filtered for Rule 5 and the server's byte limits.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .rules import MAX_CELL, win_probability
from .state import Board, Move, State

GroupOption = Tuple[float, List[Move]]

GAMMA = 0.8
MAX_GROUP_OPTIONS = 5
MAX_GROUPS_FOR_SPLIT = 4  # don't split further once we have this many groups
MIN_SPLIT_PART = 1


def _danger(board: Board, q: int, n: int, theirs: Dict[int, int], exclude: int = -1) -> bool:
    """True if a group of n creatures standing on q can be killed next enemy move."""
    for ep in board.nbrs[q]:
        e = theirs.get(ep)
        if e is not None and ep != exclude and e >= 1.5 * n:
            return True
    return False


def group_options(
    board: Board, state: State, side: int, gp: int, n: int, can_stay: bool
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
        if n >= 1.5 * e:
            val = 1.2 * e * GAMMA ** (d - 1)
            for q in steps_toward(gp, ep):
                add(q, val)
        elif e >= 1.5 * n:
            if d <= 3:
                De = D[ep]
                for q in nbrs:
                    if De[q] > d:
                        add(q, 0.6 * n)
        elif d == 1:
            # Random battle: rough expected material swing; the search judges it exactly.
            p = win_probability(n, e, False)
            gambles.add(ep)
            add(ep, p * p * n - (1 - p) ** 2 * e + (1 - p) * n)
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
        # Stepping next to a killer is usually suicide; keep it but rank it last.
        if _danger(board, q, n + (c if c is not None and c <= n else 0), theirs, exclude=q):
            s -= 2.0 * n
        opts.append((s, [(gp, n, q)]))

    # Fallback: if nothing purposeful, wander to safe neighbours (keeps the side legal & mobile).
    if not opts:
        for q in nbrs:
            if q in theirs or (q in hum and hum[q] > n) or (q in mine and mine[q] + n > MAX_CELL):
                continue
            s = -0.01 * Dg[q]
            if _danger(board, q, n, theirs):
                s -= 2.0 * n
            opts.append((s, [(gp, n, q)]))
        opts.sort(key=lambda o: o[0], reverse=True)
        opts = opts[:2]

    # Splits: grab two convertible human cells at once.
    if len(mine) < MAX_GROUPS_FOR_SPLIT and len(targets) >= 2:
        targets.sort(reverse=True)
        top = targets[:3]
        made = 0
        for i in range(len(top)):
            for j in range(i + 1, len(top)):
                v1, h1, c1 = top[i]
                v2, h2, c2 = top[j]
                if c1 + c2 > n:
                    continue
                s1 = board.steps_toward(gp, h1)
                s2 = board.steps_toward(gp, h2)
                pair = None
                for a in s1:
                    for b in s2:
                        if a != b:
                            pair = (a, b)
                            break
                    if pair:
                        break
                if pair is None:
                    continue
                # Exact force to the smaller target, the rest to the other.
                if c1 <= c2:
                    part1 = c1
                    part2 = n - part1
                else:
                    part2 = c2
                    part1 = n - part2
                if part1 < MIN_SPLIT_PART or part2 < MIN_SPLIT_PART:
                    continue
                a, b = pair
                if a in theirs or b in theirs or hum.get(a, 0) > part1 or hum.get(b, 0) > part2:
                    continue
                if _danger(board, a, part1, theirs) or _danger(board, b, part2, theirs):
                    continue
                if (a in mine and mine[a] + part1 > MAX_CELL) or (
                    b in mine and mine[b] + part2 > MAX_CELL
                ):
                    continue
                opts.append((v1 + v2 - 0.5, [(gp, part1, a), (gp, part2, b)]))
                made += 1
                if made >= 2:
                    break
            if made >= 2:
                break

    opts.sort(key=lambda o: o[0], reverse=True)
    opts = opts[:MAX_GROUP_OPTIONS]
    if can_stay:
        stay = 0.0
        if _danger(board, gp, n, theirs):
            stay = -2.0 * n
        opts.append((stay, []))
        opts.sort(key=lambda o: o[0], reverse=True)
    return opts


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
    opts = [group_options(board, state, side, gp, n, can_stay) for gp, n in groups]
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
    # Everyone moves to their 2nd choice (diversity), and "only the biggest group moves".
    push([min(1, len(o) - 1) for o in opts])

    scored.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in scored[:limit]]
