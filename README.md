# Multi-User Chat (Python)

A **local-first** TCP chat for learning sockets and threading. Messages use newline-delimited JSON, not raw TCP reads, so messages remain framed even if packets split or coalesce.

## Features
- Thread-safe nickname registration, concurrent clients, chat broadcast, join/leave notices.
- Length and input validation, graceful disconnections and explicit protocol errors.
- Up to 32 concurrent or pending connections with a 10-second authentication/TLS handshake timeout.
- Local-only by default (127.0.0.1:5000).
- **TLS certificate + shared token mandatory when listening on a non-loopback interface.**
- Python standard library only; automated tests in GitHub Actions.

## Quick start (same computer)

```bash
python server.py
# In each of two other terminals:
python client.py
```

Enter different nicknames. Type `/quit` to exit. This setup binds to localhost, so other machines cannot connect.

## Remote/LAN mode (requires certificate and authentication)

Make a TLS certificate with a subject alternative name (SAN) matching the **hostname** clients use. For a private lab, use a locally trusted certificate authority; do not disable certificate validation.

On the server, export a long random secret through the environment (**never commit it**) and start:

```bash
export CHAT_SHARED_TOKEN='replace-with-a-unique-long-random-secret'
python server.py --host 0.0.0.0 --port 5000 --cert server.pem --key server-key.pem
```

On each authorized client, set the same token in the environment, trust the certificate authority, and connect:

```bash
export CHAT_SHARED_TOKEN='replace-with-the-same-secret'
python client.py --host chat.example.test --tls --ca-file ca.pem
```

**Security limits:** A shared token identifies the group, **not individual users**; all authenticated users can impersonate any unoccupied nickname. There is no message history or end-to-end encryption. The 32-connection cap is basic resource protection, not a denial-of-service guarantee. Do not deploy as a public production chat service without per-user identity, abuse protections, and proper operations.

## Protocol
Each line is a JSON object. First send `{"type":"hello","nickname":"alice","token":"..."}`; the server replies with `welcome` or `error`. Then send `{"type":"chat","text":"Hello"}`. Incoming events are `chat`, `notice`, or `error`. Maximum inbound line length: 4096 characters, maximum message text length: 1000 characters. Nicknames: 1–24 ASCII letters, numbers, underscores or dashes.

## Tests

```bash
python -m unittest discover -s tests -v
```

The tests check framing, nickname validation, remote-mode restrictions, authentication, and message relay.

## Project files
- `server.py` — threaded TCP/TLS server and protocol.
- `client.py` — interactive client.
- `tests/test_chat.py` — unit and integration tests.
- `images/` — original screenshots.

**Note:** This is an educational project; adding TLS protects communication in transit but does not turn it into a production-ready messaging service.
