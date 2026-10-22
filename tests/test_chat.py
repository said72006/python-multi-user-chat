"""Run with: python -m unittest discover -s tests -v"""
import json
import socket
import threading
import time
import unittest

from server import ChatServer, HANDSHAKE_TIMEOUT, MAX_CONNECTIONS, is_loopback, receive_json, valid_nickname


class ChatTests(unittest.TestCase):
    def test_name_validation(self):
        self.assertTrue(valid_nickname("alice_1"))
        for name in ("", "hello there", "a" * 25, "../admin", None):
            self.assertFalse(valid_nickname(name))

    def test_remote_requires_security(self):
        with self.assertRaises(ValueError):
            ChatServer(host="0.0.0.0")
        self.assertTrue(is_loopback("127.0.0.1"))
        self.assertFalse(is_loopback("0.0.0.0"))

    def test_worker_limits_configured(self):
        self.assertGreater(MAX_CONNECTIONS, 0)
        self.assertLessEqual(HANDSHAKE_TIMEOUT, 15)

    def test_framing(self):
        left, right = socket.socketpair()
        with left, right:
            with right.makefile("r", encoding="utf-8", newline="\n") as reader:
                left.sendall(b'{"type":"chat","text":"hi"}\n')
                self.assertEqual(receive_json(reader)["text"], "hi")
                left.sendall(b"garbage\n")
                with self.assertRaises(json.JSONDecodeError):
                    receive_json(reader)

    def test_authentication_and_relay(self):
        server = ChatServer(port=0, token="a-demo-test-token")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        for _ in range(100):
            if server.running.is_set():
                break
            time.sleep(0.01)
        self.assertTrue(server.running.is_set())
        port = server.listener.getsockname()[1]
        sockets = []
        readers = []
        try:
            def connect(name, token):
                sock = socket.create_connection(("127.0.0.1", port), timeout=3)
                sock.settimeout(3)
                reader = sock.makefile("r", encoding="utf-8", newline="\n")
                sockets.append(sock)
                readers.append(reader)
                sock.sendall((json.dumps({"type": "hello", "nickname": name, "token": token}) + "\n").encode())
                return sock, reader, receive_json(reader)

            _, _, failed = connect("eve", "wrong")
            self.assertEqual(failed["type"], "error")
            alice, alice_reader, welcome = connect("alice", "a-demo-test-token")
            self.assertEqual(welcome["type"], "welcome")
            _, bob_reader, welcome = connect("bob", "a-demo-test-token")
            self.assertEqual(welcome["type"], "welcome")
            self.assertEqual(receive_json(alice_reader)["type"], "notice")
            # Two lines in one write must remain two independent messages.
            alice.sendall(b'{"type":"chat","text":"hello"}\n{"type":"chat","text":"world"}\n')
            self.assertEqual(receive_json(bob_reader)["text"], "hello")
            self.assertEqual(receive_json(bob_reader)["text"], "world")
            _, _, duplicate = connect("alice", "a-demo-test-token")
            self.assertEqual(duplicate["type"], "error")
        finally:
            for reader in readers:
                try: reader.close()
                except OSError: pass
            for sock in sockets:
                sock.close()
            server.close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
