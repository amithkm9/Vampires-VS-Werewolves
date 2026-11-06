"""The playing agent: keeps the game state from server messages and decides moves."""

from __future__ import annotations

import sys
import time
import traceback
from typing import Callable, List, Optional, Tuple

from .evaluate import DEFAULT_WEIGHTS, Weights
from .ponder import Session
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
        ponder: bool = True,
    ):
        self.budget = budget
        self.ponder_on = ponder
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
        self.session: Optional[Session] = None  # search + pondering + opponent tracking
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
        self.session = Session(self.searcher, ponder=self.ponder_on)
        if self.me == WEREWOLVES:  # Vampires move first: think during their first move
            self.session.opponent_moves_first(self.state, self.plies_left(time.perf_counter()) + 1)

    def on_upd(self, tuples) -> None:
        assert self.board is not None and self.state is not None
        self.state = State.from_updates(self.board, tuples, self.state)

    # -------------------------------------------------------------- decide
    def plies_left(self, now: float) -> int:
        """Plies remaining including the one we are about to play."""
        g = 2 * self.my_turns + (self.me or 0)
        # The limits are server settings we can't read. If the game outlives our assumption,
        # the real limit is larger: extend it rather than keep believing the end is here.
        if g >= self.max_plays:
            self.max_plays = g + 50
        left = self.max_plays - g
        if self.t_first_upd is not None and g >= 10:
            elapsed = now - self.t_first_upd
            if elapsed >= self.max_game_time:
                self.max_game_time = elapsed + 60.0
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
        plies = self.plies_left(t_received)
        session = self.session
        try:
            assert session is not None
            moves, info = session.search(state, plies, t_received + self.budget)
            if self.log:
                self._log(
                    f"turn={self.my_turns} plies_left={plies} {info} "
                    f"opp_match={session.tracker.rate:.2f} eps={session.s.opp_eps:.2f} "
                    f"moves={self._fmt(moves)}"
                )
        except Exception:  # never let a bug forfeit the game
            if self.log:
                self._log("search crashed:\n" + traceback.format_exc())
            moves = fallback_move(board, state, me)
        moves = ensure_legal(board, state, me, moves)
        if session is not None:
            try:
                session.played(state, moves, plies)
            except Exception:
                session.after = None
                if self.log:
                    self._log("session.played crashed:\n" + traceback.format_exc())
        self.my_turns += 1
        return [(board.xs[s], board.ys[s], n, board.xs[d], board.ys[d]) for s, n, d in moves]

    def ponder(self, stop: Callable[[], bool]) -> Optional[float]:
        """Think on the opponent's time until stop() (the server's next message is waiting).
        Returns when stop() was first seen true, so the move clock can start from there."""
        if self.session is None:
            return None
        try:
            return self.session.ponder(stop)
        except Exception:  # pondering is optional: never let it hurt the real move
            if self.searcher is not None:
                self.searcher.forget()
            if self.log:
                self._log("ponder crashed:\n" + traceback.format_exc())
            return None

    def _fmt(self, moves: List[Move]) -> str:
        b = self.board
        assert b is not None
        return " ".join(f"({b.xs[s]},{b.ys[s]})-{n}->({b.xs[d]},{b.ys[d]})" for s, n, d in moves)

    def _log(self, msg: str) -> None:
        out = self.log if self.log is not None else sys.stderr
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=out, flush=True)
