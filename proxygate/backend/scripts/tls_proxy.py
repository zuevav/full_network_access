#!/usr/bin/python3.12
"""
Dual-purpose TLS proxy with ALPN for ISP DPI bypass.

Listens on a single port (default 8443) with TLS + ALPN http/1.1.
- HTTP CONNECT requests → tunnel to 3proxy (proxy traffic)
- Regular HTTP requests → forward to nginx (web panel)

This makes ALL traffic look like normal HTTPS website access,
bypassing ISP DPI that throttles proxy/tunnel connections.
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
LISTEN_PORT = int(os.environ.get("TLS_PROXY_PORT", "8443"))
PROXY_BACKEND = os.environ.get("TLS_PROXY_BACKEND", "127.0.0.1:3128")
WEB_BACKEND = os.environ.get("TLS_PROXY_WEB", "127.0.0.1:8444")
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


def parse_host_port(s):
    host, port = s.rsplit(":", 1)
    return host, int(port)


PROXY_HOST, PROXY_PORT = parse_host_port(PROXY_BACKEND)
WEB_HOST, WEB_PORT = parse_host_port(WEB_BACKEND)


def create_ssl_context():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(CERT_FILE, KEY_FILE)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.set_alpn_protocols(["http/1.1"])
    return ctx


def relay(sock_a, sock_b):
    """Relay data between two sockets bidirectionally until one closes."""
    sockets = [sock_a, sock_b]
    try:
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
                dest = sock_b if sock is sock_a else sock_a
                try:
                    dest.sendall(data)
                except (ConnectionResetError, BrokenPipeError, OSError):
                    return
    except Exception:
        pass


def handle_connect(client_ssl, target_host, target_port):
    """Handle HTTP CONNECT — tunnel through 3proxy."""
    try:
        backend = socket.create_connection((PROXY_HOST, PROXY_PORT), timeout=10)
        backend.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except Exception as e:
        try:
            client_ssl.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        except Exception:
            pass
        return

    # Send CONNECT to 3proxy
    connect_req = f"CONNECT {target_host}:{target_port} HTTP/1.1\r\nHost: {target_host}:{target_port}\r\n\r\n"
    try:
        backend.sendall(connect_req.encode())
    except Exception:
        backend.close()
        try:
            client_ssl.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        except Exception:
            pass
        return

    # Read 3proxy response
    try:
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = backend.recv(4096)
            if not chunk:
                break
            resp += chunk
    except Exception:
        backend.close()
        try:
            client_ssl.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        except Exception:
            pass
        return

    # Check if 3proxy accepted
    first_line = resp.split(b"\r\n")[0]
    if b"200" in first_line:
        # Send success to client
        try:
            client_ssl.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
        except Exception:
            backend.close()
            return
        # Relay bidirectionally
        relay(client_ssl, backend)
    else:
        try:
            client_ssl.sendall(resp)
        except Exception:
            pass

    backend.close()


def handle_http(client_ssl, initial_data):
    """Handle regular HTTP — forward to nginx web backend."""
    try:
        backend = socket.create_connection((WEB_HOST, WEB_PORT), timeout=10)
        backend.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except Exception:
        try:
            client_ssl.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        except Exception:
            pass
        return

    # Send the initial data we already read
    try:
        backend.sendall(initial_data)
    except Exception:
        backend.close()
        return

    # Relay the rest
    relay(client_ssl, backend)
    backend.close()


def handle_client(client_ssl, addr):
    """Handle a single client connection — detect CONNECT vs regular HTTP."""
    try:
        # Read the first chunk to determine request type
        client_ssl.settimeout(30.0)
        initial_data = b""
        while b"\r\n" not in initial_data:
            chunk = client_ssl.recv(BUFFER_SIZE)
            if not chunk:
                return
            initial_data += chunk
            if len(initial_data) > 8192:
                break

        first_line = initial_data.split(b"\r\n")[0].decode("utf-8", errors="replace")

        if first_line.upper().startswith("CONNECT "):
            # CONNECT host:port HTTP/1.1
            parts = first_line.split()
            if len(parts) >= 2:
                target = parts[1]
                if ":" in target:
                    host, port = target.rsplit(":", 1)
                    try:
                        port = int(port)
                    except ValueError:
                        port = 443
                else:
                    host = target
                    port = 443
                # Read remaining headers
                while b"\r\n\r\n" not in initial_data:
                    chunk = client_ssl.recv(BUFFER_SIZE)
                    if not chunk:
                        return
                    initial_data += chunk
                handle_connect(client_ssl, host, port)
            else:
                client_ssl.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
        else:
            # Regular HTTP request — forward to web backend
            handle_http(client_ssl, initial_data)
    except ssl.SSLError:
        pass
    except socket.timeout:
        pass
    except Exception:
        pass
    finally:
        try:
            client_ssl.close()
        except Exception:
            pass


def main():
    ctx = create_ssl_context()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(256)
    server.settimeout(2.0)

    log.info(
        "Dual TLS proxy on %s:%d — CONNECT→%s:%d, HTTP→%s:%d (ALPN: http/1.1)",
        LISTEN_HOST, LISTEN_PORT,
        PROXY_HOST, PROXY_PORT,
        WEB_HOST, WEB_PORT,
    )

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
