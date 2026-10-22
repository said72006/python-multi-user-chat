"""CLI client for the line-delimited JSON chat protocol (Python 3.10+)."""
import argparse
import json
import os
import socket
import ssl
import threading

from server import MAX_LINE, receive_json, valid_nickname


def main():
    parser = argparse.ArgumentParser(description="Multi-user chat client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--tls", action="store_true", help="Verify TLS server certificate")
    parser.add_argument("--ca-file", help="CA or server certificate PEM for TLS")
    args = parser.parse_args()
    from server import is_loopback
    if not is_loopback(args.host) and not args.tls:
        parser.error("Remote connections require --tls and a trusted certificate")
    if args.ca_file and not args.tls:
        parser.error("--ca-file requires --tls")
    nickname = input("Nickname (letters/digits/_/-, max 24): ").strip()
    if not valid_nickname(nickname):
        parser.error("Invalid nickname")
    conn = socket.create_connection((args.host, args.port), timeout=10)
    try:
        if args.tls:
            context = ssl.create_default_context(cafile=args.ca_file)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            conn = context.wrap_socket(conn, server_hostname=args.host)
        with conn:
            with conn.makefile("r", encoding="utf-8", newline="\n") as reader:
                hello = {"type": "hello", "nickname": nickname,
                         "token": os.getenv("CHAT_SHARED_TOKEN", "")}
                conn.sendall((json.dumps(hello) + "\n").encode("utf-8"))
                response = receive_json(reader)
                if not response or response.get("type") != "welcome":
                    print(response.get("text", "Server disconnected") if response else "Server disconnected")
                    return
                print(response["text"])
                finished = threading.Event()

                def receive():
                    try:
                        while not finished.is_set():
                            item = receive_json(reader)
                            if item is None:
                                break
                            if item.get("type") == "chat":
                                print(f"\n{item.get('from', '?')}: {item.get('text', '')}")
                            else:
                                print("\n" + str(item.get("text", "")))
                    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
                        pass
                    finally:
                        finished.set()
                        print("\nDisconnected")

                threading.Thread(target=receive, daemon=True).start()
                try:
                    while not finished.is_set():
                        message = input("You (/quit to exit): ")
                        if message == "/quit":
                            break
                        message = message.strip()
                        if not message or len(message) > 1000:
                            print("Message must be 1-1000 characters")
                            continue
                        payload = (json.dumps({"type": "chat", "text": message}, ensure_ascii=False) + "\n").encode("utf-8")
                        if len(payload) > MAX_LINE:
                            print("Message is too long")
                            continue
                        conn.sendall(payload)
                except (EOFError, KeyboardInterrupt, BrokenPipeError, ConnectionError):
                    pass
                finally:
                    finished.set()
                    try:
                        conn.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
    except (OSError, ssl.SSLError, ValueError) as exc:
        print("Connection failed:", exc)


if __name__ == "__main__":
    main()
