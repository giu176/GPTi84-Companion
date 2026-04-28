from machine import Pin
import time

TIP  = 6   # 0-line
RING = 7   # 1-line

# Start as inputs with pullups (released, pullup wins).
# The Pico has no external pullups on these pins, so without Pin.PULL_UP
# the line floats while we are not driving and only the calc-side pullup
# pulls it high; that rise is slow enough to glitch the calc's bit reader.
tip  = Pin(TIP,  Pin.IN, Pin.PULL_UP)
ring = Pin(RING, Pin.IN, Pin.PULL_UP)

def release(p):
    p.init(mode=Pin.IN, pull=Pin.PULL_UP)

def pull_low(p):
    p.init(mode=Pin.OUT, value=0)

def idle():
    release(tip); release(ring)

def read():
    # returns (tip_level, ring_level), both 1 = idle
    return tip.value(), ring.value()

def recv_bit(timeout_ms=2000):
    """Wait for sender to pull a line low, ack on the other, return 0 or 1.
    Returns None on timeout."""
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while True:
        t = tip.value()
        r = ring.value()
        if t == 0 or r == 0:
            break
        if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
            return None
    if t == 0:
        bit = 0
        pull_low(ring)
        while tip.value() == 0:
            pass
        release(ring)
    else:
        bit = 1
        pull_low(tip)
        while ring.value() == 0:
            pass
        release(tip)
    return bit


def recv_byte(timeout_ms=2000):
    """Read 8 bits LSB-first, return byte or None on timeout."""
    b = 0
    for i in range(8):
        bit = recv_bit(timeout_ms)
        if bit is None:
            return None
        b |= (bit << i)
    return b


def recv_byte_traced(timeout_ms=2000):
    """Like recv_byte but logs each bit's first-edge line and timing."""
    b = 0
    bits = []
    for i in range(8):
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while True:
            t = tip.value(); r = ring.value()
            if t == 0 or r == 0:
                break
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                print("timeout at bit", i, "bits so far:", bits)
                return None
        if t == 0 and r == 1:
            bit = 0
            pull_low(ring)
            while tip.value() == 0:
                pass
            release(ring)
        elif r == 0 and t == 1:
            bit = 1
            pull_low(tip)
            while ring.value() == 0:
                pass
            release(tip)
        else:
            print("AMBIGUOUS at bit", i, "t=", t, "r=", r)
            return None
        bits.append(bit)
        b |= (bit << i)
    print("bits LSB-first:", bits, "byte:", hex(b))
    return b


def recv_n_traced(n, timeout_ms=3000):
    idle()
    out = []
    for i in range(n):
        b = recv_byte_traced(timeout_ms)
        if b is None:
            print("stopped after", i)
            return out
        out.append(b)
    return out


def recv_n(n, timeout_ms=2000):
    """Read n bytes, print each in hex as it arrives. Returns list."""
    idle()
    out = []
    for i in range(n):
        b = recv_byte(timeout_ms)
        if b is None:
            print("timeout after", i, "bytes:", [hex(x) for x in out])
            return out
        print("byte", i, "=", hex(b))
        out.append(b)
    return out


def send_bit(b, timeout_ms=2000):
    """Send a bit. Pull our line, wait for receiver to ack on the other, release.
    Returns True on success, False on timeout."""
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    if b == 0:
        pull_low(tip)
        while ring.value() == 1:
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                release(tip); return False
        release(tip)
        while ring.value() == 0:
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                return False
    else:
        pull_low(ring)
        while tip.value() == 1:
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                release(ring); return False
        release(ring)
        while tip.value() == 0:
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                return False
    return True


def send_byte(b, timeout_ms=2000):
    for i in range(8):
        if not send_bit((b >> i) & 1, timeout_ms):
            return False
    return True


def checksum(data):
    """16-bit sum of bytes, low byte first on the wire."""
    s = 0
    for b in data:
        s = (s + b) & 0xFFFF
    return s


SEND_BYTE_GAP_MS = 0


MACHINE_ID = 0x23   # we are "computer sending TI-83+/84+ data"


# Per packet.html, the machine ID identifies the *sender*, not the link partner.
# Calc-side IDs (0x82/0x83/0x73) and PC-side IDs (0x02/0x03/0x23) come in pairs.
# When the calc sends 0x82, we reply as 0x02; when 0x83, we reply as 0x03; etc.
def pc_id_for(calc_id):
    pairs = {0x82: 0x02, 0x83: 0x03, 0x73: 0x23, 0x86: 0x06, 0x88: 0x08, 0x98: 0x88}
    return pairs.get(calc_id, 0x23)


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


def hex_bytes(buf):
    return " ".join("{:02X}".format(b) for b in buf)


def parse_real_parts(b):
    """Decompose a 9-byte TI-82 real into (sign, exp, digits) without precision loss.
    sign is -1 or 1, exp is unbiased decimal exponent, digits is the 14-digit
    mantissa as an int (leading digit first). value = sign * digits * 10^(exp-13)."""
    sign = -1 if (b[0] & 0x80) else 1
    exp = b[1] - 0x80
    digits = 0
    for i in range(7):
        digits = digits * 100 + ((b[2 + i] >> 4) * 10) + (b[2 + i] & 0x0F)
    return sign, exp, digits


def parse_real_str(b):
    """Format a 9-byte TI-82 real as a decimal string. Lossless: bypasses float
    entirely so MicroPython's 32-bit float precision can't mangle 14-digit values."""
    sign, exp, digits = parse_real_parts(b)
    if digits == 0:
        return "0"
    s = "{:014d}".format(digits).rstrip("0") or "0"
    if exp >= 0 and exp < 14 and len(s) <= exp + 1:
        body = s + "0" * (exp + 1 - len(s))
    elif exp >= 0 and exp < 14:
        body = s[: exp + 1] + "." + s[exp + 1 :]
    elif exp < 0 and exp > -5:
        body = "0." + "0" * (-exp - 1) + s
    else:
        body = s[0] + ("." + s[1:] if len(s) > 1 else "") + "e" + str(exp)
    return ("-" if sign < 0 else "") + body


def parse_real(b):
    """Parse a 9-byte TI-82 real to a Python float. Lossy on MicroPython builds
    that use 32-bit floats: prefer parse_real_str for display."""
    sign, exp, digits = parse_real_parts(b)
    shift = exp - 13
    if shift >= 0:
        return sign * digits * (10 ** shift)
    return sign * digits / (10 ** -shift)


def parse_real_list(data):
    """Parse a TI-82 real-number list payload: [count_le16][N * 9-byte reals].
    Returns floats (lossy under 32-bit float MicroPython); see parse_real_list_str."""
    n = data[0] | (data[1] << 8)
    out = []
    for i in range(n):
        out.append(parse_real(data[2 + i * 9 : 2 + (i + 1) * 9]))
    return out


def parse_real_list_str(data):
    """Like parse_real_list but returns strings; lossless on any MicroPython build."""
    n = data[0] | (data[1] << 8)
    out = []
    for i in range(n):
        out.append(parse_real_str(data[2 + i * 9 : 2 + (i + 1) * 9]))
    return out


def send_packet(cmd, data=b'', machine=MACHINE_ID):
    """Send a DBUS packet. Returns True on success."""
    pkt = packet_bytes(cmd, data, machine=machine)
    for i, b in enumerate(pkt):
        if not send_byte(b):
            print("send_packet stalled at byte", i, "of", len(pkt), "value=", hex(b))
            print("packet:", hex_bytes(pkt))
            return False
        if SEND_BYTE_GAP_MS and i + 1 != len(pkt):
            time.sleep_ms(SEND_BYTE_GAP_MS)
    return True


def recv_packet(timeout_ms=3000):
    """Receive one DBUS packet. Returns (machine, cmd, data) or None on error."""
    machine = recv_byte(timeout_ms)
    if machine is None: return None
    cmd = recv_byte(timeout_ms)
    if cmd is None: return None
    lo = recv_byte(timeout_ms)
    if lo is None: return None
    hi = recv_byte(timeout_ms)
    if hi is None: return None
    n = lo | (hi << 8)

    # Per the TI packet spec, some commands never carry data even if the
    # 16-bit length/status field is nonzero. On a TI-84+, CTS after RTS can
    # arrive as 73 09 0D 00 with no trailing body or checksum. If we trust the
    # length word unconditionally, we block waiting for 13 bytes that will never
    # arrive and miss the handshake.
    if cmd in (0x09, 0x56, 0x5A, 0x68, 0x6D, 0x92, 0x2D):
        return (machine, cmd, b'')

    data = bytearray()
    if n:
        for _ in range(n):
            b = recv_byte(timeout_ms)
            if b is None: return None
            data.append(b)
        cs_lo = recv_byte(timeout_ms)
        cs_hi = recv_byte(timeout_ms)
        if cs_lo is None or cs_hi is None: return None
        got = cs_lo | (cs_hi << 8)
        want = checksum(data)
        if got != want:
            print("checksum mismatch: got", hex(got), "want", hex(want))
    return (machine, cmd, bytes(data))


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


# Type IDs (TI-82; mostly compatible with 83/83+/84+ for the basic types).
T_REAL   = 0x00
T_LIST   = 0x01
T_MATRIX = 0x02
T_PROG   = 0x05


def list_name_82(idx):
    """TI-82 name field for L1..L0 (idx 0..9). Token 5D, sub-token 00..09, padded."""
    return bytes([0x5D, idx]) + b'\x00' * 6


def make_var_header(data_size, type_id, name8, proto=82):
    """Variable header used in REQ/VAR/RTS data fields.
    TI-82 form is 11 bytes: [size_le16][type][name 8].
    TI-83+/84+ form is 13 bytes: same plus [version=0][flags=0]."""
    if len(name8) != 8:
        raise ValueError("name must be exactly 8 bytes")
    base = bytes([data_size & 0xFF, (data_size >> 8) & 0xFF, type_id]) + name8
    if proto == 82:
        return base
    return base + b'\x00\x00'


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


def go():
    """REPL-friendly wrapper: the MicroPico extension mangles some direct
    function calls; calling go() always works because it's a short name."""
    return first_bits(16)


def get_l1(calc_machine=0x73):
    """Convenience: request L1 from the calc.
    Defaults to 83+/84+ native (0x73); pass calc_machine=0x82 for TI-82 compat."""
    return req_var(T_LIST, list_name_82(0), calc_machine=calc_machine)


def encode_real(value):
    """Encode a number into the 9-byte TI-82 real format.
    Goes through string formatting to avoid float precision artifacts in the
    BCD digits; '%.14e' gives 14 digits of precision plus exponent which is
    exactly what the TI format wants."""
    if value == 0:
        return b'\x00\x80' + b'\x00' * 7
    sign = 0x80 if value < 0 else 0x00
    s = "{:.13e}".format(abs(value))   # 1 leading digit + 13 fractional + 'e+NN'
    mant_str, exp_str = s.split("e")
    exp = int(exp_str)
    digits = mant_str.replace(".", "")  # 14 digits total, no leading zeros
    if len(digits) < 14:
        digits = digits + "0" * (14 - len(digits))
    elif len(digits) > 14:
        digits = digits[:14]
    out = bytearray(9)
    out[0] = sign
    out[1] = (exp + 0x80) & 0xFF
    for i in range(7):
        hi = int(digits[2 * i])
        lo = int(digits[2 * i + 1])
        out[2 + i] = (hi << 4) | lo
    return bytes(out)


def encode_real_list(values):
    """Encode a Python sequence of numbers into a TI-82 list payload."""
    out = bytearray()
    out.append(len(values) & 0xFF)
    out.append((len(values) >> 8) & 0xFF)
    for v in values:
        out.extend(encode_real(v))
    return bytes(out)


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


# Real-name field for variables A..Z on the 8-byte name field. The 83+/84+
# spec example uses 0x41..0x5A (ASCII 'A'..'Z') in slot 0 and zero-pads.
def real_name(letter):
    if len(letter) != 1 or not ('A' <= letter <= 'Z'):
        raise ValueError("letter must be a single uppercase A..Z")
    return bytes([ord(letter)]) + b'\x00' * 7


def put_real(letter, value, calc_machine=0x82, quiet=False):
    """Send a single real number to var A..Z. Smaller payload than a list,
    so it isolates 'are headers OK?' from 'is list payload OK?' when
    debugging Error in Xmit."""
    return send_var(T_REAL, real_name(letter), encode_real(value),
                    calc_machine=calc_machine, quiet=quiet)


def put_real_83p(letter, value, quiet=False):
    return put_real(letter, value, calc_machine=0x73, quiet=quiet)


def prog_name(name):
    """8-byte name field for a program. ASCII uppercase A..Z and digits 0..9,
    1..8 chars, zero-padded to 8."""
    if not (1 <= len(name) <= 8):
        raise ValueError("prog name must be 1..8 chars")
    for c in name:
        if not (('A' <= c <= 'Z') or ('0' <= c <= '9')):
            raise ValueError("prog name must be uppercase A..Z or 0..9")
    return name.encode("ascii") + b'\x00' * (8 - len(name))


def put_prog(name, payload, locked=False, calc_machine=0x73, quiet=False):
    """Send a program payload to the calc.

    payload is the raw variable body: [size_le16][token_stream]. This is the
    same shape that lives inside a .8Xp file's variable entry, after the
    13-byte entry header.

    locked=False uses T_PROG=0x05 (editable); locked=True uses 0x06 (locked,
    user can run but not view/edit). Locked is the ship-time setting; default
    unlocked so the calc-side test can show source if anything's wrong."""
    type_id = 0x06 if locked else 0x05
    return send_var(type_id, prog_name(name), payload,
                    calc_machine=calc_machine, quiet=quiet)


def put_prog_83p(name, payload, locked=False, quiet=False):
    return put_prog(name, payload, locked=locked, calc_machine=0x73,
                    quiet=quiet)


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


def del_real_83p(letter):
    return delete_var(T_REAL, real_name(letter), calc_machine=0x73)


def del_l1_83p():
    return delete_var(T_LIST, list_name_82(0), calc_machine=0x73)


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


def set_send_byte_gap(ms):
    """Set an inter-byte gap for send_packet, useful for timing probes."""
    global SEND_BYTE_GAP_MS
    if ms < 0:
        raise ValueError("gap must be >= 0")
    SEND_BYTE_GAP_MS = ms
    print("SEND_BYTE_GAP_MS=", SEND_BYTE_GAP_MS)


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