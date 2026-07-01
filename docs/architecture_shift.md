# Architecture shift: BLE GATT phone relay

## Purpose

GPTi84 Companion must use the phone as the relay. The production Pico-phone
transport should move from a phone-hosted TCP socket to a BLE GATT relay so the
same product direction can work on Android and iPhone without depending on
hotspot routing, inbound phone sockets, local IP discovery, or an external
server.

```text
TI-84 Plus <--2.5 mm DBUS--> Pico 2 W <--BLE GATT--> Android/iOS app <--HTTPS--> AI provider
```

The phone remains the only component that stores provider credentials, calls AI
providers, owns rich chat history, formats calculator-safe pages, and manages
idempotency/recovery. The Pico remains a bridge between the TI link and the
phone. It must not store provider secrets or implement provider-specific logic.

## Why BLE GATT

- iOS is strict about inbound networking, hotspot behavior, background sockets,
  and local-network permissions. A phone-hosted TCP server can be useful for
  Android bring-up but is not a dependable iPhone production transport.
- Bluetooth Classic SPP is not suitable for iPhone because generic serial
  profiles are not available to normal apps outside Apple MFi-style workflows.
- BLE GATT is supported by Android and iOS app APIs and fits the calculator
  payload size: short prompt/math requests in, bounded text pages out.
- The official Pico 2 W MicroPython target advertises BLE support, but runtime
  stability must be validated on the actual board before TI-link behavior is
  changed.

## Target behavior

The phone app is a BLE central. The Pico 2 W is a BLE peripheral that advertises
a GPTi84 service. The app scans for paired or provisionable Pico devices,
connects, subscribes to notifications, receives calculator-originated requests,
calls the selected phone-stored provider profile, and writes response chunks
back to the Pico.

The calculator sends one Str1 command/prompt payload:

```text
request body:  LIST | OPEN <chatId> | SEND <chatId> <messageId>\n<prompt>
response body: pages:N\n<page1>\0<page2>...
```

The wire transport changes, not the high-level calculator contract. Page bodies
remain fixed 16x8 calculator projections, ASCII-clamped, Markdown-stripped, and
limited to eight pages.

## BLE service contract

Use one custom primary service with stable UUIDs documented in code and docs.
The exact UUID values can be generated during implementation, but the shape is
fixed:

- **Control characteristic:** phone writes session commands such as hello,
  start request, cancel, ping, and reset.
- **Pico-to-phone characteristic:** Pico sends request chunks and status events
  using notifications.
- **Phone-to-Pico characteristic:** phone writes response chunks, provider
  errors, final page frames, and acknowledgements.
- **Status characteristic:** phone reads or subscribes to current firmware
  version, protocol version, battery/power status if available, TI-link status,
  last error, and current session state.

All GATT application payloads should use a small binary envelope instead of raw
text writes:

```text
u8  protocol_version
u8  message_type
u16 session_id
u16 sequence
u16 total_length
u16 chunk_offset
u16 chunk_length
u8  flags
u16 crc16
bytes chunk
```

Required message types:

- `HELLO`: capability and version exchange.
- `REQUEST_CHUNK`: Pico-to-phone calculator request data.
- `REQUEST_END`: Pico marks request body complete.
- `ACK`: acknowledges a chunk, message, or terminal state.
- `RESPONSE_CHUNK`: phone-to-Pico response data.
- `RESPONSE_END`: phone marks response body complete.
- `ERROR`: recoverable user-visible failure.
- `CANCEL`: aborts the active session.
- `PING` / `PONG`: connection liveness.
- `STATUS`: device/app state update.

Application payloads may also carry `catalog:<len>\n...` frames from the phone
to the Pico. Those frames update the phone-master `pins.v1` cache and are not
drawn as calculator pages.

The first implementation can use stop-and-wait chunking for simplicity: send one
chunk, wait for ACK, then send the next chunk. Sliding-window transfer can be
added later only if testing proves it is needed.

## Pairing and trust

The first production trust model should be device-bound pairing, not network
credentials:

- The Pico advertises as unpaired until explicitly paired in the app.
- The app shows nearby GPTi84 devices and asks the user to pair one.
- Pairing creates a random device secret stored in phone secure storage and on
  the Pico filesystem.
- Every relay session starts with a nonce challenge using that device secret.
- Unknown or failed devices may remain visible but cannot deliver calculator
  requests to the provider runtime.

This keeps provider credentials on the phone and prevents a random nearby BLE
device from using the app as an AI relay. If MicroPython BLE bonding support is
not reliable enough on Pico 2 W, keep the app-level shared secret challenge even
when OS-level pairing is unavailable.

## Flutter app changes

Replace the production relay runtime with a BLE relay service while keeping the
current TCP relay as temporary Android/dev scaffolding until BLE is proven.

Implementation plan:

1. Add a BLE transport layer using a Flutter BLE plugin that supports Android
   and iOS scanning, connections, characteristic writes, notifications, MTU
   negotiation where available, and permission handling.
2. Add a `BleRelaySession` service that owns connection state, chunk assembly,
   ACK/retry timers, request idempotency, provider calls, response formatting,
   and status events.
3. Reuse the current phone relay provider-call path and conversation storage:
   calculator-originated requests create user and assistant messages in the
   local calculator relay conversation.
4. Move calculator-safe response formatting into a shared app module used by
   both BLE relay tests and any temporary TCP relay tests.
5. Update the Calculator/Device UI to show BLE scan, pair, connect, relay
   status, active session, firmware/protocol version, and last error.
6. Keep direct phone AI chat unchanged as the stable rich-chat path.
7. Mark TCP relay controls as Android/dev only, or hide them behind a developer
   diagnostics flag after BLE works.

iOS-specific app requirements:

- Keep `NSBluetoothAlwaysUsageDescription`.
- Do not depend on inbound TCP sockets, Personal Hotspot routing, or local IP
  discovery for production relay behavior.
- Treat BLE relay as foreground-first unless later testing proves a specific
  background mode is acceptable and App Store-safe.

Android-specific app requirements:

- Request modern Bluetooth scan/connect permissions.
- Keep foreground-service work only if needed for long calculator sessions.
- Avoid requiring location permission unless the selected BLE plugin/platform
  combination makes it unavoidable on older Android versions.

## Pico 2 W firmware changes

The TI-link/DBUS implementation should remain isolated and unchanged until the
data cable is available. The first firmware patch should touch only the
phone-transport layer and a thin bridge adapter.

Implementation plan:

1. Verify the installed Pico 2 W MicroPython build exposes `bluetooth.BLE` and
   can advertise, accept a connection, receive writes, and send notifications.
2. Add a new BLE transport module, for example `src/ble_transport.py`, that
   implements the GPTi84 GATT service, chunk envelope, ACK/retry behavior,
   pairing secret storage, and connection status.
3. Keep `src/net.py` raw TCP available as a temporary development transport,
   but stop treating Wi-Fi phone relay config as the production path.
4. Update `src/bridge.py` to talk to an abstract relay transport with the same
   `send_framed` / received-frame semantics used by the current TCP bridge.
5. Preserve the single-Str command request body and `pages:N\n...` response
   body at the bridge boundary.
6. Add a dev boot option that runs a BLE echo/parity mode without touching
   GPIO/TI-link behavior.
7. Update `src/secrets.py.example` to contain BLE device name, optional pairing
   secret seed/dev reset flag, and no required Wi-Fi relay host for production.

Pico constraints:

- BLE chunks must respect negotiated MTU and work with conservative default MTU
  sizes.
- The Pico must tolerate phone disconnects, app kills, duplicate chunks,
  repeated ACKs, and power-cycle recovery.
- Provider errors from the phone should become calculator-safe `pages:N`
  responses rather than firmware exceptions.
- No provider keys, refresh tokens, model names, or provider URLs are stored on
  the Pico.

## Conversation and relay semantics

The BLE transport must not change the product-level relay rules:

- The phone stores complete rich chat history and provider credentials.
- The calculator sees only bounded text projections.
- Any number of phone chats may be pinned; the calculator browses them through
  paginated text projections.
- Every calculator-originated provider request gets a persisted idempotency ID
  before the phone calls a provider.
- Retries after BLE reconnect must not create duplicate provider calls if the
  phone already accepted a complete request.
- Calculator pages are generated deterministically from provider output:
  printable ASCII, no Markdown formatting, fixed 128-character pages, maximum
  eight pages.
- Images and files remain phone-originated only and are never sent over BLE to
  the Pico or calculator.

## Migration from current TCP relay

The current phone-hosted framed TCP relay should be treated as a useful
prototype, not the production transport.

Migration steps:

1. Keep TCP tests passing while BLE is built.
2. Extract shared request parsing and page formatting away from the TCP server.
3. Add BLE relay tests against the shared parser/formatter.
4. Wire the Calculator/Device UI to prefer BLE when available.
5. Move TCP controls to a developer diagnostics screen or remove them once BLE
   parity is achieved on hardware.
6. Update README and `docs/architecture.md` after the BLE relay patch lands so
   BLE GATT is described as the intended production Pico-phone transport.

Temporary backend/FastAPI files, Cloudflare tooling, WSS credentials, and
external relay docs remain non-production artifacts. They must not be used as
fallbacks for normal product behavior.

## Test plan

Python/Pico-side tests:

- Unit-test envelope encode/decode, CRC validation, duplicate chunk handling,
  ACK handling, timeout/retry state, and reassembly.
- Unit-test bridge compatibility with the existing request/response body shape.
- Verify imports on Pico: `main`, `bridge`, TI-link modules, and the new BLE
  transport module.
- On hardware without TI cable, run BLE echo/parity mode and confirm phone can
  send a sample request and receive a valid `pages:N` body.

Flutter tests:

- Unit-test BLE envelope encode/decode and chunk reassembly.
- Unit-test calculator request parsing and page formatting.
- Unit-test idempotent replay when a complete BLE request is received twice.
- Widget-test scan/pair/connect status, paired-device display, relay active
  state, and provider error display.
- Regression-test direct provider chat so phone rich-chat behavior remains
  unchanged.

Manual tests without TI cable:

1. Flash Pico 2 W-compatible MicroPython.
2. Confirm `bluetooth.BLE` is available on COM4.
3. Copy BLE firmware files and run BLE echo/parity mode.
4. Install the companion app on Android and iPhone.
5. Pair with the Pico from the app.
6. Send `LIST` or `SEND <chatId> <messageId>\n<prompt>` from the app test
   harness to the Pico or have the Pico simulate a calculator request.
7. Verify the app calls the selected provider and returns a chunked
   `pages:N\n...` response.
8. Kill/reopen the app, power-cycle the Pico, and verify reconnect/retry
   behavior does not duplicate provider calls.

Hardware gate later:

- Only after the BLE relay is stable, connect the TI data cable.
- Validate DBUS timing, voltage behavior, GP6/GP7 release/output-low behavior,
  unplug recovery, page delivery, and upstream GPTi84-Plus parity.
- Do not rewrite TI-link protocol logic as part of the BLE transport patch.

## Acceptance criteria

The BLE relay architecture is ready to replace TCP when:

- Android and iPhone can pair with the Pico and complete a request/response
  session while the app is foregrounded.
- The Pico can recover after phone disconnect, app restart, and Pico reboot.
- Response pages match the existing calculator-safe layout rules.
- Duplicate BLE request delivery does not duplicate provider calls.
- No production flow requires an external relay, relay URL, Cloudflare tunnel,
  WSS token, phone hotspot, or inbound socket to the phone.
- Existing direct phone chat and provider profile behavior remain unchanged.

## Assumptions

- BLE GATT is the intended production Pico-phone transport.
- The first supported BLE mode is foreground app operation.
- The current framed TCP relay remains temporary development scaffolding until
  BLE reaches parity.
- Pico 2 W MicroPython BLE support must be verified on the actual board before
  committing to final firmware APIs.
- TI-link/DBUS code is treated as known-working upstream-derived code and is
  left intact until the data cable is available.
