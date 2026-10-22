"""Thread-safe, newline-delimited JSON chat server (Python 3.10+)."""
import argparse
import hmac
import ipaddress
import json
import os
import re
import socket
import ssl
import threading

MAX_LINE = 4096
MAX_MESSAGE = 1000


def is_loopback(host):
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


def valid_nickname(name):
    return isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,24}", name) is not None


def receive_json(reader):
    line = reader.readline(MAX_LINE + 1)
    if not line:
        return None
    if len(line) > MAX_LINE or not line.endswith("\n"):
        raise ValueError("Message too long or incomplete")
    message = json.loads(line)
    if not isinstance(message, dict):
        raise ValueError("Expected a JSON object")
    return message


class Peer:
    def __init__(self, conn):
        self.conn = conn
        self.nickname = None
        self.send_lock = threading.Lock()

    def send(self, message):
        data = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
        if len(data) > MAX_LINE:
            raise ValueError("Outgoing message too long")
        with self.send_lock:
            self.conn.sendall(data)


class ChatServer:
    def __init__(self, host="127.0.0.1", port=5000, certificate=None, key=None, token=None):
        if not is_loopback(host) and not (certificate and key and token):
            raise ValueError("Remote listening requires --cert, --key and CHAT_SHARED_TOKEN")
        if bool(certificate) != bool(key):
            raise ValueError("Provide --cert and --key together")
        self.host, self.port = host, port
        self.token = token
        self.context = None
        if certificate:
            self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            self.context.minimum_version = ssl.TLSVersion.TLSv1_2
            self.context.load_cert_chain(certificate, key)
        self.peers = {}
        self.lock = threading.Lock()
        self.running = threading.Event()
        self.listener = None

    def broadcast(self, message, except_peer=None):
        with self.lock:
            peers = [p for p in self.peers.values() if p is not except_peer]
        for peer in peers:
            try:
                peer.send(message)
            except (OSError, ValueError):
                self.disconnect(peer)

    def disconnect(self, peer):
        with self.lock:
            removed = self.peers.pop(peer.conn, None)
        try:
            peer.conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        peer.conn.close()
        if removed and peer.nickname:
            self.broadcast({"type": "notice", "text": peer.nickname + " left the chat"})

    def handle(self, conn):
        peer = Peer(conn)
        try:
            conn.settimeout(120)
            with conn.makefile("r", encoding="utf-8", newline="\n") as reader:
                hello = receive_json(reader)
                if hello is None or hello.get("type") != "hello":
                    peer.send({"type": "error", "text": "Expected hello message"})
                    return
                nickname = hello.get("nickname")
                if not valid_nickname(nickname):
                    peer.send({"type": "error", "text": "Nickname: 1-24 letters, digits, _ or -"})
                    return
                if self.token and not hmac.compare_digest(str(hello.get("token", "")), self.token):
                    peer.send({"type": "error", "text": "Authentication failed"})
                    return
                with self.lock:
                    if any(p.nickname == nickname for p in self.peers.values()):
                        peer.send({"type": "error", "text": "Nickname already taken"})
                        return
                    peer.nickname = nickname
                    peer.send({"type": "welcome", "text": "Connected as " + nickname})
                    self.peers[conn] = peer
                conn.settimeout(None)
                self.broadcast({"type": "notice", "text": nickname + " joined the chat"}, peer)
                while True:
                    payload = receive_json(reader)
                    if payload is None:
                        break
                    if payload.get("type") != "chat" or not isinstance(payload.get("text"), str):
                        peer.send({"type": "error", "text": "Expected chat text"})
                        break
                    text = payload["text"].strip()
                    if not text or len(text) > MAX_MESSAGE:
                        peer.send({"type": "error", "text": "Message must be 1-1000 characters"})
                        continue
                    self.broadcast({"type": "chat", "from": nickname, "text": text}, peer)
        except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
            pass
        finally:
            self.disconnect(peer)

    def serve_forever(self):
        family = socket.AF_INET6 if ":" in self.host else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as listener:
            self.listener = listener
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((self.host, self.port))
            listener.listen()
            listener.settimeout(0.5)
            self.running.set()
            print(f"Chat listening on {listener.getsockname()}", flush=True)
            try:
                while self.running.is_set():
                    try:
                        conn, _ = listener.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    if self.context:
                        try:
                            conn = self.context.wrap_socket(conn, server_side=True)
                        except ssl.SSLError:
                            conn.close()
                            continue
                    threading.Thread(target=self.handle, args=(conn,), daemon=True).start()
            finally:
                self.running.clear()

    def close(self):
        self.running.clear()
        if self.listener:
            try:
                self.listener.close()
            except OSError:
                pass
        with self.lock:
            peers = list(self.peers.values())
        for peer in peers:
            self.disconnect(peer)


def main():
    parser = argparse.ArgumentParser(description="Local-first TCP chat server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--cert", help="TLS certificate PEM")
    parser.add_argument("--key", help="TLS private key PEM")
    args = parser.parse_args()
    ChatServer(args.host, args.port, args.cert, args.key, os.getenv("CHAT_SHARED_TOKEN")).serve_forever()


if __name__ == "__main__":
    main()
