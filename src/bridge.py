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

Direction model (post-2026-04-28):
  calc -> Pico   : on_var callback in listen_loop ships the AppVar body
                   over TCP (unchanged from the original v0).
  Pico -> calc   : 1-slot outbox holds the latest desktop-sourced frame.
                   When the calc issues a DBUS REQ for CHATIN, on_req
                   pops the outbox and serves it as the AppVar body.
                   If the outbox is empty, on_req returns None and the
                   Pico replies with SKIP (calc-side renders no-reply).

The PC-master push path that lived here pre-shipping (`_push_chatin`
via `transfer.send_var`) is gone. Calc-master REQ is the only inbound
direction now -- see project_calc_master_req_shipped.md.
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
INMAX_BYTES = 12   # _GetSmallPacket caps the calc-side recv at 14 bytes
                   # of body INCLUDING the 2-byte size prefix, so the
                   # ASCII payload limit is 12. Truncate before stashing
                   # so we don't lie to the calc about size.


def _frame_to_appvar_payload(frame):
    """Convert a desktop-supplied frame into the wire-format AppVar body
    the calc expects: [size_le16][bytes]. Truncates to INMAX_BYTES so the
    calc-side _GetSmallPacket doesn't ERR:LINK on oversize. Returns the
    bytes ready to pass to transfer._respond_to_req."""
    body = bytes(frame)[:INMAX_BYTES]
    return bytes([len(body) & 0xFF, (len(body) >> 8) & 0xFF]) + body


def _make_callbacks(sock_holder, outbox):
    """Build (on_var, on_req) pair sharing closures over the sock holder
    and the 1-slot outbox.

    on_var (calc -> desktop): strip the AppVar size prefix from the
    inbound body and ship it as a TCP frame. If the socket is down we
    drop the frame (calc-side already got the silent-link confirmation
    so its UX won't hang).

    on_req (calc -> Pico, Pico replies): if outbox has a frame, pop it
    and return as wire-format AppVar payload. Else return None so the
    Pico SKIPs the REQ (calc-side renders the no-reply state)."""

    def on_var(type_id, name8, hdr, data):
        # AppVar (0x15) and Program (0x05/0x06) bodies are
        # [size_le16][bytes]; strip the prefix so the relay sees the
        # caller payload.
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

    def on_req(type_id, name8):
        stripped = bytes(name8).rstrip(b"\x00")
        print("bridge: on_req type=", hex(type_id), "name=", stripped)
        if type_id != APPVAR or bytes(name8) != CHATIN_NAME:
            print("  -> not CHATIN, returning None (Pico will SKIP)")
            return None
        if outbox[0] is None:
            print("  -> outbox empty, returning None (Pico will SKIP)")
            return None
        frame = outbox[0]
        outbox[0] = None
        wire = _frame_to_appvar_payload(frame)
        print("  -> serving", len(wire), "wire bytes (",
              len(frame), "raw,", repr(frame[:INMAX_BYTES]), ")")
        _flash()
        return wire

    return on_var, on_req


def run(name=None, expected_type=None):
    """Top-level supervisor. Returns only on KeyboardInterrupt.

    `name` and `expected_type` are accepted for backwards compat with the
    pre-shipping signature but are no longer used as listen_loop filters
    -- the on_var path always relays whatever the calc sends, and on_req
    only matches AppVar CHATIN. They remain in the signature so existing
    Justfile recipes (`just chat-bridge ...`) keep working without edit.
    """
    print("bridge: run() starting -- calc-master REQ era")
    if name is not None or expected_type is not None:
        print("bridge: note: name/expected_type args are now informational")
    _wifi_with_retry()

    sock_holder = [None]
    reader_holder = [None]
    outbox = [None]
    on_var, on_req = _make_callbacks(sock_holder, outbox)

    while True:
        try:
            if sock_holder[0] is None:
                _set_state(ST_SOCKET_DOWN)
                sock_holder[0] = _connect_socket()
                reader_holder[0] = net.FrameReader(sock_holder[0])
                _set_state(ST_SOCKET_UP)
                print("bridge: listen_loop running")
            # listen_loop blocks until traffic or timeout. Short timeout
            # so we get back to the FrameReader poll regularly.
            transfer.listen_loop(on_var=on_var, on_req=on_req,
                                 timeout_ms=500)
            # Idle return: tick LED, drain inbound frames into the outbox.
            # Latest-frame-wins -- if the desktop pushes faster than the
            # calc REQs, only the most recent reply is kept.
            _tick_led()
            while True:
                inbound = reader_holder[0].poll()
                if inbound is None:
                    break
                _flash()
                if outbox[0] is not None:
                    print("bridge: outbox replaced (calc didn't REQ in time)")
                outbox[0] = inbound
                print("bridge: outbox <- ", len(inbound), "bytes:",
                      repr(inbound[:32]))
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
