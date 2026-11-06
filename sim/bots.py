"""Opponents for testing: baselines of increasing strength, and our own AI."""

from __future__ import annotations

import random
from typing import List

from vvw.evaluate import DEFAULT_WEIGHTS, Weights
from vvw.rules import MAX_CELL
from vvw.safety import ensure_legal
from vvw.state import Board, Move, State


class Bot:
    name = "bot"

    def new_game(self, board: Board, me: int, state: State, max_plays: int) -> None:
        self.board = board
        self.me = me

    def choose(self, state: State, plies_left: int, deadline: float) -> List[Move]:
        raise NotImplementedError

    def ponder(self, stop) -> None:
        """Called while the opponent thinks (the referee runs it for the opponent's think time)."""


def _assemble(proposals: List[Move]) -> List[Move]:
    """Keep proposals in order, dropping those that would violate Rule 5."""
    srcs, dsts, out = set(), set(), []
    for src, n, dst in proposals:
        if src in dsts or dst in srcs:
            continue
        srcs.add(src)
        dsts.add(dst)
        out.append((src, n, dst))
    return out


class RandomBot(Bot):
    name = "random"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def choose(self, state, plies_left, deadline):
        mine = state.g[self.me]
        props = []
        for gp, n in mine.items():
            q = self.rng.choice(self.board.nbrs[gp])
            if mine.get(q, 0) + n > MAX_CELL:
                continue
            props.append((gp, n if self.rng.random() < 0.7 else self.rng.randint(1, n), q))
        return ensure_legal(self.board, state, self.me, _assemble(props))


class GreedyBot(Bot):
    """Each group goes for the best convertible human / killable enemy; flees killers; else merges.

    `aggressive=True` also attacks enemies it outnumbers (accepting random battles).
    """

    def __init__(self, aggressive: bool = False):
        self.aggressive = aggressive
        self.name = "aggressive" if aggressive else "greedy"

    def choose(self, state, plies_left, deadline):
        b = self.board
        mine, theirs, hum = state.g[self.me], state.g[1 - self.me], state.h
        props = []
        for gp, n in sorted(mine.items(), key=lambda kv: -kv[1]):
            target, best = None, -1.0
            for ep, e in theirs.items():
                if e >= 1.5 * n and b.dist(gp, ep) <= 2:
                    # flee: neighbour maximizing distance to the killer
                    q = max(b.nbrs[gp], key=lambda c: (b.dist(c, ep), -c))
                    target, best = None, 1e9
                    props.append((gp, n, q))
                    break
            if best == 1e9:
                continue
            for hp, c in hum.items():
                if c <= n:
                    v = c / b.dist(gp, hp)
                    if v > best:
                        target, best = hp, v
            for ep, e in theirs.items():
                if n >= 1.5 * e or (self.aggressive and n > e):
                    v = 1.5 * e / b.dist(gp, ep)
                    if v > best:
                        target, best = ep, v
            if target is None:
                others = [ap for ap in mine if ap != gp]
                if others:
                    target = min(others, key=lambda ap: b.dist(gp, ap))
                elif theirs:
                    target = min(theirs, key=lambda ep: b.dist(gp, ep))
            if target is None:
                continue
            steps = b.steps_toward(gp, target)
            steps = [q for q in steps if not (q in hum and hum[q] > n and q != target)]
            if steps:
                props.append((gp, n, steps[0]))
        return ensure_legal(b, state, self.me, _assemble(props))


class AIBot(Bot):
    """Our tournament AI, driven in-process through the same vvw.ponder.Session as the
    tournament client (search, pondering on the opponent's time, opponent tracking)."""

    pkg = "vvw"

    def __init__(
        self,
        weights: Weights = DEFAULT_WEIGHTS,
        budget: float = 1.3,
        name: str = "ai",
        ponder: bool = False,
        **search_kw,
    ):
        self.weights = weights
        self.budget = budget
        self.name = name
        self.use_ponder = ponder
        self.search_kw = search_kw
        self.last_info = None
        self.session = None

    def _mod(self, name: str):
        import importlib

        return importlib.import_module(f"{self.pkg}.{name}")

    def new_game(self, board, me, state, max_plays):
        st_mod = self._mod("state")
        self.board = st_mod.Board(board.rows, board.cols)
        self.me = me
        self.State = st_mod.State
        self.safety = self._mod("safety")
        kw = dict(self.search_kw)
        if self.pkg == "vvw":
            kw["weights"] = self.weights
        searcher = self._mod("search").Searcher(self.board, me, **kw)
        session_cls = getattr(self._mod("ponder"), "Session", None) if self._has("ponder") else None
        if session_cls is not None:
            self.session = session_cls(searcher, ponder=self.use_ponder)
            if me == 1:
                self.session.opponent_moves_first(self._conv(state), max_plays)
        else:  # an old snapshot: plain search
            self.searcher = searcher

    def _has(self, name: str) -> bool:
        import importlib.util

        return importlib.util.find_spec(f"{self.pkg}.{name}") is not None

    def _conv(self, state):
        return self.State(dict(state.g[0]), dict(state.g[1]), dict(state.h))

    @property
    def hits(self) -> int:
        return self.session.hits if self.session else 0

    @property
    def turns(self) -> int:
        return self.session.turns if self.session else 0

    def choose(self, state, plies_left, deadline):
        import time

        st = self._conv(state)
        t_end = time.perf_counter() + self.budget
        if self.session is None:
            moves, self.last_info = self.searcher.choose(st, plies_left, t_end)
            return self.safety.ensure_legal(self.board, st, self.me, moves)
        moves, self.last_info = self.session.search(st, plies_left, t_end)
        moves = self.safety.ensure_legal(self.board, st, self.me, moves)
        self.session.played(st, moves, plies_left)
        return moves

    def ponder(self, stop):
        if self.session is not None:
            self.session.ponder(stop)


class SnapshotBot(AIBot):
    """A frozen earlier version of our engine (sim/snapshots/<tag>), for regression matches."""

    def __init__(self, tag: str, budget: float, max_depth: int = 12, ponder: bool = False):
        super().__init__(budget=budget, name=f"snap:{tag}", ponder=ponder, max_depth=max_depth)
        self.pkg = f"sim.snapshots.{tag}"


def make_bot(spec: str, seed: int = 0) -> Bot:
    """'random' | 'greedy' | 'aggressive' | 'ai' | 'ai:0.3' (budget s) | 'aip:0.3' (pondering)
    | 'aid:3' (fixed depth) | 'snap:v1:0.3' | 'snapp:v6:0.3' (pondering) | 'snapd:v2:3'."""
    if spec.startswith(("snap:", "snapp:")):
        kind, tag, budget = spec.split(":")
        return SnapshotBot(tag, float(budget), ponder=kind == "snapp")
    if spec.startswith("snapd:"):  # snapshot at fixed depth: 'snapd:v2:3'
        _, tag, depth = spec.split(":")
        return SnapshotBot(tag, 1e9, int(depth))
    if spec == "random":
        return RandomBot(seed)
    if spec == "greedy":
        return GreedyBot(False)
    if spec == "aggressive":
        return GreedyBot(True)
    if spec.startswith("aid:"):  # fixed depth, no time limit: reproducible traces
        return AIBot(budget=1e9, name=spec, max_depth=int(spec.split(":", 1)[1]))
    if spec.startswith("ai"):
        budget = float(spec.split(":", 1)[1]) if ":" in spec else 1.3
        return AIBot(budget=budget, name=spec, ponder=spec.startswith("aip"))
    raise ValueError(spec)
