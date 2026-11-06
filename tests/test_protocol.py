import argparse
import socket
import subprocess
import sys
import threading
import time
import unittest

import main as entry
from sim.fake_server import FakeServer
from sim.maps import MapSpec, load_map
from vvw.client import ClientSocket


class ClientParsing(unittest.TestCase):
    def setUp(self):
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        self.client = ClientSocket("127.0.0.1", self.srv.getsockname()[1])
        self.conn, _ = self.srv.accept()

    def tearDown(self):
        self.client.close()
        self.conn.close()
        self.srv.close()

    def test_handshake_and_messages(self):
        self.client.send_nme("Bob")
        self.assertEqual(self.conn.recv(100), b"NME\x03Bob")
        # SET+HUM+HME arrive in one packet on the real server; split reads must still work.
        self.conn.sendall(b"SET\x05\x0aHUM\x02\x01\x02\x03\x04HME\x00\x04")
        self.conn.sendall(b"MAP\x02" + bytes([1, 2, 3, 0, 0]) + bytes([0, 4, 0, 6, 0]))
        self.conn.sendall(b"UPD\x00END")
        self.conn.sendall(b"BYE")
        self.assertEqual(self.client.get_message(), ("set", (5, 10)))
        self.assertEqual(self.client.get_message(), ("hum", [(1, 2), (3, 4)]))
        self.assertEqual(self.client.get_message(), ("hme", (0, 4)))
        self.assertEqual(self.client.get_message(), ("map", [(1, 2, 3, 0, 0), (0, 4, 0, 6, 0)]))
        self.assertEqual(self.client.get_message(), ("upd", []))
        self.assertEqual(self.client.get_message(), ("end", None))
        self.assertEqual(self.client.get_message(), ("bye", None))

    def test_byte_by_byte_delivery(self):
        for b in b"UPD\x01" + bytes([7, 8, 0, 0, 9]):
            self.conn.sendall(bytes([b]))
        self.assertEqual(self.client.get_message(), ("upd", [(7, 8, 0, 0, 9)]))

    def test_mov_encoding(self):
        self.client.send_mov([(1, 2, 3, 2, 3), (4, 4, 10, 5, 5)])
        self.assertEqual(self.conn.recv(100), b"MOV\x02" + bytes([1, 2, 3, 2, 3, 4, 4, 10, 5, 5]))


class CommandLine(unittest.TestCase):
    def test_ip_port_are_last_two_args(self):
        ip, port, opts = entry.parse_args(
            ["--myparams", "123", "--name", "X", "123.123.3.5", "6666"]
        )
        self.assertEqual((ip, port, opts.name), ("123.123.3.5", 6666, "X"))
        ip, port, _ = entry.parse_args(["10.0.0.1", "5555"])
        self.assertEqual((ip, port), ("10.0.0.1", 5555))


class SecondGameSameConnection(unittest.TestCase):
    """END means 'clear the game and prepare a new one' (brief): the client must start over."""

    def test_end_then_new_game(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        opts = argparse.Namespace(
            name="T", budget=0.05, max_plays=200, max_game_time=300.0, log=None, ponder=True
        )
        th = threading.Thread(target=entry.play, args=("127.0.0.1", srv.getsockname()[1], opts))
        th.start()
        conn, _ = srv.accept()
        conn.settimeout(10)
        self.assertEqual(conn.recv(100), b"NME\x01T")

        def recv_mov():
            head = conn.recv(4)
            self.assertEqual(head[:3], b"MOV")
            body = b""
            while len(body) < 5 * head[3]:
                body += conn.recv(5 * head[3] - len(body))
            return [tuple(body[i : i + 5]) for i in range(0, len(body), 5)]

        # Game 1: we are Vampires at (0,0) on 3x3.
        conn.sendall(b"SET\x03\x03HUM\x00HME\x00\x00")
        conn.sendall(b"MAP\x02" + bytes([0, 0, 0, 4, 0]) + bytes([2, 2, 0, 0, 4]))
        conn.sendall(b"UPD\x00")
        mv = recv_mov()
        self.assertEqual(mv[0][:2], (0, 0))
        # END mid-game, then game 2 on a different board where we are Werewolves at (4,0).
        conn.sendall(b"END")
        conn.sendall(b"SET\x01\x05HUM\x01\x02\x00HME\x04\x00")
        conn.sendall(
            b"MAP\x03" + bytes([0, 0, 0, 3, 0]) + bytes([2, 0, 2, 0, 0]) + bytes([4, 0, 0, 0, 3])
        )
        conn.sendall(b"UPD\x01" + bytes([1, 0, 0, 3, 0]))
        mv = recv_mov()
        self.assertTrue(all(m[:2] == (4, 0) and m[3:] == (3, 0) for m in mv), mv)
        conn.sendall(b"END")
        conn.sendall(b"BYE")
        th.join(10)
        self.assertFalse(th.is_alive())
        conn.close()
        srv.close()


class TurnLimitUnknown(unittest.TestCase):
    def test_extends_when_game_outlives_assumption(self):
        from vvw.ai import Agent

        a = Agent(max_plays=200)
        a.me = 0
        a.my_turns = 100  # global ply 200: the server evidently allows more
        self.assertGreater(a.plies_left(0.0), 1)


class EndToEnd(unittest.TestCase):
    """Two real client processes (main.py, pondering on) play complete games through the
    byte-exact fake server. Separate processes, as in the tournament: client threads in one
    interpreter would share the GIL, so one client's pondering would stall the other."""

    def _match(self, spec: MapSpec, max_plays: int = 40, extra=()):
        srv = FakeServer(
            spec, port=0, move_time=2.0, max_plays=max_plays, end_sleep=0.05, log=lambda *_: None
        )
        th = threading.Thread(target=srv.run)
        th.start()
        cmd = [sys.executable, "main.py", "--budget", "0.05", "--max-plays", str(max_plays)]
        cmd += [*extra, "127.0.0.1", str(srv.port)]
        clients = []
        for _ in range(2):
            clients.append(subprocess.Popen(cmd, stdout=subprocess.DEVNULL))
            time.sleep(0.2)
        th.join(120)
        for c in clients:
            self.assertEqual(c.wait(10), 0, "client did not exit cleanly after END/BYE")
        return srv.result

    def test_full_games_without_cheating(self):
        for path in ("sim/maps/testmap2.xml", "sim/maps/thetrap.xml"):
            res = self._match(load_map(path))
            self.assertNotIn("cheated", res["reason"], res)
            self.assertEqual(res["timeouts"], [0, 0], res)

    def test_without_pondering(self):
        res = self._match(load_map("sim/maps/thetrap.xml"), extra=["--no-ponder"])
        self.assertNotIn("cheated", res["reason"], res)
        self.assertEqual(res["timeouts"], [0, 0], res)


if __name__ == "__main__":
    unittest.main()
