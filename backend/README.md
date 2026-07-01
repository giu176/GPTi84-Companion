# Relay backend

This directory contains the authenticated personal relay described in
`docs/architecture.md`.

The implementation uses FastAPI and SQLite and exposes:

- administrator health, message, pin, and device endpoints under `/v1`;
- a device-scoped WebSocket endpoint at `/v1/device/ws`;
- hashed revocable device tokens;
- idempotent text message processing;
- bounded text-only pinned projections for up to eight calculator chats;
- Pico-compatible framed responses shaped as `pages:N\n...`.

The retained `tools/relay_server.py` remains the upstream development relay and
must not be confused with this future authenticated service.

## Local run

```powershell
$env:RELAY_ADMIN_TOKEN="dev-admin-token"
$env:RELAY_DB="backend/relay.sqlite3"
.\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload
```

Flutter relay settings should point at `http://127.0.0.1:8000` with the
administrator token above.
