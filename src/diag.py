"""DBUS bring-up diagnostics: RDY pings, RTS reply tracing, line snooping.

These are REPL helpers used while debugging silent mode and bit-bang timing.
None of them are in the ship path.
"""

import time
import wire
from wire import (
    idle, read, recv_bit, recv_n_traced,
    tip, ring,
)
from packet import (
    ACK, RDY, RTS,
    pc_id_for, packet_bytes, send_packet, recv_packet, hex_bytes,
)
from vartypes import (
    T_LIST, T_REAL,
    list_name_82, real_name, make_var_header,
    encode_real, encode_real_list,
)


def ready_check(calc_machine=0x73, timeout_ms=3000):
    """Send a 'check ready' (0x68) packet. Returns True if calc replies ACK,
    meaning it's in silent-mode receive and willing to accept commands.
    The 84+ only responds to RTS/REQ once silent mode is active; this is the
    cheapest way to confirm that without sending a full variable handshake."""
    idle()
    pc_machine = pc_id_for(calc_machine)
    print("sending RDY (0x68) as machine", hex(pc_machine))
    print("RDY bytes:", hex_bytes(packet_bytes(RDY, machine=pc_machine)))
    if not send_packet(RDY, machine=pc_machine):
        print("RDY send failed; lines=", read())
        return False
    p = recv_packet(timeout_ms)
    if p is None:
        print("no reply to RDY within", timeout_ms, "ms; lines=", read())
        return False
    _, cmd, body = p
    print("pkt: cmd=", hex(cmd), "body=", bytes(body))
    return cmd == ACK


def ready_check_82():
    """RDY against TI-82 machine ID. Per linkguide the TI-82 doesn't implement
    the silent command set at all -- this should fail. Useful for confirming
    the calc is in 84+ native (0x73) mode vs TI-82 compat (0x82) mode."""
    return ready_check(calc_machine=0x82)


def probe_rts_reply(type_id, name8, data_len, calc_machine=0x73,
                    timeout_ms=3000, traced_bytes=6):
    """Send RTS, receive the initial ACK, then trace the calc's next bytes.

    This is a diagnostic for cases where the calc ACKs RTS but never yields a
    full CTS/SKIP packet through recv_packet(). If the calc starts sending a
    follow-up packet and stalls mid-byte or mid-packet, recv_n_traced() will
    show how far it got.
    """
    idle()
    pc_machine = pc_id_for(calc_machine)
    proto = 82 if calc_machine == 0x82 else 83
    hdr = make_var_header(data_len, type_id, name8, proto=proto)
    print("probing RTS reply for type=", hex(type_id), "name=", bytes(name8),
          "len=", data_len)
    print("RTS bytes:", hex_bytes(packet_bytes(RTS, hdr, machine=pc_machine)))
    if not send_packet(RTS, hdr, machine=pc_machine):
        print("RTS send failed; lines=", read())
        return None

    p = recv_packet(timeout_ms)
    if p is None:
        print("no ACK after RTS; lines=", read())
        return None
    _, cmd, body = p
    print("ack pkt: cmd=", hex(cmd), "body=", bytes(body))
    if cmd != ACK:
        print("expected ACK, got", hex(cmd))
        return None

    print("tracing next", traced_bytes, "bytes from calc...")
    return recv_n_traced(traced_bytes, timeout_ms)


def probe_rts_real_83p(letter, value=0.0, timeout_ms=3000, traced_bytes=6):
    return probe_rts_reply(T_REAL, real_name(letter), len(encode_real(value)),
                           calc_machine=0x73, timeout_ms=timeout_ms,
                           traced_bytes=traced_bytes)


def probe_rts_l1_83p(values, timeout_ms=3000, traced_bytes=6):
    return probe_rts_reply(T_LIST, list_name_82(0), len(encode_real_list(values)),
                           calc_machine=0x73, timeout_ms=timeout_ms,
                           traced_bytes=traced_bytes)


def first_bits(n=16, timeout_ms=10000):
    """Wait for the first wire edge, log which line moved, then read n raw bits.
    Decodes the first 16 as two LSB-first bytes so you can sanity-check the
    machine ID and command of the first incoming packet."""
    idle()
    print("idle, lines:", read())
    print("waiting for first edge...")
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while True:
        t, r = tip.value(), ring.value()
        if t == 0 or r == 0:
            print("first edge: tip=", t, "ring=", r)
            break
        if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
            print("nothing")
            return
    bits = []
    for i in range(n):
        bit = recv_bit(2000)
        if bit is None:
            print("timeout at bit", i)
            break
        bits.append(bit)
    print("bits LSB-first:", bits)
    if len(bits) >= 8:
        b0 = 0
        for i in range(8):
            b0 |= bits[i] << i
        print("byte0=", hex(b0))
    if len(bits) >= 16:
        b1 = 0
        for i in range(8):
            b1 |= bits[8+i] << i
        print("byte1=", hex(b1))


def snoop(timeout_ms=10000):
    """Passively watch both lines, print every transition with a us timestamp.
    Ctrl+C to stop early."""
    idle()
    last = read()
    t0 = time.ticks_us()
    print("start:", last)
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    n = 0
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        cur = (tip.value(), ring.value())
        if cur != last:
            print(time.ticks_diff(time.ticks_us(), t0), cur)
            last = cur
            n += 1
    print("done, transitions:", n)


def go():
    """REPL-friendly wrapper: the MicroPico extension mangles some direct
    function calls; calling go() always works because it's a short name."""
    return first_bits(16)
