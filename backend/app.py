from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import struct
import time
from contextlib import asynccontextmanager
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, status
from fastapi.websockets import WebSocketDisconnect
from pydantic import BaseModel, Field


VERSION = "0.1.0"
PAGE_COLS = 16
PAGE_ROWS = 7
PAGE_CHARS = PAGE_COLS * PAGE_ROWS
MAX_PAGES = 8
MAX_PINNED = 8


def _database_path() -> Path:
    return Path(os.environ.get("RELAY_DB", "backend/relay.sqlite3"))


def _admin_token() -> str:
    return os.environ.get("RELAY_ADMIN_TOKEN", "dev-admin-token")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now_ms() -> int:
    return int(time.time() * 1000)


@contextmanager
def connect() -> Any:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()


def init_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS idempotency (
                key TEXT PRIMARY KEY,
                response_json TEXT NOT NULL,
                created_at_ms INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pins (
                conversation_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                projection_text TEXT NOT NULL,
                pin_order INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                revoked INTEGER NOT NULL DEFAULT 0,
                created_at_ms INTEGER NOT NULL,
                last_seen_at_ms INTEGER
            );
            """
        )


def require_admin(authorization: str | None = Header(default=None)) -> None:
    expected = f"Bearer {_admin_token()}"
    if not authorization or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid administrator token")


class TextPart(BaseModel):
    type: str
    text: str = ""


class MessageRequest(BaseModel):
    id: str = Field(min_length=1)
    conversationId: str = Field(min_length=1)
    parts: list[TextPart] = Field(default_factory=list)


class PinProjection(BaseModel):
    conversationId: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=120)
    text: str = ""
    pinOrder: int


class PinsRequest(BaseModel):
    pins: list[PinProjection] = Field(default_factory=list)


class DeviceRequest(BaseModel):
    name: str = Field(default="Pico 2W", min_length=1, max_length=80)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="GPTi84 Companion Relay", version=VERSION, lifespan=lifespan)


@app.get("/v1/health", dependencies=[Depends(require_admin)])
def health() -> dict[str, Any]:
    return {"status": "ok", "version": VERSION}


@app.post("/v1/messages", dependencies=[Depends(require_admin)])
def create_message(
    request: MessageRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    key = idempotency_key or request.id
    with connect() as db:
        cached = db.execute(
            "SELECT response_json FROM idempotency WHERE key = ?", (key,)
        ).fetchone()
        if cached is not None:
            return json.loads(cached["response_json"])

        text = "\n".join(part.text for part in request.parts if part.type == "text")
        reply = _relay_text_reply(text)
        assistant_id = f"{request.id}_assistant"
        now = _now_ms()
        db.execute(
            "INSERT OR REPLACE INTO messages VALUES (?, ?, ?, ?, ?)",
            (request.id, request.conversationId, "user", text, now),
        )
        db.execute(
            "INSERT OR REPLACE INTO messages VALUES (?, ?, ?, ?, ?)",
            (assistant_id, request.conversationId, "assistant", reply, now),
        )
        response = {"message": {"id": assistant_id, "text": reply}}
        db.execute(
            "INSERT INTO idempotency VALUES (?, ?, ?)",
            (key, json.dumps(response, separators=(",", ":")), now),
        )
        return response


@app.get("/v1/pins", dependencies=[Depends(require_admin)])
def get_pins() -> dict[str, Any]:
    with connect() as db:
        rows = db.execute(
            """
            SELECT conversation_id, title, projection_text, pin_order, updated_at_ms
            FROM pins ORDER BY pin_order ASC
            """
        ).fetchall()
    return {
        "pins": [
            {
                "conversationId": row["conversation_id"],
                "title": row["title"],
                "text": row["projection_text"],
                "pinOrder": row["pin_order"],
                "updatedAtMs": row["updated_at_ms"],
            }
            for row in rows
        ]
    }


@app.put("/v1/pins", dependencies=[Depends(require_admin)])
def put_pins(request: PinsRequest) -> dict[str, Any]:
    if len(request.pins) > MAX_PINNED:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only eight chats can be pinned")
    seen = set()
    with connect() as db:
        db.execute("DELETE FROM pins")
        for pin in sorted(request.pins, key=lambda item: item.pinOrder):
            if pin.conversationId in seen:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Duplicate pinned chat")
            seen.add(pin.conversationId)
            db.execute(
                "INSERT INTO pins VALUES (?, ?, ?, ?, ?)",
                (
                    pin.conversationId,
                    pin.title.strip(),
                    _calculator_text(pin.text),
                    pin.pinOrder,
                    _now_ms(),
                ),
            )
    return get_pins()


@app.post("/v1/devices", dependencies=[Depends(require_admin)])
def create_device(request: DeviceRequest) -> dict[str, Any]:
    token = f"gpti84_{secrets.token_urlsafe(32)}"
    device_id = secrets.token_hex(8)
    with connect() as db:
        db.execute(
            "INSERT INTO devices VALUES (?, ?, ?, 0, ?, NULL)",
            (device_id, request.name.strip(), _hash_token(token), _now_ms()),
        )
    return {
        "device": {
            "id": device_id,
            "name": request.name.strip(),
            "token": token,
            "wsPath": "/v1/device/ws",
        }
    }


@app.websocket("/v1/device/ws")
async def device_ws(websocket: WebSocket) -> None:
    token = _websocket_bearer(websocket)
    device_id = _device_id_for_token(token)
    if device_id is None:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    _mark_device_seen(device_id)
    try:
        while True:
            packet = await websocket.receive_bytes()
            payload = _unframe(packet)
            prompt, math = _parse_pair(payload.decode("ascii", errors="replace"))
            reply_text = _relay_text_reply(prompt if not math else f"{prompt}\n{math}")
            frame = _pages_frame(reply_text)
            await websocket.send_bytes(struct.pack(">I", len(frame)) + frame)
    except WebSocketDisconnect:
        return


def _websocket_bearer(websocket: WebSocket) -> str:
    auth = websocket.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return ""
    return auth.removeprefix("Bearer ").strip()


def _device_id_for_token(token: str) -> str | None:
    if not token:
        return None
    token_hash = _hash_token(token)
    with connect() as db:
        row = db.execute(
            "SELECT id FROM devices WHERE token_hash = ? AND revoked = 0",
            (token_hash,),
        ).fetchone()
    return row["id"] if row else None


def _mark_device_seen(device_id: str) -> None:
    with connect() as db:
        db.execute(
            "UPDATE devices SET last_seen_at_ms = ? WHERE id = ?",
            (_now_ms(), device_id),
        )


def _unframe(packet: bytes) -> bytes:
    if len(packet) >= 4:
        (length,) = struct.unpack(">I", packet[:4])
        if length == len(packet) - 4:
            return packet[4:]
    return packet


def _parse_pair(text: str) -> tuple[str, str]:
    prompt = ""
    math = ""
    for line in text.split("\n"):
        if line.startswith("prompt:"):
            prompt = line[len("prompt:") :]
        elif line.startswith("math:"):
            math = line[len("math:") :]
    return prompt, math


def _relay_text_reply(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return "Relay received an empty calculator request."
    return f"Relay received: {cleaned}"


def _calculator_text(text: str) -> str:
    return "".join(c if 0x20 <= ord(c) < 0x7F else " " for c in text)


def _rewrap_line(line: str, cols: int = PAGE_COLS) -> list[str]:
    line = line.rstrip()
    if not line:
        return [""]
    words = line.split(" ")
    out: list[str] = []
    cur = ""
    for word in words:
        if len(word) > cols:
            if cur:
                out.append(cur)
                cur = ""
            for index in range(0, len(word), cols):
                chunk = word[index : index + cols]
                if len(chunk) == cols:
                    out.append(chunk)
                else:
                    cur = chunk
            continue
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= cols:
            cur = f"{cur} {word}"
        else:
            out.append(cur)
            cur = word
    if cur:
        out.append(cur)
    return out or [""]


def _layout_pages(text: str) -> list[str]:
    rows: list[str] = []
    for logical in _calculator_text(text).splitlines() or [""]:
        rows.extend(_rewrap_line(logical))
    pages: list[str] = []
    while rows and len(pages) < MAX_PAGES:
        page_rows = rows[:PAGE_ROWS]
        rows = rows[PAGE_ROWS:]
        while len(page_rows) < PAGE_ROWS:
            page_rows.append("")
        pages.append("".join(row[:PAGE_COLS].ljust(PAGE_COLS) for row in page_rows))
    return pages or [" " * PAGE_CHARS]


def _pages_frame(text: str) -> bytes:
    pages = _layout_pages(text)
    body = b"\x00".join(page.encode("ascii", errors="replace") for page in pages)
    return f"pages:{len(pages)}\n".encode("ascii") + body
