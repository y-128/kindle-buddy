from __future__ import annotations

"""Transport layer — WiFi TCP server + USB Serial (CDC gadget).

The Kindle acts as the **server**:
  - WiFiTransport  : binds TCP port 9877, accepts one connection at a time.
  - SerialTransport: opens /dev/ttyGS0 (USB CDC gadget, appears as serial
                     port on the Mac side).

Both transports call ``on_line(line)`` with a complete UTF-8 JSON line
whenever one arrives, and expose ``write(data)`` for sending JSON frames
back to the Mac.

Usage (from buddy.py):
    t = build_transport()
    t.start(on_line=state.update_from_json)
    ...
    t.write(json.dumps(ack).encode() + b"\\n")
"""

import json
import logging
import os
import socket
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable

log = logging.getLogger(__name__)

LineCallback = Callable[[str], None]

# ── Base ──────────────────────────────────────────────────────────────────────

class Transport(ABC):
    """Minimal async-like line-based transport (runs reader on a thread)."""

    def __init__(self):
        self._on_line: LineCallback | None = None
        self._buf = bytearray()
        self._write_lock = threading.Lock()

    def start(self, on_line: LineCallback) -> None:
        self._on_line = on_line
        threading.Thread(target=self._accept_loop, daemon=True, name=f"{type(self).__name__}-accept").start()

    @abstractmethod
    def _accept_loop(self) -> None: ...

    def _feed(self, data: bytes) -> None:
        """Append bytes and dispatch complete lines."""
        self._buf.extend(data)
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            line = line.strip()
            if line and self._on_line:
                try:
                    self._on_line(line.decode("utf-8", errors="replace"))
                except Exception:
                    log.exception("on_line callback raised")

    @abstractmethod
    def write(self, data: bytes) -> None: ...

    @abstractmethod
    def connected(self) -> bool: ...


# ── WiFi TCP (Kindle = server) ────────────────────────────────────────────────

class WiFiTransport(Transport):
    """Listen on ``port`` for a single TCP connection from the Mac."""

    def __init__(self, host: str = "0.0.0.0", port: int = 9877):
        super().__init__()
        self._host = host
        self._port = port
        self._conn: socket.socket | None = None
        self._connected = False

    def connected(self) -> bool:
        return self._connected

    def _accept_loop(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self._host, self._port))
        srv.listen(1)
        log.info("[wifi] listening on %s:%d", self._host, self._port)
        while True:
            try:
                conn, addr = srv.accept()
                log.info("[wifi] connected from %s", addr)
                self._conn = conn
                self._connected = True
                self._buf = bytearray()
                self._reader(conn)
            except Exception as e:
                log.warning("[wifi] connection error: %s", e)
            finally:
                self._connected = False
                self._conn = None
                time.sleep(1)

    def _reader(self, conn: socket.socket) -> None:
        try:
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    log.info("[wifi] connection closed by peer")
                    break
                self._feed(chunk)
        except OSError as e:
            log.warning("[wifi] read error: %s", e)
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def write(self, data: bytes) -> None:
        with self._write_lock:
            conn = self._conn
            if conn is None:
                return
            try:
                conn.sendall(data)
            except OSError as e:
                log.warning("[wifi] write error: %s", e)
                self._connected = False


# ── USB Serial (Kindle CDC gadget /dev/ttyGS0) ────────────────────────────────

class SerialTransport(Transport):
    """Read/write /dev/ttyGS0 (or any serial path) in raw byte mode."""

    def __init__(self, path: str = "/dev/ttyGS0", baud: int = 115200):
        super().__init__()
        self._path = path
        self._baud = baud
        self._fd: int | None = None
        self._connected = False

    def connected(self) -> bool:
        return self._connected

    def _accept_loop(self) -> None:
        """Continuously (re)open the serial port and relay bytes."""
        import termios, tty

        while True:
            try:
                fd = os.open(self._path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
                # Set raw mode + baud
                attrs = termios.tcgetattr(fd)
                tty.setraw(fd)
                speed = {
                    9600: termios.B9600, 115200: termios.B115200,
                }.get(self._baud, termios.B115200)
                attrs[4] = attrs[5] = speed
                termios.tcsetattr(fd, termios.TCSANOW, attrs)
                os.set_blocking(fd, True)

                self._fd = fd
                self._connected = True
                self._buf = bytearray()
                log.info("[serial] opened %s", self._path)

                while True:
                    chunk = os.read(fd, 256)
                    if not chunk:
                        break
                    self._feed(chunk)

            except Exception as e:
                log.warning("[serial] error: %s", e)
            finally:
                self._connected = False
                self._fd = None
                try:
                    os.close(fd)  # type: ignore[name-defined]
                except Exception:
                    pass
                time.sleep(2)

    def write(self, data: bytes) -> None:
        with self._write_lock:
            fd = self._fd
            if fd is None:
                return
            try:
                os.write(fd, data)
            except OSError as e:
                log.warning("[serial] write error: %s", e)
                self._connected = False


# ── Auto-select + build ───────────────────────────────────────────────────────

def build_transport(mode: str = "auto",
                    serial_path: str = "/dev/ttyGS0",
                    tcp_port: int = 9877) -> Transport:
    """Return the appropriate transport based on *mode*.

    ``auto``   — prefer WiFiTransport; also start SerialTransport if path exists
    ``wifi``   — WiFiTransport only
    ``serial`` — SerialTransport only
    ``both``   — MultiTransport (WiFi + Serial)
    """
    if mode == "serial":
        return SerialTransport(serial_path)
    if mode == "wifi":
        return WiFiTransport(port=tcp_port)
    if mode == "both":
        return MultiTransport(WiFiTransport(port=tcp_port), SerialTransport(serial_path))
    # auto
    if os.path.exists(serial_path):
        return MultiTransport(WiFiTransport(port=tcp_port), SerialTransport(serial_path))
    return WiFiTransport(port=tcp_port)


class MultiTransport(Transport):
    """Fan-out: start multiple transports, merge their on_line streams, broadcast writes."""

    def __init__(self, *transports: Transport):
        super().__init__()
        self._transports = list(transports)

    def start(self, on_line: LineCallback) -> None:
        self._on_line = on_line
        for t in self._transports:
            t.start(on_line)

    def _accept_loop(self) -> None:
        pass  # each sub-transport manages its own thread

    def write(self, data: bytes) -> None:
        for t in self._transports:
            if t.connected():
                t.write(data)

    def connected(self) -> bool:
        return any(t.connected() for t in self._transports)
