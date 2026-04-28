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

Direction model (post-2026-04-28 Str1/Str2 pivot):
  calc -> Pico   : asm program _SendVarCmds Str1 to us. on_var callback
                   sees a String var (type 0x04, name [0xAA, tStr1, ...]),
                   translates the token stream to ASCII, ships the text
                   over TCP.
  Pico -> calc   : when a desktop frame arrives, translate ASCII back to
                   tokens and PC-master push as Str2. Calc must be at
                   the home screen for the OS's idle silent-link receive
                   to accept it; the asm program exits immediately after
                   _SendVarCmd so the calc is back at the home screen
                   by the time the desktop reply round-trips.

User UX: at home screen, "text"->Str1, run prgmCHAT, then Str2 ENTER
to see the reply.

Why PC-master push and not calc-master REQ: every variant of calc-as-
master receive we tried (_GetSmallPacket, _GetVariableData inside the
asm program) wedges the calc's keypad matrix post-recv. PC-master push
to a calc at the home screen completes cleanly. Two-step UX (run, then
Str2 to see reply) is the price.
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


STR2_NAME = str_name(2)

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


def _push_str2(frame):
    """PC-master push of an inbound desktop frame to the calc as Str2.
    Frame is treated as ASCII text. Returns True on success."""
    # Coerce bytes -> printable-ASCII str without relying on the
    # `errors=` kwarg (MicroPython's decode() doesn't accept it).
    text = "".join(chr(b) if 0x20 <= b < 0x7F else "?" for b in bytes(frame))
    wire = _ascii_to_str_payload(text)
    print("bridge: pushing Str2 to calc (", len(wire), "wire bytes,",
          len(text), "chars,", repr(text[:INMAX_CHARS]), ")")
    try:
        ok = transfer.send_var(T_STRING, STR2_NAME, wire,
                               calc_machine=0x73, quiet=True)
    except Exception as e:
        print("bridge: send_var raised:", e)
        return False
    if not ok:
        print("bridge: send_var returned False (calc not at home screen?)")
    return ok


def _make_on_var(sock_holder):
    """Build an on_var callback that ships calc-initiated var bodies over
    the socket. Strips the [size_le16] prefix on size-prefixed types and
    translates String token streams to ASCII before relaying."""

    # Types whose payload starts with a 2-byte size word: Program, Locked
    # Program, AppVar, String. _SendVarCmd wraps the raw data in a count
    # so the calc-side parser knows where the body ends.
    SIZE_PREFIXED = (0x04, 0x05, 0x06, 0x15)

    def on_var(type_id, name8, hdr, data):
        payload = data
        if type_id in SIZE_PREFIXED and len(data) >= 2:
            declared = data[0] | (data[1] << 8)
            if declared == len(data) - 2:
                payload = data[2:]
        if type_id == 0x04:
            # String var: translate token stream to ASCII for desktop.
            text = tokens.tokens_to_ascii(payload)
            payload = text.encode("ascii")
        stripped = bytes(name8).rstrip(b"\x00")
        print("bridge: on_var type=", hex(type_id), "name=", stripped,
              "len=", len(payload), "-> relay")
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

    return on_var


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
    on_var = _make_on_var(sock_holder)

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
            # Drain any inbound desktop frames and push each to the
            # calc as Str2. send_var blocks on the wire while the
            # handshake completes; it's fine to do this synchronously
            # because calc-side traffic is paused (we just returned
            # from listen_loop with no calc activity).
            while True:
                inbound = reader_holder[0].poll()
                if inbound is None:
                    break
                _flash()
                # Settle: the calc OS needs wallclock time to unwind the
                # asm program (CHAT.z80's `ret`) back to the home screen
                # and re-arm its idle silent-link receive. Without this,
                # the inbound RTS hits the calc before it's listening
                # and gets no ACK. 2s is comfortably above the floor we
                # measured; reduce only with hardware retesting.
                time.sleep_ms(2000)
                _push_str2(inbound)
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
