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

Two-byte token prefixes are detected and consume their second byte. The
matrix/list/picture/GDB/StrN families decode to their human-readable names
(L1..L6, [MatA]..[MatJ], Pic1..Pic0, GDB1..GDB0, Str1..Str0) so an LLM or
SymPy consumer can see what variable was referenced. Other prefixes
(0x7E mode/menu, 0xBB and 0xEF extended) still emit '?'.
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
# byte, it consumes the next byte too. If a sub-byte mapping exists in
# _TWO_BYTE_TO_ASCII below, that name is emitted; otherwise '?'.
_TWO_BYTE_PREFIXES = frozenset((
    0x5C,  # matrix         -- sub: tMatA..tMatJ -> [MatA]..[MatJ]
    0x5D,  # list           -- sub: tL1..tL6     -> L1..L6
    0x60,  # picture        -- sub: tPic1..tPic9 -> Pic1..Pic9, tPic0 -> Pic0
    0x61,  # GDB            -- sub: tGDB1..tGDB9 -> GDB1..GDB9, tGDB0 -> GDB0
    0xAA,  # StrN           -- sub: tStr1..tStr9, tStr0 -> Str1..Str0
    0x7E,  # mode/menu
    0xBB,  # extended
    0xEF,  # newer-OS extended
))


def _numbered_with_zero_last(prefix):
    """Build {0x00: prefix+'1', ..., 0x08: prefix+'9', 0x09: prefix+'0'}.

    Mirrors the calc convention for Pic / GDB / StrN where sub-byte 0x09
    is the user-visible '0' slot, not a tenth one."""
    table = {}
    for i in range(9):
        table[i] = prefix + str(i + 1)
    table[0x09] = prefix + "0"
    return table


def _list_table():
    table = {}
    for i in range(6):
        table[i] = "L" + str(i + 1)
    return table


def _matrix_table():
    table = {}
    for i in range(10):
        table[i] = "[Mat" + chr(ord("A") + i) + "]"
    return table


# Sub-byte tables for two-byte tokens. The second byte indexes into the
# table; missing entries fall through to '?'. Only mathematically/textually
# meaningful prefixes are populated -- 0x7E/0xBB/0xEF stay unmapped.
#
# Built with explicit helpers (not dict-spread / dict comprehensions over
# kwargs) so this module imports cleanly under MicroPython too.
_TWO_BYTE_TO_ASCII = {
    # Lists L1..L6: 0x5D 0x00..0x05.
    0x5D: _list_table(),
    # Matrices [A]..[J]: 0x5C 0x00..0x09. Wrap in brackets so an LLM/SymPy
    # consumer can tell them apart from a juxtaposed letter ('MATA' would be
    # ambiguous with the four-letter word).
    0x5C: _matrix_table(),
    # Pic / GDB / StrN: sub byte 0x00..0x08 -> N1..N9, sub byte 0x09 -> N0.
    0x60: _numbered_with_zero_last("Pic"),
    0x61: _numbered_with_zero_last("GDB"),
    # Letting StrN decode means a Str ref inside another Str shows the
    # slot it points at instead of '?'.
    0xAA: _numbered_with_zero_last("Str"),
}


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


def _is_ascii_alnum(ch):
    """str.isalnum() isn't available on stock MicroPython; the token decoder
    only ever emits ASCII letters/digits, so an explicit range check is
    both correct and portable."""
    if not ch:
        return False
    c = ord(ch)
    return (0x30 <= c <= 0x39) or (0x41 <= c <= 0x5A) or (0x61 <= c <= 0x7A)


def _is_math_value_producer(ch):
    """Math-mode rule: last emitted char closes a value. Digits, letters, ')',
    or ']' (matrix tokens decode as '[MatA]' so the trailing bracket marks
    the end of a value). '^2'/'^3' postfixes end in a digit, already covered."""
    return _is_ascii_alnum(ch) or ch in (")", "]")


def _is_text_value_producer(ch):
    """Text-mode rule: only digits trigger implicit-mult. 'HELLO' stays
    'HELLO', but '2X' / '2pi' / '5(' still get the '*' insertion because
    digit-then-value is unambiguous even in prose. Note: the caller also
    suppresses '*' when the *next* char is also a digit, so multi-digit
    numbers ('2026') stay intact."""
    return bool(ch) and ch.isdigit()


def _is_value_starter(ch):
    """First emitted char of a token opens a value -- needs '*' after a
    preceding value-producer. Digits, letters, '(' or '[' (matrix tokens
    decode as '[MatA]' so '[' opens a value just like '(' does)."""
    return _is_ascii_alnum(ch) or ch in ("(", "[")


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
            sub = tok_bytes[i + 1] if i + 1 < n else None
            sub_table = _TWO_BYTE_TO_ASCII.get(b)
            if sub_table is not None and sub is not None and sub in sub_table:
                piece = sub_table[sub]
            else:
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
