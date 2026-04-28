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

Direction model (Str1=text + Str2=math + Str0=reply pivot):
  calc -> Pico   : asm program _SendVarCmds Str1 (text/prompt) and Str2
                   (math/equation) to us back-to-back. on_var sees each
                   String var (type 0x04, name [0xAA, slot, 0...]),
                   buffers by slot, and emits ONE combined frame over
                   TCP once both halves arrive (or a short pairing
                   timeout elapses with only one). Str1 decodes in 'text'
                   mode (no implicit-mult between letters); Str2 decodes
                   in 'math' mode (full implicit-mult, 2X -> 2*X).
  Pico -> calc   : when a desktop frame arrives, translate ASCII back to
                   tokens and PC-master push as Str0. Calc must be at
                   the home screen for the OS's idle silent-link receive
                   to accept it; the asm program exits immediately after
                   sending so the calc is back at the home screen by the
                   time the desktop reply round-trips.

User UX: a TI-BASIC "deck" program owns the GUI -- it sets up Str1 and
Str2, calls Asm(prgmCHAT), and reads Str0. The asm stays a one-shot
dumb pipe: send Str1, send Str2, exit.

Combined frame format: two lines, newline-separated.
  prompt:<text from Str1>\n
  math:<text from Str2>\n
Either line's value may be empty (when that slot was an empty Str).

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
from vartypes import T_STRING, str_name


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


STR0_NAME = str_name(0)
STR_SLOT_TEXT = 0x00  # Str1 sub-byte (user-visible 1, table index 0) -- prose
STR_SLOT_MATH = 0x01  # Str2 sub-byte                                 -- equation

# How long to wait for the second half of a Str1/Str2 pair before
# flushing what we have. The asm sends both back-to-back, so 500ms is
# generous; if the deck only populated one slot, the asm only sends
# that one and we flush as a half-pair.
PAIR_TIMEOUT_MS = 500

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


def _push_str0(frame):
    """PC-master push of an inbound desktop frame to the calc as Str0.
    Frame is treated as ASCII text. Returns True on success."""
    # Coerce bytes -> printable-ASCII str without relying on the
    # `errors=` kwarg (MicroPython's decode() doesn't accept it).
    text = "".join(chr(b) if 0x20 <= b < 0x7F else "?" for b in bytes(frame))
    wire = _ascii_to_str_payload(text)
    print("bridge: pushing Str0 to calc (", len(wire), "wire bytes,",
          len(text), "chars,", repr(text[:INMAX_CHARS]), ")")
    try:
        ok = transfer.send_var(T_STRING, STR0_NAME, wire,
                               calc_machine=0x73, quiet=True)
    except Exception as e:
        print("bridge: send_var raised:", e)
        return False
    if not ok:
        print("bridge: send_var returned False (calc not at home screen?)")
    return ok


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
                time.sleep_ms(SETTLE_MS)
                _push_str0(inbound)
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
