"""Wire protocol shared by the Windows file relay tests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import struct

VERSION = 1
MAX_PAYLOAD = 128
HEADER = struct.Struct("<BBBHIH")


class MessageType(IntEnum):
    HELLO = 0x01
    HELLO_ACK = 0x02
    PING = 0x03
    PONG = 0x04
    REQUEST_BEGIN = 0x10
    REQUEST_CHUNK = 0x11
    REQUEST_END = 0x12
    RESPONSE_BEGIN = 0x20
    RESPONSE_CHUNK = 0x21
    RESPONSE_END = 0x22
    STATUS = 0x30
    ACK = 0x31
    NACK = 0x32
    ERROR = 0x33
    CANCEL = 0x34


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class Frame:
    type: MessageType
    sequence: int
    transaction_id: int = 0
    payload: bytes = b""
    flags: int = 0


def crc16_ccitt(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def cobs_encode(data: bytes) -> bytes:
    output = bytearray([0])
    code_index = 0
    code = 1
    for value in data:
        if value == 0:
            output[code_index] = code
            code_index = len(output)
            output.append(0)
            code = 1
        else:
            output.append(value)
            code += 1
            if code == 0xFF:
                output[code_index] = code
                code_index = len(output)
                output.append(0)
                code = 1
    output[code_index] = code
    return bytes(output)


def cobs_decode(data: bytes) -> bytes:
    if not data:
        raise ProtocolError("empty COBS packet")
    output = bytearray()
    index = 0
    while index < len(data):
        code = data[index]
        if code == 0:
            raise ProtocolError("zero byte inside COBS packet")
        index += 1
        end = index + code - 1
        if end > len(data):
            raise ProtocolError("truncated COBS packet")
        output.extend(data[index:end])
        index = end
        if code != 0xFF and index < len(data):
            output.append(0)
    return bytes(output)


def encode_frame(frame: Frame) -> bytes:
    if len(frame.payload) > MAX_PAYLOAD:
        raise ProtocolError("payload exceeds 128 bytes")
    body = HEADER.pack(
        VERSION,
        int(frame.type),
        frame.flags & 0xFF,
        frame.sequence & 0xFFFF,
        frame.transaction_id & 0xFFFFFFFF,
        len(frame.payload),
    ) + frame.payload
    decoded = body + struct.pack("<H", crc16_ccitt(body))
    return cobs_encode(decoded) + b"\x00"


def decode_frame(packet: bytes) -> Frame:
    if packet.endswith(b"\x00"):
        packet = packet[:-1]
    decoded = cobs_decode(packet)
    if len(decoded) < HEADER.size + 2:
        raise ProtocolError("frame too short")
    body, received_crc = decoded[:-2], struct.unpack("<H", decoded[-2:])[0]
    if crc16_ccitt(body) != received_crc:
        raise ProtocolError("CRC mismatch")
    version, type_value, flags, sequence, transaction_id, length = HEADER.unpack(body[: HEADER.size])
    if version != VERSION:
        raise ProtocolError(f"unsupported version {version}")
    payload = body[HEADER.size:]
    if length != len(payload) or length > MAX_PAYLOAD:
        raise ProtocolError("invalid payload length")
    try:
        message_type = MessageType(type_value)
    except ValueError as exc:
        raise ProtocolError(f"unknown message type {type_value:#x}") from exc
    return Frame(message_type, sequence, transaction_id, payload, flags)


class StreamDecoder:
    def __init__(self, maximum_encoded_size: int = 160):
        self._buffer = bytearray()
        self._maximum = maximum_encoded_size

    def feed(self, data: bytes) -> list[Frame]:
        frames: list[Frame] = []
        for value in data:
            if value == 0:
                if self._buffer:
                    frames.append(decode_frame(bytes(self._buffer)))
                    self._buffer.clear()
            elif len(self._buffer) >= self._maximum:
                self._buffer.clear()
                raise ProtocolError("encoded frame overflow")
            else:
                self._buffer.append(value)
        return frames

