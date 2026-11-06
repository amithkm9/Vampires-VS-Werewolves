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
- Search tables live in a per-root context, so a position that was already searched
  while waiting for the opponent (vvw/ponder.py) resumes at the depth reached.
"""

from __future__ import annotations

import gc
import time
from typing import Callable, Dict, List, Optional, Tuple

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
        self.pondered = 0  # depth already completed on the opponent's time
        self.nodes = 0
        self.value = 0.0
        self.elapsed = 0.0
        self.root_moves = 0

    def __repr__(self):
        return (
            f"depth={self.depth} pondered={self.pondered} nodes={self.nodes} "
            f"value={self.value:.1f} root={self.root_moves} t={self.elapsed * 1000:.0f}ms"
        )


class RootContext:
    """Everything a search of one root position accumulates, kept so it can be resumed."""

    __slots__ = (
        "tt",
        "ecache",
        "killers",
        "params",
        "moves",
        "ordered",
        "depth",
        "best",
        "best_val",
        "done",
    )

    def __init__(self, params: Tuple[float, float, float], moves: List[List[Move]]):
        self.tt: Dict[tuple, Tuple[int, float, int, Optional[tuple]]] = {}
        self.ecache: Dict[tuple, float] = {}  # leaf evaluations
        self.killers: Dict[int, List[tuple]] = {}  # ply -> moves that recently caused cutoffs
        self.params = params  # (G, risk, tempo): fixed per root, so table values stay comparable
        self.moves = moves  # root moves, best first after each completed depth
        self.ordered = False
        self.depth = 0  # last completed depth
        self.best: Optional[List[Move]] = None
        self.best_val = -INF
        self.done = False  # max depth reached or a forced result found


class Searcher:
    def __init__(
        self,
        board: Board,
        me: int,
        weights: Weights = DEFAULT_WEIGHTS,
        root_limit: int = 40,
        inner_limit: int = 14,
        max_depth: int = 12,
        killers: bool = True,
    ):
        self.board = board
        self.me = me
        self.w = weights
        self.root_limit = root_limit
        self.inner_limit = inner_limit
        self.max_depth = max_depth
        self.use_killers = killers
        self.contexts: Dict[tuple, RootContext] = {}  # (root key, plies_left) -> context
        self.killers: Dict[int, List[tuple]] = {}
        self.tt: Dict[tuple, Tuple[int, float, int, Optional[tuple]]] = {}
        self.ecache: Dict[tuple, float] = {}
        self.mcache: Dict[tuple, List[List[Move]]] = {}  # move lists survive across turns
        self.deadline = 0.0
        self.stop: Optional[Callable[[], bool]] = None
        self.stopped: Optional[float] = None  # when stop() fired during the last search
        self.nodes = 0
        self.G = 20.0  # value of a win (creatures); set per search
        self.tempo = weights.tempo
        self.risk = weights.risk
        self.opp_eps = weights.opp_model  # opponent model weight (set per turn by ponder.Session)

    # ------------------------------------------------------------------ root
    def forget(self) -> None:
        """Drop every per-root context (their tables can be large)."""
        self.contexts.clear()

    def _context(self, state: State, plies_left: int, ponder: bool) -> RootContext:
        rk = (state.key(), plies_left)
        ctx = self.contexts.get(rk)
        if ctx is not None:
            if not ponder:  # the real position: other pondered guesses are now useless
                self.contexts = {rk: ctx}
            return ctx
        if not ponder:
            self.contexts.clear()
        if len(self.mcache) > 15_000:
            self.mcache.clear()
        if len(self.board._steps) > 150_000:
            self.board._steps.clear()
        G = win_value(state)
        params = (
            G,
            self.w.risk * min(1.0, plies_left / self.w.risk_fade),
            # Tempo bonuses are root-relative: that is why tables are per root.
            self.w.tempo * root_slope(state, self.me, plies_left, self.w, G),
        )
        ctx = RootContext(params, generate_moves(self.board, state, self.me, self.root_limit))
        self.contexts[rk] = ctx
        return ctx

    def choose(
        self,
        state: State,
        plies_left: int,
        deadline: float,
        stop: Optional[Callable[[], bool]] = None,
        ponder: bool = False,
    ) -> Tuple[List[Move], SearchInfo]:
        """Best move for `state`. Resumes the root's context if it was searched before (e.g.
        pondered). `stop()` is polled every 128 nodes; `ponder=True` searches until the
        deadline instead of stopping early to save time."""
        info = SearchInfo()
        t0 = time.perf_counter()
        # The cyclic GC can pause ~400 ms on our big tables (measured); search data has no
        # reference cycles, so refcounting frees it and the collector is not needed.
        gc.disable()
        self.deadline = deadline
        self.stop = stop
        self.stopped = None
        self.nodes = 0
        ctx = self._context(state, plies_left, ponder)
        self.tt, self.ecache, self.killers = ctx.tt, ctx.ecache, ctx.killers
        self.G, self.risk, self.tempo = ctx.params
        info.root_moves = len(ctx.moves)
        info.pondered = info.depth = ctx.depth
        if len(ctx.moves) <= 1:
            ctx.done = True
            info.elapsed = time.perf_counter() - t0
            return (ctx.moves[0] if ctx.moves else []), info

        if not ctx.ordered:
            # Order root moves by a 1-ply static look (cheap and much better than heuristic order).
            ctx.moves = self._order_root(state, ctx.moves, plies_left)
            ctx.ordered = True
        best = ctx.best if ctx.best is not None else ctx.moves[0]
        best_val = ctx.best_val
        depth = ctx.depth
        while not ctx.done and depth < self.max_depth:
            depth += 1
            try:
                val, mv, moves = self._root(state, ctx.moves, depth, plies_left)
            except Timeout as t:
                partial = t.args[0] if t.args else None
                if partial is not None and not ponder:
                    best, best_val = partial[1], partial[0]
                    info.depth = depth  # partially completed
                break
            ctx.moves, ctx.depth, ctx.best, ctx.best_val = moves, depth, mv, val
            best, best_val = mv, val
            info.depth = depth
            if abs(val) >= TERMINAL * self.G or depth >= self.max_depth:  # forced result / done
                ctx.done = True
                break
            if not ponder:
                elapsed = time.perf_counter() - t0
                remaining = deadline - time.perf_counter()
                if remaining < elapsed * 1.5:  # next depth very likely can't finish
                    break
        info.nodes = self.nodes
        info.value = best_val
        info.elapsed = time.perf_counter() - t0
        return best, info

    def expected_reply(
        self, state: State, mv: List[Move], plies_left: int
    ) -> Tuple[State, Optional[tuple]]:
        """After the last search of `state`: the position after our move `mv` (most likely
        battle outcome) and the opponent reply the search expected there (None if unknown)."""
        child = max(apply_moves(state, self.me, mv), key=lambda br: br[0])[1]
        entry = self.tt.get((child.key(), 1 - self.me, plies_left - 1))
        return child, (entry[3] if entry is not None else None)

    def ranked_moves(self, state: State, plies_left: int, deadline: float) -> List[List[Move]]:
        """This side's candidate moves ranked by a 1-ply look: a cheap guess of what it plays."""
        self.deadline = deadline
        self.G = win_value(state)
        moves = generate_moves(self.board, state, self.me, self.root_limit)
        if len(moves) <= 1:
            return moves
        return self._order_root(state, moves, plies_left, share=1.0)

    def _order_root(
        self, state: State, moves: List[List[Move]], plies_left: int, share: float = 0.25
    ) -> List[List[Move]]:
        scored = []
        stop_at = time.perf_counter() + share * max(0.0, self.deadline - time.perf_counter())
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
        if self.risk and (side == me or self.w.risk_all):
            # Risk aversion on OUR gambles: a fair coin flip scores below a quiet move, so we
            # only gamble when the expected gain is real (e.g. clearly behind). Keeping the
            # game going also leaves room for a weaker opponent to blunder.
            mean -= self.risk * sum(p * abs(v - mean) for p, v in vals)
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
        if self.stop is not None and not self.nodes & 127 and self.stop():
            self.stopped = time.perf_counter()
            raise Timeout()
        me = self.me
        tv = terminal_value(state, me, plies_left, ply, self.G)
        if tv is not None:
            return tv
        if depth <= 0:
            ekey = (state.key(), to_move, plies_left)
            v = self.ecache.get(ekey)
            if v is None:
                v = evaluate(self.board, state, me, to_move, plies_left, self.w, self.G)
                self.ecache[ekey] = v
            return v

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
        # Ordering: transposition-table move first, then killer moves for this ply.
        front = []
        if tt_move is not None:
            front.append(tt_move)
        if self.use_killers:
            front.extend(k for k in self.killers.get(ply, ()) if k != tt_move)
        if front:
            ranked = {m: i for i, m in enumerate(front)}
            moves.sort(key=lambda mv: ranked.get(tuple(mv), len(front)))

        maximizing = to_move == me
        if not maximizing and ply == 1 and self.opp_eps > 0.0 and len(moves) > 1:
            return self._soft_min(state, to_move, moves, key, depth, alpha, ply, plies_left)
        a0, b0 = alpha, beta
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
                if self.use_killers:
                    km = tuple(mv)
                    ks = self.killers.setdefault(ply, [])
                    if km != tt_move and km not in ks:
                        ks.insert(0, km)
                        del ks[2:]
                break

        if best_val <= a0:
            flag = UPPER
        elif best_val >= b0:
            flag = LOWER
        else:
            flag = EXACT
        self.tt[key] = (depth, best_val, flag, tuple(best_mv))
        return best_val

    def _soft_min(self, state, to_move, moves, key, depth, alpha, ply, plies_left):
        """Opponent model at the opponent's first reply: (1-eps)*min + eps*mean(k lowest).

        A pure minimax opponent always finds its single best reply; real opponents (shallower,
        greedy, buggy) often don't, so a move that leaves them only one good answer is worth a
        little more than one that leaves several. Exact for the k lowest replies: each reply is
        searched with beta = the current k-th lowest value (higher values can't enter the mean),
        and the node fails low as soon as its upper bound drops to alpha.
        """
        eps = self.opp_eps
        k = self.w.opp_k
        low: List[float] = []  # k lowest reply values, ascending
        best_mv = moves[0]
        for mv in moves:
            cap = low[k - 1] if len(low) >= k else INF
            v = self._value_of_move(
                state, to_move, mv, depth - 1, -INF, cap, ply + 1, plies_left - 1
            )
            if v < cap:
                if not low or v < low[0]:
                    best_mv = mv
                low.append(v)
                low.sort()
                del low[k:]
            if len(low) >= k:
                ub = (1.0 - eps) * low[0] + eps * sum(low) / k  # more replies can only lower it
                if ub <= alpha:
                    self.tt[key] = (depth, ub, UPPER, tuple(best_mv))
                    return ub
        val = (1.0 - eps) * low[0] + eps * sum(low) / len(low)
        self.tt[key] = (depth, val, EXACT, tuple(best_mv))
        return val
