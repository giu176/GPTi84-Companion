"""Pico W wifi + framed-TCP client for the chat bridge.

Loads SSID/PSK and SERVER_HOST/SERVER_PORT from `secrets`. Frames are
4-byte big-endian length followed by N payload bytes.
"""

import network
import socket
import struct
import time

import secrets


def connect_wifi(timeout_s=15):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("wifi: connecting to", secrets.WIFI_SSID)
        wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
        deadline = time.ticks_add(time.ticks_ms(), timeout_s * 1000)
        while not wlan.isconnected():
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                raise OSError("wifi connect timed out")
            time.sleep_ms(200)
    print("wifi: connected, ifconfig=", wlan.ifconfig())
    return wlan


def open_socket(host=None, port=None):
    host = host if host is not None else secrets.SERVER_HOST
    port = port if port is not None else secrets.SERVER_PORT
    addr = socket.getaddrinfo(host, port)[0][-1]
    s = socket.socket()
    s.connect(addr)
    print("net: connected to", host, port)
    return s


def send_framed(sock, payload):
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise TypeError("payload must be bytes-like")
    sock.sendall(struct.pack(">I", len(payload)))
    sock.sendall(bytes(payload))


def _recv_n_blocking(sock, n):
    """Read exactly n bytes from a blocking socket. None on clean close."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


class FrameReader:
    """Stateful non-blocking framed-frame reader.

    Drives a single TCP socket in non-blocking mode. `poll()` returns a
    completed payload (bytes) if one is ready, or None if not enough data
    has arrived yet. Frame format: 4-byte big-endian length + payload.

    Use this from the bridge supervisor's idle path so we can interleave
    with DBUS work without blocking.
    """
    def __init__(self, sock):
        self.sock = sock
        sock.setblocking(False)
        self._hdr = bytearray()
        self._body = bytearray()
        self._needed = None     # None until header parsed

    def poll(self):
        try:
            if self._needed is None:
                while len(self._hdr) < 4:
                    chunk = self.sock.recv(4 - len(self._hdr))
                    if chunk is None:
                        return None         # MicroPython: no data available
                    if chunk == b"":
                        raise OSError("peer closed")
                    print("FrameReader: hdr chunk len=", len(chunk),
                          "bytes=", bytes(chunk))
                    self._hdr.extend(chunk)
                (self._needed,) = struct.unpack(">I", bytes(self._hdr))
                print("FrameReader: parsed length=", self._needed)
                if self._needed > 1 << 20:
                    raise OSError("oversize frame")
            while len(self._body) < self._needed:
                chunk = self.sock.recv(self._needed - len(self._body))
                if chunk is None:
                    return None
                if chunk == b"":
                    raise OSError("peer closed")
                print("FrameReader: body chunk len=", len(chunk))
                self._body.extend(chunk)
            payload = bytes(self._body)
            self._hdr = bytearray()
            self._body = bytearray()
            self._needed = None
            return payload
        except OSError as e:
            # MicroPython's non-blocking recv may either return None,
            # raise OSError(EAGAIN), or behave like CPython depending on
            # build. Treat EAGAIN as "no frame yet". Other OSError
            # (peer closed, oversize, real socket error) propagates.
            errno = e.args[0] if e.args else 0
            if errno in (11, 35, 110):  # EAGAIN linux/darwin, ETIMEDOUT
                return None
            print("FrameReader: OSError errno=", errno, "args=", e.args)
            raise
