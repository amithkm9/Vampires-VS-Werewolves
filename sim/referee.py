"""In-process referee replicating GameControl.GameRoutine + Board.PerformMoves (real dice)."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from vvw.rules import KILL_RATIO, MAX_CELL, win_probability
from vvw.state import VAMPIRES, Board, Move, State, validate

from .maps import MapSpec


def initial_state(spec: MapSpec) -> State:
    b = Board(spec.rows, spec.cols)
    hum = {b.pos(x, y): c for (x, y), c in spec.humans.items()}
    vx, vy, vc = spec.vampires
    wx, wy, wc = spec.werewolves
    return State({b.pos(vx, vy): vc}, {b.pos(wx, wy): wc}, hum)


def perform_moves(state: State, side: int, moves: List[Move], rng: random.Random) -> Set[int]:
    """Mutates `state` exactly like the server. Returns the set of changed cells."""
    mine = state.g[side]
    theirs = state.g[1 - side]
    hum = state.h
    changed: Set[int] = set()
    by_target: Dict[int, List[Move]] = {}
    for m in moves:
        by_target.setdefault(m[2], []).append(m)
    for dst, group in by_target.items():
        a = sum(m[1] for m in group)
        if a > MAX_CELL:
            raise OverflowError("Convert.ToByte overflow")
        changed.add(dst)
        for src, cnt, _ in group:
            mine[src] -= cnt
            if mine[src] == 0:
                del mine[src]
            changed.add(src)
        if dst in mine:
            mine[dst] = (mine[dst] + a) & 0xFF  # server stores a byte (wraps)
        elif dst in hum:
            h = hum[dst]
            if a >= h:
                del hum[dst]
                mine[dst] = (a + h) & 0xFF
            else:
                _random_battle(state, side, dst, a, h, True, rng)
        elif dst in theirs:
            e = theirs[dst]
            if KILL_RATIO * e <= a:
                del theirs[dst]
                mine[dst] = a
            else:
                _random_battle(state, side, dst, a, e, False, rng)
        else:
            mine[dst] = a
    state._key = None
    return changed


def _random_battle(
    state: State, side: int, dst: int, a: int, d: int, vs_humans: bool, rng: random.Random
) -> None:
    mine = state.g[side]
    defenders = state.h if vs_humans else state.g[1 - side]
    p = win_probability(a, d, vs_humans)
    if rng.random() < p:
        survivors = 0
        if vs_humans:
            survivors += sum(1 for _ in range(d) if rng.random() < p)
        survivors += sum(1 for _ in range(a) if rng.random() < p)
        del defenders[dst]
        if survivors:
            mine[dst] = survivors
    else:
        survivors = sum(1 for _ in range(d) if rng.random() < 1 - p)
        if survivors:
            defenders[dst] = survivors
        else:
            del defenders[dst]


@dataclass
class GameResult:
    winner: Optional[int]  # 0 vampires, 1 werewolves, None draw
    reason: str
    plies: int
    totals: tuple
    timeouts: List[int] = field(default_factory=lambda: [0, 0])
    move_times: List[List[float]] = field(default_factory=lambda: [[], []])
    history: List[tuple] = field(default_factory=list)


def play_game(
    spec: MapSpec,
    bots,
    seed: int = 0,
    max_plays: int = 200,
    move_time_limit: float = 2.0,
    record: bool = False,
) -> GameResult:
    """bots[0] plays Vampires (moves first), bots[1] Werewolves."""
    rng = random.Random(seed)
    board = Board(spec.rows, spec.cols)
    state = initial_state(spec)
    for side, bot in enumerate(bots):
        bot.new_game(board, side, state.copy(), max_plays)
    res = GameResult(None, "", 0, (0, 0))
    for ply in range(max_plays):
        side = ply % 2
        t0 = time.perf_counter()
        try:
            moves = bots[side].choose(state.copy(), max_plays - ply, t0 + move_time_limit)
        except Exception as ex:  # a crashing bot loses, like a protocol error on the server
            res.winner, res.reason, res.plies = 1 - side, f"{side} crashed: {ex!r}", ply + 1
            break
        dt = time.perf_counter() - t0
        res.move_times[side].append(dt)
        # The other player thinks on this player's time, exactly as long as this player took
        # (on the real server the two run concurrently, on separate cores).
        t_end = time.perf_counter() + min(dt, move_time_limit)
        bots[1 - side].ponder(lambda t_end=t_end: time.perf_counter() > t_end)
        if dt > move_time_limit:
            res.timeouts[side] += 1
            continue  # server: MoveTimeOverException -> turn skipped
        err = validate(board, state, side, moves)
        if err is not None:
            res.winner, res.reason, res.plies = 1 - side, f"{side} bad move: {err}", ply + 1
            break
        perform_moves(state, side, moves, rng)
        if record:
            res.history.append((side, list(moves), state.copy()))
        v, w = state.total(0), state.total(1)
        if v == 0:
            res.winner, res.reason, res.plies = 1, "vampires eliminated", ply + 1
            break
        if w == 0:
            res.winner, res.reason, res.plies = 0, "werewolves eliminated", ply + 1
            break
    else:
        res.plies = max_plays
        v, w = state.total(0), state.total(1)
        res.reason = "max plays"
        res.winner = None if v == w else (VAMPIRES if v > w else 1)
    res.totals = (state.total(0), state.total(1))
    return res
