"""DBUS packet framing layer.

Packet shape: [machine_id][cmd][len_lo][len_hi] (+ [data...][cs_lo][cs_hi])
Some commands are header-only and never carry a data body even if their
length field is nonzero (CTS, ACK, ERR, RDY, SCR, EOT, VER); recv_packet
short-circuits these so we don't block waiting for body bytes that never come.
"""

import time
import wire

# Command IDs
VAR  = 0x06
CTS  = 0x09
DATA = 0x15
VER  = 0x2D  # silent: request OS/hardware versions
SKIP = 0x36
ACK  = 0x56
ERR  = 0x5A
RDY  = 0x68  # silent: "are you ready?" -- calc replies ACK if listening
SCR  = 0x6D  # silent: request screenshot
DEL  = 0x88  # silent: delete variable
EOT  = 0x92
REQ  = 0xA2
RTS  = 0xC9


MACHINE_ID = 0x23   # we are "computer sending TI-83+/84+ data"


# Per packet.html, the machine ID identifies the *sender*, not the link partner.
# Calc-side IDs (0x82/0x83/0x73) and PC-side IDs (0x02/0x03/0x23) come in pairs.
# When the calc sends 0x82, we reply as 0x02; when 0x83, we reply as 0x03; etc.
def pc_id_for(calc_id):
    pairs = {0x82: 0x02, 0x83: 0x03, 0x73: 0x23, 0x86: 0x06, 0x88: 0x08, 0x98: 0x88}
    return pairs.get(calc_id, 0x23)


def checksum(data):
    """16-bit sum of bytes, low byte first on the wire."""
    s = 0
    for b in data:
        s = (s + b) & 0xFFFF
    return s


def hex_bytes(buf):
    return " ".join("{:02X}".format(b) for b in buf)


def packet_bytes(cmd, data=b'', machine=MACHINE_ID):
    """Return the exact bytes that send_packet will place on the wire."""
    n = len(data)
    out = bytearray([machine, cmd, n & 0xFF, (n >> 8) & 0xFF])
    if n:
        out.extend(data)
        cs = checksum(data)
        out.append(cs & 0xFF)
        out.append((cs >> 8) & 0xFF)
    return bytes(out)


def send_packet(cmd, data=b'', machine=MACHINE_ID):
    """Send a DBUS packet. Returns True on success."""
    pkt = packet_bytes(cmd, data, machine=machine)
    gap = wire.get_send_byte_gap_ms()
    for i, b in enumerate(pkt):
        if not wire.send_byte(b):
            print("send_packet stalled at byte", i, "of", len(pkt), "value=", hex(b))
            print("packet:", hex_bytes(pkt))
            return False
        if gap and i + 1 != len(pkt):
            time.sleep_ms(gap)
    return True


def recv_packet(timeout_ms=3000):
    """Receive one DBUS packet. Returns (machine, cmd, data) or None on error."""
    machine = wire.recv_byte(timeout_ms)
    if machine is None: return None
    cmd = wire.recv_byte(timeout_ms)
    if cmd is None: return None
    lo = wire.recv_byte(timeout_ms)
    if lo is None: return None
    hi = wire.recv_byte(timeout_ms)
    if hi is None: return None
    n = lo | (hi << 8)

    # Per the TI packet spec, some commands never carry data even if the
    # 16-bit length/status field is nonzero. On a TI-84+, CTS after RTS can
    # arrive as 73 09 0D 00 with no trailing body or checksum. If we trust the
    # length word unconditionally, we block waiting for 13 bytes that will never
    # arrive and miss the handshake.
    if cmd in (CTS, ACK, ERR, RDY, SCR, EOT, VER):
        return (machine, cmd, b'')

    data = bytearray()
    if n:
        for _ in range(n):
            b = wire.recv_byte(timeout_ms)
            if b is None: return None
            data.append(b)
        cs_lo = wire.recv_byte(timeout_ms)
        cs_hi = wire.recv_byte(timeout_ms)
        if cs_lo is None or cs_hi is None: return None
        got = cs_lo | (cs_hi << 8)
        want = checksum(data)
        if got != want:
            print("checksum mismatch: got", hex(got), "want", hex(want))
    return (machine, cmd, bytes(data))
