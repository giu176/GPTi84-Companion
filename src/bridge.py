"""Calculator <-> Pico <-> phone relay bridge, supervised.

Owns the lifecycle of the selected relay transport and raw Axe link loop.
Catches transport failures and reconnects with exponential backoff. LED on
the Pico reflects state so the unit is observable when sealed.

States (onboard LED on machine.Pin("LED")):
  off            : pre-init / fatal
  solid          : wifi connecting
  slow blink 1Hz : phone transport down
  fast blink 4Hz : phone transport up, idle (waiting on calc)
  brief flash    : packet relayed (visual ping)

Blink is cooperative: ticked between raw calculator packets. A long transfer
freezes the LED, which is informative -- the thing is busy on the wire.

Direction model (Axe raw frame + phone page frame):
  calc -> Pico   : Axe sends a raw frame containing one V2 command/prompt
                   payload unchanged to the phone.
  Pico -> calc   : phone reply is returned as one raw response frame whose
                   payload is the normal paginated body:
                       pages:N\n<page1>\x00<page2>\x00...<pageN>

Command frame format (calc -> phone): ASCII V2 body.
  LIST
  OPEN <chatId>
  SEND <chatId> <clientMessageId>\n<prompt>

Reply frame format (phone -> calc): one header line then NUL-joined
page bodies.
  pages:N\n<page1>\x00<page2>\x00...<pageN>
N is 1..8. Each page body is ASCII, already clamped by the relay to
PAGE_CHARS chars (the screen-fittable budget).

The old TI-BASIC/Str/N bridge is intentionally no longer the active runtime.
"""

import time

import machine

import raw_axe_protocol as raw_axe
import tokens
import transfer
from vartypes import (
    T_REAL, T_STRING, encode_real, real_name, str_name,
)


LED = machine.Pin("LED", machine.Pin.OUT)
LOG_PATH = "bridge.log"

ST_WIFI_CONNECTING = 0
ST_SOCKET_DOWN = 1
ST_SOCKET_UP = 2

_state = ST_WIFI_CONNECTING
_last_toggle_ms = 0
_led_on = False


def _log(*parts):
    text = " ".join(str(part) for part in parts)
    print(text)
    try:
        with open(LOG_PATH, "a") as handle:
            handle.write(text + "\n")
    except Exception:
        pass


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


def _connect_transport():
    backoff = 1
    while True:
        try:
            import relay_transport
            relay = relay_transport.open_transport()
            _log("bridge: transport opened")
            return relay
        except OSError as e:
            _log("bridge: relay unavailable:", e, "-- retrying in", backoff, "s")
            t_end = time.ticks_add(time.ticks_ms(), backoff * 1000)
            while time.ticks_diff(t_end, time.ticks_ms()) > 0:
                _tick_led()
                time.sleep_ms(50)
            backoff = min(backoff * 2, 30)


def _send_relay(relay, payload):
    """Send through a message transport, retaining old socket test support."""
    if hasattr(relay, "send"):
        relay.send(payload)
        return
    import net
    net.send_framed(relay, payload)


def _transport_ready(relay):
    """True when the relay can accept calculator-originated payloads."""
    return bool(getattr(relay, "connected", True))


def _wait_transport_ready(relay):
    """Hold off DBUS listening until the phone is actually connected.

    BLETransport can be advertising but not connected yet. Listening to the
    calculator in that state drops the one-shot prompt before the phone sees it.
    """
    last_log = time.ticks_ms()
    while not _transport_ready(relay):
        now = time.ticks_ms()
        if time.ticks_diff(now, last_log) >= 2000:
            _log("bridge: waiting for phone BLE connection")
            last_log = now
        _tick_led()
        time.sleep_ms(50)
    _log("bridge: phone BLE connected; settling before raw link listen")
    time.sleep_ms(1000)


def _safe_error(text):
    return "".join(ch if 0x20 <= ord(ch) < 0x7F else " "
                   for ch in str(text))[:128].encode("ascii")


def _wait_for_phone_response(relay, timeout_ms=30000):
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        inbound = relay.poll()
        if inbound is not None:
            _flash()
            _log("bridge: inbound phone frame len=", len(inbound))
            if _maybe_save_catalog(inbound):
                continue
            return bytes(inbound)
        _tick_led()
        time.sleep_ms(10)
    raise OSError("phone response timeout")


def _service_raw_axe_once(relay, read_byte=None, write_byte=None):
    """Handle at most one Axe raw frame. Returns True if one was serviced."""
    if read_byte is None:
        import wire
        read_byte = wire.recv_byte
    if write_byte is None:
        import wire
        write_byte = wire.send_byte
    frame = raw_axe.read_frame(read_byte, timeout_ms=250)
    if frame is None:
        return False
    frame_type, payload = frame
    if frame_type != raw_axe.REQUEST:
        raw_axe.write_frame(
            write_byte,
            raw_axe.ERROR,
            b"EXPECTED REQUEST",
            timeout_ms=1000,
        )
        return True
    _log("bridge: raw Axe request", repr(payload[:64]))
    try:
        _send_relay(relay, payload)
        response = _wait_for_phone_response(relay)
        if not raw_axe.write_frame(
            write_byte,
            raw_axe.RESPONSE,
            response,
            timeout_ms=1000,
        ):
            raise OSError("calculator response write failed")
        _log("bridge: raw Axe response sent len=", len(response))
    except Exception as error:
        _log("bridge: raw Axe request failed:", error)
        raw_axe.write_frame(
            write_byte,
            raw_axe.ERROR,
            _safe_error(error),
            timeout_ms=1000,
        )
    return True


STR_SLOT_TEXT = 0x00  # Str1 sub-byte (user-visible 1, table index 0) -- prose
STR_SLOT_MATH = 0x01  # Str2 sub-byte, diagnostic fallback only

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

    drop_unknown=False so the output length matches the input length
    exactly: chars without a TI-charset mapping become tSpace (0x29)
    instead of vanishing. The pager paints fixed-grid pages with
    sub(StrP, 1+(R-1)*16, 16) which assumes constant page length;
    silently dropping a single '?' would shorten the Str by one char
    and turn the last row's sub() into ERR:INVALID DIM."""
    text = text[:INMAX_CHARS]
    body = tokens.ascii_to_tokens_lossy(text, drop_unknown=False)
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
    _log("bridge: pushing", label, "to calc (",
          len(wire), "wire bytes,", len(text), "chars,",
          repr(text[:INMAX_CHARS]), ")")
    try:
        ok = transfer.send_var(T_STRING, name8, wire,
                               calc_machine=0x73, quiet=True)
    except Exception as e:
        _log("bridge: send_var raised:", e)
        return False
    if not ok:
        _log("bridge:", label, "send_var returned False "
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
        _log("bridge: pagecount send_var raised:", e)
        return False
    if not ok:
        _log("bridge: pagecount send_var returned False")
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
        _log("bridge: empty pages list, nothing to push")
        return False
    pages = pages[:MAX_PAGES]
    n = len(pages)
    _log("bridge: pushing", n, "page(s) to calc")
    for i, page in enumerate(pages):
        time.sleep_ms(SETTLE_MS)
        label = "page %d/%d (Str slot)" % (i + 1, n)
        if not _push_one_str(PAGE_STR_NAMES[i], page, label):
            _log("bridge: aborting paginated push at page", i + 1)
            return False
    time.sleep_ms(SETTLE_MS)
    _log("bridge: all pages pushed; setting N=", n)
    if not _push_pagecount(n):
        return False
    return True


def _maybe_save_catalog(frame):
    data = bytes(frame)
    if not data.startswith(b"catalog:"):
        return False
    nl = data.find(b"\n")
    if nl == -1:
        return True
    try:
        expected = int(data[8:nl])
    except ValueError:
        expected = -1
    body = data[nl + 1:]
    if expected >= 0 and len(body) != expected:
        _log("bridge: catalog length mismatch expected=", expected,
             "actual=", len(body))
    try:
        import pins_cache
        pins_cache.save(body.decode("utf-8"), path="pins.v1")
        _log("bridge: saved phone-master pinned catalog")
    except Exception as e:
        _log("bridge: failed to save catalog:", e)
    return True


def _emit_command(sock_holder, text):
    """Ship one calculator command/prompt frame to the phone."""
    _log("bridge: emitting command", repr(text[:64]))
    if sock_holder[0] is None:
        _log("bridge: socket down, dropping command")
        return
    try:
        _send_relay(sock_holder[0], text.encode("ascii"))
        _log("bridge: relay send ok")
        _flash()
    except OSError as e:
        _log("bridge: send_framed failed:", e, "-- dropping socket")
        try:
            sock_holder[0].close()
        except Exception:
            pass
        sock_holder[0] = None
        raise

def _make_on_var(sock_holder):
    """Build an on_var callback. Str1 is the V2 command/prompt frame;
    other var types are relayed as-is for diagnostic compatibility."""

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
            _log("bridge: socket down, dropping outbound frame")
            return
        try:
            _send_relay(sock_holder[0], payload)
            _log("bridge: raw relay send ok")
            _flash()
        except OSError as e:
            _log("bridge: send_framed failed:", e, "-- dropping socket")
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
                _log("bridge: on_var Str1 command len=", len(text),
                      "->", repr(text[:64]))
                _emit_command(sock_holder, text)
                return
            if slot == STR_SLOT_MATH:
                text = tokens.tokens_to_ascii(payload, mode="text")
                _log("bridge: ignoring legacy Str2 len=", len(text),
                      "->", repr(text[:64]))
                return
            # Other Str slots (Str3..Str9, Str0): treat as text-mode for
            # diagnostic visibility but ship as a raw frame, not paired.
            text = tokens.tokens_to_ascii(payload, mode="text")
            _log("bridge: on_var unpaired Str slot=", slot,
                  "len=", len(text), "->", repr(text[:64]))
            _relay_raw(text.encode("ascii"))
            return

        # Non-Str vars: relay as raw bytes. Keeps the bridge useful for
        # anything that isn't part of the chat deck.
        _log("bridge: on_var type=", hex(type_id), "name=", stripped_name,
              "len=", len(payload), "-> relay")
        _relay_raw(payload)

    return on_var

def run(name=None, expected_type=None):
    """Top-level supervisor. Returns only on KeyboardInterrupt.

    `name` and `expected_type` are accepted for backwards compat with
    the pre-shipping signature but are not used as listen_loop filters
    -- the on_var path always relays whatever the calc sends.
    """
    try:
        with open(LOG_PATH, "w") as handle:
            handle.write("")
    except Exception:
        pass
    _log("bridge: run() starting -- Axe raw-link command bridge")

    relay = None

    while True:
        try:
            if relay is None:
                _set_state(ST_SOCKET_DOWN)
                relay = _connect_transport()
                _wait_transport_ready(relay)
                _set_state(ST_SOCKET_UP)
                _log("bridge: raw Axe listen loop running")
            elif not _transport_ready(relay):
                _log("bridge: phone transport disconnected")
                try:
                    relay.close()
                except Exception:
                    pass
                relay = None
                continue
            _service_raw_axe_once(relay)
            _tick_led()
        except KeyboardInterrupt:
            _log("bridge: interrupted")
            try:
                if relay:
                    relay.close()
            except Exception:
                pass
            LED.off()
            return
        except OSError as e:
            _log("bridge: OSError in supervisor:", e)
            try:
                if relay:
                    relay.close()
            except Exception:
                pass
            relay = None
