import pytest

import ble_protocol as ble


def test_envelope_roundtrip_and_crc_validation():
    packet = ble.encode(ble.REQUEST_CHUNK, 7, 2, 11, 5, b"world")
    decoded = ble.decode(packet)

    assert decoded["type"] == ble.REQUEST_CHUNK
    assert decoded["session_id"] == 7
    assert decoded["sequence"] == 2
    assert decoded["total_length"] == 11
    assert decoded["chunk_offset"] == 5
    assert decoded["chunk"] == b"world"

    corrupt = bytearray(packet)
    corrupt[-1] ^= 1
    with pytest.raises(ValueError, match="CRC"):
        ble.decode(corrupt)


def test_chunk_reassembly_ignores_duplicate_chunks():
    packets = ble.chunk_message(
        ble.RESPONSE_CHUNK,
        session_id=19,
        payload=b"pages:1\nhello",
    )
    assembler = ble.MessageAssembler()
    for packet in packets:
        envelope = ble.decode(packet)
        assembler.add(envelope)
        assembler.add(envelope)

    assert assembler.finish(19) == b"pages:1\nhello"


def test_reassembly_rejects_incomplete_message():
    packets = ble.chunk_message(
        ble.REQUEST_CHUNK,
        session_id=3,
        payload=b"prompt:hello\nmath:\n",
    )
    assembler = ble.MessageAssembler()
    assembler.add(ble.decode(packets[0]))

    assert assembler.finish(3) is None
