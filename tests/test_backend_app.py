import struct

from fastapi.testclient import TestClient

from backend import app as relay


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("RELAY_DB", str(tmp_path / "relay.sqlite3"))
    monkeypatch.setenv("RELAY_ADMIN_TOKEN", "admin-test")
    relay.init_db()
    return TestClient(relay.app)


def _auth():
    return {"Authorization": "Bearer admin-test"}


def test_health_requires_admin_token(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    assert client.get("/v1/health").status_code == 401
    response = client.get("/v1/health", headers=_auth())

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_messages_are_idempotent(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    body = {
        "id": "message-1",
        "conversationId": "chat-1",
        "parts": [{"type": "text", "text": "hello"}],
    }

    first = client.post(
        "/v1/messages",
        headers={**_auth(), "Idempotency-Key": "idem-1"},
        json=body,
    )
    second = client.post(
        "/v1/messages",
        headers={**_auth(), "Idempotency-Key": "idem-1"},
        json={**body, "parts": [{"type": "text", "text": "changed"}]},
    )

    assert first.status_code == 200
    assert second.json() == first.json()
    assert first.json()["message"]["text"] == "Relay received: hello"


def test_pin_sync_enforces_eight_chat_limit(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    too_many = {
        "pins": [
            {
                "conversationId": f"chat-{index}",
                "title": f"Chat {index}",
                "text": "Pinned text",
                "pinOrder": index,
            }
            for index in range(9)
        ]
    }
    assert client.put("/v1/pins", headers=_auth(), json=too_many).status_code == 400

    valid = {"pins": too_many["pins"][:8]}
    response = client.put("/v1/pins", headers=_auth(), json=valid)

    assert response.status_code == 200
    assert len(client.get("/v1/pins", headers=_auth()).json()["pins"]) == 8


def test_device_creation_returns_one_time_token(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    response = client.post("/v1/devices", headers=_auth(), json={"name": "Bench Pico"})

    body = response.json()["device"]
    assert response.status_code == 200
    assert body["name"] == "Bench Pico"
    assert body["token"].startswith("gpti84_")
    assert body["wsPath"] == "/v1/device/ws"


def test_websocket_accepts_pico_framed_payload(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    device = client.post(
        "/v1/devices", headers=_auth(), json={"name": "Pico"}
    ).json()["device"]
    payload = b"prompt:hello\nmath:2*X\n"
    packet = struct.pack(">I", len(payload)) + payload

    with client.websocket_connect(
        "/v1/device/ws", headers={"Authorization": f"Bearer {device['token']}"}
    ) as ws:
        ws.send_bytes(packet)
        reply = ws.receive_bytes()

    (length,) = struct.unpack(">I", reply[:4])
    body = reply[4:]
    assert length == len(body)
    assert body.startswith(b"pages:1\n")
    page = body.split(b"\n", 1)[1]
    assert len(page) == relay.PAGE_CHARS

