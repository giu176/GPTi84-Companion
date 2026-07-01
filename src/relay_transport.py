"""Select the production BLE relay or temporary framed-TCP transport."""


class TCPTransport:
    def __init__(self, sock, net_module):
        self.sock = sock
        self.net = net_module
        self.reader = net_module.FrameReader(sock)

    @property
    def connected(self):
        return self.sock is not None

    def send(self, payload):
        self.net.send_framed(self.sock, payload)

    def poll(self):
        return self.reader.poll()

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None


def open_transport():
    import secrets
    mode = getattr(secrets, "RELAY_TRANSPORT", "ble").lower()
    if mode == "tcp":
        import net
        net.connect_wifi()
        return TCPTransport(net.open_socket(), net)
    if mode != "ble":
        raise ValueError("RELAY_TRANSPORT must be 'ble' or 'tcp'")
    from ble_transport import BLETransport
    return BLETransport(
        name=getattr(secrets, "BLE_DEVICE_NAME", "GPTi84-Pico"),
    )
