"""TI variable encoding/decoding: real numbers, real lists, names, headers.

Real format is the TI-82 9-byte BCD shape, also used by 83/83+/84+ for the
basic numeric types. Programs are stored as [size_le16][token_stream].
The variable header field that wraps the payload differs between TI-82
(11 bytes) and 83+/84+ (13 bytes, two trailing zero bytes for version+flags).
"""

# Type IDs (TI-82; mostly compatible with 83/83+/84+ for the basic types).
T_REAL   = 0x00
T_LIST   = 0x01
T_MATRIX = 0x02
T_PROG   = 0x05
T_PROG_LOCKED = 0x06


def list_name_82(idx):
    """TI-82 name field for L1..L0 (idx 0..9). Token 5D, sub-token 00..09, padded."""
    return bytes([0x5D, idx]) + b'\x00' * 6


def real_name(letter):
    """Name field for real var A..Z. ASCII letter in slot 0, zero pad."""
    if len(letter) != 1 or not ('A' <= letter <= 'Z'):
        raise ValueError("letter must be a single uppercase A..Z")
    return bytes([ord(letter)]) + b'\x00' * 7


def prog_name(name):
    """8-byte name field for a program. ASCII uppercase A..Z and digits 0..9,
    1..8 chars, zero-padded to 8."""
    if not (1 <= len(name) <= 8):
        raise ValueError("prog name must be 1..8 chars")
    for c in name:
        if not (('A' <= c <= 'Z') or ('0' <= c <= '9')):
            raise ValueError("prog name must be uppercase A..Z or 0..9")
    return name.encode("ascii") + b'\x00' * (8 - len(name))


def make_var_header(data_size, type_id, name8, proto=82):
    """Variable header used in REQ/VAR/RTS data fields.
    TI-82 form is 11 bytes: [size_le16][type][name 8].
    TI-83+/84+ form is 13 bytes: same plus [version=0][flags=0]."""
    if len(name8) != 8:
        raise ValueError("name must be exactly 8 bytes")
    base = bytes([data_size & 0xFF, (data_size >> 8) & 0xFF, type_id]) + name8
    if proto == 82:
        return base
    return base + b'\x00\x00'


def parse_real_parts(b):
    """Decompose a 9-byte TI-82 real into (sign, exp, digits) without precision loss.
    sign is -1 or 1, exp is unbiased decimal exponent, digits is the 14-digit
    mantissa as an int (leading digit first). value = sign * digits * 10^(exp-13)."""
    sign = -1 if (b[0] & 0x80) else 1
    exp = b[1] - 0x80
    digits = 0
    for i in range(7):
        digits = digits * 100 + ((b[2 + i] >> 4) * 10) + (b[2 + i] & 0x0F)
    return sign, exp, digits


def parse_real_str(b):
    """Format a 9-byte TI-82 real as a decimal string. Lossless: bypasses float
    entirely so MicroPython's 32-bit float precision can't mangle 14-digit values."""
    sign, exp, digits = parse_real_parts(b)
    if digits == 0:
        return "0"
    s = "{:014d}".format(digits).rstrip("0") or "0"
    if exp >= 0 and exp < 14 and len(s) <= exp + 1:
        body = s + "0" * (exp + 1 - len(s))
    elif exp >= 0 and exp < 14:
        body = s[: exp + 1] + "." + s[exp + 1 :]
    elif exp < 0 and exp > -5:
        body = "0." + "0" * (-exp - 1) + s
    else:
        body = s[0] + ("." + s[1:] if len(s) > 1 else "") + "e" + str(exp)
    return ("-" if sign < 0 else "") + body


def parse_real(b):
    """Parse a 9-byte TI-82 real to a Python float. Lossy on MicroPython builds
    that use 32-bit floats: prefer parse_real_str for display."""
    sign, exp, digits = parse_real_parts(b)
    shift = exp - 13
    if shift >= 0:
        return sign * digits * (10 ** shift)
    return sign * digits / (10 ** -shift)


def parse_real_list(data):
    """Parse a TI-82 real-number list payload: [count_le16][N * 9-byte reals].
    Returns floats (lossy under 32-bit float MicroPython); see parse_real_list_str."""
    n = data[0] | (data[1] << 8)
    out = []
    for i in range(n):
        out.append(parse_real(data[2 + i * 9 : 2 + (i + 1) * 9]))
    return out


def parse_real_list_str(data):
    """Like parse_real_list but returns strings; lossless on any MicroPython build."""
    n = data[0] | (data[1] << 8)
    out = []
    for i in range(n):
        out.append(parse_real_str(data[2 + i * 9 : 2 + (i + 1) * 9]))
    return out


def encode_real(value):
    """Encode a number into the 9-byte TI-82 real format.
    Goes through string formatting to avoid float precision artifacts in the
    BCD digits; '%.14e' gives 14 digits of precision plus exponent which is
    exactly what the TI format wants."""
    if value == 0:
        return b'\x00\x80' + b'\x00' * 7
    sign = 0x80 if value < 0 else 0x00
    s = "{:.13e}".format(abs(value))   # 1 leading digit + 13 fractional + 'e+NN'
    mant_str, exp_str = s.split("e")
    exp = int(exp_str)
    digits = mant_str.replace(".", "")  # 14 digits total, no leading zeros
    if len(digits) < 14:
        digits = digits + "0" * (14 - len(digits))
    elif len(digits) > 14:
        digits = digits[:14]
    out = bytearray(9)
    out[0] = sign
    out[1] = (exp + 0x80) & 0xFF
    for i in range(7):
        hi = int(digits[2 * i])
        lo = int(digits[2 * i + 1])
        out[2 + i] = (hi << 4) | lo
    return bytes(out)


def encode_real_list(values):
    """Encode a Python sequence of numbers into a TI-82 list payload."""
    out = bytearray()
    out.append(len(values) & 0xFF)
    out.append((len(values) >> 8) & 0xFF)
    for v in values:
        out.extend(encode_real(v))
    return bytes(out)
