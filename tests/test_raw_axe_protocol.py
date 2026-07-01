import pytest

from src import raw_axe_protocol as raw


def test_raw_frame_round_trips():
    frame = raw.encode(raw.REQUEST, b"LIST")

    assert raw.decode(frame) == (raw.REQUEST, b"LIST")


def test_raw_frame_rejects_checksum_mismatch():
    frame = bytearray(raw.encode(raw.RESPONSE, b"pages:1\nhello"))
    frame[-1] ^= 0x55

    with pytest.raises(raw.RawFrameError, match="checksum"):
        raw.decode(frame)


def test_read_frame_skips_noise_and_reads_payload():
    data = iter([0x00, 0x55, *raw.encode(raw.REQUEST, b"OPEN:1")])

    assert raw.read_frame(lambda _timeout: next(data, None)) == (
        raw.REQUEST,
        b"OPEN:1",
    )


def test_read_frame_reports_partial_timeout():
    data = iter(raw.encode(raw.REQUEST, b"LIST")[:-2])

    with pytest.raises(raw.RawFrameError, match="timed out"):
        raw.read_frame(lambda _timeout: next(data, None))


def test_write_frame_stops_on_send_failure():
    sent = []

    def write_byte(byte, _timeout):
        sent.append(byte)
        return len(sent) < 3

    assert not raw.write_frame(write_byte, raw.ERROR, b"bad")

