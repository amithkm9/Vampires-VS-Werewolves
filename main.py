"""Entry point: python main.py [options] <server_ip> <server_port>

The tournament launcher appends the IP and port at the END of the command line,
so they are always taken from the last two arguments.
"""

from __future__ import annotations

import argparse
import gc
import sys
import time

from vvw.ai import Agent
from vvw.client import ClientSocket, ConnectionClosed

DEFAULT_NAME = "Nosferatu-AB"


def parse_args(argv):
    if len(argv) < 2:
        sys.exit("usage: python main.py [--name N] [--budget S] [--log FILE] <ip> <port>")
    ip, port = argv[-2], argv[-1]
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--name", default=DEFAULT_NAME)
    p.add_argument("--budget", type=float, default=1.3, help="seconds of thinking per move")
    p.add_argument("--max-plays", type=int, default=200)
    p.add_argument("--max-game-time", type=float, default=300.0)
    p.add_argument("--log", default=None, help="file to log decisions to ('-' = stderr)")
    p.add_argument(
        "--no-ponder",
        dest="ponder",
        action="store_false",
        help="don't think on the opponent's time",
    )
    opts, _unknown = p.parse_known_args(argv[:-2])  # tolerate any extra launcher params
    return ip, int(port), opts


def play(ip: str, port: int, opts) -> None:
    log = None
    if opts.log == "-":
        log = sys.stderr
    elif opts.log:
        log = open(opts.log, "a", encoding="utf-8")  # noqa: SIM115 - lives for the whole process
    agent = Agent(
        budget=opts.budget,
        max_plays=opts.max_plays,
        max_game_time=opts.max_game_time,
        log=log,
        ponder=opts.ponder,
    )
    client = ClientSocket(ip, port)
    client.send_nme(opts.name)
    noticed = None  # when pondering saw the next message arrive
    try:
        while True:
            try:
                cmd, payload = client.get_message()
            except (ConnectionClosed, OSError):  # server closed or reset the connection
                break
            t_recv = time.perf_counter()
            if noticed is not None:  # the server's clock started when it arrived, not now
                t_recv = min(t_recv, noticed)
                noticed = None
            if cmd == "set":
                agent.new_game()
                agent.on_set(*payload)
            elif cmd == "hum":
                pass  # house positions; contents arrive with MAP
            elif cmd == "hme":
                agent.on_hme(*payload)
            elif cmd == "map":
                agent.on_map(payload)
                noticed = agent.ponder(client.has_pending_data)
            elif cmd == "upd":
                agent.on_upd(payload)
                if client.has_pending_data():
                    agent.my_turns += 1  # we are behind: this turn is lost, a newer message waits
                    continue
                moves = agent.decide(t_recv)
                if client.has_pending_data():
                    continue  # turn already skipped by the server: sending now would desync
                client.send_mov(moves)
                noticed = agent.ponder(client.has_pending_data)
            elif cmd == "end":
                agent.new_game()
            elif cmd == "bye":
                break
    finally:
        client.close()
        if log is not None and log is not sys.stderr:
            log.close()


if __name__ == "__main__":
    gc.disable()  # avoid multi-100 ms collector pauses on our clock (see vvw/search.py)
    ip_, port_, opts_ = parse_args(sys.argv[1:])
    play(ip_, port_, opts_)
