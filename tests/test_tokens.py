import pytest

from tokens import (
    ascii_to_tokens,
    ascii_to_tokens_lossy,
    tokens_to_ascii,
)


def test_letters_digits_identity():
    # A..Z and 0..9 share their ASCII code points with the calc charset.
    s = "HELLO 2026"
    toks = ascii_to_tokens(s)
    # 'HELLO' = ASCII letters, ' ' = 0x29 tSpace, digits = ASCII.
    assert toks == bytes([0x48, 0x45, 0x4C, 0x4C, 0x4F, 0x29, 0x32, 0x30, 0x32, 0x36])


def test_space_is_tspace_not_ascii_space():
    # The whole point of this module: " " is 0x29, NOT 0x20.
    assert ascii_to_tokens(" ") == bytes([0x29])
    assert tokens_to_ascii(bytes([0x29])) == " "
    assert tokens_to_ascii(bytes([0x20])) == "?"  # ASCII space is not a token


def test_punctuation_basics():
    pairs = [
        ("(", 0x10), (")", 0x11), (",", 0x2B), (".", 0x3A), (":", 0x3E),
        ("=", 0x6A), ("<", 0x6B), (">", 0x6C),
        ("+", 0x70), ("-", 0x71), ("*", 0x82), ("/", 0x83),
        ("^", 0xF0),
    ]
    for ch, tok in pairs:
        assert ascii_to_tokens(ch) == bytes([tok]), ch
        assert tokens_to_ascii(bytes([tok])) == ch, hex(tok)


def test_lowercase_upcased_on_encode():
    assert ascii_to_tokens("hello") == ascii_to_tokens("HELLO")


def test_unknown_ascii_strict_raises():
    with pytest.raises(ValueError):
        ascii_to_tokens("HELLO!")  # ! has no Phase 1 mapping


def test_unknown_ascii_lossy_drops():
    # ! gets dropped; rest passes through.
    assert ascii_to_tokens_lossy("HI!") == ascii_to_tokens("HI")


def test_unknown_token_renders_as_question_mark():
    # 0xC2 is tSin (not in Phase 1) -- decode degrades to '?' instead of crashing.
    assert tokens_to_ascii(bytes([0xC2])) == "?"


def test_roundtrip_ascii_subset():
    s = "ECHO 2X+SIN+5"
    # SIN is letters S, I, N here (not the sin function token), so this
    # should round-trip identically.
    assert tokens_to_ascii(ascii_to_tokens(s)) == s


def test_chs_renders_as_minus_but_minus_encodes_as_sub():
    # tChs (0xB0) and tSub (0x71) both render as "-" on the way out.
    assert tokens_to_ascii(bytes([0xB0])) == "-"
    assert tokens_to_ascii(bytes([0x71])) == "-"
    # On the way in, "-" is always tSub (binary subtraction). Calc parses
    # leading "-" fine because tSub at start of an expression unary-promotes.
    assert ascii_to_tokens("-") == bytes([0x71])
