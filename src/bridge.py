"""Calc <-> Pico <-> desktop bridge, supervised.

Owns the lifecycle: wifi connect, socket connect, listen_loop. Catches
network failures and reconnects with exponential backoff. LED on the
Pico W reflects state so the unit is observable when sealed.

States (onboard LED on machine.Pin("LED")):
  off            : pre-init / fatal
  solid          : wifi connecting
  slow blink 1Hz : wifi up, socket down
  fast blink 4Hz : socket up, idle (waiting on calc)
  brief flash    : packet relayed (visual ping)

Blink is cooperative: ticked between DBUS packets. A long DBUS transfer
freezes the LED, which is informative -- the thing is busy on the wire.

Direction model (Str1=text + Str2=math + Str3..Str0=paginated reply):
  calc -> Pico   : asm program _SendVarCmds Str1 (text/prompt) and Str2
                   (math/equation) to us back-to-back. on_var sees each
                   String var (type 0x04, name [0xAA, slot, 0...]),
                   buffers by slot, and emits ONE combined frame over
                   TCP once both halves arrive (or a short pairing
                   timeout elapses with only one). Str1 decodes in 'text'
                   mode (no implicit-mult between letters); Str2 decodes
                   in 'math' mode (full implicit-mult, 2X -> 2*X).
  Pico -> calc   : the desktop reply is a paginated body shaped:
                       pages:N\n<page1>\x00<page2>\x00...<pageN>
                   We push each page as a separate Str (page 1 -> Str3,
                   page 2 -> Str4, ..., page 8 -> Str0), then push the
                   page count N as real var N. The BASIC deck pre-sets
                   N=0 and busy-waits on N>0 to detect reply-ready, then
                   runs an arrow-key pager. Calc must be at the home
                   screen between pushes for the OS's idle silent-link
                   receive to accept each one; the asm exits to home
                   immediately so the deck is parked there.

User UX: a TI-BASIC "deck" program owns the GUI -- it sets up Str1 and
Str2, zeroes N, calls Asm(prgmCHAT), waits for N>0, then pages through
Str3..Str(2+min(N,7))[+Str0 for page 8] under arrow-key control. The
asm stays a one-shot dumb pipe: send Str1, send Str2, exit.

Combined frame format (calc -> desktop): two lines, newline-separated.
  prompt:<text from Str1>\n
  math:<text from Str2>\n
Either line's value may be empty (when that slot was an empty Str).

Reply frame format (desktop -> calc): one header line then NUL-joined
page bodies.
  pages:N\n<page1>\x00<page2>\x00...<pageN>
N is 1..8. Each page body is ASCII, already clamped by the relay to
PAGE_CHARS chars (the screen-fittable budget).

Why PC-master push and not calc-master REQ: every variant of calc-as-
master receive we tried (_GetSmallPacket, _GetVariableData inside the
asm program) wedges the calc's keypad matrix post-recv. PC-master push
to a calc at the home screen completes cleanly. Two-step UX (run the
deck, wait for it to render Str0) is the price.
"""

import time

import machine

import net
import tokens
import transfer
from vartypes import (
    T_REAL, T_STRING, encode_real, real_name, str_name,
)


LED = machine.Pin("LED", machine.Pin.OUT)

ST_WIFI_CONNECTING = 0
ST_SOCKET_DOWN = 1
ST_SOCKET_UP = 2

_state = ST_WIFI_CONNECTING
_last_toggle_ms = 0
_led_on = False


def _set_state(s):
    global _state
    _state = s
    if s == ST_WIFI_CONNECTING:
        LED.on()


def _tick_led():
    """Update the LED based on current state. Call frequently from idle paths."""
    global _last_toggle_ms, _led_on
    now = time.ticks_ms()
    if _state == ST_WIFI_CONNECTING:
        return
    period = 500 if _state == ST_SOCKET_DOWN else 125
    if time.ticks_diff(now, _last_toggle_ms) >= period:
        _led_on = not _led_on
        LED.value(_led_on)
        _last_toggle_ms = now


def _flash():
    """Brief visible blip to mark a relayed packet."""
    LED.on()
    time.sleep_ms(40)
    LED.off()


def _connect_socket():
    backoff = 1
    while True:
        try:
            return net.open_socket()
        except OSError as e:
            print("bridge: socket connect failed:", e, "-- retrying in", backoff, "s")
            t_end = time.ticks_add(time.ticks_ms(), backoff * 1000)
            while time.ticks_diff(t_end, time.ticks_ms()) > 0:
                _tick_led()
                time.sleep_ms(50)
            backoff = min(backoff * 2, 30)


def _wifi_with_retry():
    backoff = 1
    while True:
        try:
            _set_state(ST_WIFI_CONNECTING)
            net.connect_wifi()
            return
        except OSError as e:
            print("bridge: wifi connect failed:", e, "-- retrying in", backoff, "s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)


STR_SLOT_TEXT = 0x00  # Str1 sub-byte (user-visible 1, table index 0) -- prose
STR_SLOT_MATH = 0x01  # Str2 sub-byte                                 -- equation

# Page-routing slots, in order: page 1 -> Str3, ..., page 8 -> Str0.
# Matches str_name() output (a name field of [0xAA, slot, 0,0,0,0,0,0])
# so the deck can address them as Str(2+P) for P=1..7 and Str0 for P=8.
PAGE_STR_NAMES = [
    str_name(3),  # page 1
    str_name(4),  # page 2
    str_name(5),  # page 3
    str_name(6),  # page 4
    str_name(7),  # page 5
    str_name(8),  # page 6
    str_name(9),  # page 7
    str_name(0),  # page 8 (Str0 is index 9 internally)
]
MAX_PAGES = len(PAGE_STR_NAMES)

# Real var the deck reads to learn how many pages arrived. Deck pre-sets
# 0->N before calling CHAT, then `Repeat N>0` until we push the count.
PAGECOUNT_NAME = real_name("N")

# How long to wait for the second half of a Str1/Str2 pair before
# flushing what we have. The asm sends Str1 and Str2 back-to-back, but
# each _SendVarCmd carries its own DBUS handshake; observed gap between
# Str1's last ACK and Str2's first byte is variable and crossed 500ms
# in real chats, splitting a real pair into two half-pairs. 2500ms is
# comfortably wider than any clean send and only adds latency to the
# single-slot path (deck only populated one of Str1/Str2).
PAIR_TIMEOUT_MS = 2500

# How long to wait after listen_loop returns before pushing Str0 back.
# The calc OS needs wallclock time to unwind asm + redraw + rearm its
# idle silent-link receive. Without this, the inbound RTS arrives before
# the calc is listening and gets no ACK. Empirical floor (84+ at this
# OS rev) lives between 375ms (fails) and 500ms (3/3 success); 600ms
# gives a small safety margin without making the round-trip feel laggy.
SETTLE_MS = 600

# Calc Strings round-trip cleanly at small sizes; cap so a long LLM
# reply doesn't blow past silent-link receive limits or wrap the home
# screen into illegible scroll.
INMAX_CHARS = 128


def _ascii_to_str_payload(text):
    """ASCII -> wire-format String var body: [size_le16][token_bytes...].
    Drops chars the TI charset doesn't have a phase-1 mapping for."""
    text = text[:INMAX_CHARS]
    body = tokens.ascii_to_tokens_lossy(text, drop_unknown=True)
    return bytes([len(body) & 0xFF, (len(body) >> 8) & 0xFF]) + body


def _bytes_to_ascii(data):
    """Coerce bytes-like to printable-ASCII str without relying on
    decode(errors=...) -- MicroPython's decode() doesn't accept kwargs."""
    return "".join(chr(b) if 0x20 <= b < 0x7F else "?" for b in bytes(data))


def _parse_pages_frame(frame):
    """Return list[str] of page bodies parsed from a desktop reply frame.

    Frame shape:
        pages:N\n<page1>\x00<page2>\x00...<pageN>
    Tolerates a missing header (legacy single-string replies) by
    returning a one-element list."""
    data = bytes(frame)
    if data.startswith(b"pages:"):
        nl = data.find(b"\n")
        if nl == -1:
            return [_bytes_to_ascii(data)]
        try:
            n = int(data[6:nl])
        except ValueError:
            n = 0
        body = data[nl + 1:]
        # Always split on NUL even if N is wrong -- the wire is the
        # source of truth for how many pages we actually got.
        chunks = body.split(b"\x00") if body else []
        pages = [_bytes_to_ascii(c) for c in chunks]
        if n and len(pages) != n:
            print("bridge: page-count mismatch: header N=", n,
                  "but parsed", len(pages), "chunks")
        return pages or [""]
    # Legacy / non-paginated reply: treat as one page.
    return [_bytes_to_ascii(data)]


def _push_one_str(name8, text, label):
    """PC-master push of a single Str to the calc. Returns True on success."""
    wire = _ascii_to_str_payload(text)
    print("bridge: pushing", label, "to calc (",
          len(wire), "wire bytes,", len(text), "chars,",
          repr(text[:INMAX_CHARS]), ")")
    try:
        ok = transfer.send_var(T_STRING, name8, wire,
                               calc_machine=0x73, quiet=True)
    except Exception as e:
        print("bridge: send_var raised:", e)
        return False
    if not ok:
        print("bridge:", label, "send_var returned False "
              "(calc not at home screen?)")
    return ok


def _push_pagecount(n):
    """PC-master push of real var N=<page count>. Deck busy-waits on
    N>0 to know the paginated reply is ready. Pushed AFTER all pages
    so partial state is never observable."""
    try:
        ok = transfer.send_var(T_REAL, PAGECOUNT_NAME, encode_real(n),
                               calc_machine=0x73, quiet=True)
    except Exception as e:
        print("bridge: pagecount send_var raised:", e)
        return False
    if not ok:
        print("bridge: pagecount send_var returned False")
    return ok


def _push_paginated_reply(frame):
    """Parse a desktop reply frame and push its pages to Str3..Str0,
    then signal completion by pushing the page count to real var N.

    Each push needs SETTLE_MS of wallclock between it and the previous
    OS-level redraw event (asm unwind, prior push acceptance) so the
    OS idle silent-link receive is rearmed. Returns True iff every
    page AND the count made it across."""
    pages = _parse_pages_frame(frame)
    if not pages:
        print("bridge: empty pages list, nothing to push")
        return False
    pages = pages[:MAX_PAGES]
    n = len(pages)
    print("bridge: pushing", n, "page(s) to calc")
    for i, page in enumerate(pages):
        time.sleep_ms(SETTLE_MS)
        label = "page %d/%d (Str slot)" % (i + 1, n)
        if not _push_one_str(PAGE_STR_NAMES[i], page, label):
            print("bridge: aborting paginated push at page", i + 1)
            return False
    time.sleep_ms(SETTLE_MS)
    print("bridge: all pages pushed; setting N=", n)
    if not _push_pagecount(n):
        return False
    return True


def _emit_pair(sock_holder, prompt_text, math_text):
    """Build the combined frame and ship it. Either field may be ''."""
    body = "prompt:" + prompt_text + "\nmath:" + math_text + "\n"
    print("bridge: emitting pair (prompt=", repr(prompt_text[:64]),
          "math=", repr(math_text[:64]), ")")
    if sock_holder[0] is None:
        print("bridge: socket down, dropping pair")
        return
    try:
        net.send_framed(sock_holder[0], body.encode("ascii"))
        _flash()
    except OSError as e:
        print("bridge: send_framed failed:", e, "-- dropping socket")
        try:
            sock_holder[0].close()
        except Exception:
            pass
        sock_holder[0] = None
        raise


def _flush_pair(sock_holder, pair):
    """Emit whatever's buffered (one or both halves) and clear state."""
    prompt_text = pair["prompt"] if pair["prompt"] is not None else ""
    math_text = pair["math"] if pair["math"] is not None else ""
    pair["prompt"] = None
    pair["math"] = None
    pair["first_arrival_ms"] = None
    _emit_pair(sock_holder, prompt_text, math_text)


def _make_on_var(sock_holder, pair):
    """Build an on_var callback. Strs go into the pair buffer (Str1=text
    in 'text' mode, Str2=math in 'math' mode); other var types are
    relayed as-is for compatibility with non-chat callers."""

    # Types whose payload starts with a 2-byte size word: Program, Locked
    # Program, AppVar, String. _SendVarCmd wraps the raw data in a count
    # so the calc-side parser knows where the body ends.
    SIZE_PREFIXED = (0x04, 0x05, 0x06, 0x15)

    def _strip_size_prefix(type_id, data):
        if type_id in SIZE_PREFIXED and len(data) >= 2:
            declared = data[0] | (data[1] << 8)
            if declared == len(data) - 2:
                return data[2:]
        return data

    def _relay_raw(payload):
        if sock_holder[0] is None:
            print("bridge: socket down, dropping outbound frame")
            return
        try:
            net.send_framed(sock_holder[0], payload)
            _flash()
        except OSError as e:
            print("bridge: send_framed failed:", e, "-- dropping socket")
            try:
                sock_holder[0].close()
            except Exception:
                pass
            sock_holder[0] = None
            raise

    def on_var(type_id, name8, hdr, data):
        payload = _strip_size_prefix(type_id, data)
        stripped_name = bytes(name8).rstrip(b"\x00")

        if type_id == 0x04 and len(name8) >= 2 and name8[0] == 0xAA:
            slot = name8[1]
            if slot == STR_SLOT_TEXT:
                text = tokens.tokens_to_ascii(payload, mode="text")
                print("bridge: on_var Str1 (text) len=", len(text),
                      "->", repr(text[:64]))
                pair["prompt"] = text
                if pair["first_arrival_ms"] is None:
                    pair["first_arrival_ms"] = time.ticks_ms()
                if pair["math"] is not None:
                    _flush_pair(sock_holder, pair)
                return
            if slot == STR_SLOT_MATH:
                text = tokens.tokens_to_ascii(payload, mode="math")
                print("bridge: on_var Str2 (math) len=", len(text),
                      "->", repr(text[:64]))
                pair["math"] = text
                if pair["first_arrival_ms"] is None:
                    pair["first_arrival_ms"] = time.ticks_ms()
                if pair["prompt"] is not None:
                    _flush_pair(sock_holder, pair)
                return
            # Other Str slots (Str3..Str9, Str0): treat as text-mode for
            # diagnostic visibility but ship as a raw frame, not paired.
            text = tokens.tokens_to_ascii(payload, mode="text")
            print("bridge: on_var unpaired Str slot=", slot,
                  "len=", len(text), "->", repr(text[:64]))
            _relay_raw(text.encode("ascii"))
            return

        # Non-Str vars: relay as raw bytes. Keeps the bridge useful for
        # anything that isn't part of the chat deck.
        print("bridge: on_var type=", hex(type_id), "name=", stripped_name,
              "len=", len(payload), "-> relay")
        _relay_raw(payload)

    return on_var


def _maybe_flush_stale_pair(sock_holder, pair):
    """If only one half of a pair has been sitting for longer than
    PAIR_TIMEOUT_MS, flush it as a half-pair. Called from the supervisor
    loop between listen_loop iterations."""
    if pair["first_arrival_ms"] is None:
        return
    if pair["prompt"] is not None and pair["math"] is not None:
        # Both present -- shouldn't happen (on_var flushes immediately)
        # but guard anyway.
        _flush_pair(sock_holder, pair)
        return
    age = time.ticks_diff(time.ticks_ms(), pair["first_arrival_ms"])
    if age >= PAIR_TIMEOUT_MS:
        print("bridge: pair timeout (", age, "ms) -- flushing half-pair")
        _flush_pair(sock_holder, pair)


def run(name=None, expected_type=None):
    """Top-level supervisor. Returns only on KeyboardInterrupt.

    `name` and `expected_type` are accepted for backwards compat with
    the pre-shipping signature but are not used as listen_loop filters
    -- the on_var path always relays whatever the calc sends.
    """
    print("bridge: run() starting -- PC-master push (option A)")
    _wifi_with_retry()

    sock_holder = [None]
    reader_holder = [None]
    pair = {"prompt": None, "math": None, "first_arrival_ms": None}
    on_var = _make_on_var(sock_holder, pair)

    while True:
        try:
            if sock_holder[0] is None:
                _set_state(ST_SOCKET_DOWN)
                sock_holder[0] = _connect_socket()
                reader_holder[0] = net.FrameReader(sock_holder[0])
                _set_state(ST_SOCKET_UP)
                print("bridge: listen_loop running")
            # Service calc-initiated traffic. Short timeout so we get
            # back to the inbound-frame poll regularly.
            transfer.listen_loop(on_var=on_var, timeout_ms=500)
            _tick_led()
            # Flush a half-pair if one slot arrived but the second never
            # came (deck only populated Str1 or Str2, asm only sent one).
            _maybe_flush_stale_pair(sock_holder, pair)
            # Drain any inbound desktop frames and push each to the
            # calc as Str0. send_var blocks on the wire while the
            # handshake completes; it's fine to do this synchronously
            # because calc-side traffic is paused (we just returned
            # from listen_loop with no calc activity).
            while True:
                inbound = reader_holder[0].poll()
                if inbound is None:
                    break
                _flash()
                # _push_paginated_reply handles per-push settle timing
                # internally (one SETTLE_MS gap before each Str + N).
                _push_paginated_reply(inbound)
        except KeyboardInterrupt:
            print("bridge: interrupted")
            try:
                if sock_holder[0]:
                    sock_holder[0].close()
            except Exception:
                pass
            LED.off()
            return
        except OSError as e:
            print("bridge: OSError in supervisor:", e)
            try:
                if sock_holder[0]:
                    sock_holder[0].close()
            except Exception:
                pass
            sock_holder[0] = None
            reader_holder[0] = None
            import network
            if not network.WLAN(network.STA_IF).isconnected():
                _wifi_with_retry()
