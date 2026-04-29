"""Lightweight TCP relay for the calc<->desktop chat bridge.

Listens on a TCP port, reads length-prefixed frames (4-byte big-endian
length + payload) from connected clients and prints each frame.

Reverse direction (three modes):
  --echo  : every received frame is auto-replied with "echo: <text>".
            v0 stub for "ChatGPT on the calc": proves the calc-as-master
            REQ/response architecture without an LLM in the loop.
  --llm   : parse the bridge's 'prompt:...\\nmath:...\\n' frame, send
            it to Ollama (cloud or local) with a JSON-schema format
            asking for a paginated reply (1..MAX_PAGES pages, each up
            to PAGE_CHARS chars), ASCII-clamp, ship back as a single
            framed body shaped:
                pages:N\\n<page1>\\x00<page2>\\x00...<pageN>
            Per-frame worker thread so a slow model call doesn't stall
            reads. Env: OLLAMA_URL, OLLAMA_MODEL, OLLAMA_API_KEY.
  default : lines typed on stdin are shipped to the latest client.
"""

import argparse
import datetime as dt
import json
import os
import socketserver
import struct
import sys
import threading
import urllib.error
import urllib.request


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
_llm_mode = False


# Screen geometry. The TI-84 Plus homescreen is 16 cols x 8 rows in
# large font. Row 8 is reserved for the BASIC pager UI ("1/4  < >"),
# leaving 16x7=112 chars per page of body text. MAX_PAGES is bounded
# by how many Str slots we can route into on the calc side: Str3..Str9
# plus Str0 = 8 slots. Str1 and Str2 are user-input reserved.
PAGE_COLS = 16
PAGE_ROWS = 7
PAGE_CHARS = PAGE_COLS * PAGE_ROWS  # 112
MAX_PAGES = 8

OLLAMA_URL = os.environ.get("OLLAMA_URL", "https://ollama.com/api/chat")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gpt-oss:120b-cloud")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "")
OLLAMA_TIMEOUT_S = 25

_REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "pages": {
            "type": "array",
            "minItems": 1,
            "maxItems": MAX_PAGES,
            "items": {"type": "string", "maxLength": PAGE_CHARS},
        },
    },
    "required": ["pages"],
}

_SYSTEM_PROMPT = (
    "You are a helper running on a TI-84 Plus calculator. The user "
    "flips through your reply with the calculator's left/right arrow "
    "keys, one screenful at a time. The screen shows "
    + str(PAGE_COLS) + " columns by " + str(PAGE_ROWS) + " rows of "
    "large-font text.\n"
    "Output rules:\n"
    " - Plain ASCII only. No unicode, no markdown, no code fences.\n"
    " - Each page is at most " + str(PAGE_CHARS) + " characters.\n"
    " - Hard-wrap each line at " + str(PAGE_COLS) + " columns. Insert "
    "a literal newline ('\\n') where you want a line break. Do not "
    "break a word mid-letter unless the single token is longer than "
    + str(PAGE_COLS) + " characters.\n"
    " - Use up to " + str(MAX_PAGES) + " pages. Use as few as the "
    "answer needs. A short answer should be a single page. Do not "
    "pad pages with blank lines to look fuller.\n"
    " - Keep semantically related content (a code block, a table row, "
    "a list item) on the same page when it fits.\n"
    "If the user provided a 'math' field, treat it as a TI-BASIC-style "
    "expression and incorporate it into your answer."
)

# Bound concurrent in-flight model calls per relay process. Cheap
# backpressure if the calc spam-clicks RUN.
_LLM_INFLIGHT = threading.Semaphore(2)


def _parse_pair(text):
    prompt, math = "", ""
    for line in text.split("\n"):
        if line.startswith("prompt:"):
            prompt = line[len("prompt:"):]
        elif line.startswith("math:"):
            math = line[len("math:"):]
    return prompt, math


def _ascii_clamp(s, n):
    out = "".join(c if 0x20 <= ord(c) < 0x7F else "?" for c in s)
    return out[:n]


def _call_ollama(prompt, math):
    """Returns a list[str] of pages (1..MAX_PAGES). Raises on transport
    or decode failure; caller wraps to a one-page error reply."""
    user = "prompt: " + prompt + "\nmath: " + math
    body = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "format": _REPLY_SCHEMA,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    headers = {"Content-Type": "application/json"}
    if OLLAMA_API_KEY:
        headers["Authorization"] = "Bearer " + OLLAMA_API_KEY
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT_S) as r:
        resp = json.loads(r.read().decode("utf-8"))
    content = resp.get("message", {}).get("content", "")
    try:
        obj = json.loads(content)
        pages = obj.get("pages")
        if isinstance(pages, list) and pages:
            return [str(p) for p in pages]
        # Older single-string shape, or no pages key: treat as one page.
        reply = str(obj.get("reply", content)).strip()
        return [reply] if reply else [""]
    except (ValueError, TypeError):
        return [content.strip()]


def _llm_reply_pages(text):
    """Build the framed multi-page body for one inbound prompt frame.
    Format: 'pages:N\\n' + NUL-separated page bodies. Each page is
    ASCII-clamped to PAGE_CHARS so the calc side never sees a page
    that won't fit a Str."""
    prompt, math = _parse_pair(text)
    print("[%s] llm: prompt=%r math=%r" % (_now(), prompt[:80], math[:80]), flush=True)
    with _LLM_INFLIGHT:
        try:
            pages = _call_ollama(prompt, math)
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
            print("[%s] llm error: %s" % (_now(), e), flush=True)
            pages = ["err: " + str(e)[:PAGE_CHARS - 5]]
    pages = [_ascii_clamp(p, PAGE_CHARS) for p in pages[:MAX_PAGES]]
    if not pages:
        pages = [""]
    print("[%s] llm: %d pages, sizes=%s" % (
        _now(), len(pages), [len(p) for p in pages]), flush=True)
    header = ("pages:" + str(len(pages)) + "\n").encode("ascii")
    body = b"\x00".join(p.encode("ascii", errors="replace") for p in pages)
    return header + body


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
                elif _llm_mode and text is not None:
                    sock = self.request
                    peer_for_log = peer
                    payload = text

                    def _worker():
                        reply = _llm_reply_pages(payload)
                        try:
                            sock.sendall(struct.pack(">I", len(reply)) + reply)
                            print("[%s] -> %s len=%d %r" % (_now(), peer_for_log, len(reply), reply), flush=True)
                        except OSError as e:
                            print("[%s] llm reply to %s failed: %s" % (_now(), peer_for_log, e), flush=True)

                    threading.Thread(target=_worker, daemon=True).start()
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
    ap.add_argument("--llm", action="store_true",
                    help="auto-reply via Ollama (cloud or local) with structured "
                         "JSON output. Reads OLLAMA_URL/MODEL/API_KEY from env.")
    args = ap.parse_args(argv)
    if args.echo and args.llm:
        ap.error("--echo and --llm are mutually exclusive")
    global _echo_mode, _llm_mode
    _echo_mode = args.echo
    _llm_mode = args.llm
    with ReusingServer((args.host, args.port), FramedHandler) as srv:
        print("relay: listening on %s:%d" % (args.host, args.port), flush=True)
        if _echo_mode:
            print("relay: ECHO MODE -- every frame auto-replied 'echo: <text>'", flush=True)
        elif _llm_mode:
            print("relay: LLM MODE -- model=%s url=%s key=%s" % (
                OLLAMA_MODEL, OLLAMA_URL, "set" if OLLAMA_API_KEY else "unset"),
                flush=True)
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
