# GPTi84-Companion architecture

## Product boundary

- **TI-84 Plus:** text/math entry, eight pinned chats, recent projected history, paging, and status.
- **Pico 2WH:** DBUS transfer, Wi-Fi/WSS transport, BLE provisioning, acknowledgements, and recovery. It never stores provider keys or images.
- **Personal relay:** authenticated provider calls, encrypted provider settings, idempotency, pinned text projections, and calculator event queue.
- **Flutter app:** authoritative rich history, images, relay/device configuration, and synchronization.

### Direct phone chat

The Flutter application may call a user-selected AI provider directly for rich phone conversations. Provider API keys are held in platform secure storage; images and files are copied to app-private storage and sent only with their owning message. This path works without the Pico or relay.

Provider credentials live in a versioned encrypted vault. Multiple named profiles of the same provider are permitted. New chats snapshot the global favorite, existing chats retain their selected profile, and assistant messages record which profile generated them.

ChatGPT consumer-subscription access is an isolated experimental interface. It uses Codex device authorization, stores access and refresh tokens in platform secure storage, and calls the private Codex Responses backend. It supports text and Responses-compatible image inputs, but not general file inputs. It must remain visibly marked experimental and removable without changing stable API-key adapters. The application must never collect ChatGPT passwords, cookies, or browser sessions.

### Calculator and relay

The hosted or self-hosted relay remains responsible for provider access used by standalone calculator chat, synchronization, and bounded pinned-chat projections.

## Current implementation

The firmware and calculator implementation are inherited from GPTi84-Plus and remain in their upstream layout. The companion app implements direct rich provider chat plus its local data and relay-facing seams; it does not pretend the unimplemented production relay or BLE protocol exists.

The working Arduino prototype is preserved at `legacy/arduino-relay/` as a tested reference and possible future variant.

## Pico 2WH gate

The upstream Pico W implementation must first be proven on RP2350:

1. Install Pico 2 W-compatible MicroPython, never the original Pico W UF2.
2. Validate GPIO, timing, filesystem, Wi-Fi, DNS, NTP, TLS, WSS, and BLE.
3. Measure the exact TI-84 link-line voltage and timing before direct wiring.
4. Validate GP6/GP7 release and output-low behavior.
5. Pass bidirectional all-byte, timeout, unplug, and power-cycle tests.
6. Reproduce upstream echo and LLM/WSS operation before extending the protocol.

## Conversation rules

- The phone stores complete rich chats and app-private image files.
- No more than eight chats may be pinned to the calculator.
- The relay stores bounded text-only context for pinned chats and pending device events.
- Each provider request has a persisted idempotency ID before submission.
- Images originate on the phone, are transient on the relay, and never reach the calculator.
- Calculator output is deterministically transliterated, stripped of display-only Markdown, mapped to TI-safe math, and wrapped into at most eight 16×7 pages.

## Roadmap

1. Establish Pico 2WH parity with upstream.
2. Build the FastAPI/SQLite authenticated relay and provider adapters.
3. Define versioned WSS envelopes, acknowledgements, and synchronization.
4. Add BLE provisioning and device status.
5. Add calculator pinned-chat browsing and history.
6. Complete Flutter pin synchronization and offline recovery.
7. Run complete hardware, Android, iOS, security, and reconnect acceptance tests.

The full pre-migration planning record remains available at
`legacy/arduino-relay/documents/blueprints.md`.
