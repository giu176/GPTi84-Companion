import random
import unittest

from protocol import (
    Frame,
    MessageType,
    ProtocolError,
    StreamDecoder,
    cobs_decode,
    cobs_encode,
    crc16_ccitt,
    decode_frame,
    encode_frame,
)


class ProtocolTests(unittest.TestCase):
    def test_known_crc(self):
        self.assertEqual(crc16_ccitt(b"123456789"), 0x29B1)

    def test_cobs_round_trip(self):
        for length in range(260):
            data = bytes(random.randrange(256) for _ in range(length))
            self.assertEqual(cobs_decode(cobs_encode(data)), data)

    def test_frame_round_trip(self):
        original = Frame(MessageType.REQUEST_CHUNK, 42, 0x12345678, b"hello\0world")
        self.assertEqual(decode_frame(encode_frame(original)), original)

    def test_fragmented_stream(self):
        frames = [Frame(MessageType.STATUS, i, 7, f"item-{i}".encode()) for i in range(10)]
        wire = b"".join(encode_frame(frame) for frame in frames)
        decoder = StreamDecoder()
        decoded = []
        for byte in wire:
            decoded.extend(decoder.feed(bytes([byte])))
        self.assertEqual(decoded, frames)

    def test_corrupt_frame_rejected(self):
        wire = bytearray(encode_frame(Frame(MessageType.PING, 1)))
        wire[3] ^= 0x55
        with self.assertRaises(ProtocolError):
            decode_frame(bytes(wire))


if __name__ == "__main__":
    unittest.main()
