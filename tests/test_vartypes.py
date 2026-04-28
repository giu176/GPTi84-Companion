import pytest

from vartypes import (
    T_REAL, T_LIST, T_PROG, T_PROG_LOCKED, T_STRING, T_VAR_STRNG,
    list_name_82, real_name, prog_name, str_name, make_var_header,
    parse_real_str, parse_real, parse_real_list_str,
    encode_real, encode_real_list,
)


def test_list_name_82_l1():
    # L1 -> 5D 00 00 00 00 00 00 00
    assert list_name_82(0) == bytes([0x5D, 0x00, 0, 0, 0, 0, 0, 0])
    assert list_name_82(1) == bytes([0x5D, 0x01, 0, 0, 0, 0, 0, 0])


def test_real_name_a():
    assert real_name("A") == b"A\x00\x00\x00\x00\x00\x00\x00"
    with pytest.raises(ValueError):
        real_name("a")
    with pytest.raises(ValueError):
        real_name("AB")


def test_prog_name_padding_and_validation():
    assert prog_name("SEX") == b"SEX\x00\x00\x00\x00\x00"
    assert prog_name("FLAPBIRD") == b"FLAPBIRD"
    with pytest.raises(ValueError):
        prog_name("")
    with pytest.raises(ValueError):
        prog_name("TOOLONGNAME")
    with pytest.raises(ValueError):
        prog_name("lower")


def test_str_name_str1_str2():
    # tStr1 = 0, tStr2 = 1; name8 = [0xAA, idx, 0,0,0,0,0,0].
    assert str_name(1) == bytes([T_VAR_STRNG, 0x00, 0, 0, 0, 0, 0, 0])
    assert str_name(2) == bytes([T_VAR_STRNG, 0x01, 0, 0, 0, 0, 0, 0])


def test_str_name_str0_is_slot_9():
    # The calc displays Str0 last but stores it at index 9.
    assert str_name(0) == bytes([T_VAR_STRNG, 0x09, 0, 0, 0, 0, 0, 0])


def test_str_name_invalid():
    with pytest.raises(ValueError):
        str_name(10)
    with pytest.raises(ValueError):
        str_name(-1)


def test_t_string_is_4():
    # StrngObj per ti83plus.inc.
    assert T_STRING == 0x04


def test_make_var_header_82_real_a():
    """Linkguide RTS Real "A" body: 09 00 00 41 00 00 00 00 00 00 00 (11 bytes)."""
    hdr = make_var_header(9, T_REAL, real_name("A"), proto=82)
    assert hdr == bytes([0x09, 0x00, 0x00, 0x41, 0x00, 0x00, 0x00, 0x00,
                         0x00, 0x00, 0x00])
    assert len(hdr) == 11


def test_make_var_header_83p_real_a_pads_two_zeros():
    hdr = make_var_header(9, T_REAL, real_name("A"), proto=83)
    assert len(hdr) == 13
    assert hdr[-2:] == b"\x00\x00"


def test_make_var_header_rejects_wrong_name_length():
    with pytest.raises(ValueError):
        make_var_header(9, T_REAL, b"A", proto=82)


# --- real codec round-trip ---


@pytest.mark.parametrize("v", [
    0, 1, -1, 1.5, -2.25, 3.0, 1e10, -1e-5, 12345.6789,
])
def test_real_str_round_trip(v):
    enc = encode_real(v)
    assert len(enc) == 9
    # parse_real (lossy) should round-trip floats within tolerance
    if v == 0:
        assert parse_real(enc) == 0
    else:
        assert abs(parse_real(enc) - v) / abs(v) < 1e-12


def test_parse_real_str_specific_values():
    # A=1.5 in TI 9-byte form: sign=0, exp=0x80 (==0), digits 1500...0
    enc = encode_real(1.5)
    assert parse_real_str(enc) == "1.5"

    # very small negative
    assert parse_real_str(encode_real(-1e-5)) == "-1e-5"


def test_real_list_round_trip():
    values = [1.5, -2.25, 3.0, 1e10, -1e-5]
    payload = encode_real_list(values)

    # 2-byte count + 5 * 9-byte reals = 47 bytes
    assert len(payload) == 2 + 5 * 9 == 47
    assert payload[0] == 5 and payload[1] == 0

    out = parse_real_list_str(payload)
    assert out == ["1.5", "-2.25", "3", "10000000000", "-1e-5"]


def test_type_ids_are_stable():
    """These bytes are part of the wire protocol; locking them prevents
    accidental renumbering during refactors."""
    assert T_REAL == 0x00
    assert T_LIST == 0x01
    assert T_PROG == 0x05
    assert T_PROG_LOCKED == 0x06
