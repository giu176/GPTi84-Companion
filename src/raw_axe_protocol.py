"""Raw calculator-link framing for the Axe-native GPTi84 app.

Frame:
  0x7E type len_lo len_hi payload... xor

The checksum is XOR(type, len_lo, len_hi, every payload byte). It is not
cryptographic; it only catches common line noise and framing mistakes on the
short calculator-to-Pico link. The phone-side BLE transport still has its own
CRC/session layer.
"""

START = 0x7E

REQUEST = 0x01
RESPONSE = 0x02
STATUS = 0x03
ERROR = 0x7F

MAX_PAYLOAD = 1024


class RawFrameError(Exception):
    pass


def checksum(frame_type, payload):
    payload = bytes(payload)
    value = frame_type ^ (len(payload) & 0xFF) ^ ((len(payload) >> 8) & 0xFF)
    for byte in payload:
        value ^= byte
    return value & 0xFF


def encode(frame_type, payload=b""):
    payload = bytes(payload)
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("raw Axe payload too large")
    return bytes((
        START,
        frame_type,
        len(payload) & 0xFF,
        (len(payload) >> 8) & 0xFF,
    )) + payload + bytes((checksum(frame_type, payload),))


def decode(frame):
    frame = bytes(frame)
    if len(frame) < 5:
        raise RawFrameError("raw Axe frame is too short")
    if frame[0] != START:
        raise RawFrameError("raw Axe frame has bad start byte")
    frame_type = frame[1]
    length = frame[2] | (frame[3] << 8)
    if length > MAX_PAYLOAD:
        raise RawFrameError("raw Axe payload is too large")
    if len(frame) != length + 5:
        raise RawFrameError("raw Axe frame length mismatch")
    payload = frame[4:4 + length]
    got = frame[-1]
    want = checksum(frame_type, payload)
    if got != want:
        raise RawFrameError("raw Axe checksum mismatch")
    return frame_type, payload


def read_frame(read_byte, timeout_ms=1000):
    """Read one frame using a callable compatible with wire.recv_byte."""
    while True:
        first = read_byte(timeout_ms)
        if first is None:
            return None
        if first == START:
            break
    header = [START]
    for _ in range(3):
        byte = read_byte(timeout_ms)
        if byte is None:
            raise RawFrameError("raw Axe frame header timed out")
        header.append(byte)
    length = header[2] | (header[3] << 8)
    if length > MAX_PAYLOAD:
        raise RawFrameError("raw Axe payload is too large")
    body = []
    for _ in range(length + 1):
        byte = read_byte(timeout_ms)
        if byte is None:
            raise RawFrameError("raw Axe frame body timed out")
        body.append(byte)
    return decode(bytes(header + body))


def write_frame(write_byte, frame_type, payload=b"", timeout_ms=1000):
    for byte in encode(frame_type, payload):
        if not write_byte(byte, timeout_ms):
            return False
    return True

