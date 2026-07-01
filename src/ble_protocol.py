"""GPTi84 BLE application envelope and reassembly helpers."""

import struct


PROTOCOL_VERSION = 1
HEADER_LEN = 15
DEFAULT_CHUNK_LEN = 5

HELLO = 1
REQUEST_CHUNK = 2
REQUEST_END = 3
ACK = 4
RESPONSE_CHUNK = 5
RESPONSE_END = 6
ERROR = 7
CANCEL = 8
PING = 9
PONG = 10
STATUS = 11


def crc16_ccitt(data):
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def encode(message_type, session_id, sequence, total_length,
           chunk_offset, chunk=b"", flags=0):
    chunk = bytes(chunk)
    if len(chunk) > 0xFFFF or total_length > 0xFFFF:
        raise ValueError("BLE envelope length exceeds u16")
    header = struct.pack(
        ">BBHHHHHBH",
        PROTOCOL_VERSION,
        message_type,
        session_id,
        sequence,
        total_length,
        chunk_offset,
        len(chunk),
        flags,
        0,
    )
    packet = bytearray(header + chunk)
    crc = crc16_ccitt(packet)
    packet[13] = (crc >> 8) & 0xFF
    packet[14] = crc & 0xFF
    return bytes(packet)


def decode(packet):
    packet = bytes(packet)
    if len(packet) < HEADER_LEN:
        raise ValueError("truncated BLE envelope")
    fields = struct.unpack(">BBHHHHHBH", packet[:HEADER_LEN])
    version, message_type, session_id, sequence, total_length, \
        chunk_offset, chunk_length, flags, expected_crc = fields
    if version != PROTOCOL_VERSION:
        raise ValueError("unsupported BLE protocol version")
    if len(packet) != HEADER_LEN + chunk_length:
        raise ValueError("BLE envelope length mismatch")
    check = bytearray(packet)
    check[13] = 0
    check[14] = 0
    if crc16_ccitt(check) != expected_crc:
        raise ValueError("BLE envelope CRC mismatch")
    return {
        "type": message_type,
        "session_id": session_id,
        "sequence": sequence,
        "total_length": total_length,
        "chunk_offset": chunk_offset,
        "flags": flags,
        "chunk": packet[HEADER_LEN:],
    }


def chunk_message(message_type, session_id, payload,
                  chunk_length=DEFAULT_CHUNK_LEN):
    payload = bytes(payload)
    packets = []
    sequence = 0
    for offset in range(0, len(payload), chunk_length):
        packets.append(encode(
            message_type,
            session_id,
            sequence,
            len(payload),
            offset,
            payload[offset:offset + chunk_length],
        ))
        sequence += 1
    return packets


class MessageAssembler:
    def __init__(self):
        self.reset()

    def reset(self):
        self.session_id = None
        self.total_length = None
        self.chunks = {}

    def add(self, envelope):
        session_id = envelope["session_id"]
        if self.session_id is not None and self.session_id != session_id:
            self.reset()
        self.session_id = session_id
        self.total_length = envelope["total_length"]
        self.chunks.setdefault(envelope["chunk_offset"], envelope["chunk"])

    def finish(self, session_id):
        if self.session_id != session_id or self.total_length is None:
            return None
        output = bytearray()
        offset = 0
        while offset < self.total_length:
            chunk = self.chunks.get(offset)
            if chunk is None:
                return None
            output.extend(chunk)
            offset += len(chunk)
        if len(output) != self.total_length:
            return None
        self.reset()
        return bytes(output)
