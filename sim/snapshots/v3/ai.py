"""The playing agent: keeps the game state from server messages and decides moves."""

from __future__ import annotations

import sys
import time
import traceback
from typing import List, Optional, Tuple

from .evaluate import DEFAULT_WEIGHTS, Weights
from .safety import ensure_legal, fallback_move
from .search import Searcher
from .state import VAMPIRES, WEREWOLVES, Board, Move, State

WireMove = Tuple[int, int, int, int, int]


class Agent:
    def __init__(
        self,
        budget: float = 1.3,
        max_plays: int = 200,
        max_game_time: float = 300.0,
        weights: Weights = DEFAULT_WEIGHTS,
        log=None,
    ):
        self.budget = budget
        self.max_plays = max_plays
        self.max_game_time = max_game_time
        self.weights = weights
        self.log = log
        self.new_game()

    # ------------------------------------------------------------ messages
    def new_game(self) -> None:
        self.board: Optional[Board] = None
        self.home: Optional[Tuple[int, int]] = None
        self.state: Optional[State] = None
        self.me: Optional[int] = None
        self.searcher: Optional[Searcher] = None
        self.my_turns = 0
        self.t_first_upd: Optional[float] = None

    def on_set(self, rows: int, cols: int) -> None:
        self.board = Board(rows, cols)

    def on_hme(self, x: int, y: int) -> None:
        self.home = (x, y)

    def on_map(self, tuples) -> None:
        assert self.board is not None
        self.state = State.from_updates(self.board, tuples)
        if self.home is not None:
            p = self.board.pos(*self.home)
            if p in self.state.g[VAMPIRES]:
                self.me = VAMPIRES
            elif p in self.state.g[WEREWOLVES]:
                self.me = WEREWOLVES
        if self.me is None:  # should not happen; guess from who owns more
            self.me = VAMPIRES
        self.searcher = Searcher(self.board, self.me, self.weights)

    def on_upd(self, tuples) -> None:
        assert self.board is not None and self.state is not None
        self.state = State.from_updates(self.board, tuples, self.state)

    # -------------------------------------------------------------- decide
    def plies_left(self, now: float) -> int:
        """Plies remaining including the one we are about to play."""
        g = 2 * self.my_turns + (self.me or 0)
        left = self.max_plays - g
        if self.t_first_upd is not None and g >= 10:
            elapsed = now - self.t_first_upd
            per_ply = elapsed / g
            if per_ply > 0:
                by_time = int((self.max_game_time - elapsed) / per_ply) + 1
                left = min(left, max(1, by_time))
        return max(1, left)

    def decide(self, t_received: float) -> List[WireMove]:
        assert self.board is not None and self.state is not None and self.me is not None
        if self.t_first_upd is None:
            self.t_first_upd = t_received
        board, state, me = self.board, self.state, self.me
        moves: List[Move] = []
        try:
            assert self.searcher is not None
            plies = self.plies_left(t_received)
            moves, info = self.searcher.choose(state, plies, t_received + self.budget)
            if self.log:
                self._log(
                    f"turn={self.my_turns} plies_left={plies} {info} moves={self._fmt(moves)}"
                )
        except Exception:  # never let a bug forfeit the game
            if self.log:
                self._log("search crashed:\n" + traceback.format_exc())
            moves = fallback_move(board, state, me)
        moves = ensure_legal(board, state, me, moves)
        self.my_turns += 1
        return [(board.xs[s], board.ys[s], n, board.xs[d], board.ys[d]) for s, n, d in moves]

    def _fmt(self, moves: List[Move]) -> str:
        b = self.board
        assert b is not None
        return " ".join(f"({b.xs[s]},{b.ys[s]})-{n}->({b.xs[d]},{b.ys[d]})" for s, n, d in moves)

    def _log(self, msg: str) -> None:
        out = self.log if self.log is not None else sys.stderr
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=out, flush=True)
