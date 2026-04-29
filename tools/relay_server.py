"""Lightweight TCP relay for the calc<->desktop chat bridge.

Listens on a TCP port, reads length-prefixed frames (4-byte big-endian
length + payload) from connected clients and prints each frame.

Reverse direction (two modes):
  --echo  : every received frame is auto-replied with "echo: <text>".
            This is the v0 stub for "ChatGPT on the calc": proves the
            calc-as-master REQ/response architecture without an LLM
            in the loop.
  default : lines typed on stdin are shipped to the latest client.
"""

import argparse
import datetime as dt
import socketserver
import struct
import sys
import threading


def _read_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


_active_lock = threading.Lock()
_active_client = None  # most recent connection's request socket


def _set_active(sock):
    global _active_client
    with _active_lock:
        _active_client = sock


def _send_to_active(payload):
    with _active_lock:
        sock = _active_client
    if sock is None:
        print("[%s] no active client; dropping send (%d bytes)" % (_now(), len(payload)), flush=True)
        return
    try:
        sock.sendall(struct.pack(">I", len(payload)) + payload)
        print("[%s] -> client len=%d %r" % (_now(), len(payload), payload), flush=True)
    except OSError as e:
        print("[%s] send to client failed: %s" % (_now(), e), flush=True)


_echo_mode = False


class FramedHandler(socketserver.BaseRequestHandler):
    def handle(self):
        peer = "%s:%d" % self.client_address
        print("[%s] connected: %s" % (_now(), peer), flush=True)
        _set_active(self.request)
        try:
            while True:
                hdr = _read_exact(self.request, 4)
                if hdr is None:
                    break
                (length,) = struct.unpack(">I", hdr)
                if length > 1 << 20:
                    print("[%s] %s: oversize frame %d, closing" % (_now(), peer, length), flush=True)
                    return
                body = _read_exact(self.request, length)
                if body is None:
                    print("[%s] %s: short read mid-frame" % (_now(), peer), flush=True)
                    return
                try:
                    text = body.decode("ascii")
                    pretty = repr(text)
                except UnicodeDecodeError:
                    text = None
                    pretty = body.hex()
                print("[%s] %s len=%d %s" % (_now(), peer, length, pretty), flush=True)
                if _echo_mode and text is not None:
                    reply = ("echo: " + text).encode("ascii", errors="replace")
                    try:
                        self.request.sendall(struct.pack(">I", len(reply)) + reply)
                        print("[%s] -> %s len=%d %r" % (_now(), peer, len(reply), reply), flush=True)
                    except OSError as e:
                        print("[%s] echo to %s failed: %s" % (_now(), peer, e), flush=True)
        finally:
            print("[%s] disconnected: %s" % (_now(), peer), flush=True)
            with _active_lock:
                global _active_client
                if _active_client is self.request:
                    _active_client = None


def _stdin_pump():
    """Read lines from stdin; each line gets framed and sent to the
    most-recently-connected client. EOF closes silently."""
    try:
        for line in sys.stdin:
            line = line.rstrip("\n")
            if not line:
                continue
            _send_to_active(line.encode("ascii", errors="replace"))
    except (EOFError, KeyboardInterrupt):
        pass


def _now():
    return dt.datetime.now().strftime("%H:%M:%S")


class ReusingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9999)
    ap.add_argument("--echo", action="store_true",
                    help="auto-reply every received frame with 'echo: <text>' "
                         "(v0 stub for ChatGPT-on-calc)")
    args = ap.parse_args(argv)
    global _echo_mode
    _echo_mode = args.echo
    with ReusingServer((args.host, args.port), FramedHandler) as srv:
        print("relay: listening on %s:%d" % (args.host, args.port), flush=True)
        if _echo_mode:
            print("relay: ECHO MODE -- every frame auto-replied 'echo: <text>'", flush=True)
        else:
            print("relay: type a line + ENTER to send to the latest connected client", flush=True)
        t = threading.Thread(target=_stdin_pump, daemon=True)
        t.start()
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nrelay: shutting down", flush=True)


if __name__ == "__main__":
    sys.exit(main())
