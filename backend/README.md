# Relay backend

This directory is reserved for the authenticated personal relay described in
`docs/architecture.md`.

The production implementation will use FastAPI and SQLite and will expose:

- administrator endpoints for provider, device, conversation, and message management;
- a device-scoped WSS endpoint for Pico 2WH traffic;
- encrypted provider credentials and revocable device tokens;
- provider-neutral OpenAI, Anthropic, Gemini, OpenAI-compatible, and Ollama adapters;
- idempotent message processing, pinned text projections, and pending event synchronization.

The retained `tools/relay_server.py` remains the upstream development relay and
must not be confused with this future authenticated service.
