from machine import Pin
import time

TIP  = 6   # "red" / 0-line
RING = 7   # "white" / 1-line

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


MACHINE_ID = 0x23   # we are "computer sending TI-83+/84+ data"


# Per packet.html, the machine ID identifies the *sender*, not the link partner.
# Calc-side IDs (0x82/0x83/0x73) and PC-side IDs (0x02/0x03/0x23) come in pairs.
# When the calc sends 0x82, we reply as 0x02; when 0x83, we reply as 0x03; etc.
def pc_id_for(calc_id):
    pairs = {0x82: 0x02, 0x83: 0x03, 0x73: 0x23, 0x86: 0x06, 0x88: 0x08, 0x98: 0x88}
    return pairs.get(calc_id, 0x23)


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
    n = len(data)
    hdr = bytes([machine, cmd, n & 0xFF, (n >> 8) & 0xFF])
    for b in hdr:
        if not send_byte(b): return False
    if n:
        for b in data:
            if not send_byte(b): return False
        cs = checksum(data)
        if not send_byte(cs & 0xFF): return False
        if not send_byte((cs >> 8) & 0xFF): return False
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
SKIP = 0x36
ACK  = 0x56
ERR  = 0x5A
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


def get_l1():
    """Convenience: request L1 from the calc (TI-82 protocol)."""
    return req_var(T_LIST, list_name_82(0))


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


def send_var(type_id, name8, data, calc_machine=0x82, timeout_ms=5000):
    """PC-initiated send: deliver a variable to the calc.
    type_id is e.g. T_LIST; name8 is the 8-byte name field; data is the
    variable payload (count-prefixed for lists, raw real for reals, etc).
    Returns True on success."""
    idle()
    pc_machine = pc_id_for(calc_machine)
    proto = 82 if calc_machine == 0x82 else 83
    var_hdr = make_var_header(len(data), type_id, name8, proto=proto)
    print("sending RTS for type=", hex(type_id), "name=", bytes(name8), "len=", len(data))
    if not send_packet(RTS, var_hdr, machine=pc_machine):
        print("RTS send failed"); return False

    p = recv_packet(timeout_ms)
    if p is None: print("no ACK after RTS"); return False
    _, cmd, _ = p
    print("pkt: cmd=", hex(cmd))
    if cmd != ACK:
        print("expected ACK, got", hex(cmd)); return False

    # Calc may take a moment after ACK to decide whether to send CTS or SKIP
    # (it has to look up if the var name exists, check archive flags, etc).
    # Use a longer timeout here than the per-packet default.
    p = recv_packet(timeout_ms * 2)
    if p is None:
        print("no CTS within", timeout_ms * 2, "ms")
        # If we got *some* bytes but not a full packet, dump line state.
        print("idle now: lines=", read())
        return False
    _, cmd, body = p
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
        print("DATA send failed"); return False

    p = recv_packet(timeout_ms)
    if p is None: print("no ACK after DATA"); return False
    _, cmd, _ = p
    print("pkt: cmd=", hex(cmd))
    if cmd != ACK:
        print("expected ACK, got", hex(cmd)); return False

    # TI-82 protocol ends here; 83/83+/84+ expect an EOT from us next.
    if calc_machine != 0x82:
        if not send_packet(EOT, machine=pc_machine):
            print("EOT send failed"); return False
    print("done")
    return True


def put_l1(values):
    """Convenience: write a real-number list into L1 (TI-82 protocol)."""
    return send_var(T_LIST, list_name_82(0), encode_real_list(values))


def put_l1_83p(values):
    """Same as put_l1 but using TI-83+/84+ native protocol (machine ID 0x73).
    Use this if put_l1 fails with 'no ACK after RTS' -- the 84+ in TI-82
    compat mode does not respond to PC-initiated RTS, but its native silent
    protocol does."""
    return send_var(T_LIST, list_name_82(0), encode_real_list(values),
                    calc_machine=0x73)


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