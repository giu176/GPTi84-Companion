"""Host-side coverage for the Str1/Str2 pairing path inside src/bridge.py.

The bridge's `_make_on_var` callback is the hot loop of the chat path:
calc-side asm sends Str1 then Str2 back-to-back, and the callback must
buffer by slot, decode each in the right token mode (text vs math),
and emit one combined newline-separated frame to the desktop.

We don't exercise wifi or the DBUS wire here; we synthesise the
`(type_id, name8, hdr, data)` tuples that listen_loop would have
delivered, and inspect what the bridge tries to send through the socket.
"""

import time

import bridge
import tokens


def _str_payload(token_bytes):
    """Build the size-prefixed wire body the calc emits for a String var."""
    n = len(token_bytes)
    return bytes([n & 0xFF, (n >> 8) & 0xFF]) + bytes(token_bytes)


def _str_name(slot):
    """8-byte name field [0xAA, slot, 0,0,0,0,0,0]."""
    return bytes([0x0AA, slot]) + b"\x00" * 6


class _FakeSock:
    """Stand-in for the socket holder. Captures every send_framed call so
    the test can read back the frames the bridge emitted, in order."""
    def __init__(self):
        self.sends = []          # list[bytes] -- payloads, not raw frames
        self.closed = False

    def sendall(self, _b):
        # net.send_framed calls sendall twice (length, then payload). We
        # don't care; the bridge stamps frames via net.send_framed which
        # we monkeypatch anyway. This stub is only here in case anything
        # bypasses the patch.
        pass

    def close(self):
        self.closed = True


def _patch_net_capture(monkeypatch, fake):
    """Replace net.send_framed with a captor that records (sock, payload)
    pairs into fake.sends. The bridge's _emit_pair / _relay_raw both go
    through net.send_framed, so this is the chokepoint."""
    import net as net_mod

    def fake_send_framed(sock, payload):
        assert sock is fake, "send_framed targeted unexpected socket"
        fake.sends.append(bytes(payload))

    monkeypatch.setattr(net_mod, "send_framed", fake_send_framed)


def _make_harness(monkeypatch):
    """Build the (sock_holder, pair, on_var) tuple the bridge uses."""
    fake = _FakeSock()
    _patch_net_capture(monkeypatch, fake)
    sock_holder = [fake]
    pair = {"prompt": None, "math": None, "first_arrival_ms": None}
    on_var = bridge._make_on_var(sock_holder, pair)
    return fake, sock_holder, pair, on_var


# ---- Pairing: Str1 then Str2 emits one combined frame ----

def test_str1_then_str2_emits_combined_frame(monkeypatch):
    fake, _sh, pair, on_var = _make_harness(monkeypatch)

    # Str1 = "HELLO" (text mode -- letters stay a word).
    str1_tokens = tokens.ascii_to_tokens("HELLO")
    on_var(0x04, _str_name(bridge.STR_SLOT_TEXT), b"\x00" * 13,
           _str_payload(str1_tokens))
    # Buffered, no emit yet.
    assert fake.sends == []
    assert pair["prompt"] == "HELLO"
    assert pair["math"] is None

    # Str2 = "2X+1" (math mode -- 2X -> 2*X).
    str2_tokens = bytes([0x32, 0x58, 0x70, 0x31])  # 2 X + 1
    on_var(0x04, _str_name(bridge.STR_SLOT_MATH), b"\x00" * 13,
           _str_payload(str2_tokens))

    assert len(fake.sends) == 1
    frame = fake.sends[0].decode("ascii")
    assert frame == "prompt:HELLO\nmath:2*X+1\n"
    # Pair buffer cleared after flush.
    assert pair["prompt"] is None and pair["math"] is None
    assert pair["first_arrival_ms"] is None


def test_str2_then_str1_also_pairs(monkeypatch):
    """Order independence: deck might populate Str2 first."""
    fake, _sh, pair, _on_var_unused = _make_harness(monkeypatch)
    on_var = bridge._make_on_var(_sh, pair)

    on_var(0x04, _str_name(bridge.STR_SLOT_MATH), b"\x00" * 13,
           _str_payload(bytes([0x58, 0x59])))   # XY math -> X*Y
    assert fake.sends == []
    on_var(0x04, _str_name(bridge.STR_SLOT_TEXT), b"\x00" * 13,
           _str_payload(tokens.ascii_to_tokens("HI")))
    assert len(fake.sends) == 1
    assert fake.sends[0] == b"prompt:HI\nmath:X*Y\n"


def test_str1_alone_flushes_after_pair_timeout(monkeypatch):
    fake, _sh, pair, on_var = _make_harness(monkeypatch)

    on_var(0x04, _str_name(bridge.STR_SLOT_TEXT), b"\x00" * 13,
           _str_payload(tokens.ascii_to_tokens("ALONE")))
    # No flush yet -- waiting on Str2 or timeout.
    assert fake.sends == []

    # Force the buffer to look stale: rewind first_arrival_ms past the
    # timeout. Using time.ticks_diff semantics from MicroPython here would
    # be correct, but time.ticks_diff in CPython works as plain subtraction
    # for these small values, so this is fine.
    pair["first_arrival_ms"] = time.ticks_ms() - bridge.PAIR_TIMEOUT_MS - 1
    bridge._maybe_flush_stale_pair(_sh, pair)

    assert len(fake.sends) == 1
    assert fake.sends[0] == b"prompt:ALONE\nmath:\n"


def test_str2_alone_flushes_after_pair_timeout(monkeypatch):
    fake, _sh, pair, on_var = _make_harness(monkeypatch)

    on_var(0x04, _str_name(bridge.STR_SLOT_MATH), b"\x00" * 13,
           _str_payload(bytes([0x32, 0x58])))   # math 2X -> 2*X
    assert fake.sends == []
    pair["first_arrival_ms"] = time.ticks_ms() - bridge.PAIR_TIMEOUT_MS - 1
    bridge._maybe_flush_stale_pair(_sh, pair)

    assert len(fake.sends) == 1
    assert fake.sends[0] == b"prompt:\nmath:2*X\n"


def test_pair_does_not_flush_before_timeout(monkeypatch):
    fake, _sh, pair, on_var = _make_harness(monkeypatch)
    on_var(0x04, _str_name(bridge.STR_SLOT_TEXT), b"\x00" * 13,
           _str_payload(tokens.ascii_to_tokens("WAIT")))
    # Same tick: don't flush.
    bridge._maybe_flush_stale_pair(_sh, pair)
    assert fake.sends == []
    assert pair["prompt"] == "WAIT"


# ---- Mode selection: Str1=text vs Str2=math ----

def test_str1_decodes_in_text_mode_no_implicit_mult(monkeypatch):
    """Str1 'HELLO' must NOT become 'H*E*L*L*O'. That's the whole reason
    text mode exists."""
    fake, _sh, pair, on_var = _make_harness(monkeypatch)
    on_var(0x04, _str_name(bridge.STR_SLOT_TEXT), b"\x00" * 13,
           _str_payload(tokens.ascii_to_tokens("HELLO")))
    on_var(0x04, _str_name(bridge.STR_SLOT_MATH), b"\x00" * 13,
           _str_payload(b""))   # empty Str2 to force flush

    assert b"prompt:HELLO\n" in fake.sends[0]


def test_str2_decodes_in_math_mode_inserts_implicit_mult(monkeypatch):
    """Str2 'XY' must become 'X*Y'."""
    fake, _sh, pair, on_var = _make_harness(monkeypatch)
    on_var(0x04, _str_name(bridge.STR_SLOT_TEXT), b"\x00" * 13,
           _str_payload(b""))
    on_var(0x04, _str_name(bridge.STR_SLOT_MATH), b"\x00" * 13,
           _str_payload(bytes([0x58, 0x59])))

    assert b"math:X*Y\n" in fake.sends[0]


# ---- Size-prefix stripping ----

def test_size_prefix_is_stripped_from_str_payload(monkeypatch):
    """The wire body is [size_le16][tokens]; the bridge must strip it
    before handing bytes to the token decoder. Otherwise the size word
    would be decoded as junk leading bytes."""
    fake, _sh, pair, on_var = _make_harness(monkeypatch)

    payload = _str_payload(tokens.ascii_to_tokens("HI"))
    # Two-byte size prefix + two letter tokens.
    assert payload == bytes([0x02, 0x00, 0x48, 0x49])

    on_var(0x04, _str_name(bridge.STR_SLOT_TEXT), b"\x00" * 13, payload)
    on_var(0x04, _str_name(bridge.STR_SLOT_MATH), b"\x00" * 13,
           _str_payload(b""))

    # If the prefix wasn't stripped, the frame would contain garbage from
    # decoding 0x02/0x00 as standalone tokens.
    assert fake.sends[0] == b"prompt:HI\nmath:\n"


def test_size_prefix_stripping_skipped_when_size_word_disagrees(monkeypatch):
    """Defensive: if the declared size doesn't match actual bytes, the
    bridge passes the raw payload through. Keeps malformed frames visible
    instead of silently chopping two bytes off the front."""
    fake, _sh, pair, on_var = _make_harness(monkeypatch)
    # Declares 99 bytes of body but only carries 2.
    bogus = bytes([0x63, 0x00, 0x48, 0x49])
    on_var(0x04, _str_name(bridge.STR_SLOT_TEXT), b"\x00" * 13, bogus)
    on_var(0x04, _str_name(bridge.STR_SLOT_MATH), b"\x00" * 13,
           _str_payload(b""))

    # 0x63 is unmapped -> '?', 0x00 is unmapped -> '?', then 'H','I'.
    assert fake.sends[0] == b"prompt:??HI\nmath:\n"


# ---- Non-Str traffic falls through ----

def test_non_string_var_relays_raw(monkeypatch):
    """An AppVar (type 0x15) or anything that isn't a Str slot should
    just be forwarded as raw bytes -- the bridge stays useful for any
    listener that isn't the chat deck."""
    fake, _sh, pair, on_var = _make_harness(monkeypatch)

    name = b"FOOBAR\x00\x00"
    raw = bytes([0x05, 0x00, 0x41, 0x42, 0x43, 0x44, 0x45])  # size + 'ABCDE'
    on_var(0x15, name, b"\x00" * 13, raw)

    # Stripped of size prefix, raw 'ABCDE' relayed.
    assert fake.sends == [b"ABCDE"]
    # Pair buffer untouched.
    assert pair["prompt"] is None and pair["math"] is None


def test_unpaired_str_slot_relays_as_text_frame(monkeypatch):
    """Str3 (slot 0x02) is 'unpaired' in the chat deck. The bridge logs
    it and ships the decoded text as a raw frame, but it must NOT land
    in the prompt or math slot of the next pair."""
    fake, _sh, pair, on_var = _make_harness(monkeypatch)

    on_var(0x04, _str_name(0x02), b"\x00" * 13,
           _str_payload(tokens.ascii_to_tokens("STRAY")))

    assert fake.sends == [b"STRAY"]
    assert pair["prompt"] is None and pair["math"] is None


# ---- Socket-down behaviour ----

def test_emits_drop_silently_when_socket_down(monkeypatch):
    """If the socket holder is None (bridge is reconnecting), the on_var
    callback must not raise or buffer-leak. We just drop and let the
    pair buffer stay coherent."""
    fake = _FakeSock()
    _patch_net_capture(monkeypatch, fake)
    sock_holder = [None]      # simulate reconnect
    pair = {"prompt": None, "math": None, "first_arrival_ms": None}
    on_var = bridge._make_on_var(sock_holder, pair)

    on_var(0x04, _str_name(bridge.STR_SLOT_TEXT), b"\x00" * 13,
           _str_payload(tokens.ascii_to_tokens("HI")))
    on_var(0x04, _str_name(bridge.STR_SLOT_MATH), b"\x00" * 13,
           _str_payload(b""))

    # Nothing reached the captor (because the captor checks sock identity
    # and we never called net.send_framed with a real socket).
    assert fake.sends == []
