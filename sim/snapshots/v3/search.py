"""Adversarial search: alpha-beta minimax with chance nodes (expectiminimax).

- One ply = one player's complete turn (all of its group moves).
- MAX nodes are our turns, MIN nodes the opponent's: we assume a rational
  opponent using the same move generator (not a reflex agent).
- Random battles create chance nodes (win / loss branches with expected
  survivors); their value is the probability-weighted average.
- Iterative deepening under a hard wall-clock deadline, with a transposition
  table and best-move-first ordering. If time runs out mid-iteration we keep
  the best fully searched root move of that iteration (the previous best is
  always searched first, so this is never worse than the last full depth).
"""

from __future__ import annotations

import gc
import time
from typing import Dict, List, Optional, Tuple

from .evaluate import (
    TERMINAL,
    DEFAULT_WEIGHTS,
    Weights,
    evaluate,
    root_slope,
    terminal_value,
    win_value,
)
from .movegen import generate_moves
from .state import Board, Move, State, apply_moves

INF = float("inf")
EXACT, LOWER, UPPER = 0, 1, 2


class Timeout(Exception):
    pass


class SearchInfo:
    def __init__(self):
        self.depth = 0
        self.nodes = 0
        self.value = 0.0
        self.elapsed = 0.0
        self.root_moves = 0

    def __repr__(self):
        return (
            f"depth={self.depth} nodes={self.nodes} value={self.value:.1f} "
            f"root={self.root_moves} t={self.elapsed * 1000:.0f}ms"
        )


class Searcher:
    def __init__(
        self,
        board: Board,
        me: int,
        weights: Weights = DEFAULT_WEIGHTS,
        root_limit: int = 40,
        inner_limit: int = 14,
        max_depth: int = 12,
    ):
        self.board = board
        self.me = me
        self.w = weights
        self.root_limit = root_limit
        self.inner_limit = inner_limit
        self.max_depth = max_depth
        self.tt: Dict[tuple, Tuple[int, float, int, Optional[tuple]]] = {}
        self.mcache: Dict[tuple, List[List[Move]]] = {}  # move lists survive across turns
        self.deadline = 0.0
        self.nodes = 0
        self.G = 20.0  # value of a win (creatures); set per search
        self.tempo = weights.tempo

    # ------------------------------------------------------------------ root
    def choose(
        self, state: State, plies_left: int, deadline: float
    ) -> Tuple[List[Move], SearchInfo]:
        info = SearchInfo()
        t0 = time.perf_counter()
        # The cyclic GC can pause ~400 ms on our big tables (measured); search data has no
        # reference cycles, so refcounting frees it and the collector is not needed.
        gc.disable()
        self.deadline = deadline
        self.nodes = 0
        # Tempo bonuses are root-relative, so table entries from earlier turns aren't comparable.
        self.tt.clear()
        if len(self.mcache) > 15_000:
            self.mcache.clear()
        if len(self.board._steps) > 150_000:
            self.board._steps.clear()
        self.G = win_value(state)
        self.tempo = self.w.tempo * root_slope(state, self.me, plies_left, self.w, self.G)
        moves = generate_moves(self.board, state, self.me, self.root_limit)
        info.root_moves = len(moves)
        if not moves:
            return [], info
        if len(moves) == 1:
            info.elapsed = time.perf_counter() - t0
            return moves[0], info

        # Order root moves by a 1-ply static look (cheap and much better than heuristic order).
        moves = self._order_root(state, moves, plies_left)
        best = moves[0]
        best_val = -INF
        for depth in range(1, self.max_depth + 1):
            try:
                val, mv, moves = self._root(state, moves, depth, plies_left)
            except Timeout as t:
                partial = t.args[0] if t.args else None
                if partial is not None:
                    best, best_val = partial[1], partial[0]
                    info.depth = depth  # partially completed
                break
            best, best_val = mv, val
            info.depth = depth
            if abs(val) >= TERMINAL * self.G:  # forced win or loss found
                break
            elapsed = time.perf_counter() - t0
            remaining = deadline - time.perf_counter()
            if remaining < elapsed * 1.5:  # next depth very likely can't finish
                break
        info.nodes = self.nodes
        info.value = best_val
        info.elapsed = time.perf_counter() - t0
        return best, info

    def _order_root(
        self, state: State, moves: List[List[Move]], plies_left: int
    ) -> List[List[Move]]:
        scored = []
        stop_at = time.perf_counter() + 0.25 * max(0.0, self.deadline - time.perf_counter())
        for i, mv in enumerate(moves):
            if (
                time.perf_counter() > stop_at
            ):  # out of ordering time: keep heuristic order for the rest
                rest = moves[i:]
                scored.sort(key=lambda x: x[0], reverse=True)
                return [m for _, m in scored] + rest
            v = 0.0
            for p, child in apply_moves(state, self.me, mv):
                tv = terminal_value(child, self.me, plies_left - 1, 1, self.G)
                if tv is None:
                    tv = evaluate(
                        self.board, child, self.me, 1 - self.me, plies_left - 1, self.w, self.G
                    )
                v += p * tv
            scored.append((v, mv))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored]

    def _root(self, state: State, moves: List[List[Move]], depth: int, plies_left: int):
        alpha = -INF
        best_val = -INF
        best_mv = moves[0]
        results = []
        for i, mv in enumerate(moves):
            try:
                v = self._value_of_move(
                    state, self.me, mv, depth - 1, alpha, INF, 1, plies_left - 1
                )
            except Timeout:
                # Only trust partial results if the previous best (moves[0]) was searched.
                raise Timeout((best_val, best_mv) if i > 0 else None) from None
            results.append((v, i, mv))
            if v > best_val:
                best_val, best_mv = v, mv
            if v > alpha:
                alpha = v
        # Reorder for the next iteration: best first, rest by their (bound) values.
        results.sort(key=lambda r: (r[0], -r[1]), reverse=True)
        return best_val, best_mv, [r[2] for r in results]

    # ------------------------------------------------------------- recursion
    def _value_of_move(self, state, side, mv, depth, alpha, beta, ply, plies_left):
        """Value of playing `mv` from `state`; `ply`/`plies_left` describe the child.

        Adds a tempo bonus: material won on root-relative ply k counts an extra
        tempo * lambda^(k-1), so the same capture made earlier always scores higher
        (without it the search happily postpones captures forever).
        """
        me = self.me
        m0 = state.total(me) - state.total(1 - me)
        scale = self.tempo * self.w.tempo_decay ** (ply - 1)
        branches = apply_moves(state, side, mv)
        nxt = 1 - side
        if len(branches) == 1:
            child = branches[0][1]
            bonus = scale * (child.total(me) - child.total(1 - me) - m0)
            return bonus + self._ab(child, nxt, depth, alpha - bonus, beta - bonus, ply, plies_left)
        vals = []
        for p, child in branches:
            bonus = scale * (child.total(me) - child.total(1 - me) - m0)
            vals.append((p, bonus + self._ab(child, nxt, depth, -INF, INF, ply, plies_left)))
        mean = sum(p * v for p, v in vals)
        if self.w.risk and (side == me or self.w.risk_all):
            # Risk aversion on OUR gambles: a fair coin flip scores below a quiet move, so we
            # only gamble when the expected gain is real (e.g. clearly behind). Keeping the
            # game going also leaves room for a weaker opponent to blunder.
            mean -= self.w.risk * sum(p * abs(v - mean) for p, v in vals)
        return mean

    def _ab(
        self,
        state: State,
        to_move: int,
        depth: int,
        alpha: float,
        beta: float,
        ply: int,
        plies_left: int,
    ) -> float:
        self.nodes += 1
        if time.perf_counter() > self.deadline:
            raise Timeout()
        me = self.me
        tv = terminal_value(state, me, plies_left, ply, self.G)
        if tv is not None:
            return tv
        if depth <= 0:
            return evaluate(self.board, state, me, to_move, plies_left, self.w, self.G)

        key = (state.key(), to_move, plies_left)
        entry = self.tt.get(key)
        tt_move = None
        if entry is not None:
            e_depth, e_val, e_flag, tt_move = entry
            if e_depth >= depth:
                if e_flag == EXACT:
                    return e_val
                if e_flag == LOWER and e_val >= beta:
                    return e_val
                if e_flag == UPPER and e_val <= alpha:
                    return e_val

        mkey = (key[0], to_move)
        moves = self.mcache.get(mkey)
        if moves is None:
            moves = generate_moves(self.board, state, to_move, self.inner_limit)
            if len(self.mcache) < 20_000:
                self.mcache[mkey] = moves
        else:
            moves = list(moves)
        if not moves:
            return evaluate(self.board, state, me, to_move, plies_left, self.w, self.G)
        if tt_move is not None:
            for i, mv in enumerate(moves):
                if tuple(mv) == tt_move:
                    if i:
                        moves.insert(0, moves.pop(i))
                    break

        a0, b0 = alpha, beta
        maximizing = to_move == me
        best_val = -INF if maximizing else INF
        best_mv = moves[0]
        for mv in moves:
            v = self._value_of_move(
                state, to_move, mv, depth - 1, alpha, beta, ply + 1, plies_left - 1
            )
            if maximizing:
                if v > best_val:
                    best_val, best_mv = v, mv
                if v > alpha:
                    alpha = v
            else:
                if v < best_val:
                    best_val, best_mv = v, mv
                if v < beta:
                    beta = v
            if alpha >= beta:
                break

        if best_val <= a0:
            flag = UPPER
        elif best_val >= b0:
            flag = LOWER
        else:
            flag = EXACT
        self.tt[key] = (depth, best_val, flag, tuple(best_mv))
        return best_val
