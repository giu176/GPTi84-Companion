# GPTi84-Companion architecture

## Product boundary

GPTi84 Companion turns the phone into the relay. There is no required hosted,
self-hosted, PC, VPS, or cloud relay in the intended product path.

```text
TI-84 Plus Axe app <--raw link bytes--> Pico 2 W <--BLE GATT--> phone app <--HTTPS--> AI provider
```

- **TI-84 Plus:** Axe-native text entry, pinned-chat browsing, recent
  projected history, paging, key loop, and status.
- **Pico 2 W:** raw Axe link framing, local phone transport, BLE provisioning,
  acknowledgements, and recovery. It never stores provider keys, provider
  refresh tokens, images, or rich chat history.
- **Phone companion app:** authoritative relay runtime, provider calls,
  encrypted provider settings, idempotency, complete rich history, image/file
  handling, pinned text projections, device status, and calculator event queue.

The phone must be able to serve calculator-originated chat without any external
relay service. Provider traffic leaves the user's devices only when the phone
calls the selected AI provider over HTTPS.

## Direct phone chat

The Flutter application may call a user-selected AI provider directly for rich
phone conversations. Provider API keys are held in platform secure storage;
images and files are copied to app-private storage and sent only with their
owning message. This path works without the Pico.

Provider credentials live in a versioned encrypted vault. Multiple named
profiles of the same provider are permitted. New chats snapshot the global
favorite, existing chats retain their selected profile, and assistant messages
record which profile generated them.

ChatGPT consumer-subscription access is an isolated experimental interface. It
uses Codex device authorization, stores access and refresh tokens in platform
secure storage, and calls the private Codex Responses backend. It supports text
and Responses-compatible image inputs, but not general file inputs. It must
remain visibly marked experimental and removable without changing stable API-key
adapters. The application must never collect ChatGPT passwords, cookies, or
browser sessions.

## Calculator relay path

The phone app owns the relay behavior for standalone calculator chat:

- receives calculator requests from the Pico over a local transport;
- persists an idempotency record before calling an AI provider;
- calls the selected provider using credentials stored on the phone;
- converts rich provider output into calculator-safe text;
- wraps responses into at most eight 16x8 pages;
- sends acknowledgements, status, errors, and final pages back to the Pico;
- stores the resulting assistant message in the phone's conversation history.

The production phone transport is the custom GPTi84 BLE GATT service documented
in `architecture_shift.md`. Calculator-originated traffic now uses the raw Axe
link protocol documented in `raw_axe_link_protocol.md`:

```text
calc -> Pico -> phone: raw frame containing LIST | OPEN:<slot> | SEND:<slot>:<prompt>
phone -> Pico -> calc: raw frame containing pages:N\n<page1>\0<page2>...
```

The app is the BLE central and the Pico is the peripheral. Binary envelopes,
CRC validation, stop-and-wait acknowledgements, and session IDs carry request
and response chunks. The framed TCP phone server remains developer scaffolding,
not a production fallback.

## Current implementation

The companion app implements rich provider chat, local conversation storage,
BLE discovery/connection, chunk assembly, idempotent provider dispatch, and
calculator-safe response paging. Pico firmware advertises the GPTi84 GATT
service and adapts it to the raw Axe calculator-link bridge.

The older TI-BASIC/DBUS `Str1` plus `Str3..Str0` implementation remains in the
repository as bring-up history, but it no longer defines the active production
calculator path.

The working Arduino prototype is preserved at `legacy/arduino-relay/` as an
important reference because it already used an Android app as the relay between
bridge hardware and AI providers.

The temporary FastAPI backend and server relay tooling are development artifacts
and must not define the final product architecture.

## Pico 2 W gate

The upstream Pico W implementation must first be proven on RP2350:

1. Install Pico 2 W-compatible MicroPython, never the original Pico W UF2.
2. Validate GPIO, timing, filesystem, Wi-Fi, DNS, NTP, TLS if used, local
   phone transport, and BLE.
3. Measure the exact TI-84 link-line voltage and timing before direct wiring.
4. Validate GP6/GP7 release and output-low behavior.
5. Pass bidirectional all-byte, timeout, unplug, and power-cycle tests.
6. Reproduce upstream echo and paginated reply operation before extending the
   protocol.

## Conversation rules

- The phone stores complete rich chats and app-private image files.
- Any number of chats may be pinned on the phone; the calculator browses them
  through paginated text projections.
- The phone stores bounded text-only projections for pinned chats and pending
  calculator events.
- Each provider request has a persisted idempotency ID before submission.
- Images originate on the phone, never reach the Pico or calculator, and are
  sent only to the selected provider when attached to a phone-originated request.
- Calculator output is deterministically transliterated, stripped of
  display-only Markdown, mapped to TI-safe math where appropriate, and wrapped
  into at most eight 16x8 pages.

## Roadmap

1. Establish raw Axe link framing between TI-84 Plus and Pico 2 W.
2. Validate the BLE peripheral on the installed Pico 2 W MicroPython build.
3. Complete device-bound pairing and reconnect recovery on physical hardware.
4. Validate foreground Android and iOS request/response sessions.
5. Complete Axe-native pinned-chat browsing and history.
6. Complete phone-owned pin synchronization and offline recovery.
7. Run complete hardware, Android, iOS, security, reconnect, and power-cycle
   acceptance tests.

The external-relay cleanup record is tracked in `docs/architecture_shift.md`.
