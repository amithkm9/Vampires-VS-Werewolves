"""Board geometry, game state, move validation and state transitions.

Cells are integers ``p = y * cols + x``. A move is a tuple ``(src, count, dst)``.
Side 0 = Vampires (moves first on the server), side 1 = Werewolves.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .rules import MAX_CELL, battle_outcomes

VAMPIRES, WEREWOLVES = 0, 1
Move = Tuple[int, int, int]
Cells = Dict[int, int]

MAX_BRANCHES = 4  # cap on chance branches produced by one turn's random battles


class Board:
    """Static grid geometry: neighbours and Chebyshev distance."""

    def __init__(self, rows: int, cols: int):
        self.rows = rows
        self.cols = cols
        self.size = rows * cols
        self.xs = [p % cols for p in range(self.size)]
        self.ys = [p // cols for p in range(self.size)]
        nbrs = []
        for p in range(self.size):
            x, y = self.xs[p], self.ys[p]
            row = []
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < cols and 0 <= ny < rows:
                        row.append(ny * cols + nx)
            nbrs.append(tuple(row))
        self.nbrs = nbrs
        self.nbr_sets = [frozenset(r) for r in nbrs]
        # D[a][b] = Chebyshev distance; rows are built lazily (only for occupied cells).
        self.D = _DistRows(self.xs, self.ys)
        self._steps: Dict[Tuple[int, int], Tuple[int, ...]] = {}

    def pos(self, x: int, y: int) -> int:
        return y * self.cols + x

    def xy(self, p: int) -> Tuple[int, int]:
        return self.xs[p], self.ys[p]

    def dist(self, a: int, b: int) -> int:
        return self.D[a][b]

    def steps_toward(self, a: int, b: int) -> Tuple[int, ...]:
        """Neighbours of ``a`` that are one step closer to ``b`` (cached)."""
        key = (a, b)
        r = self._steps.get(key)
        if r is None:
            Db = self.D[b]
            d = Db[a]
            r = tuple(q for q in self.nbrs[a] if Db[q] < d)
            self._steps[key] = r
        return r


class _DistRows(dict):
    """Lazily computed rows of the distance matrix, stored as bytes (max distance 254)."""

    def __init__(self, xs: List[int], ys: List[int]):
        super().__init__()
        self.xs = xs
        self.ys = ys

    def __missing__(self, a: int) -> bytes:
        xa, ya = self.xs[a], self.ys[a]
        row = bytes(max(abs(x - xa), abs(y - ya)) for x, y in zip(self.xs, self.ys))
        self[a] = row
        return row


class State:
    """Immutable-by-convention game state. ``g[side]`` maps cell -> creature count."""

    __slots__ = ("g", "h", "_key")

    def __init__(self, vamp: Cells, wolf: Cells, hum: Cells):
        self.g = (vamp, wolf)
        self.h = hum
        self._key = None

    def total(self, side: int) -> int:
        return sum(self.g[side].values())

    def key(self):
        if self._key is None:
            self._key = (
                frozenset(self.g[0].items()),
                frozenset(self.g[1].items()),
                frozenset(self.h.items()),
            )
        return self._key

    def copy(self) -> State:
        return State(dict(self.g[0]), dict(self.g[1]), dict(self.h))

    @staticmethod
    def from_updates(board: Board, updates, base: Optional[State] = None) -> State:
        """Apply MAP/UPD 5-tuples ``(x, y, humans, vampires, werewolves)``."""
        st = base.copy() if base is not None else State({}, {}, {})
        for x, y, h, v, w in updates:
            p = board.pos(x, y)
            for cells, n in ((st.h, h), (st.g[0], v), (st.g[1], w)):
                if n > 0:
                    cells[p] = n
                else:
                    cells.pop(p, None)
        return st


def validate(board: Board, state: State, side: int, moves: List[Move]) -> Optional[str]:
    """Mirror of Board.CheckMoves plus the crash cases (bounds, byte overflow).

    Returns None when the move set is legal, otherwise a reason string.
    """
    if not moves:
        return "no move (server: static -> loss)"
    mine = state.g[side]
    srcs = {m[0] for m in moves}
    dsts = {m[2] for m in moves}
    inter = srcs & dsts
    out: Dict[int, int] = {}
    arrive: Dict[int, int] = {}
    for src, cnt, dst in moves:
        if not (0 <= src < board.size and 0 <= dst < board.size):
            return f"cell out of board in {(src, cnt, dst)}"
        if src in inter or dst in inter:
            return f"cell is both source and target in {(src, cnt, dst)}"
        if src not in mine:
            return f"source is not ours in {(src, cnt, dst)}"
        if cnt <= 0:
            return f"zero creatures in {(src, cnt, dst)}"
        if cnt > mine[src]:
            return f"too many creatures in {(src, cnt, dst)}"
        if dst not in board.nbr_sets[src]:
            return f"target not adjacent in {(src, cnt, dst)}"
        out[src] = out.get(src, 0) + cnt
        arrive[dst] = arrive.get(dst, 0) + cnt
    for src, n in out.items():
        if n > mine[src]:
            return f"sum leaving {src} exceeds group"
    for dst, a in arrive.items():
        if a > MAX_CELL:
            return f"more than {MAX_CELL} arriving at {dst}"
        if mine.get(dst, 0) + a > MAX_CELL or (
            dst in state.h and a >= state.h[dst] and a + state.h[dst] > MAX_CELL
        ):
            return f"cell {dst} would exceed {MAX_CELL}"
    return None


def apply_moves(state: State, side: int, moves: List[Move]) -> List[Tuple[float, State]]:
    """Resolve one turn exactly like Board.PerformMoves.

    Random battles become chance branches carrying expected survivor counts.
    Returns a list of (probability, next_state).
    """
    mine = dict(state.g[side])
    theirs = state.g[1 - side]
    hum = state.h
    arrive: Dict[int, int] = {}
    for src, cnt, dst in moves:
        left = mine[src] - cnt
        if left:
            mine[src] = left
        else:
            del mine[src]
        arrive[dst] = arrive.get(dst, 0) + cnt

    theirs_mod = None
    hum_mod = None
    battles = []
    for dst, a in arrive.items():
        if dst in mine:  # own non-moving group: merge
            mine[dst] += a
        elif dst in hum:
            hcount = hum[dst]
            if a >= hcount:
                if hum_mod is None:
                    hum_mod = dict(hum)
                del hum_mod[dst]
                mine[dst] = a + hcount
            else:
                battles.append((dst, a, hcount, True))
        elif dst in theirs:
            e = theirs[dst]
            if a >= 1.5 * e:
                if theirs_mod is None:
                    theirs_mod = dict(theirs)
                del theirs_mod[dst]
                mine[dst] = a
            else:
                battles.append((dst, a, e, False))
        else:
            mine[dst] = a

    theirs_final = theirs_mod if theirs_mod is not None else theirs
    hum_final = hum_mod if hum_mod is not None else hum

    def build(m: Cells, t: Cells, h: Cells) -> State:
        return State(m, t, h) if side == 0 else State(t, m, h)

    if not battles:
        return [(1.0, build(mine, theirs_final, hum_final))]

    branches = [(1.0, mine, theirs_final, hum_final)]
    for dst, a, d, vs_humans in battles:
        outcomes = battle_outcomes(a, d, vs_humans)
        if len(branches) * len(outcomes) > MAX_BRANCHES:
            outcomes = [max(outcomes, key=lambda o: o[0])]
            outcomes = [(1.0, outcomes[0][1], outcomes[0][2])]
        new_branches = []
        for prob, m, t, h in branches:
            for p_o, att_wins, survivors in outcomes:
                m2 = dict(m)
                if vs_humans:
                    h2 = dict(h)
                    t2 = t
                    if att_wins:
                        del h2[dst]
                        if survivors > 0:
                            m2[dst] = survivors
                    elif survivors > 0:
                        h2[dst] = survivors
                    else:
                        del h2[dst]
                else:
                    t2 = dict(t)
                    h2 = h
                    if att_wins:
                        del t2[dst]
                        if survivors > 0:
                            m2[dst] = survivors
                    elif survivors > 0:
                        t2[dst] = survivors
                    else:
                        del t2[dst]
                new_branches.append((prob * p_o, m2, t2, h2))
        branches = new_branches
    return [(p, build(m, t, h)) for p, m, t, h in branches]
