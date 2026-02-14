#!/usr/bin/python3.12
"""
TLS proxy with ALPN support for ISP DPI bypass.
Terminates TLS (with ALPN http/1.1) and forwards raw TCP to 3proxy.
This makes the TLS handshake look like a normal HTTPS website,
bypassing ISP detection of proxy/tunnel traffic.
"""

import ssl
import socket
import select
import threading
import signal
import sys
import os
import logging

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = int(os.environ.get("TLS_PROXY_PORT", "2096"))
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = int(os.environ.get("TLS_PROXY_BACKEND", "3128"))
CERT_FILE = os.environ.get("TLS_PROXY_CERT", "/etc/letsencrypt/live/fna.zetit.ru/fullchain.pem")
KEY_FILE = os.environ.get("TLS_PROXY_KEY", "/etc/letsencrypt/live/fna.zetit.ru/privkey.pem")
BUFFER_SIZE = 65536

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("tls-proxy")

shutdown_event = threading.Event()


def create_ssl_context():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT_FILE, KEY_FILE)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.set_alpn_protocols(["http/1.1"])
    # Session cache for performance
    ctx.options |= ssl.OP_NO_TICKET  # use session IDs, not tickets (more compatible)
    return ctx


def relay(client_sock, backend_sock, label):
    """Relay data between two sockets bidirectionally."""
    try:
        sockets = [client_sock, backend_sock]
        while not shutdown_event.is_set():
            readable, _, errored = select.select(sockets, [], sockets, 5.0)
            if errored:
                break
            for sock in readable:
                try:
                    data = sock.recv(BUFFER_SIZE)
                except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
                    continue
                except (ConnectionResetError, BrokenPipeError, OSError):
                    return
                if not data:
                    return
                dest = backend_sock if sock is client_sock else client_sock
                try:
                    dest.sendall(data)
                except (ConnectionResetError, BrokenPipeError, OSError):
                    return
    except Exception:
        pass
    finally:
        for s in (client_sock, backend_sock):
            try:
                s.close()
            except Exception:
                pass


def handle_client(client_ssl, addr):
    """Handle a single client connection."""
    try:
        backend = socket.create_connection((BACKEND_HOST, BACKEND_PORT), timeout=10)
        backend.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except Exception as e:
        log.warning("backend connect failed for %s: %s", addr[0], e)
        client_ssl.close()
        return

    relay(client_ssl, backend, addr[0])


def main():
    ctx = create_ssl_context()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(256)
    server.settimeout(2.0)

    log.info("TLS proxy listening on %s:%d -> %s:%d (ALPN: http/1.1)",
             LISTEN_HOST, LISTEN_PORT, BACKEND_HOST, BACKEND_PORT)

    def shutdown(sig, frame):
        log.info("Shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    while not shutdown_event.is_set():
        try:
            client, addr = server.accept()
        except socket.timeout:
            continue
        except OSError:
            break

        try:
            client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            client_ssl = ctx.wrap_socket(client, server_side=True)
        except ssl.SSLError:
            client.close()
            continue
        except Exception:
            client.close()
            continue

        t = threading.Thread(target=handle_client, args=(client_ssl, addr), daemon=True)
        t.start()

    server.close()
    log.info("Stopped.")


if __name__ == "__main__":
    main()
