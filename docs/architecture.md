# GPTi84-Companion architecture

## Product boundary

- **TI-84 Plus:** text/math entry, eight pinned chats, recent projected history, paging, and status.
- **Pico 2WH:** DBUS transfer, Wi-Fi/WSS transport, BLE provisioning, acknowledgements, and recovery. It never stores provider keys or images.
- **Personal relay:** authenticated provider calls, encrypted provider settings, idempotency, pinned text projections, and calculator event queue.
- **Flutter app:** authoritative rich history, images, relay/device configuration, and synchronization.

## Current implementation

The firmware and calculator implementation are inherited from GPTi84-Plus and remain in their upstream layout. The companion app currently implements its local data and relay-facing seams; it does not pretend the unimplemented production relay or BLE protocol exists.

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
6. Complete Flutter provider management, images, pin synchronization, and offline recovery.
7. Run complete hardware, Android, iOS, security, and reconnect acceptance tests.

The full pre-migration planning record remains available at
`legacy/arduino-relay/documents/blueprints.md`.
