import bridge
import raw_axe_protocol as raw


class _FakeRelay:
    connected = True

    def __init__(self, responses):
        self.sent = []
        self.responses = list(responses)

    def send(self, payload):
        self.sent.append(bytes(payload))

    def poll(self):
        if self.responses:
            return self.responses.pop(0)
        return None


def _reader(data):
    stream = iter(data)
    return lambda _timeout: next(stream, None)


def _writer(output):
    def write(byte, _timeout):
        output.append(byte)
        return True
    return write


def test_raw_axe_bridge_forwards_list_and_returns_pages():
    relay = _FakeRelay([b"pages:1\n0 NEW CHAT"])
    output = []

    serviced = bridge._service_raw_axe_once(
        relay,
        read_byte=_reader(raw.encode(raw.REQUEST, b"LIST")),
        write_byte=_writer(output),
    )

    assert serviced
    assert relay.sent == [b"LIST"]
    assert raw.decode(bytes(output)) == (raw.RESPONSE, b"pages:1\n0 NEW CHAT")


def test_raw_axe_bridge_skips_catalog_before_pages(monkeypatch):
    saved = {}

    class _Pins:
        @staticmethod
        def save(text, path):
            saved[path] = text

    monkeypatch.setitem(__import__("sys").modules, "pins_cache", _Pins)
    relay = _FakeRelay([b"catalog:13\nGPTI84PINS 1\n", b"pages:1\nOK"])
    output = []

    bridge._service_raw_axe_once(
        relay,
        read_byte=_reader(raw.encode(raw.REQUEST, b"LIST")),
        write_byte=_writer(output),
    )

    assert saved == {"pins.v1": "GPTI84PINS 1\n"}
    assert raw.decode(bytes(output)) == (raw.RESPONSE, b"pages:1\nOK")


def test_raw_axe_bridge_rejects_non_request_frame():
    relay = _FakeRelay([])
    output = []

    assert bridge._service_raw_axe_once(
        relay,
        read_byte=_reader(raw.encode(raw.STATUS, b"hi")),
        write_byte=_writer(output),
    )

    frame_type, payload = raw.decode(bytes(output))
    assert frame_type == raw.ERROR
    assert payload == b"EXPECTED REQUEST"
    assert relay.sent == []

