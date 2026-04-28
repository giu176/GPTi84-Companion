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

Direction model (post-2026-04-29):
  calc -> Pico   : on_var callback in listen_loop ships the AppVar body
                   over TCP.
  Pico -> calc   : when a desktop frame arrives, Pico immediately runs
                   transfer.send_var(APPVAR, b"CHATIN", body, 0x73). The
                   calc must be at the home screen (or equivalently in
                   a clean asm-exit handoff back to the home screen) for
                   the OS's idle silent-link service to receive it. The
                   AppVar lands in NVRAM; user re-runs CHAT to see the
                   reply.

Why PC-master push and not calc-master REQ: every variant of calc-as-
master receive we tried (_GetSmallPacket, _GetVariableData inside the
asm program) wedges the calc's keypad matrix post-recv. PC-master push
to a calc at the home screen completes cleanly with the keypad alive
afterwards. Two-step UX (re-run CHAT after each reply) is the price.
"""

import time

import machine

import net
import transfer


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


CHATIN_NAME = b"CHATIN\x00\x00"
APPVAR = 0x15

# 84+ silent receive accepts AppVars far larger than our ASCII chat
# bodies; cap conservatively so we don't flood the home screen render
# with multi-row payloads.
INMAX_BYTES = 64


def _frame_to_appvar_payload(frame):
    """Convert a desktop-supplied frame into the wire-format AppVar body
    the calc expects: [size_le16][bytes]. Truncates to INMAX_BYTES."""
    body = bytes(frame)[:INMAX_BYTES]
    return bytes([len(body) & 0xFF, (len(body) >> 8) & 0xFF]) + body


def _push_chatin(frame):
    """PC-master push of an inbound desktop frame to the calc as
    AppVar CHATIN. Calls transfer.send_var with the 84+ native machine
    ID. Returns True on success, False on any failure (logged)."""
    wire = _frame_to_appvar_payload(frame)
    print("bridge: pushing CHATIN to calc (", len(wire), "wire bytes,",
          len(frame), "raw,", repr(frame[:INMAX_BYTES]), ")")
    try:
        ok = transfer.send_var(APPVAR, CHATIN_NAME, wire,
                               calc_machine=0x73, quiet=True)
    except Exception as e:
        print("bridge: send_var raised:", e)
        return False
    if not ok:
        print("bridge: send_var returned False (calc not at home screen?)")
    return ok


def _make_on_var(sock_holder):
    """Build an on_var callback that ships calc-initiated AppVar bodies
    over the socket. Drops the AppVar size prefix."""

    def on_var(type_id, name8, hdr, data):
        payload = data
        if type_id in (0x05, 0x06, 0x15) and len(data) >= 2:
            declared = data[0] | (data[1] << 8)
            if declared == len(data) - 2:
                payload = data[2:]
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
            # calc as CHATIN. send_var blocks on the wire while the
            # handshake completes; it's fine to do this synchronously
            # because calc-side traffic is paused (we just returned
            # from listen_loop with no calc activity).
            while True:
                inbound = reader_holder[0].poll()
                if inbound is None:
                    break
                _flash()
                _push_chatin(inbound)
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
