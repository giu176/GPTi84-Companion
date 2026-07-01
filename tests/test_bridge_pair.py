"""Host-side coverage for the V2 single-Str command path in src/bridge.py."""

import bridge
import tokens


def _str_payload(token_bytes):
    n = len(token_bytes)
    return bytes([n & 0xFF, (n >> 8) & 0xFF]) + bytes(token_bytes)


def _str_name(slot):
    return bytes([0xAA, slot]) + b"\x00" * 6


class _FakeSock:
    def __init__(self):
        self.sends = []
        self.closed = False

    def sendall(self, _b):
        pass

    def close(self):
        self.closed = True


def _patch_net_capture(monkeypatch, fake):
    import net as net_mod

    def fake_send_framed(sock, payload):
        assert sock is fake
        fake.sends.append(bytes(payload))

    monkeypatch.setattr(net_mod, "send_framed", fake_send_framed)


def _make_harness(monkeypatch, sock=True):
    fake = _FakeSock()
    _patch_net_capture(monkeypatch, fake)
    sock_holder = [fake if sock else None]
    on_var = bridge._make_on_var(sock_holder)
    return fake, on_var


def test_str1_emits_single_command_frame(monkeypatch):
    fake, on_var = _make_harness(monkeypatch)

    on_var(0x04, _str_name(bridge.STR_SLOT_TEXT), b"\x00" * 13,
           _str_payload(tokens.ascii_to_tokens("LIST")))

    assert fake.sends == [b"LIST"]


def test_str1_size_prefix_is_stripped(monkeypatch):
    fake, on_var = _make_harness(monkeypatch)

    on_var(0x04, _str_name(bridge.STR_SLOT_TEXT), b"\x00" * 13,
           _str_payload(tokens.ascii_to_tokens("OPEN CABC")))

    assert fake.sends == [b"OPEN CABC"]


def test_malformed_size_prefix_stays_visible(monkeypatch):
    fake, on_var = _make_harness(monkeypatch)
    bogus = bytes([0x63, 0x00, 0x48, 0x49])

    on_var(0x04, _str_name(bridge.STR_SLOT_TEXT), b"\x00" * 13, bogus)

    assert fake.sends == [b"??HI"]


def test_str2_is_ignored_for_legacy_chat_compat(monkeypatch):
    fake, on_var = _make_harness(monkeypatch)

    on_var(0x04, _str_name(bridge.STR_SLOT_MATH), b"\x00" * 13,
           _str_payload(tokens.ascii_to_tokens("DIAG")))

    assert fake.sends == []


def test_non_string_var_relays_raw(monkeypatch):
    fake, on_var = _make_harness(monkeypatch)
    name = b"FOOBAR\x00\x00"
    raw = bytes([0x05, 0x00, 0x41, 0x42, 0x43, 0x44, 0x45])

    on_var(0x15, name, b"\x00" * 13, raw)

    assert fake.sends == [b"ABCDE"]


def test_emits_drop_silently_when_socket_down(monkeypatch):
    fake, on_var = _make_harness(monkeypatch, sock=False)

    on_var(0x04, _str_name(bridge.STR_SLOT_TEXT), b"\x00" * 13,
           _str_payload(tokens.ascii_to_tokens("LIST")))

    assert fake.sends == []


def test_parse_pages_frame_multi_page():
    pages = bridge._parse_pages_frame(b"pages:3\nONE\x00TWO\x00THREE")
    assert pages == ["ONE", "TWO", "THREE"]


def test_catalog_frame_is_saved_not_drawn(monkeypatch, tmp_path):
    saved = {}

    class _PinsCache:
        @staticmethod
        def save(text, path="pins.v1"):
            saved["text"] = text
            saved["path"] = path

    monkeypatch.setitem(__import__("sys").modules, "pins_cache", _PinsCache)

    assert bridge._maybe_save_catalog(b"catalog:13\nGPTI84PINS 1\n")
    assert saved == {"text": "GPTI84PINS 1\n", "path": "pins.v1"}
