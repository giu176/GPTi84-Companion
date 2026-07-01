"""DBUS wire layer: bit/byte bang over tip and ring.

The 2.5mm link is two open-collector lines. Idle is both high (released with
pullups). To send a 0 the sender pulls TIP low; the receiver acks by pulling
RING low until the sender releases TIP, then both release. A 1 is the mirror
image on RING. Bytes are LSB-first.
"""

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


SEND_BYTE_GAP_MS = 0
EDGE_LOGGER = None


def set_edge_logger(logger):
    global EDGE_LOGGER
    EDGE_LOGGER = logger


def _log_edge(message):
    if EDGE_LOGGER is not None:
        try:
            EDGE_LOGGER(message)
        except Exception:
            pass


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
            _log_edge("edge tip=%d ring=%d" % (t, r))
            break
        if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
            return None
    if t == 0:
        bit = 0
        pull_low(ring)
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while tip.value() == 0:
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                release(ring)
                return None
        release(ring)
    else:
        bit = 1
        pull_low(tip)
        deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
        while ring.value() == 0:
            if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
                release(tip)
                return None
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


def get_send_byte_gap_ms():
    return SEND_BYTE_GAP_MS


def set_send_byte_gap(ms):
    """Set an inter-byte gap for send_packet, useful for timing probes."""
    global SEND_BYTE_GAP_MS
    if ms < 0:
        raise ValueError("gap must be >= 0")
    SEND_BYTE_GAP_MS = ms
    print("SEND_BYTE_GAP_MS=", SEND_BYTE_GAP_MS)
