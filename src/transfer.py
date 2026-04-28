"""High-level DBUS variable transfers: REQ/VAR/RTS handshakes + delete.

Convenience wrappers for the variables we actually push during bring-up:
L1 (real list), single A..Z reals, and program payloads (.8Xp body).
"""

import time
import wire
from wire import idle, read
from packet import (
    ACK, CTS, DATA, DEL, EOT, RDY, REQ, RTS, SKIP, VAR,
    pc_id_for, packet_bytes, send_packet, recv_packet, hex_bytes,
)
from vartypes import (
    T_REAL, T_LIST, T_PROG, T_PROG_LOCKED,
    list_name_82, real_name, prog_name, make_var_header,
    encode_real, encode_real_list,
)


def recv_var(timeout_ms=10000):
    """Run the full silent-link receive flow for one variable.
    Returns (header_bytes, data_bytes) or None on error."""
    idle()
    print("waiting for RTS or VAR from calc...")
    p = recv_packet(timeout_ms)
    if p is None:
        print("no packet"); return None
    machine, cmd, hdr = p
    pc_machine = pc_id_for(machine)
    print("pkt1: machine=", hex(machine), "cmd=", hex(cmd), "hdr=", bytes(hdr))
    print("we will reply as", hex(pc_machine))
    if cmd not in (RTS, VAR):
        print("unexpected cmd"); return None

    print("sending ACK")
    if not send_packet(ACK, machine=pc_machine): print("ACK send failed"); return None

    print("sending CTS")
    if not send_packet(CTS, machine=pc_machine): print("CTS send failed"); return None

    p = recv_packet(timeout_ms)
    if p is None: print("no ACK after CTS"); return None
    _, cmd2, _ = p
    print("pkt2: cmd=", hex(cmd2))
    if cmd2 != ACK: print("expected ACK, got", hex(cmd2)); return None

    p = recv_packet(timeout_ms)
    if p is None: print("no DATA"); return None
    _, cmd3, data = p
    print("pkt3 (DATA): cmd=", hex(cmd3), "len=", len(data))
    if cmd3 != DATA: print("expected DATA, got", hex(cmd3)); return None

    print("sending ACK for DATA")
    if not send_packet(ACK, machine=pc_machine): print("final ACK failed"); return None

    # TI-82 protocol ends here (no EOT). TI-83/83+/84+ send an EOT next.
    if machine == 0x82:
        print("done (TI-82 protocol, no EOT expected)")
        return (bytes(hdr), bytes(data))

    p = recv_packet(timeout_ms)
    if p is None: print("no EOT"); return None
    _, cmd4, _ = p
    print("pkt4: cmd=", hex(cmd4))
    if cmd4 != EOT: print("expected EOT, got", hex(cmd4))

    return (bytes(hdr), bytes(data))


def _finish_recv_after_first_pkt(machine, cmd, hdr, timeout_ms=10000):
    """Continue the silent-link receive flow after the first packet (RTS or
    VAR) has already been read. Shared between `recv_var` (one-shot) and
    `listen_loop` (long-lived). Returns (header_bytes, data_bytes) or None."""
    pc_machine = pc_id_for(machine)
    if cmd not in (RTS, VAR):
        print("unexpected cmd", hex(cmd))
        return None

    if not send_packet(ACK, machine=pc_machine):
        print("ACK send failed"); return None
    if not send_packet(CTS, machine=pc_machine):
        print("CTS send failed"); return None

    p = recv_packet(timeout_ms)
    if p is None: print("no ACK after CTS"); return None
    _, cmd2, _ = p
    if cmd2 != ACK:
        print("expected ACK, got", hex(cmd2)); return None

    p = recv_packet(timeout_ms)
    if p is None: print("no DATA"); return None
    _, cmd3, data = p
    if cmd3 != DATA:
        print("expected DATA, got", hex(cmd3)); return None

    if not send_packet(ACK, machine=pc_machine):
        print("final ACK failed"); return None

    # Drain optional EOT. Real TI-82 protocol omits it; an 84+ in compat
    # mode (machine=0x82 wire ID) sends one anyway. Try briefly either way
    # so the next loop iteration doesn't see it as garbage.
    p = recv_packet(500)
    if p is not None:
        _, cmd4, _ = p
        if cmd4 != EOT:
            print("trailing pkt was", hex(cmd4), "not EOT")
    return (bytes(hdr), bytes(data))


def _respond_to_req(machine, hdr, on_req):
    """Pico-as-DBUS-slave response to a calc-initiated REQ.

    REQ packet's body is the var header the calc wants. We invoke on_req
    with (type_id, name8); it returns either bytes (the variable's wire
    payload) or None ("variable doesn't exist"). On a hit we emit
    ACK -> VAR -> wait for ACK -> wait for CTS -> ACK -> DATA -> wait for
    final ACK. On a miss we emit SKIP/EXIT and bail.

    Returns True on a clean exchange, False on any wire error."""
    pc_machine = pc_id_for(machine)
    if len(hdr) < 11:
        print("respond: short REQ header"); return False
    req_type = hdr[2]
    req_name = bytes(hdr[3:11])
    print("respond: REQ type=", hex(req_type), "name=", req_name)

    payload = on_req(req_type, req_name)
    if payload is None:
        print("respond: no such var; SKIP/EXIT")
        # Per packet.html, SKIP (0x36) is the "skip/exit" rejection.
        send_packet(SKIP, machine=pc_machine)
        return True

    # Build VAR header echoing back the type/name with real size.
    proto = 82 if machine == 0x82 else 83
    var_hdr = make_var_header(len(payload), req_type, req_name, proto=proto)

    if not send_packet(ACK, machine=pc_machine):
        print("respond: ACK after REQ failed"); return False
    time.sleep_ms(20)
    if not send_packet(VAR, var_hdr, machine=pc_machine):
        print("respond: VAR send failed"); return False

    p = recv_packet(5000)
    if p is None: print("respond: no ACK after VAR"); return False
    _, cmd, _ = p
    if cmd != ACK:
        print("respond: expected ACK after VAR, got", hex(cmd)); return False

    p = recv_packet(5000)
    if p is None: print("respond: no CTS"); return False
    _, cmd, _ = p
    if cmd == SKIP:
        print("respond: calc rejected with SKIP after VAR"); return True
    if cmd != CTS:
        print("respond: expected CTS, got", hex(cmd)); return False

    if not send_packet(ACK, machine=pc_machine):
        print("respond: ACK after CTS failed"); return False
    time.sleep_ms(20)

    if not send_packet(DATA, payload, machine=pc_machine):
        print("respond: DATA send failed"); return False

    p = recv_packet(5000)
    if p is None: print("respond: no ACK after DATA"); return False
    _, cmd, _ = p
    if cmd != ACK:
        print("respond: expected ACK after DATA, got", hex(cmd)); return False

    # TI-82 protocol ends here; native 0x73 expects EOT from us.
    if machine != 0x82:
        if not send_packet(EOT, machine=pc_machine):
            print("respond: EOT failed"); return False
    print("respond: done")
    return True


def listen_loop(name=None, expected_type=None, on_var=None, on_req=None,
                timeout_ms=0):
    """Sit on the wire and accept calc-initiated transfers in a loop.

    For RTS/VAR (calc sending us a variable), calls on_var(type_id, name8,
    header, data) if provided; otherwise prints a hex summary.

    For REQ (calc requesting a variable from us), calls on_req(type_id,
    name8) which must return either bytes (the wire-format payload, e.g.
    [size_le16][bytes] for AppVars) or None to reject with SKIP/EXIT.

    Filters by `name` (8-byte field, or shorter str -- zero-padded) and
    `expected_type` when set; the filter applies to BOTH on_var and on_req.
    Handles RDY (0x68) by ACKing.

    timeout_ms=0 means wait forever for the first packet; set nonzero to
    return after that long with no traffic."""
    if isinstance(name, str):
        name8 = name.encode("ascii") + b'\x00' * (8 - len(name))
    elif name is None:
        name8 = None
    else:
        name8 = bytes(name)
        if len(name8) != 8:
            raise ValueError("name must be 8 bytes or a <=8-char str")

    print("listen_loop: filter name=", name8, "type=",
          hex(expected_type) if expected_type is not None else None)
    while True:
        idle()
        p = recv_packet(timeout_ms if timeout_ms else 60000)
        if p is None:
            if timeout_ms:
                print("listen_loop: no traffic, returning")
                return
            continue
        machine, cmd, body = p
        pc_machine = pc_id_for(machine)

        if cmd == RDY:
            # Calc is asking "are you there?" before sending. ACK keeps it talking.
            print("RDY from", hex(machine), "-> ACK")
            send_packet(ACK, machine=pc_machine)
            continue

        if cmd == REQ and on_req is not None:
            print("incoming REQ: machine=", hex(machine), "hdr_len=", len(body))
            # Apply name/type filter same as we do for RTS/VAR.
            if len(body) >= 11:
                got_type = body[2]
                got_name = bytes(body[3:11])
                if expected_type is not None and got_type != expected_type:
                    print("listen: REQ type", hex(got_type), "!= expected; SKIP")
                    send_packet(SKIP, machine=pc_machine)
                    continue
                if name8 is not None and got_name != name8:
                    print("listen: REQ name", got_name, "!= expected; SKIP")
                    send_packet(SKIP, machine=pc_machine)
                    continue
            _respond_to_req(machine, body, on_req)
            continue

        if cmd not in (RTS, VAR):
            # Unknown opener. ACK so the calc doesn't hang, then loop.
            print("listen: unexpected first cmd", hex(cmd), "-> ACK and continue")
            send_packet(ACK, machine=pc_machine)
            continue

        print("incoming: machine=", hex(machine), "cmd=", hex(cmd),
              "hdr_len=", len(body))
        result = _finish_recv_after_first_pkt(machine, cmd, body)
        if result is None:
            continue
        hdr, data = result

        # 83+/84+ var header: [size_lo, size_hi, type, name(8), ver, flags]
        # TI-82 form: [size_lo, size_hi, type, name(8)]
        if len(hdr) < 11:
            print("listen: short header, skipping"); continue
        got_type = hdr[2]
        got_name = bytes(hdr[3:11])

        if expected_type is not None and got_type != expected_type:
            print("listen: type", hex(got_type), "!= expected", hex(expected_type),
                  "-- skipping")
            continue
        if name8 is not None and got_name != name8:
            print("listen: name", got_name, "!= expected", name8, "-- skipping")
            continue

        if on_var is not None:
            on_var(got_type, got_name, hdr, data)
        else:
            # AppVar (0x15) and Program (0x05/0x06) bodies on the wire are
            # [size_le16][bytes]. Strip the prefix so the display shows the
            # caller-visible payload, not the framing.
            payload = data
            if got_type in (0x05, 0x06, 0x15) and len(data) >= 2:
                declared = data[0] | (data[1] << 8)
                if declared == len(data) - 2:
                    payload = data[2:]
            try:
                ascii_view = payload.decode("ascii")
            except Exception:
                ascii_view = repr(bytes(payload))
            stripped = bytes(got_name).rstrip(b'\x00')
            print("RECV type=", hex(got_type), "name=", stripped,
                  "len=", len(payload), "ascii=", repr(ascii_view))


def req_var(type_id, name8, calc_machine=0x82, timeout_ms=5000):
    """PC-initiated variable request. Asks the calc to send the named variable.
    Returns (header_bytes, data_bytes) on success, or None on error.

    For TI-82 list L1: req_var(T_LIST, list_name_82(0))."""
    idle()
    pc_machine = pc_id_for(calc_machine)
    proto = 82 if calc_machine == 0x82 else 83
    # The size field in a REQ header is "expected size"; calc fills in the real
    # one in its VAR reply. 0 is conventional for "I don't know yet".
    hdr_data = make_var_header(0, type_id, name8, proto=proto)
    print("sending REQ for type=", hex(type_id), "name=", bytes(name8))
    if not send_packet(REQ, hdr_data, machine=pc_machine):
        print("REQ send failed"); return None

    p = recv_packet(timeout_ms)
    if p is None: print("no ACK after REQ"); return None
    _, cmd, _ = p
    print("pkt: cmd=", hex(cmd))
    if cmd == SKIP:  # variable doesn't exist
        print("calc says variable does not exist (SKIP/EXIT)")
        send_packet(ACK, machine=pc_machine)
        return None
    if cmd != ACK:
        print("expected ACK, got", hex(cmd)); return None

    p = recv_packet(timeout_ms)
    if p is None: print("no VAR after REQ"); return None
    _, cmd, hdr = p
    print("pkt VAR: cmd=", hex(cmd), "hdr=", bytes(hdr))
    if cmd != VAR:
        print("expected VAR, got", hex(cmd)); return None

    if not send_packet(ACK, machine=pc_machine):
        print("ACK after VAR failed"); return None
    if not send_packet(CTS, machine=pc_machine):
        print("CTS after VAR failed"); return None

    p = recv_packet(timeout_ms)
    if p is None: print("no ACK after CTS"); return None
    _, cmd, _ = p
    print("pkt: cmd=", hex(cmd))
    if cmd != ACK:
        print("expected ACK, got", hex(cmd)); return None

    p = recv_packet(timeout_ms)
    if p is None: print("no DATA"); return None
    _, cmd, data = p
    print("pkt DATA: cmd=", hex(cmd), "len=", len(data))
    if cmd != DATA:
        print("expected DATA, got", hex(cmd)); return None

    if not send_packet(ACK, machine=pc_machine):
        print("final ACK failed"); return None

    return (bytes(hdr), bytes(data))


def send_var(type_id, name8, data, calc_machine=0x82, timeout_ms=5000,
             quiet=False):
    """PC-initiated send: deliver a variable to the calc.
    type_id is e.g. T_LIST; name8 is the 8-byte name field; data is the
    variable payload (count-prefixed for lists, raw real for reals, etc).
    Returns True on success.

    quiet=True suppresses logging across the time-critical RTS->ACK->CTS
    window. USB-serial prints under MicroPython can take several ms each;
    that delay is enough that the calc, having ACKed our RTS, starts trying
    to send CTS before we're back in the recv loop, gives up bit-bang
    handshaking on its first CTS bit, and displays 'Error in Xmit' instead
    of completing the transfer. With quiet=True we collect timestamps and
    cmd bytes inline and only print after the handshake settles."""
    idle()
    pc_machine = pc_id_for(calc_machine)
    proto = 82 if calc_machine == 0x82 else 83
    var_hdr = make_var_header(len(data), type_id, name8, proto=proto)
    if not quiet:
        print("sending RTS for type=", hex(type_id), "name=", bytes(name8), "len=", len(data))
        print("RTS bytes:", hex_bytes(packet_bytes(RTS, var_hdr, machine=pc_machine)))
    t_rts_start = time.ticks_us()
    if not send_packet(RTS, var_hdr, machine=pc_machine):
        print("RTS send failed"); return False
    t_rts_end = time.ticks_us()

    p = recv_packet(timeout_ms)
    t_ack_done = time.ticks_us()
    if p is None:
        print("no ACK after RTS")
        print("timing: send RTS=", time.ticks_diff(t_rts_end, t_rts_start), "us")
        print("idle now: lines=", read())
        return False
    _, cmd, _ = p
    if cmd != ACK:
        print("expected ACK, got", hex(cmd)); return False

    # Time-critical: do NOT print here. Go straight back to recv for CTS.
    p2 = recv_packet(timeout_ms * 2)
    t_cts_done = time.ticks_us()
    if p2 is None:
        print("no CTS within", timeout_ms * 2, "ms")
        print("timing: send RTS=", time.ticks_diff(t_rts_end, t_rts_start),
              "us, ACK recv=", time.ticks_diff(t_ack_done, t_rts_end), "us")
        print("idle now: lines=", read())
        return False
    _, cmd, body = p2
    if not quiet:
        print("RTS sent in", time.ticks_diff(t_rts_end, t_rts_start), "us")
        print("ACK received", time.ticks_diff(t_ack_done, t_rts_end), "us after RTS done")
        print("CTS received", time.ticks_diff(t_cts_done, t_ack_done), "us after ACK done")
        print("pkt: cmd=", hex(cmd), "body_len=", len(body))
    if cmd == SKIP:
        print("calc rejected: SKIP/EXIT, body=", bytes(body))
        send_packet(ACK, machine=pc_machine)
        return False
    if cmd != CTS:
        print("expected CTS, got", hex(cmd)); return False

    if not send_packet(ACK, machine=pc_machine):
        print("ACK after CTS failed"); return False

    # Give the calc a beat to switch from "I just sent ACK" to "now receiving DATA";
    # without this, long DATA packets fail mid-stream with "Error in Xmit".
    time.sleep_ms(20)

    print("sending DATA")
    if not send_packet(DATA, data, machine=pc_machine):
        # send_packet returns False if a single bit's ack timed out, which is
        # what "Error in Xmit" looks like from our side: the calc gave up
        # mid-packet and stopped pulling its line. Dump where we are so we can
        # tell whether it died near the start, middle, or end.
        print("DATA send failed; lines=", read())
        return False

    p = recv_packet(timeout_ms)
    if p is None:
        print("no ACK after DATA; lines=", read())
        return False
    _, cmd, _ = p
    print("pkt: cmd=", hex(cmd))
    if cmd == SKIP:
        print("calc rejected DATA: SKIP/EXIT")
        send_packet(ACK, machine=pc_machine)
        return False
    if cmd != ACK:
        print("expected ACK, got", hex(cmd)); return False

    # TI-82 protocol ends here; 83/83+/84+ expect an EOT from us next.
    if calc_machine != 0x82:
        if not send_packet(EOT, machine=pc_machine):
            print("EOT send failed"); return False
    print("done")
    return True


def delete_var(type_id, name8, calc_machine=0x73, timeout_ms=3000):
    """Send a silent delete command for a variable header.

    This is a useful upload diagnostic on 83+/84+: it exercises the same
    native machine ID and header encoding as RTS, but the calc should answer
    with ACK/ACK instead of entering the RTS->CTS->DATA handshake.
    """
    idle()
    pc_machine = pc_id_for(calc_machine)
    proto = 82 if calc_machine == 0x82 else 83
    hdr = make_var_header(0, type_id, name8, proto=proto)
    print("sending DEL for type=", hex(type_id), "name=", bytes(name8))
    print("DEL bytes:", hex_bytes(packet_bytes(DEL, hdr, machine=pc_machine)))
    if not send_packet(DEL, hdr, machine=pc_machine):
        print("DEL send failed; lines=", read())
        return False

    p = recv_packet(timeout_ms)
    if p is None:
        print("no first ACK after DEL; lines=", read())
        return False
    _, cmd, body = p
    print("pkt1: cmd=", hex(cmd), "body=", bytes(body))
    if cmd != ACK:
        print("expected ACK, got", hex(cmd))
        return False

    p = recv_packet(timeout_ms)
    if p is None:
        print("no second ACK after DEL; lines=", read())
        return False
    _, cmd, body = p
    print("pkt2: cmd=", hex(cmd), "body=", bytes(body))
    if cmd != ACK:
        print("expected second ACK, got", hex(cmd))
        return False

    print("delete handshake done")
    return True


def get_l1(calc_machine=0x73):
    """Convenience: request L1 from the calc.
    Defaults to 83+/84+ native (0x73); pass calc_machine=0x82 for TI-82 compat."""
    return req_var(T_LIST, list_name_82(0), calc_machine=calc_machine)


def put_l1(values, quiet=False):
    """Convenience: write a real-number list into L1 (TI-82 protocol)."""
    return send_var(T_LIST, list_name_82(0), encode_real_list(values),
                    quiet=quiet)


def put_l1_83p(values, quiet=False):
    """Same as put_l1 but using TI-83+/84+ native protocol (machine ID 0x73).
    Use this if put_l1 fails with 'no ACK after RTS' -- the 84+ in TI-82
    compat mode does not respond to PC-initiated RTS, but its native silent
    protocol does."""
    return send_var(T_LIST, list_name_82(0), encode_real_list(values),
                    calc_machine=0x73, quiet=quiet)


def put_real(letter, value, calc_machine=0x82, quiet=False):
    """Send a single real number to var A..Z. Smaller payload than a list,
    so it isolates 'are headers OK?' from 'is list payload OK?' when
    debugging Error in Xmit."""
    return send_var(T_REAL, real_name(letter), encode_real(value),
                    calc_machine=calc_machine, quiet=quiet)


def put_real_83p(letter, value, quiet=False):
    return put_real(letter, value, calc_machine=0x73, quiet=quiet)


def put_prog(name, payload, locked=False, calc_machine=0x73, quiet=False):
    """Send a program payload to the calc.

    payload is the raw variable body: [size_le16][token_stream]. This is the
    same shape that lives inside a .8Xp file's variable entry, after the
    13-byte entry header.

    locked=False uses T_PROG=0x05 (editable); locked=True uses 0x06 (locked,
    user can run but not view/edit). Locked is the ship-time setting; default
    unlocked so the calc-side test can show source if anything's wrong."""
    type_id = T_PROG_LOCKED if locked else T_PROG
    return send_var(type_id, prog_name(name), payload,
                    calc_machine=calc_machine, quiet=quiet)


def put_prog_83p(name, payload, locked=False, quiet=False):
    return put_prog(name, payload, locked=locked, calc_machine=0x73,
                    quiet=quiet)


def del_real_83p(letter):
    return delete_var(T_REAL, real_name(letter), calc_machine=0x73)


def del_l1_83p():
    return delete_var(T_LIST, list_name_82(0), calc_machine=0x73)
