"""Byte-exact stand-in for VampiresVSWerewolvesGameServer.exe (v3.2.1 GameRoutine).

    uv run --no-project python -m sim.fake_server --map sim/maps/testmap2.xml --port 5555
    (then start two clients: python main.py 127.0.0.1 5555)

Behaviour copied from the disassembly (see RULES.md):
  - first connection = player 0 = Vampires, second = Werewolves
  - NME, then SET+HUM+HME in one packet, then MAP
  - each turn: flush unread bytes, send UPD (union of every player's last changes),
    wait for 'MOV'+n within the move deadline, then 5n bytes within the same deadline
  - timeout: turn skipped; bad/empty move or protocol error: that player loses
  - end: sleep, then END + BYE to each player and close
"""

from __future__ import annotations

import argparse
import random
import socket
import time
from typing import List, Optional, Set

from vvw.state import Board, validate

from .maps import MapSpec, load_map
from .referee import initial_state, perform_moves


class ProtocolError(Exception):
    pass


class FakeServer:
    def __init__(
        self,
        spec: MapSpec,
        host: str = "127.0.0.1",
        port: int = 5555,
        players: int = 2,
        move_time: float = 2.0,
        max_plays: int = 200,
        max_game_time: float = 300.0,
        end_sleep: float = 0.2,
        seed: int = 0,
        log=print,
    ):
        self.spec = spec
        self.host, self.port = host, port
        self.players = players
        self.move_time = move_time
        self.max_plays = max_plays
        self.max_game_time = max_game_time
        self.end_sleep = end_sleep
        self.rng = random.Random(seed)
        self.log = log
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind((host, port))
        self.listener.listen(players)
        self.port = self.listener.getsockname()[1]
        self.names: List[str] = []
        self.result: dict = {}

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _recv_exact(sock: socket.socket, n: int, deadline: Optional[float]) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            if deadline is not None:
                left = deadline - time.perf_counter()
                if left <= 0:
                    raise TimeoutError()
                sock.settimeout(left)
            else:
                sock.settimeout(None)
            chunk = sock.recv(n - len(buf))
            if not chunk:
                raise ProtocolError("connection closed")
            buf += chunk
        return bytes(buf)

    @staticmethod
    def _flush(sock: socket.socket) -> int:
        sock.setblocking(False)
        n = 0
        try:
            while True:
                chunk = sock.recv(1300)
                if not chunk:
                    break
                n += len(chunk)
        except (BlockingIOError, OSError):
            pass
        finally:
            sock.setblocking(True)
        return n

    def _cell_tuple(self, board: Board, state, p: int) -> bytes:
        return bytes(
            [
                board.xs[p],
                board.ys[p],
                state.h.get(p, 0),
                state.g[0].get(p, 0),
                state.g[1].get(p, 0),
            ]
        )

    # ---------------------------------------------------------------- game
    def run(self) -> dict:
        socks = []
        for _ in range(self.players):
            s, _addr = self.listener.accept()
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            socks.append(s)
        board = Board(self.spec.rows, self.spec.cols)
        state = initial_state(self.spec)
        homes = [self.spec.vampires[:2], self.spec.werewolves[:2]]
        for i, s in enumerate(socks):
            head = self._recv_exact(s, 4, None)
            if head[:3] != b"NME":
                raise ProtocolError(f"expected NME, got {head[:3]!r}")
            name = self._recv_exact(s, head[3], None).decode("ascii", errors="replace")
            self.names.append(name)
            pkt = bytearray(b"SET" + bytes([self.spec.rows, self.spec.cols]))
            pkt += b"HUM" + bytes([len(self.spec.humans)])
            for x, y in self.spec.humans:
                pkt += bytes([x, y])
            pkt += b"HME" + bytes(homes[i])
            s.sendall(bytes(pkt))
            cells = sorted(set(state.h) | set(state.g[0]) | set(state.g[1]))
            s.sendall(
                b"MAP"
                + bytes([len(cells)])
                + b"".join(self._cell_tuple(board, state, p) for p in cells)
            )

        last_changes: List[Set[int]] = [set() for _ in range(self.players)]
        winner: Optional[int] = None
        reason = "max plays"
        t_game = time.perf_counter()
        timeouts = [0] * self.players
        ply = 0
        while ply < self.max_plays:
            cur = ply % self.players
            s = socks[cur]
            flushed = self._flush(s)
            if flushed:
                self.log(f"[server] flushed {flushed} stale bytes from player {cur}")
            changed = set().union(*last_changes)
            s.sendall(
                b"UPD"
                + bytes([len(changed)])
                + b"".join(self._cell_tuple(board, state, p) for p in sorted(changed))
            )
            deadline = time.perf_counter() + self.move_time
            try:
                head = self._recv_exact(s, 4, deadline)
                if head[:3] != b"MOV":
                    raise ProtocolError(f"expected MOV, got {head[:3]!r}")
                n = head[3]
                body = self._recv_exact(s, 5 * n, deadline)
                moves = []
                for i in range(n):
                    x1, y1, cnt, x2, y2 = body[5 * i : 5 * i + 5]
                    if x2 >= board.cols or y2 >= board.rows or x1 >= board.cols or y1 >= board.rows:
                        raise ProtocolError(f"cell out of board: {(x1, y1, cnt, x2, y2)}")
                    moves.append((board.pos(x1, y1), cnt, board.pos(x2, y2)))
                err = validate(board, state, cur, moves)
                if err is not None:
                    raise ProtocolError("bad move: " + err)
                last_changes[cur] = perform_moves(state, cur, moves, self.rng)
            except TimeoutError:
                timeouts[cur] += 1
                self.log(f"[server] player {cur} timed out (turn skipped)")
            except (ProtocolError, OverflowError) as ex:
                winner, reason = 1 - cur, f"player {cur} cheated: {ex}"
                break
            v, w = state.total(0), state.total(1)
            if v == 0:
                winner, reason = 1, "vampires eliminated"
                break
            if w == 0:
                winner, reason = 0, "werewolves eliminated"
                break
            if ply % 2 == 1 and time.perf_counter() - t_game >= self.max_game_time:
                reason = "game time over"
                break
            ply += 1
        if winner is None:
            v, w = state.total(0), state.total(1)
            winner = None if v == w else (0 if v > w else 1)
        time.sleep(self.end_sleep)
        for s in socks:
            try:
                s.sendall(b"END")
                s.sendall(b"BYE")
                s.close()
            except OSError:
                pass
        self.listener.close()
        self.result = {
            "winner": winner,
            "reason": reason,
            "plies": min(ply + 1, self.max_plays),  # ply is max_plays after a full game
            "totals": (state.total(0), state.total(1)),
            "names": self.names,
            "timeouts": timeouts,
        }
        self.log(f"[server] {self.result}")
        return self.result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--map", default="sim/maps/testmap2.xml")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5555)
    p.add_argument("--players", type=int, default=2)
    p.add_argument("--move-time", type=float, default=2.0)
    p.add_argument("--max-plays", type=int, default=200)
    p.add_argument("--seed", type=int, default=0)
    a = p.parse_args()
    srv = FakeServer(
        load_map(a.map), a.host, a.port, a.players, a.move_time, a.max_plays, seed=a.seed
    )
    print(f"[server] listening on {a.host}:{srv.port}")
    srv.run()


if __name__ == "__main__":
    main()
