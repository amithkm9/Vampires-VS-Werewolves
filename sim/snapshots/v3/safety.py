"""Last line of defence: a move that is always legal.

The server treats an empty, illegal or malformed MOV as cheating (instant loss),
so whatever happens in the search we must always be able to send *something* legal.
"""

from __future__ import annotations

from typing import List

from .rules import MAX_CELL
from .state import Board, Move, State, validate


def fallback_move(board: Board, state: State, side: int) -> List[Move]:
    """Move one whole group to the safest neighbouring cell. Legal by construction."""
    mine = state.g[side]
    theirs = state.g[1 - side]
    hum = state.h
    best = None
    for gp, n in sorted(mine.items(), key=lambda kv: -kv[1]):
        for q in board.nbrs[gp]:
            if q in mine and mine[q] + n > MAX_CELL:
                continue
            score = 0.0
            if q in theirs:
                e = theirs[q]
                score += 50.0 if n >= 1.5 * e else -100.0
            elif q in hum:
                c = hum[q]
                if n >= c:
                    if n + c > MAX_CELL:
                        continue
                    score += 10.0 + c
                else:
                    score -= 80.0
            for ep in board.nbrs[q]:
                e = theirs.get(ep)
                if e is not None and ep != q and e >= 1.5 * n:
                    score -= 60.0
            if best is None or score > best[0]:
                best = (score, [(gp, n, q)])
    if best is None:
        # Every neighbour would overflow a byte: move a single creature instead.
        for gp, _n in mine.items():
            for q in board.nbrs[gp]:
                if q not in theirs and q not in hum and mine.get(q, 0) < MAX_CELL:
                    return [(gp, 1, q)]
        gp = next(iter(mine))
        return [(gp, 1, board.nbrs[gp][0])]
    return best[1]


def ensure_legal(board: Board, state: State, side: int, moves: List[Move]) -> List[Move]:
    """Return `moves` if the server would accept them, else a legal fallback."""
    if moves and validate(board, state, side, moves) is None:
        return moves
    fb = fallback_move(board, state, side)
    return fb
