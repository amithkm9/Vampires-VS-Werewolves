"""Thinking on the opponent's time (pondering).

After we send our move the opponent has up to 2 s to reply, and we would otherwise sit idle.
Instead we guess its most likely replies and pre-search our answer to each resulting
position. When the real position arrives and it is one of the guesses, the search resumes
from the depth already reached, with its transposition table intact (Searcher.choose looks the
position up in Searcher.contexts); otherwise it is an ordinary search and nothing is lost.

Predicted replies, most likely first:
  1. the reply our own search expected (the opponent's best move in our tree),
  2. the next best replies by a 1-ply look from the opponent's point of view.
Candidates are deepened round-robin, the most likely one getting the longest slices.
Everything stops within a few milliseconds of `stop()` turning true (the server's message
has arrived).
"""

from __future__ import annotations

import time
from typing import Callable, List, Optional, Tuple

from .search import Searcher
from .state import Move, State, apply_moves

TOP_REPLIES = 3
SLICES = (0.4, 0.2, 0.2)  # seconds per round for candidate 0, 1, 2
MAX_TABLE_ENTRIES = 1_500_000  # stop pondering rather than grow memory without bound


class Ponderer:
    def __init__(self, searcher: Searcher):
        self.s = searcher
        self.opp = Searcher(searcher.board, 1 - searcher.me, searcher.w)

    def candidates(
        self, state: State, plies_opp: int, hint: Optional[tuple], deadline: float
    ) -> List[State]:
        """Our next root positions, one per predicted opponent reply (most likely first)."""
        me = self.s.me
        replies: List[List[Move]] = []
        if hint is not None:
            replies.append(list(hint))
        for mv in self.opp.ranked_moves(state, plies_opp, deadline):
            if len(replies) >= TOP_REPLIES:
                break
            if hint is None or tuple(mv) != hint:
                replies.append(mv)
        out, seen = [], set()
        for mv in replies:
            child = max(apply_moves(state, 1 - me, mv), key=lambda br: br[0])[1]
            k = child.key()
            if k not in seen and child.total(me) and child.total(1 - me):
                seen.add(k)
                out.append(child)
        return out

    def ponder(
        self,
        state: State,
        plies_opp: int,
        stop: Callable[[], bool],
        deadline: float = float("inf"),
        hint: Optional[tuple] = None,
    ) -> Optional[float]:
        """Ponder `state` (the opponent to move, `plies_opp` plies left including its move)
        until stop() or deadline. Returns the time stop() was first seen true, else None."""
        s = self.s
        s.forget()
        if plies_opp <= 1:  # the game ends with the opponent's move: nothing to prepare
            return None
        cands = self.candidates(state, plies_opp, hint, min(deadline, time.perf_counter() + 0.05))
        while cands:
            busy = False
            for i, c in enumerate(cands):
                now = time.perf_counter()
                if stop():
                    return now
                if (
                    now >= deadline
                    or sum(len(x.tt) for x in s.contexts.values()) > MAX_TABLE_ENTRIES
                ):
                    return None
                s.choose(c, plies_opp - 1, min(deadline, now + SLICES[i]), stop=stop, ponder=True)
                if s.stopped is not None:
                    return s.stopped
                busy = busy or not s.contexts[(c.key(), plies_opp - 1)].done
            if not busy:  # every candidate searched to max depth (or a forced result)
                return None
        return None


class OpponentTracker:
    """How often does the opponent play the reply our search predicted?

    Our search models the opponent as a player who always finds its best reply. That is right
    against strong engines, but against weaker bots it passes up moves that leave them only
    one good answer. The match rate tells the two apart, and sets the weight of the search's
    opponent model (Searcher.opp_eps): 0 for opponents we predict well, up to EPS_MAX for
    opponents that keep playing something else.
    """

    PRIOR_RATE = 0.75  # start by assuming a strong opponent (eps = 0)...
    PRIOR_WEIGHT = 6.0  # ...worth this many observations
    STRONG = 0.5  # match rate at or above which eps = 0 (engines measured: 56-58%)
    WEAK = 0.25  # match rate at or below which eps = EPS_MAX (greedy bots: 24-26%)
    EPS_MAX = 0.1  # best measured vs greedy bots (gain within noise; harmless vs engines)

    def __init__(self):
        self.matches = 0
        self.total = 0
        self.expected: Optional[tuple] = None  # key of the position our predicted reply leads to

    def expect(self, state: State, opp: int, hint: Optional[tuple]) -> None:
        """`state`: position with the opponent to move; `hint`: the reply we predict."""
        self.expected = None
        if hint is not None:
            branches = apply_moves(state, opp, list(hint))
            if len(branches) == 1:  # only deterministic replies can be checked exactly
                self.expected = branches[0][1].key()

    def observe(self, actual: State, deterministic: bool) -> None:
        """The opponent has moved and we now see `actual` (our move's outcome must have
        been deterministic too, or the comparison means nothing)."""
        if self.expected is not None and deterministic:
            self.total += 1
            self.matches += actual.key() == self.expected
        self.expected = None

    @property
    def rate(self) -> float:
        return (self.matches + self.PRIOR_RATE * self.PRIOR_WEIGHT) / (
            self.total + self.PRIOR_WEIGHT
        )

    @property
    def eps(self) -> float:
        f = (self.STRONG - self.rate) / (self.STRONG - self.WEAK)
        return self.EPS_MAX * min(1.0, max(0.0, f))


class Session:
    """One game's thinking: the search, pondering and opponent tracking, shared by the
    tournament client (vvw/ai.py) and the in-process simulator bots (sim/bots.py)."""

    def __init__(self, searcher: Searcher, ponder: bool = True, adaptive: bool = True):
        self.s = searcher
        self.me = searcher.me
        self.ponderer = Ponderer(searcher)
        self.tracker = OpponentTracker()
        self.ponder_on = ponder
        self.adaptive = adaptive
        self.after: Optional[Tuple[State, int, Optional[tuple]]] = None  # what to ponder
        self.det = False  # was our last move's outcome deterministic?
        self.hits = 0  # turns whose position had been pondered
        self.turns = 0

    def opponent_moves_first(self, state: State, plies_opp: int) -> None:
        self.after = (state, plies_opp, None)

    def search(self, state: State, plies_left: int, deadline: float):
        self.tracker.observe(state, self.det)
        if self.adaptive:
            self.s.opp_eps = self.tracker.eps
        moves, info = self.s.choose(state, plies_left, deadline)
        self.turns += 1
        self.hits += info.pondered > 0
        return moves, info

    def played(self, state: State, moves: List[Move], plies_left: int) -> None:
        """We sent `moves` (the final, legal ones) from `state`: prepare for the reply."""
        self.after = None
        self.det = len(apply_moves(state, self.me, moves)) == 1
        child, hint = self.s.expected_reply(state, moves, plies_left)
        self.tracker.expect(child, 1 - self.me, hint)
        if self.ponder_on:
            self.after = (child, plies_left - 1, hint)

    def ponder(self, stop: Callable[[], bool]) -> Optional[float]:
        if self.after is None:
            return None
        st, plies_opp, hint = self.after
        self.after = None
        return self.ponderer.ponder(st, plies_opp, stop, hint=hint)
