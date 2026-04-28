"""TI-83+/84+ token <-> ASCII translation for String var payloads.

A TI String var on the wire is a token stream (same encoding TI-BASIC programs
use), not raw ASCII. Letters A..Z and digits 0..9 happen to share their ASCII
code points, but space is 0x29 (not 0x20), most punctuation differs, and math
functions are single-byte tokens (sin=0xC2, sqrt=0xBC, pi=0xAC, ...).

This module is the boundary that lets the desktop see plain text. Phase 1
covers the chat-app subset: letters, digits, space, basic ASCII punctuation,
and the relational operators. Phase 2 will extend to math function tokens
with LaTeX/SymPy output. Asymmetric on purpose: tokens_to_ascii is best-effort
(unknown bytes become '?'), ascii_to_tokens is strict (unknown chars raise).

Two-byte token prefixes (0x5C/0x5D matrix and list, 0x60 picture, 0x62/0x63
GDB, 0xAA system string itself, 0xBB extended, 0xEF newer-OS) are not handled
here yet; if the calc ever sends one in a Str payload it will appear as '?'
in the ASCII view.
"""


# Phase 1 token -> ASCII map. Keys are single-byte token values; values are
# the ASCII character to render. Letters/digits omitted because they're
# identity-mapped by code point.
_TOK_TO_ASCII = {
    0x10: "(",
    0x11: ")",
    0x29: " ",     # tSpace
    0x2A: '"',     # tString (the literal " char inside a quoted string)
    0x2B: ",",     # tComma
    0x3A: ".",     # tDecPt
    0x3E: ":",     # tColon
    0x6A: "=",     # tEQ (relational equals; not the STO-> arrow)
    0x6B: "<",
    0x6C: ">",
    0x70: "+",     # tAdd
    0x71: "-",     # tSub
    0x82: "*",     # tMul
    0x83: "/",     # tDiv
    0xB0: "-",     # tChs (unary negate); same glyph as subtraction in plain text
    0xF0: "^",     # tPower
}

# Inverse for ASCII -> token. Letters and digits are filled in below.
_ASCII_TO_TOK = {v: k for k, v in _TOK_TO_ASCII.items()}
# tChs and tSub both render as "-"; prefer tSub (binary) for plain ASCII input.
_ASCII_TO_TOK["-"] = 0x71

# Identity for letters and digits.
for _ch in range(ord("A"), ord("Z") + 1):
    _ASCII_TO_TOK[chr(_ch)] = _ch
for _ch in range(ord("0"), ord("9") + 1):
    _ASCII_TO_TOK[chr(_ch)] = _ch


def tokens_to_ascii(tok_bytes):
    """Translate a token byte sequence to ASCII. Best-effort: any byte that
    isn't a letter/digit and isn't in the table becomes '?'. Returns str.

    Two-byte token prefixes are NOT consumed -- the lead byte renders as '?'
    and the next byte is also processed (likely also '?'). Phase 1 limit.
    """
    out = []
    for b in tok_bytes:
        if 0x41 <= b <= 0x5A or 0x30 <= b <= 0x39:
            out.append(chr(b))
        else:
            out.append(_TOK_TO_ASCII.get(b, "?"))
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
