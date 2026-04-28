"""Calc -> Pico -> desktop bridge, supervised.

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
INMAX_BYTES = 16  # match CHAT.z80's INMAX so the calc can render it whole


def _push_chatin(payload):
    """PC-master push: deliver `payload` as AppVar CHATIN to the calc.
    Truncates to INMAX_BYTES. Returns True on success.

    The B1 plan: calc enters _GetKey after sending CHATMSG. _GetKey
    blocks but lets OS interrupts run, including the silent-link RTS
    handler. When this push lands, the OS writes CHATIN to NVRAM and
    _GetKey returns with kClear (OS-takeover signal). The asm then
    checks NVRAM for CHATIN and proceeds."""
    body = bytes(payload)[:INMAX_BYTES]
    # Wire format for AppVar body: [size_le16][bytes].
    framed = bytes([len(body) & 0xFF, (len(body) >> 8) & 0xFF]) + body
    print("bridge: -> calc CHATIN len=", len(body), "ascii=", repr(body))
    return transfer.send_var(APPVAR, CHATIN_NAME, framed,
                             calc_machine=0x73, quiet=True)


def _make_on_var(sock_holder):
    """Closure capturing a 1-element list so we can null the socket out
    on send failure and have the supervisor reconnect."""
    def on_var(type_id, name8, hdr, data):
        # AppVar (0x15) and Program (0x05/0x06) bodies are [size_le16][bytes];
        # strip so the relay sees the caller payload.
        payload = data
        if type_id in (0x05, 0x06, 0x15) and len(data) >= 2:
            declared = data[0] | (data[1] << 8)
            if declared == len(data) - 2:
                payload = data[2:]
        stripped = bytes(name8).rstrip(b"\x00")
        print("bridge: type=", hex(type_id), "name=", stripped,
              "len=", len(payload), "-> relay")
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
    """Top-level supervisor. Returns only on KeyboardInterrupt."""
    print("bridge: run(name=", repr(name), "type=",
          hex(expected_type) if expected_type is not None else None, ")")
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
            # listen_loop blocks until traffic or timeout; on send failure
            # on_var raises and we land in the except below, drop the
            # socket, reconnect.
            transfer.listen_loop(name=None, expected_type=None,
                                 on_var=on_var, timeout_ms=1000)
            # Idle return: tick LED, drain inbound frames. Each frame
            # is pushed to the calc as CHATIN immediately (PC-master).
            # B1 architecture: calc is sitting in _GetKey waiting; OS
            # link service handles our RTS as an interrupt-driven event.
            _tick_led()
            while True:
                inbound = reader_holder[0].poll()
                if inbound is None:
                    break
                _flash()
                if not _push_chatin(inbound):
                    print("bridge: CHATIN push failed (calc not ready?)")
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
            # Socket died mid-relay or wifi flapped. Drop and rebuild.
            print("bridge: OSError in supervisor:", e)
            try:
                if sock_holder[0]:
                    sock_holder[0].close()
            except Exception:
                pass
            sock_holder[0] = None
            reader_holder[0] = None
            # If wifi itself dropped, re-associate before retrying socket.
            import network
            if not network.WLAN(network.STA_IF).isconnected():
                _wifi_with_retry()
