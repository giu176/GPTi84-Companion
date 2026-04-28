"""TI-83+/84+ token <-> ASCII translation for String var payloads.

A TI String var on the wire is a token stream (same encoding TI-BASIC programs
use), not raw ASCII. Letters A..Z and digits 0..9 happen to share their ASCII
code points, but space is 0x29 (not 0x20), most punctuation differs, and math
functions are single-byte tokens (sin=0xC2, sqrt=0xBC, pi=0xAC, ...).

This module is the boundary that lets the desktop see plain text. The decode
path (tokens_to_ascii) has two modes:

  text mode (default): for chat / prose. Letters stay as words: 'HELLO' is
    'HELLO', not 'H*E*L*L*O'. Math tokens still decode (so 'pi' and 'sin('
    work in prose), but no implicit-mult is inserted between letters.

  math mode: for equations. Inserts '*' between juxtaposed value tokens so
    'XY' is 'X*Y', '2X' is '2*X', '2sin(X)' is '2*sin(X)'. Output is parsable
    by SymPy and readable by an LLM.

Mode is selected by the caller because the wire can't distinguish: 'HELLO' and
'H*E*L*L*O' are both five letter tokens. The bridge picks the mode based on
which Str slot the payload arrived in (Str1 = text, Str2 = math).

The encode path (ascii_to_tokens) is strict and only handles the ASCII subset
our reply path produces. Asymmetric on purpose: decode is best-effort
(unknown bytes become '?'); encode is strict (unknown chars raise).

Two-byte token prefixes (0xBB, 0xEF, plus the matrix/list/picture/GDB/sysstr
families) are detected and consume their second byte without expanding into
the table; they emit '?' until something useful uses them.
"""


# Single-byte token -> ASCII string. Multi-char emissions are intentional:
# 'sin(' opens its own paren, 'pi'/'theta' are word-shaped values, '^2'/'^3'
# are postfix exponents.
_TOK_TO_ASCII = {
    # Postfix powers (tSqr 0x0D = ^2, tCube 0x0F = ^3).
    0x0D: "^2",
    0x0F: "^3",
    # Punctuation and operators.
    0x10: "(",
    0x11: ")",
    0x29: " ",     # tSpace
    0x2A: '"',     # tString (the literal " char inside a quoted string)
    0x2B: ",",     # tComma
    0x3A: ".",     # tDecPt
    0x3E: ":",     # tColon
    0x5B: "theta", # tTheta
    0x6A: "=",     # tEQ (relational equals; not the STO-> arrow)
    0x6B: "<",
    0x6C: ">",
    0x70: "+",     # tAdd
    0x71: "-",     # tSub
    0x82: "*",     # tMul
    0x83: "/",     # tDiv
    0xAC: "pi",    # tPi
    0xB0: "-",     # tChs (unary negate); same glyph as subtraction in plain text
    0xBC: "sqrt(", # tSqrt (opens its own paren)
    0xBE: "ln(",
    0xBF: "e^(",   # tExp -- 'e raised to', written with explicit base for SymPy
    0xC0: "log(",
    0xC2: "sin(",
    0xC4: "cos(",
    0xC6: "tan(",
    0xF0: "^",     # tPower
}

# Two-byte token prefixes. When the decoder sees one of these as the lead
# byte, it consumes the next byte too and emits '?'. Adding real entries
# means switching to a {(prefix, lo): "string"} table; we don't need it yet.
_TWO_BYTE_PREFIXES = frozenset((
    0x5C,  # matrix
    0x5D,  # list
    0x60,  # picture
    0x62,  # GDB lo
    0x63,  # GDB hi
    0xAA,  # system string itself (StrN)
    0x7E,  # mode/menu
    0xBB,  # extended
    0xEF,  # newer-OS extended
))


# ASCII -> single-byte token. Only chars our reply path actually produces.
# Multi-char tokens like 'pi'/'sin(' are decode-only -- the desktop never
# needs to encode 'sin(' back into a calc-side token stream in v2.
_ASCII_TO_TOK = {
    "(": 0x10, ")": 0x11, " ": 0x29, '"': 0x2A, ",": 0x2B, ".": 0x3A,
    ":": 0x3E, "=": 0x6A, "<": 0x6B, ">": 0x6C,
    "+": 0x70, "-": 0x71, "*": 0x82, "/": 0x83, "^": 0xF0,
}

# Identity for letters and digits.
for _ch in range(ord("A"), ord("Z") + 1):
    _ASCII_TO_TOK[chr(_ch)] = _ch
for _ch in range(ord("0"), ord("9") + 1):
    _ASCII_TO_TOK[chr(_ch)] = _ch


def _is_math_value_producer(ch):
    """Math-mode rule: last emitted char closes a value. Digits, letters, ')'.
    ')' also covers '^2'/'^3' (they end in a digit, also a value-producer)."""
    if not ch:
        return False
    return ch.isalnum() or ch == ")"


def _is_text_value_producer(ch):
    """Text-mode rule: only digits trigger implicit-mult. 'HELLO' stays
    'HELLO', but '2X' / '2pi' / '5(' still get the '*' insertion because
    digit-then-value is unambiguous even in prose. Note: the caller also
    suppresses '*' when the *next* char is also a digit, so multi-digit
    numbers ('2026') stay intact."""
    return bool(ch) and ch.isdigit()


def _is_value_starter(ch):
    """First emitted char of a token opens a value -- needs '*' after a
    preceding value-producer. Digits, letters, '('."""
    if not ch:
        return False
    return ch.isalnum() or ch == "("


def tokens_to_ascii(tok_bytes, mode="text"):
    """Translate a token byte sequence to ASCII. Returns str.

    mode='text' (default): chat / prose. Only digit-then-value-starter gets
      a '*' inserted ('2X' -> '2*X'); letter juxtaposition is left alone
      ('HELLO' -> 'HELLO', 'XY' -> 'XY').

    mode='math': equation. Any value-producer followed by a value-starter
      gets a '*' ('XY' -> 'X*Y', '2sin(X)' -> '2*sin(X)').

    Best-effort: unmapped bytes render as '?'. Two-byte token prefixes
    consume the next byte and emit a single '?'.
    """
    if mode == "math":
        is_producer = _is_math_value_producer
    elif mode == "text":
        is_producer = _is_text_value_producer
    else:
        raise ValueError("tokens_to_ascii mode must be 'text' or 'math'")
    out = []
    last_emitted = ""
    i = 0
    n = len(tok_bytes)
    while i < n:
        b = tok_bytes[i]
        if b in _TWO_BYTE_PREFIXES:
            piece = "?"
            i += 2  # consume prefix + next byte unconditionally
        else:
            i += 1
            if 0x41 <= b <= 0x5A or 0x30 <= b <= 0x39:
                piece = chr(b)
            elif b in _TOK_TO_ASCII:
                piece = _TOK_TO_ASCII[b]
            else:
                piece = "?"
        # Suppress '*' between consecutive digits so multi-digit numbers
        # stay intact ('2026' is one number, not 2*0*2*6).
        if (piece
                and is_producer(last_emitted)
                and _is_value_starter(piece[0])
                and not (last_emitted.isdigit() and piece[0].isdigit())):
            out.append("*")
        out.append(piece)
        if piece:
            last_emitted = piece[-1]
    return "".join(out)


def ascii_to_tokens(s):
    """Translate ASCII text to a token byte sequence. Lowercase letters are
    upcased (the calc has no lowercase tokens by default). Unknown chars
    raise ValueError -- the caller should sanitise before this point.
    Returns bytes.
    """
    out = bytearray()
    for ch in s:
        if "a" <= ch <= "z":
            ch = ch.upper()
        if ch not in _ASCII_TO_TOK:
            raise ValueError("no token mapping for ASCII char {!r}".format(ch))
        out.append(_ASCII_TO_TOK[ch])
    return bytes(out)


def ascii_to_tokens_lossy(s, drop_unknown=True):
    """Like ascii_to_tokens but drops (or replaces with space) unmapped chars
    instead of raising. Used on the reply path where the desktop may produce
    chars the calc charset doesn't represent."""
    out = bytearray()
    for ch in s:
        if "a" <= ch <= "z":
            ch = ch.upper()
        if ch in _ASCII_TO_TOK:
            out.append(_ASCII_TO_TOK[ch])
        elif not drop_unknown:
            out.append(0x29)  # tSpace
    return bytes(out)
