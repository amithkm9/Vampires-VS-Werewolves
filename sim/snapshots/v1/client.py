"""TCP client for the Vampires vs Werewolves server (byte-exact protocol, see RULES.md)."""

from __future__ import annotations

import select
import socket
from typing import List, Tuple


class ConnectionClosed(Exception):
    pass


class ClientSocket:
    def __init__(self, ip: str, port: int, timeout: float = 600.0):
        self._sock = socket.create_connection((ip, port), timeout=timeout)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._sock.settimeout(None)

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass

    # ------------------------------------------------------------ receiving
    def _recv_exact(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionClosed()
            buf += chunk
        return bytes(buf)

    def _byte(self) -> int:
        return self._recv_exact(1)[0]

    def has_pending_data(self) -> bool:
        r, _, _ = select.select([self._sock], [], [], 0)
        return bool(r)

    def get_message(self) -> Tuple[str, object]:
        """Return (command, payload). Commands: set, hum, hme, map, upd, end, bye."""
        cmd = self._recv_exact(3).decode("ascii", errors="replace")
        if cmd == "SET":
            rows, cols = self._recv_exact(2)
            return "set", (rows, cols)
        if cmd == "HUM":
            n = self._byte()
            data = self._recv_exact(2 * n)
            return "hum", [(data[2 * i], data[2 * i + 1]) for i in range(n)]
        if cmd == "HME":
            x, y = self._recv_exact(2)
            return "hme", (x, y)
        if cmd in ("MAP", "UPD"):
            n = self._byte()
            data = self._recv_exact(5 * n)
            tuples: List[Tuple[int, int, int, int, int]] = [
                tuple(data[5 * i : 5 * i + 5]) for i in range(n)
            ]  # type: ignore[misc]
            return cmd.lower(), tuples
        if cmd == "END":
            return "end", None
        if cmd == "BYE":
            return "bye", None
        raise ValueError(f"unknown command {cmd!r}")

    # -------------------------------------------------------------- sending
    def send_nme(self, name: str) -> None:
        raw = name.encode("ascii", errors="replace")[:255]
        self._sock.sendall(b"NME" + bytes([len(raw)]) + raw)

    def send_mov(self, moves: List[Tuple[int, int, int, int, int]]) -> None:
        """moves: list of (x_from, y_from, count, x_to, y_to). Sent in a single write."""
        payload = bytearray(b"MOV")
        payload.append(len(moves))
        for m in moves:
            payload.extend(bytes(m))
        self._sock.sendall(bytes(payload))
