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
    # 0x68 is tEng (mode token, not in the chat charset) -- decode degrades
    # to '?' instead of crashing.
    assert tokens_to_ascii(bytes([0x68])) == "?"


def test_chs_renders_as_minus_but_minus_encodes_as_sub():
    # tChs (0xB0) and tSub (0x71) both render as "-" on the way out.
    assert tokens_to_ascii(bytes([0xB0])) == "-"
    assert tokens_to_ascii(bytes([0x71])) == "-"
    # On the way in, "-" is always tSub (binary subtraction). Calc parses
    # leading "-" fine because tSub at start of an expression unary-promotes.
    assert ascii_to_tokens("-") == bytes([0x71])


def test_invalid_mode_raises():
    with pytest.raises(ValueError):
        tokens_to_ascii(bytes([0x41]), mode="weird")


# ---- Phase 2: math token decoding (mode-independent) ----

def test_math_function_tokens_decode():
    # Each function token opens its own paren on emit.
    cases = [
        (0xBC, "sqrt("),
        (0xBE, "ln("),
        (0xBF, "e^("),
        (0xC0, "log("),
        (0xC2, "sin("),
        (0xC4, "cos("),
        (0xC6, "tan("),
    ]
    for tok, text in cases:
        assert tokens_to_ascii(bytes([tok])) == text, hex(tok)


def test_constant_tokens_decode():
    assert tokens_to_ascii(bytes([0xAC])) == "pi"
    assert tokens_to_ascii(bytes([0x5B])) == "theta"


def test_postfix_powers_decode():
    # tSqr (0x0D) and tCube (0x0F) emit ^2 and ^3.
    # X^2 on the wire is [tX][tSqr] = [0x58, 0x0D] -> "X^2".
    assert tokens_to_ascii(bytes([0x58, 0x0D])) == "X^2"
    assert tokens_to_ascii(bytes([0x58, 0x0F])) == "X^3"


def test_two_byte_prefix_consumes_next_byte():
    # 0xBB is the extended prefix. We don't expand it yet, but the decoder
    # must consume the second byte so it doesn't get mis-rendered as a
    # standalone token.
    assert tokens_to_ascii(bytes([0xBB, 0x31])) == "?"
    # Same for the other prefix family.
    assert tokens_to_ascii(bytes([0xEF, 0x10])) == "?"
    # And around real tokens: [0xBB, 0x31, tA] -> "?" + "A".
    assert tokens_to_ascii(bytes([0xBB, 0x31, 0x41])) == "?A"


def test_two_byte_prefix_implicit_mult():
    # The '?' from a two-byte prefix shouldn't trigger implicit-mult in
    # either direction (it's an unknown, not a value).
    assert tokens_to_ascii(bytes([0xBB, 0x31, 0x58])) == "?X"
    assert tokens_to_ascii(bytes([0xBB, 0x31, 0x58]), mode="math") == "?X"


# ---- Phase 2: math-mode implicit multiplication ----

def test_math_mode_digit_letter():
    # 2X -> 2*X
    assert tokens_to_ascii(bytes([0x32, 0x58]), mode="math") == "2*X"


def test_math_mode_letter_letter():
    # XY in math mode means X*Y (juxtaposition).
    assert tokens_to_ascii(bytes([0x58, 0x59]), mode="math") == "X*Y"


def test_math_mode_paren_close_value():
    # )X -> )*X, )2 -> )*2
    assert tokens_to_ascii(bytes([0x11, 0x58]), mode="math") == ")*X"
    assert tokens_to_ascii(bytes([0x11, 0x32]), mode="math") == ")*2"


def test_math_mode_value_paren_open():
    # 2( -> 2*(, X( -> X*(
    assert tokens_to_ascii(bytes([0x32, 0x10]), mode="math") == "2*("
    assert tokens_to_ascii(bytes([0x58, 0x10]), mode="math") == "X*("


def test_math_mode_no_mult_after_operator():
    # +X stays +X (no '*' after binary operator).
    assert tokens_to_ascii(bytes([0x70, 0x58]), mode="math") == "+X"
    # 2+X stays 2+X.
    assert tokens_to_ascii(bytes([0x32, 0x70, 0x58]), mode="math") == "2+X"


def test_math_mode_no_mult_inside_function_call():
    # sin(X) -> sin(X). After 'sin(' the last char is '(' (not a value-
    # producer), so X doesn't get '*' prefixed.
    assert tokens_to_ascii(bytes([0xC2, 0x58, 0x11]), mode="math") == "sin(X)"


def test_math_mode_implicit_mult_with_pi():
    assert tokens_to_ascii(bytes([0x32, 0xAC]), mode="math") == "2*pi"
    assert tokens_to_ascii(bytes([0xAC, 0x32]), mode="math") == "pi*2"
    assert tokens_to_ascii(bytes([0x58, 0xAC]), mode="math") == "X*pi"


def test_math_mode_implicit_mult_after_postfix_power():
    # X^2 followed by Y -> "X^2*Y".
    assert tokens_to_ascii(bytes([0x58, 0x0D, 0x59]), mode="math") == "X^2*Y"


# ---- Phase 2: text mode (default) ----

def test_text_mode_letters_stay_words():
    # 'HELLO' is a word, not H*E*L*L*O.
    assert tokens_to_ascii(b"HELLO") == "HELLO"
    # 'XY' is two adjacent letters in prose -- leave alone.
    assert tokens_to_ascii(b"XY") == "XY"


def test_text_mode_digit_then_letter_still_inserts_star():
    # '2X' is unambiguously math even in chat -- '2*X' is recoverable, but
    # leaving it as '2X' loses meaning if it really is math.
    assert tokens_to_ascii(bytes([0x32, 0x58])) == "2*X"


def test_text_mode_digit_then_open_paren_inserts_star():
    # '5(' -> '5*('
    assert tokens_to_ascii(bytes([0x35, 0x10])) == "5*("


def test_text_mode_no_star_after_close_paren():
    # ')X' in text stays ')X'. In chat, parens around words ('(hi)there')
    # are common and shouldn't get a '*' welded on.
    assert tokens_to_ascii(bytes([0x11, 0x58])) == ")X"


def test_text_mode_chat_phrase_round_trips():
    s = "ECHO 2026"
    # ECHO has letters only (no implicit-mult in text), then space, then
    # digits. Should come back identical.
    assert tokens_to_ascii(ascii_to_tokens(s)) == s


def test_text_mode_pi_in_prose():
    # 'pi' tokens in text decode as the word 'pi', no surrounding mult.
    # 'I LIKE pi' (encoded with explicit pi token) -> 'I LIKE pi'.
    wire = ascii_to_tokens("I LIKE ") + bytes([0xAC])
    assert tokens_to_ascii(wire) == "I LIKE pi"


# ---- Phase 2: end-to-end-shaped expressions (math mode) ----

def test_math_decode_sin_pi_over_4():
    # sin(pi/4) -- bytes: [tSin][tPi][tDiv][t4][t)] -> "sin(pi/4)".
    wire = bytes([0xC2, 0xAC, 0x83, 0x34, 0x11])
    assert tokens_to_ascii(wire, mode="math") == "sin(pi/4)"


def test_math_decode_2x_plus_5():
    # "2X+5" -> bytes [t2][tX][tAdd][t5] -> "2*X+5"
    wire = bytes([0x32, 0x58, 0x70, 0x35])
    assert tokens_to_ascii(wire, mode="math") == "2*X+5"


def test_math_decode_multi_digit_number_stays_intact():
    # 1024X -> "1024*X", not "1*0*2*4*X". Multi-digit numbers are one value.
    wire = bytes([0x31, 0x30, 0x32, 0x34, 0x58])
    assert tokens_to_ascii(wire, mode="math") == "1024*X"


def test_math_decode_x_squared_minus_4_eq_0():
    # X^2-4=0 -> bytes [tX][tSqr][tSub][t4][tEQ][t0] -> "X^2-4=0"
    wire = bytes([0x58, 0x0D, 0x71, 0x34, 0x6A, 0x30])
    assert tokens_to_ascii(wire, mode="math") == "X^2-4=0"


def test_math_decode_paren_X_plus_1_squared():
    # (X+1)^2 -> [(][tX][tAdd][t1][)][tSqr] -> "(X+1)^2"
    wire = bytes([0x10, 0x58, 0x70, 0x31, 0x11, 0x0D])
    assert tokens_to_ascii(wire, mode="math") == "(X+1)^2"


# ---- Two-byte tokens: list / matrix / picture / GDB / StrN ----

def test_two_byte_list_l1_decodes():
    # 0x5D 0x00 is L1.
    assert tokens_to_ascii(bytes([0x5D, 0x00])) == "L1"
    assert tokens_to_ascii(bytes([0x5D, 0x05])) == "L6"


def test_two_byte_list_unknown_sub_falls_through():
    # Custom-name lists use sub-bytes >= 0x06 with extra trailing bytes;
    # we don't decode those and emit '?' instead. Important: still
    # consumes exactly one sub-byte so the next token doesn't get eaten.
    assert tokens_to_ascii(bytes([0x5D, 0x40, 0x41])) == "?A"


def test_two_byte_matrix_decodes_with_brackets():
    # [MatA] -- bracketed so a downstream parser can tell it apart from
    # the four-letter word 'MATA'.
    assert tokens_to_ascii(bytes([0x5C, 0x00])) == "[MatA]"
    assert tokens_to_ascii(bytes([0x5C, 0x09])) == "[MatJ]"


def test_two_byte_picture_and_gdb_decode():
    # Pic1..Pic9 then Pic0 (sub byte 0x09 maps to Pic0). Same pattern for GDB.
    assert tokens_to_ascii(bytes([0x60, 0x00])) == "Pic1"
    assert tokens_to_ascii(bytes([0x60, 0x09])) == "Pic0"
    assert tokens_to_ascii(bytes([0x61, 0x00])) == "GDB1"
    assert tokens_to_ascii(bytes([0x61, 0x09])) == "GDB0"


def test_two_byte_strn_decodes():
    # An embedded Str ref shows the slot it points at.
    assert tokens_to_ascii(bytes([0xAA, 0x00])) == "Str1"
    assert tokens_to_ascii(bytes([0xAA, 0x09])) == "Str0"


def test_extended_prefix_still_unknown():
    # 0xBB is still unmapped -- we have no entries for the extended family.
    # Important regression: the prefix must still be recognised so the
    # second byte is consumed (not mis-decoded as a standalone token).
    assert tokens_to_ascii(bytes([0xBB, 0x31])) == "?"
    assert tokens_to_ascii(bytes([0xEF, 0x10])) == "?"


def test_math_mode_implicit_mult_around_list_token():
    # 2L1 -> '2*L1' (digit then value-starter 'L').
    assert tokens_to_ascii(bytes([0x32, 0x5D, 0x00]), mode="math") == "2*L1"
    # L1+L2 has no juxtaposition, no extra '*'.
    assert tokens_to_ascii(bytes([0x5D, 0x00, 0x70, 0x5D, 0x01]),
                           mode="math") == "L1+L2"
    # L1X -> 'L1*X'. The trailing '1' is a digit (value-producer); 'X' is
    # a value-starter; '*' inserts.
    assert tokens_to_ascii(bytes([0x5D, 0x00, 0x58]), mode="math") == "L1*X"


def test_math_mode_implicit_mult_around_matrix_token():
    # 2[MatA] -> '2*[MatA]' ('[' counts as a value-starter).
    assert tokens_to_ascii(bytes([0x32, 0x5C, 0x00]), mode="math") == "2*[MatA]"
    # [MatA]X -> '[MatA]*X' (']' counts as a value-producer).
    assert tokens_to_ascii(bytes([0x5C, 0x00, 0x58]), mode="math") == "[MatA]*X"
    # Two matrices side by side: matrix multiplication.
    assert tokens_to_ascii(bytes([0x5C, 0x00, 0x5C, 0x01]),
                           mode="math") == "[MatA]*[MatB]"


def test_text_mode_no_mult_inside_list_label():
    # 'L1' in text shouldn't internally split as 'L*1'. The decoder emits
    # 'L1' as one piece, so there's no chance to insert a '*' inside it.
    assert tokens_to_ascii(bytes([0x5D, 0x00])) == "L1"
    # 'CHECK L1' -- letters then space then 'L1'. Space is tSpace (0x29).
    wire = bytes([0x43, 0x48, 0x45, 0x43, 0x4B, 0x29, 0x5D, 0x00])
    assert tokens_to_ascii(wire) == "CHECK L1"


def test_truncated_two_byte_prefix_at_eof():
    # Lone prefix at the very end (no sub byte to consume) shouldn't crash.
    assert tokens_to_ascii(bytes([0x5D])) == "?"
    assert tokens_to_ascii(bytes([0x41, 0x5D])) == "A?"
