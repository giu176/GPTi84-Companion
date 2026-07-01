"""Minimal TI-BASIC/Axe line tokenizer + .8Xp wrapper.

Scoped intentionally: only handles the keywords and constructs used by
the chat deck program. Adding a new keyword means adding an entry to
KEYWORDS below and (if multi-character) ensuring the longest-match
ordering is right -- the scanner walks KEYWORDS top-to-bottom and
takes the first prefix match.

Token bytes verified against the standard TI-83+/84+ token map. Any
disagreement with the calc is a bug here; the wire format is the
authoritative thing the calc parses.

Usage:
  python tools/bastok.py build PROGNAME source.basic out.8xp
  python tools/bastok.py tokens source.basic        # hex dump only

The PROGNAME goes in the .8Xp variable name field (1-8 chars, A-Z and
0-9 only). Line endings in the source can be LF or CRLF; both encode
to a single tEnter (0x3F) token between statements.
"""

import sys
from pathlib import Path


# Multi-char keyword -> token bytes. Order matters: longer prefixes
# must come before any shorter prefix that could swallow them. The
# scanner tries each entry in order and takes the first that matches
# at the current position.
KEYWORDS = [
    # Two-byte tokens first (so 'Asm(' isn't mis-scanned as letters).
    # Asm( = t2ByteTok(0xBB) + tasm(0x6A); verified against
    # references/other_projects/spasm/ti83plus.inc 'tasm equ 6Ah' in
    # the 2-byte token table at line 4761.
    ("Asm(",     bytes([0xBB, 0x6A])),
    # sub( = t2ByteTok(0xBB) + tSubStrng(0x0C); the BASIC string
    # substring built-in. ti83plus.inc line 4674 'tSubStrng equ 0Ch'.
    # Used by the chat pager to extract row R of a fixed-grid page
    # via sub(StrP, 1+(R-1)*16, 16).
    ("sub(",     bytes([0xBB, 0x0C])),
    # Axe Parser token replacements used by the native calculator UI.
    # These bytes are the calculator tokens that Axe's hook interprets as
    # native commands. They are verified against docs/axe/Developers/
    # tokenhook.inc and the bundled example programs:
    #   hFix=0x0E6 -> 0x73, hClrDraw=0x10A -> 0x85,
    #   hText=0x126 -> 0x93, hLine=0x138 -> 0x9C,
    #   hDispGraph=0x1BE -> 0xDF, hSend=0x1CE -> 0xE7,
    #   hGet=0x1D0 -> 0xE8, hClrTable/port=0x1F6 -> 0xFB.
    ("DispGraph", bytes([0xDF])),
    ("ClrDraw",  bytes([0x85])),
    ("Text(",    bytes([0x93])),
    ("Line(",    bytes([0x9C])),
    ("Buff(",    bytes([0xB3])),
    ("Send(",    bytes([0xE7])),
    ("Get(",     bytes([0xE8])),
    ("port",     bytes([0xFB])),
    ("Fix",      bytes([0x73])),
    ("Full",     bytes([0xBB, 0x67])),
    # Two-char comparison operators. Must come before '<' / '>' /
    # '=' single-char punctuation so longest-match wins.
    ("<=",       bytes([0x6D])),
    (">=",       bytes([0x6E])),
    ("!=",       bytes([0x6F])),
    # Control-flow keywords. Note many include a trailing space in
    # their on-screen glyph (e.g. 'Repeat '); the calc tokens are
    # single-byte regardless. Match the bare keyword and let the
    # scanner's whitespace-skip handle the gap to the next token.
    ("ClrHome",  bytes([0xE1])),
    ("Input",    bytes([0xDC])),
    ("Pause",    bytes([0xD8])),
    ("Disp",     bytes([0xDE])),
    ("prgm",     bytes([0x5F])),
    ("Repeat",   bytes([0xD2])),
    ("While",    bytes([0xD1])),
    ("Return",   bytes([0xD5])),
    ("Then",     bytes([0xCF])),
    ("Else",     bytes([0xD0])),
    ("Stop",     bytes([0xD9])),
    ("Goto",     bytes([0xD7])),
    ("Lbl",      bytes([0xD6])),
    ("End",      bytes([0xD4])),
    ("If",       bytes([0xCE])),
    # Output( is a single-byte 0xE0 keyword (the '(' is part of the
    # glyph, not a separate token). Place before any rule that would
    # split it as 'Output' + '('.
    ("Output(",  bytes([0xE0])),
    ("getKey",   bytes([0xAD])),
    # Boolean ops. Must come before letter-by-letter encoding so the
    # scanner sees them as single tokens. The on-calc forms are
    # ' or ', ' xor ', ' and ' (with surrounding spaces in the glyph);
    # we match the bare word and rely on whitespace-skip on either side.
    ("or",       bytes([0x3C])),
    ("xor",      bytes([0x3D])),
    ("and",      bytes([0x40])),
    # System string vars: 'StrN' encodes as [tVarStrng=0xAA, sub-byte].
    # Str1=0x00 .. Str9=0x08, Str0=0x09 (Str0 is index 9, not 0).
    ("Str1",     bytes([0xAA, 0x00])),
    ("Str2",     bytes([0xAA, 0x01])),
    ("Str3",     bytes([0xAA, 0x02])),
    ("Str4",     bytes([0xAA, 0x03])),
    ("Str5",     bytes([0xAA, 0x04])),
    ("Str6",     bytes([0xAA, 0x05])),
    ("Str7",     bytes([0xAA, 0x06])),
    ("Str8",     bytes([0xAA, 0x07])),
    ("Str9",     bytes([0xAA, 0x08])),
    ("Str0",     bytes([0xAA, 0x09])),
    # The STO arrow (right-arrow assignment) is written '->' in source.
    ("->",       bytes([0x04])),
]

# Single-char punctuation -> token byte.
PUNCT = {
    "(":  0x10,
    ")":  0x11,
    "{":  0x08,
    "}":  0x09,
    '"':  0x2A,
    ",":  0x2B,
    ".":  0x3A,
    ":":  0x3E,
    "+":  0x70,
    "-":  0x71,
    "*":  0x82,
    "/":  0x83,
    "=":  0x6A,
    "<":  0x6B,
    ">":  0x6C,
    "^":  0xF0,
    " ":  0x29,
    "?":  0xAF,
    "!":  0x2D,
}


def tokenize(source):
    """Tokenize a BASIC source string into a token byte stream. LF and
    CRLF both become tEnter (0x3F). Trailing newline is preserved as
    tEnter so the program ends with a clean separator (the calc accepts
    both with and without, but with is canonical)."""
    out = bytearray()
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]

        if ch == "\r":
            i += 1
            continue  # treat CR as part of CRLF; the LF will emit the Enter
        if ch == "\n":
            out.append(0x3F)  # tEnter
            i += 1
            continue

        # Skip leading whitespace at start of a logical line. Inside a
        # statement, a literal space encodes as tSpace (0x29). The
        # distinction: spaces between keywords/operators are noise to
        # the calc tokenizer (it skips them when re-tokenizing), so
        # we drop runs of spaces here. Spaces inside quoted strings
        # are preserved by the string-literal branch below.
        if ch == " ":
            i += 1
            continue

        if ch == '"':
            # Quoted string literal. Open quote is tString (0x2A); body
            # is the calc string token stream (letters/digits identity,
            # space=tSpace=0x29, etc.); closing quote is tString again
            # OR the end-of-line tEnter implicitly closes it.
            out.append(PUNCT['"'])
            i += 1
            while i < n and source[i] != '"' and source[i] != "\n":
                c = source[i]
                if "A" <= c <= "Z" or "0" <= c <= "9":
                    out.append(ord(c))
                elif c in PUNCT:
                    out.append(PUNCT[c])
                else:
                    # Unknown char in string literal -- emit a space
                    # rather than crashing, since the deck only needs
                    # the printable-ASCII subset.
                    out.append(0x29)
                i += 1
            if i < n and source[i] == '"':
                out.append(PUNCT['"'])
                i += 1
            continue

        # Try multi-char keywords (longest-match by table order).
        matched = False
        for kw, toks in KEYWORDS:
            if source.startswith(kw, i):
                out.extend(toks)
                i += len(kw)
                matched = True
                break
        if matched:
            continue

        # Letters and digits encode as their ASCII byte.
        if "A" <= ch <= "Z" or "0" <= ch <= "9":
            out.append(ord(ch))
            i += 1
            continue

        # Single-char punctuation.
        if ch in PUNCT:
            out.append(PUNCT[ch])
            i += 1
            continue

        raise ValueError("bastok: unknown char {!r} at offset {}".format(ch, i))

    return bytes(out)


# ---- .8Xp container ----

T_PROG = 0x05  # unprotected program; T_PROG_LOCKED=0x06 is the locked variant.


def make_8xp(name, body, locked=False):
    """Wrap a token-stream body as a single-program .8Xp file.

    name: 1-8 char program name, uppercase A-Z and 0-9 only.
    body: bytes -- the BASIC token stream (no length prefix yet).
    locked: True to mark as locked program (type 0x06).

    The on-wire variable data is [size_le16][body]; the .8Xp wraps that
    in the standard [sig][comment][entry][checksum] container.
    """
    if not (1 <= len(name) <= 8) or not all(
            ("A" <= c <= "Z") or ("0" <= c <= "9") for c in name):
        raise ValueError("name must be 1-8 chars, uppercase A-Z and 0-9")

    type_id = 0x06 if locked else T_PROG
    name_field = name.encode("ascii") + b"\x00" * (8 - len(name))
    var_data = bytes([len(body) & 0xFF, (len(body) >> 8) & 0xFF]) + body
    var_size = len(var_data)

    sig = b"**TI83F*\x1a\x0a\x00"
    comment = b"chat deck                                 "  # 42 bytes
    assert len(comment) == 42, len(comment)

    entry = (
        bytes([0x0D, 0x00])                                 # entry header len = 13
        + bytes([var_size & 0xFF, (var_size >> 8) & 0xFF])  # var size A
        + bytes([type_id])
        + name_field
        + bytes([0x00, 0x00])                               # version, flags
        + bytes([var_size & 0xFF, (var_size >> 8) & 0xFF])  # var size B (repeated)
        + var_data
    )

    data_section = entry
    data_section_len = len(data_section)
    header = sig + comment + bytes([data_section_len & 0xFF, (data_section_len >> 8) & 0xFF])

    checksum = sum(data_section) & 0xFFFF
    return header + data_section + bytes([checksum & 0xFF, (checksum >> 8) & 0xFF])


def main(argv):
    if len(argv) < 2:
        sys.stderr.write(
            "usage: bastok.py build PROGNAME source.basic out.8xp\n"
            "       bastok.py tokens source.basic\n"
        )
        return 2
    cmd = argv[1]
    if cmd == "tokens":
        if len(argv) != 3:
            sys.stderr.write("usage: bastok.py tokens source.basic\n")
            return 2
        body = tokenize(Path(argv[2]).read_text())
        sys.stderr.write("body length: {} bytes\n".format(len(body)))
        sys.stdout.write(" ".join("{:02X}".format(b) for b in body) + "\n")
        return 0
    if cmd == "build":
        if len(argv) != 5:
            sys.stderr.write("usage: bastok.py build PROGNAME source.basic out.8xp\n")
            return 2
        name = argv[2]
        body = tokenize(Path(argv[3]).read_text())
        out = make_8xp(name, body)
        Path(argv[4]).write_bytes(out)
        sys.stderr.write(
            "bastok: wrote {} ({} bytes; body {} bytes)\n".format(
                argv[4], len(out), len(body)))
        return 0
    sys.stderr.write("bastok: unknown command {!r}\n".format(cmd))
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
