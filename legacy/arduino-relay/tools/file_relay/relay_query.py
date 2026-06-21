#!/usr/bin/env python3
"""Read query.txt, relay it over an Arduino serial bridge, and write query_reply.txt."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import random
import struct
import sys
import time
import zlib

try:
    import serial
except ImportError:
    serial = None

from protocol import Frame, MessageType, ProtocolError, StreamDecoder, encode_frame

QUERY_LIMIT = 4096
RESPONSE_LIMIT = 16384
CHUNK_SIZE = 128


class RelayFailure(RuntimeError):
    pass


class SerialRelay:
    def __init__(self, port: str, baud: int = 115200, timeout: float = 120.0):
        if serial is None:
            raise RelayFailure("pyserial is missing; run: python -m pip install -r requirements.txt")
        self.serial = serial.Serial(port, baudrate=baud, timeout=0.1, write_timeout=2)
        # Opening a Uno's USB serial port toggles DTR and resets the ATmega328P.
        # Wait for the bootloader and setup() before sending the binary HELLO.
        time.sleep(2.0)
        self.serial.reset_input_buffer()
        self.decoder = StreamDecoder()
        self.sequence = random.randrange(1, 65535)
        self.timeout = timeout

    def close(self) -> None:
        self.serial.close()

    def next_sequence(self) -> int:
        value = self.sequence
        self.sequence = 1 if value == 0xFFFF else value + 1
        return value

    def send(self, frame: Frame) -> None:
        self.serial.write(encode_frame(frame))
        self.serial.flush()

    def read_frames(self, deadline: float):
        while time.monotonic() < deadline:
            data = self.serial.read(256)
            if data:
                try:
                    yield from self.decoder.feed(data)
                except ProtocolError as exc:
                    print(f"protocol warning: {exc}", file=sys.stderr)

    def send_reliable(self, message_type: MessageType, transaction_id: int, payload: bytes) -> None:
        sequence = self.next_sequence()
        frame = Frame(message_type, sequence, transaction_id, payload)
        for attempt in range(1, 4):
            self.send(frame)
            deadline = time.monotonic() + 2.0
            for incoming in self.read_frames(deadline):
                if incoming.type == MessageType.ACK and incoming.sequence == sequence:
                    return
                self._print_sideband(incoming)
            print(f"retry {attempt}/3 for sequence {sequence}", file=sys.stderr)
        raise RelayFailure(f"no ACK for sequence {sequence}")

    @staticmethod
    def _print_sideband(frame: Frame) -> None:
        if frame.type == MessageType.STATUS:
            print(f"status: {frame.payload.decode('utf-8', 'replace')}")
        elif frame.type in (MessageType.ERROR, MessageType.NACK):
            raise RelayFailure(frame.payload.replace(b"\0", b": ").decode("utf-8", "replace"))

    def handshake(self) -> None:
        sequence = self.next_sequence()
        self.send(Frame(MessageType.HELLO, sequence, 0, b"WINDOWS-FILE-RELAY"))
        deadline = time.monotonic() + 3.0
        for frame in self.read_frames(deadline):
            if frame.type == MessageType.HELLO_ACK:
                print("bridge:", frame.payload.decode("utf-8", "replace"))
                return
            self._print_sideband(frame)
        raise RelayFailure("Arduino bridge did not answer HELLO")

    def request(self, query: bytes, transaction_id: int) -> bytes:
        self.send_reliable(MessageType.REQUEST_BEGIN, transaction_id, struct.pack("<I", len(query)))
        for offset in range(0, len(query), CHUNK_SIZE):
            self.send_reliable(MessageType.REQUEST_CHUNK, transaction_id, query[offset: offset + CHUNK_SIZE])
        self.send_reliable(MessageType.REQUEST_END, transaction_id, struct.pack("<I", zlib.crc32(query)))

        response = bytearray()
        declared_length = None
        deadline = time.monotonic() + self.timeout
        for frame in self.read_frames(deadline):
            if frame.type == MessageType.STATUS:
                self._print_sideband(frame)
                continue
            if frame.type == MessageType.ERROR:
                self._print_sideband(frame)
            if frame.transaction_id != transaction_id:
                continue
            if frame.type == MessageType.RESPONSE_BEGIN:
                if len(frame.payload) != 4:
                    raise RelayFailure("invalid RESPONSE_BEGIN")
                declared_length = struct.unpack("<I", frame.payload)[0]
                if declared_length > RESPONSE_LIMIT:
                    raise RelayFailure("response exceeds local limit")
                self.send(Frame(MessageType.ACK, frame.sequence, transaction_id))
            elif frame.type == MessageType.RESPONSE_CHUNK:
                response.extend(frame.payload)
                if len(response) > RESPONSE_LIMIT:
                    raise RelayFailure("response exceeds local limit")
                self.send(Frame(MessageType.ACK, frame.sequence, transaction_id))
            elif frame.type == MessageType.RESPONSE_END:
                self.send(Frame(MessageType.ACK, frame.sequence, transaction_id))
                if len(frame.payload) != 4:
                    raise RelayFailure("invalid RESPONSE_END")
                expected_crc = struct.unpack("<I", frame.payload)[0]
                if declared_length != len(response):
                    raise RelayFailure("response length mismatch")
                if zlib.crc32(response) != expected_crc:
                    raise RelayFailure("response CRC mismatch")
                return bytes(response)
        raise RelayFailure("timed out waiting for provider response")


def atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True, help="Arduino serial port, for example COM5")
    parser.add_argument("--query", type=Path, default=Path("query.txt"))
    parser.add_argument("--reply", type=Path, default=Path("query_reply.txt"))
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    try:
        query = args.query.read_text(encoding="utf-8-sig").encode("utf-8")
        if not query.strip():
            raise RelayFailure("query file is empty")
        if len(query) > QUERY_LIMIT:
            raise RelayFailure(f"query is {len(query)} bytes; maximum is {QUERY_LIMIT}")
        transaction_id = random.randrange(1, 0xFFFFFFFF)
        relay = SerialRelay(args.port, timeout=args.timeout)
        try:
            relay.handshake()
            response = relay.request(query, transaction_id)
        finally:
            relay.close()
        text = response.decode("utf-8")
        atomic_write(args.reply, text)
        print("\n--- reply ---\n" + text)
        return 0
    except (OSError, UnicodeError, RelayFailure) as exc:
        message = f"[ERROR] {exc}"
        atomic_write(args.reply, message)
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
