"""BLE GATT peripheral transport for the GPTi84 phone relay."""

import time

import ble_protocol as protocol

try:
    import bluetooth
except ImportError:
    bluetooth = None


SERVICE_UUID = "7e400001-b5a3-f393-e0a9-e50e24dcca9e"
CONTROL_UUID = "7e400002-b5a3-f393-e0a9-e50e24dcca9e"
PICO_TO_PHONE_UUID = "7e400003-b5a3-f393-e0a9-e50e24dcca9e"
PHONE_TO_PICO_UUID = "7e400004-b5a3-f393-e0a9-e50e24dcca9e"
STATUS_UUID = "7e400005-b5a3-f393-e0a9-e50e24dcca9e"

_IRQ_CENTRAL_CONNECT = 1
_IRQ_CENTRAL_DISCONNECT = 2
_IRQ_GATTS_WRITE = 3

_FLAG_READ = 0x0002
_FLAG_WRITE = 0x0008
_FLAG_WRITE_NO_RESPONSE = 0x0004
_FLAG_NOTIFY = 0x0010
LOG_PATH = "bridge.log"


def _log(*parts):
    text = " ".join(str(part) for part in parts)
    print(text)
    try:
        with open(LOG_PATH, "a") as handle:
            handle.write(text + "\n")
    except Exception:
        pass


def _advertising_payload(name):
    full_name = name.encode("utf-8")
    name = full_name[:8]
    name_type = 0x09 if len(name) == len(full_name) else 0x08
    raw_uuid = bytes.fromhex(SERVICE_UUID.replace("-", ""))
    uuid = bytes(raw_uuid[index] for index in range(len(raw_uuid) - 1, -1, -1))
    return (
        b"\x02\x01\x06"
        + bytes((len(name) + 1, name_type)) + name
        + bytes((len(uuid) + 1, 0x07)) + uuid
    )


class BLETransport:
    """Message transport with send(payload), poll(), connected and close()."""

    def __init__(self, name="GPTi84-Pico"):
        if bluetooth is None or not hasattr(bluetooth, "BLE"):
            raise OSError("bluetooth.BLE is unavailable on this firmware")
        self.name = name
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)
        service = (
            bluetooth.UUID(SERVICE_UUID),
            (
                (bluetooth.UUID(CONTROL_UUID), _FLAG_WRITE),
                (bluetooth.UUID(PICO_TO_PHONE_UUID), _FLAG_READ | _FLAG_NOTIFY),
                (bluetooth.UUID(PHONE_TO_PICO_UUID),
                 _FLAG_WRITE | _FLAG_WRITE_NO_RESPONSE),
                (bluetooth.UUID(STATUS_UUID), _FLAG_READ | _FLAG_NOTIFY),
            ),
        )
        handles = self.ble.gatts_register_services((service,))[0]
        self.control_handle, self.notify_handle, self.write_handle, \
            self.status_handle = handles
        self.ble.gatts_set_buffer(self.control_handle, 64, True)
        self.ble.gatts_set_buffer(self.write_handle, 64, True)
        self.ble.gatts_write(
            self.status_handle,
            protocol.encode(protocol.STATUS, 0, 0, 5, 0, b"p1;ok"),
        )
        self.connections = set()
        self.session_id = 0
        self.outgoing = []
        self.waiting = None
        self.waiting_since = 0
        self.waiting_retries = 0
        self.incoming = protocol.MessageAssembler()
        self.completed = []
        self._advertise()

    @property
    def connected(self):
        return bool(self.connections)

    def _advertise(self):
        self.ble.gap_advertise(
            250000,
            adv_data=_advertising_payload(self.name),
        )

    def _irq(self, event, data):
        if event == _IRQ_CENTRAL_CONNECT:
            conn_handle, _, _ = data
            self.connections.add(conn_handle)
            _log("ble: central connected", conn_handle)
            self._notify_status()
        elif event == _IRQ_CENTRAL_DISCONNECT:
            conn_handle, _, _ = data
            self.connections.discard(conn_handle)
            self.waiting = None
            _log("ble: central disconnected", conn_handle)
            self._advertise()
        elif event == _IRQ_GATTS_WRITE:
            conn_handle, value_handle = data
            try:
                packet = self.ble.gatts_read(value_handle)
                envelope = protocol.decode(packet)
                self._on_envelope(conn_handle, value_handle, envelope)
            except (ValueError, OSError) as error:
                print("ble: invalid write:", error)

    def _on_envelope(self, conn_handle, value_handle, envelope):
        message_type = envelope["type"]
        if message_type == protocol.ACK:
            if self.waiting is not None:
                sent = protocol.decode(self.waiting)
                if sent["session_id"] == envelope["session_id"] \
                        and sent["sequence"] == envelope["sequence"]:
                    self.waiting = None
            return
        if value_handle == self.control_handle:
            if message_type == protocol.PING:
                self._notify_packet(protocol.encode(
                    protocol.PONG,
                    envelope["session_id"],
                    envelope["sequence"],
                    0,
                    0,
                ), conn_handle)
            elif message_type == protocol.CANCEL:
                self.outgoing = []
                self.waiting = None
                self.incoming.reset()
            elif message_type == protocol.HELLO:
                self._notify_status()
            return
        if message_type == protocol.RESPONSE_CHUNK:
            self.incoming.add(envelope)
            self._notify_ack(conn_handle, envelope)
        elif message_type == protocol.RESPONSE_END:
            payload = self.incoming.finish(envelope["session_id"])
            self._notify_ack(conn_handle, envelope)
            if payload is not None:
                self.completed.append(payload)
        elif message_type == protocol.ERROR:
            self.completed.append(envelope["chunk"])

    def _notify_packet(self, packet, conn_handle=None):
        targets = (conn_handle,) if conn_handle is not None \
            else tuple(self.connections)
        for handle in targets:
            self.ble.gatts_notify(handle, self.notify_handle, packet)

    def _notify_ack(self, conn_handle, envelope):
        self._notify_packet(protocol.encode(
            protocol.ACK,
            envelope["session_id"],
            envelope["sequence"],
            envelope["total_length"],
            envelope["chunk_offset"],
        ), conn_handle)

    def _notify_status(self):
        text = b"p1;ok" if self.connected else b""
        status = protocol.encode(protocol.STATUS, 0, 0, len(text), 0, text)
        self.ble.gatts_write(self.status_handle, status)
        for conn_handle in tuple(self.connections):
            self.ble.gatts_notify(conn_handle, self.status_handle, status)

    def send(self, payload):
        if not self.connected:
            raise OSError("BLE phone is not connected")
        self.session_id = (self.session_id + 1) & 0xFFFF
        if self.session_id == 0:
            self.session_id = 1
        packets = protocol.chunk_message(
            protocol.REQUEST_CHUNK,
            self.session_id,
            payload,
        )
        packets.append(protocol.encode(
            protocol.REQUEST_END,
            self.session_id,
            len(packets),
            len(payload),
            len(payload),
        ))
        self.outgoing.extend(packets)
        _log("ble: queued request session=", self.session_id, "len=", len(payload))

    def _pump(self):
        if not self.connected:
            return
        now = time.ticks_ms()
        if self.waiting is not None:
            if time.ticks_diff(now, self.waiting_since) < 2000:
                return
            if self.waiting_retries >= 2:
                self.waiting = None
                raise OSError("BLE ACK timeout")
            self.waiting_retries += 1
            self.waiting_since = now
            self._notify_packet(self.waiting)
            return
        if self.outgoing:
            self.waiting = self.outgoing.pop(0)
            self.waiting_since = now
            self.waiting_retries = 0
            self._notify_packet(self.waiting)

    def poll(self):
        self._pump()
        if self.completed:
            _log("ble: completed response")
            return self.completed.pop(0)
        return None

    def close(self):
        self.ble.gap_advertise(None)
        self.ble.active(False)


def echo_mode(name="GPTi84-Pico"):
    """Hardware bring-up mode that avoids importing DBUS/GPIO modules."""
    transport = BLETransport(name=name)
    print("ble: echo mode advertising as", name)
    sent = False
    while True:
        if transport.connected and not sent:
            transport.send(b"prompt:BLE parity test\nmath:2+2\n")
            sent = True
            print("ble: parity request queued")
        if not transport.connected:
            sent = False
        response = transport.poll()
        if response is not None:
            print("ble: parity response:", response)
        time.sleep_ms(10)
