# TI-84 Plus AI Chat Link — Project Blueprint

Status: implementation blueprint; Path C selected  
Baseline hardware: **classic monochrome TI-84 Plus** (Z80 CPU, 96×64 display) + **Arduino Uno bridge** + **ZS-040/HC-05 Bluetooth Classic module**  
Calculator connection: **2.5 mm I/O link port**; the USB port is out of scope for the first prototype  
Phone target: Android 12+  
Last updated: 2026-06-21

Implementation note: the PC/Arduino/HC-05/Android/API test stack is now present under `tools/file_relay`, `arduino`, and `android`. The TI-84 link-port application remains the next hardware milestone.

## 1. Purpose

Build a calculator-to-phone chat system in two milestones:

1. Turn a TI-84 Plus into a small, reliable Bluetooth chat terminal.
2. Turn the Android phone into an unattended relay between that terminal and one or more AI APIs.

The calculator owns text entry, chat display, local history, link status and retry behavior. The phone owns Bluetooth pairing, internet access, API credentials, provider calls, response normalization and optional calculator-specific formatting.

This document is a build guide, not a promise that every proposed electrical connection is safe. Verify the exact calculator revision and Bluetooth board before connecting hardware.

## 2. The first decision: exact calculator model

“TI-84 Plus” and “TI-84 Plus CE” are different development targets. This blueprint assumes the original monochrome TI-84 Plus. Do not begin firmware work until the model is recorded in `hardware/target.md`.

| Target | Display | CPU/toolchain family | This blueprint |
|---|---:|---|---|
| TI-84 Plus / Silver Edition | 96×64 monochrome | Z80 | Primary target |
| TI-84 Plus C Silver Edition | 320×240 color | eZ80 family | Separate port |
| TI-84 Plus CE | 320×240 color | eZ80/CE toolchain | Separate port; not source-compatible |

Keep shared protocol test vectors platform-neutral so a CE client can be added later.

## 3. Feasibility and hardware warning

### 3.1 Why a ZS-040 is not a plug-in peripheral

A common ZS-040 carrier contains an HC-05-style Bluetooth Classic serial module. Its data side is UART. The TI-84 Plus 2.5 mm link port is a calculator link bus, not a conventional TX/RX UART, and the USB connector is not a UART connector. Therefore:

- never connect a ZS-040 directly to the USB pins;
- never assume the link-port lines can accept push-pull UART signaling;
- never power the module from an unverified calculator pin;
- verify supply and logic levels for the exact board clone, since ZS-040 variants differ;
- use a common ground and current-limited bench supply during experiments.

The “calculator + ZS-040 only” goal is a research path, not the baseline production architecture. Direct link-port bit-banged serial may be possible with passive protection/level adaptation, but it must pass oscilloscope and reliability tests. It risks tying up the CPU while receiving and may not tolerate the module’s electrical behavior.

### 3.2 Selected hardware path

**Path C is selected:** TI-84 Plus 2.5 mm I/O link port ↔ protected two-wire interface ↔ Arduino Uno ↔ UART ↔ ZS-040/HC-05 ↔ Bluetooth Classic SPP ↔ Android.

The Arduino Uno is the prototype bridge. It handles calculator link timing, frame buffering, checksums, retries and UART traffic to the Bluetooth module. A smaller 3.3 V board may replace it only after the complete system works.

The first prototype will not use the calculator USB port. A standard Uno cannot act as a general USB host without extra host hardware, and implementing the calculator USB protocol would add unnecessary risk. The TI 2.5 mm link port is directly controllable by calculator software and is the appropriate interface for this milestone.

The calculator link is also **not UART**. It is a two-wire, open-drain-style handshake bus. The calculator and Arduino firmware will use a small custom packet protocol over that physical link. The Arduino-to-ZS-040 side is conventional UART.

### 3.3 Arduino Uno electrical interface

Do not connect Uno output pins directly to the calculator link lines. The Uno is a 5 V device, while the calculator link bus expects devices to release a line or pull it low; actively driving a line high can create contention.

Use a protected two-channel interface that provides:

- open-drain/open-collector pull-down control for each calculator link line;
- high-impedance sensing of each line by the Uno;
- no 5 V driven into the calculator;
- series resistance/current limiting and a common ground;
- a 2.5 mm TRS breakout whose tip, ring and sleeve are verified with measurements rather than assumed;
- named signals `LINK_A`, `LINK_B` and `GND` in all schematics and code.

A pair of small transistors or MOSFET level-interface channels is preferred. The exact component values must be approved from measured calculator idle voltage and rise time. Test with a current-limited supply and oscilloscope or logic analyzer before attaching the Bluetooth module.

The ZS-040 is powered separately during early tests. Verify the exact carrier board: many accept 5 V at the carrier supply pin but still use approximately 3.3 V UART logic. Protect the module RX input from a 5 V Uno TX signal with a suitable divider or level shifter. The module TX signal can normally be sensed by the Uno as a logic high, but this must be verified for the exact board.

For the initial Uno/ZS-040 breadboard, external power capacitors are optional rather than required: typical Uno and ZS-040 carriers already contain regulation and decoupling. Keep wires short. Add a 100 nF ceramic and 47–100 µF bulk capacitor near the module only if testing reveals radio resets, disconnects, or corrupted traffic.

Suggested Uno pin allocation for the prototype:

| Function | Uno pin | Notes |
|---|---:|---|
| Calculator `LINK_A` sense/pull-down | D2 | protected interface; interrupt-capable |
| Calculator `LINK_B` sense/pull-down | D3 | protected interface; interrupt-capable |
| ZS-040 RX | D11 | Uno TX through level adaptation |
| ZS-040 TX | D10 | Uno software UART RX |
| USB serial diagnostics | D0/D1 | keep isolated from calculator and Bluetooth paths |

Pin allocation is provisional until the firmware timing experiment passes.

## 4. Proposed system architecture

```text
┌───────────────────────────┐
│ TI-84 Plus                │
│ chat UI + editor          │
│ history + formula tokens  │
│ framed protocol + retry   │
└─────────────┬─────────────┘
              │ 2.5 mm two-wire link bus
┌─────────────▼─────────────┐
│ protected level interface │
└─────────────┬─────────────┘
              │ LINK_A + LINK_B
┌─────────────▼─────────────┐
│ Arduino Uno bridge        │
│ handshake + frame buffer  │
└─────────────┬─────────────┘
              │ UART
┌─────────────▼─────────────┐
│ ZS-040 / HC-05            │
│ Bluetooth Classic SPP     │
└─────────────┬─────────────┘
              │ RFCOMM byte stream
┌─────────────▼─────────────┐
│ Android relay             │
│ connection service        │
│ provider adapters         │
│ queue, database, security │
│ response formatter        │
└─────────────┬─────────────┘
              │ HTTPS
┌─────────────▼─────────────┐
│ OpenAI / other AI APIs    │
└───────────────────────────┘
```

The calculator never calls an AI provider directly. The Android app never sends provider JSON over Bluetooth. The on-air protocol remains small and provider-neutral.

## 5. Recommended software stack

### Calculator

- **Primary language:** Z80 assembly for the link driver, interrupt-sensitive routines and small drawing primitives.
- **Application language:** C where the selected TI-84 Plus toolchain proves stable; otherwise Z80 assembly for the first release. Evaluate z88dk and spasm-ng with a hello-world, grayscale-free graphics test and link-port test before committing.
- **Build:** reproducible command-line build, pinned tool versions, emulator smoke tests and real-calculator acceptance tests.
- **Storage:** TI application variables for preferences and bounded history; validate size before every write and use versioned records with checksums.

Assembly is not the easiest language in general, but it is the lowest-risk choice for tight memory, timing-sensitive I/O and a 96×64 Z80 target. C is preferred for higher-level UI/state code only after its runtime cost is measured.

### Android

- **Language:** Kotlin.
- **UI:** Jetpack Compose for settings, diagnostics and chat inspection.
- **Architecture:** unidirectional state flow with `ViewModel`; separate Bluetooth, protocol, persistence and AI-provider modules.
- **Bluetooth:** Android Bluetooth Classic RFCOMM/SPP APIs. Request runtime Bluetooth permissions according to the Android version; do not assume discovery can run silently.
- **Background work:** a foreground service while an active calculator session is connected; WorkManager for deferred retries and health checks, not for a permanent socket.
- **Persistence:** Room database for devices, conversations, queue entries and provider metadata; Android Keystore-backed encrypted storage for API secrets.
- **Networking:** OkHttp/Ktor with explicit timeouts, cancellation, streaming support and redacted logs.
- **Serialization:** Kotlinx Serialization.
- **Testing:** JUnit, coroutine test utilities, fake RFCOMM streams, MockWebServer and Android instrumentation tests.

### AI integration

Implement `AiProvider` as an internal interface:

```kotlin
interface AiProvider {
    suspend fun selfTest(): ProviderHealth
    fun stream(request: RelayRequest): Flow<ProviderEvent>
    fun capabilities(): ProviderCapabilities
}
```

Each provider adapter owns authentication, request mapping, streaming parsing, error mapping and rate-limit hints. The first adapter should use the current OpenAI Responses API rather than automating the ChatGPT consumer application. Do not hard-code a “latest” model name in calculator firmware; store model selection in Android configuration and validate it during provider self-test.

For a personal prototype, secrets may live encrypted on the phone. For distribution, do not embed shared provider keys in the APK; use user-supplied keys or a controlled server-side token broker.

## 6. Calculator application design

### 6.1 Screen layout

The 96×64 display is extremely small. Favor information density over decorative chat bubbles.

```text
┌────────────────────────┐  0..7   status: BT ● / TX / RX / ERR
│BT●  PHONE       12:34  │
├────────────────────────┤
│YOU: solve x^2=4        │  scrollable transcript
│AI : x = -2 or 2        │
│      because ...       │
│                        │
├────────────────────────┤
│> _                     │  one/two-line composer
└────────────────────────┘
```

Suggested keys:

- arrows: move cursor or scroll;
- `ENTER`: send;
- `CLEAR`: cancel/back; hold to clear draft;
- `DEL`: delete character/token;
- `ALPHA` and `2nd`: normal calculator input modes;
- `GRAPH`: conversation list;
- `TRACE`: connection diagnostics;
- `ZOOM`: formatting/view options.

Use a deterministic UI state machine: `STARTUP`, `DISCONNECTED`, `CONNECTING`, `READY`, `EDITING`, `SENDING`, `RECEIVING`, `ERROR`, `SETTINGS`. Every state must define accepted keys, rendered indicators and timeout behavior.

### 6.2 Text model

Do not store screen pixels as the message. Store a compact sequence of semantic runs:

- ASCII-compatible text;
- calculator symbol tokens (π, √, exponent, comparison operators);
- line break;
- emphasis role (`normal`, `user`, `assistant`, `system`, `code`);
- formula start/end and optional superscript/subscript runs.

Use a constrained wire encoding. UTF-8 is acceptable between phone and protocol library, but the phone formatter must transliterate unsupported characters before display. Maintain an explicit glyph map and a visible replacement glyph; never silently drop bytes.

### 6.3 Formula formatting

Do not attempt a complete LaTeX renderer in milestone 1. Support a small grammar:

- fractions as `a/b` initially;
- powers using the calculator exponent glyph and compact superscript where legible;
- square roots, π, θ, ≤, ≥, ≠ and arrows through native/custom glyphs;
- short inline expressions;
- plain-text fallback for any unsupported construct.

Android should transform Markdown/LaTeX-like provider output into this subset. The calculator renderer remains deterministic and does not parse arbitrary Markdown.

### 6.4 History and memory policy

- Keep a ring buffer of only the most recent rendered messages in RAM.
- Store a bounded conversation summary/history in an application variable.
- Save atomically: write a new version, verify checksum, then replace the index record.
- Define hard limits for draft bytes, message bytes, messages per conversation and stored conversations.
- The Android database is the authoritative full transcript; the calculator is a cache.

## 7. Bluetooth ownership and device memory

The ZS-040/HC-05 behaves as a serial radio; Android performs system Bluetooth pairing. Do not build a second security fiction inside the calculator UI.

Calculator stores only:

- logical peer nickname;
- protocol peer ID and last successful session ID;
- preferred baud/profile;
- last sequence counters and a small resume token;
- checksum and record version.

Android stores:

- bonded-device address/identifier and friendly name;
- calculator peer ID;
- last-seen time, protocol version and capabilities;
- auto-connect preference;
- connection health counters.

Connection policy:

1. Android opens the RFCOMM listener/client appropriate to the tested module mode.
2. Peers exchange `HELLO` and capabilities.
3. Both validate protocol version and maximum frame size.
4. Android sends `READY`; calculator enables send.
5. Heartbeats detect half-open links.
6. On failure, preserve unsent frames and reconnect with exponential backoff plus jitter.
7. Resume only after peer ID and conversation ID match; otherwise start a clean session.

## 8. Wire protocol

Treat Bluetooth/RFCOMM as a byte stream: reads can split or combine messages. Never equate one socket read with one application message.

### 8.1 Frame format

Use a compact binary frame with byte stuffing (COBS or SLIP). A suitable decoded layout is:

| Field | Bytes | Meaning |
|---|---:|---|
| Magic/version | 1 | upper bits identify protocol, lower bits version |
| Type | 1 | message kind |
| Flags | 1 | ACK requested, continuation, final, error |
| Sequence | 2 | sender sequence number |
| Payload length | 2 | bounded payload size |
| Payload | 0..N | type-specific bytes |
| CRC-16 | 2 | detects corruption |

Start with `N = 192` or smaller after RAM measurement. Multi-frame messages carry message ID, chunk index and total/final marker.

### 8.2 Message types

- `HELLO`, `CAPABILITIES`, `READY`;
- `PING`, `PONG`;
- `CHAT_BEGIN`, `CHAT_CHUNK`, `CHAT_END`;
- `REPLY_BEGIN`, `REPLY_CHUNK`, `REPLY_END`;
- `ACK`, `NACK`, `CANCEL`;
- `STATUS`, `ERROR`;
- `FORMAT_PROFILE`;
- `RESET_SESSION`.

Use ACKs for complete frames, a small sliding or stop-and-wait window for milestone 1, retry limits and idempotency keys. Android must never submit the same user message twice after a reconnect: persist the calculator message ID before making the provider call.

### 8.3 Protocol repository artifacts

Maintain:

- `protocol/spec.md` as the normative definition;
- `protocol/test-vectors/` with valid, truncated, escaped, bad-CRC and duplicate frames;
- a JVM reference codec;
- a host-side C codec compiled with sanitizers/fuzzing where supported;
- golden interoperability tests shared with calculator fixtures.

## 9. Milestone 1 — Bluetooth screen

### Small-step implementation plan

Complete these steps in order. Each step ends with a visible, repeatable test and is committed before starting the next one.

#### Step 1 — Arduino Uno ↔ TI-84 physical communication

Goal: prove that the Uno and a custom calculator program can exchange bytes through the 2.5 mm I/O link port.

1. Confirm the exact TI-84 Plus model and create the protected two-channel interface.
2. With the calculator disconnected, verify that the Arduino side can only pull each interface output low or release it; it must never drive the calculator side high.
3. Connect the calculator and record idle and asserted waveforms for both lines.
4. Implement Arduino primitives: `releaseA`, `pullLowA`, `readA`, `releaseB`, `pullLowB`, `readB` and timeout handling.
5. Implement matching Z80 primitives in a minimal calculator test program.
6. Implement one byte transfer using the two link lines and explicit acknowledgement.
7. Add a timeout that releases both lines and returns to idle after any interrupted transfer.
8. Send fixed byte patterns in both directions: `00`, `FF`, `55`, `AA`, then all values `00..FF`.

Pass condition: all 256 byte values transfer both ways for 1,000 cycles, with no stuck line and automatic recovery after unplugging/reconnecting the cable.

This is link communication, not asynchronous UART. Keep the low-level calculator link driver separate from the later packet and Bluetooth code.

#### Step 2 — print a known Arduino message on the calculator

Goal: make success visible on the TI-84 screen before introducing Bluetooth.

1. Define a temporary test packet: `length`, ASCII payload, simple checksum.
2. Make the Arduino send `HELLO FROM ARDUINO` when its reset button is pressed or when a command is entered over the Uno USB serial monitor.
3. Make the calculator receive the packet into a bounded buffer.
4. Validate the length and checksum before displaying anything.
5. Render the message on the calculator graph screen and show `LINK ERROR`, `TIMEOUT` or `BAD CHECKSUM` for controlled failures.
6. Add scrolling only if the test message exceeds the screen; do not build the full chat UI yet.

Pass condition: the calculator displays `HELLO FROM ARDUINO` correctly on 100 consecutive Uno resets, rejects a deliberately corrupted packet and returns to a ready screen after a timeout.

#### Step 3 — send calculator text back to the Arduino

Goal: establish full duplex behavior independently of Bluetooth.

1. Enter a short message on the calculator.
2. Send it as a checked packet to the Uno.
3. Print the decoded payload in the Arduino USB serial monitor.
4. Add sequence numbers and ACK/NACK responses.

Pass condition: 100 calculator messages arrive exactly once and in order; a forced dropped ACK causes retransmission without duplicate delivery.

#### Step 4 — add ZS-040 Bluetooth transport

Goal: replace the Uno USB serial monitor as the external terminal.

1. Qualify ZS-040 power and UART logic levels.
2. Configure and record module name, PIN, role and baud rate.
3. Connect the module to the Uno software UART through the required level adaptation.
4. Forward complete calculator packets to Bluetooth and Bluetooth packets to the calculator.
5. Keep USB serial diagnostics enabled without mixing diagnostic text into protocol bytes.

Pass condition: an Android serial-terminal/debug app sends `HELLO TI84` and receives a calculator reply through the complete chain.

#### Step 5 — replace the temporary packet with protocol v1

Goal: make the link robust enough for chat messages.

Add framing, CRC-16, sequence IDs, ACK/NACK, retry limits, chunking, heartbeat and bounded queues. Reuse the same logical frame on the Arduino/Bluetooth path; only the calculator-link byte transport is hardware-specific.

Pass condition: pass stream fragmentation, corruption, unplug/reconnect and duplicate-frame tests without crashes or duplicate chat delivery.

#### Step 6 — build the minimal calculator chat UI

Goal: one editable outgoing message and one scrollable incoming reply.

Add the status bar, editor, send/cancel controls, transcript renderer and explicit link/error states. Rich formula layout and persistent conversation history remain later tasks.

Pass condition: complete a ten-message conversation through the Android debug app while displaying connection and retry state accurately.

#### Step 7 — connect the Android AI relay

Goal: replace the debug echo/terminal with one configured AI provider.

Implement durable message receipt, exactly-once provider submission, deterministic reply formatting and resumable delivery. Add multiple providers only after this vertical slice passes process-death and reconnect tests.

### Deliverables

1. Calculator app with editor, transcript, scrolling, status bar and error screens.
2. Calculator transport driver for the selected hardware path.
3. Version 1 framed protocol with CRC, ACK/retry, chunking and heartbeat.
4. Pairing/reconnect flow and persisted peer metadata.
5. Debug Android app that can:
   - list already bonded compatible devices;
   - connect/disconnect;
   - show raw and decoded frames;
   - send text, patterns and fault-injected frames;
   - measure throughput, latency, retries and reconnect time;
   - export a redacted diagnostic report.
6. Electrical schematic, bill of materials and feasibility report.

### Acceptance criteria

- Send and receive 1,000 mixed-size messages without an unrecovered protocol error.
- Correctly reassemble messages across arbitrary stream fragmentation.
- Recover after radio power loss without restarting the calculator app.
- Do not duplicate a sent chat message after reconnect.
- Restore the known peer after 100 calculator/radio/phone power-cycle combinations.
- Keep the calculator UI responsive during receive and retry.
- Render all supported glyphs and visibly replace unsupported ones.
- Corrupt, oversized or out-of-order frames produce a bounded error, never a crash or buffer overrun.
- Document measured battery/current behavior and safe electrical limits.

## 10. Milestone 2 — Android AI relay

### 10.1 Relay pipeline

```text
calculator frame
  → validate/deduplicate
  → persist queued message
  → build provider-neutral request
  → provider adapter
  → stream response
  → normalize Markdown/formulas
  → wrap to calculator display profile
  → chunk + persist
  → transmit with ACK/resume
```

Persist state at every boundary. A process death between provider response and Bluetooth delivery must resume delivery without calling the provider again.

### 10.2 API manager

Each provider configuration includes endpoint/profile, credential reference, model ID, timeouts, maximum output, enabled capabilities and health state. The self-test should check:

1. credential is present and decryptable;
2. network/DNS/TLS are available;
3. provider authentication succeeds using the least costly supported request;
4. selected model is accessible;
5. a tiny structured response can be parsed;
6. streaming/cancellation works if enabled;
7. failures are translated into actionable categories.

Never expose API keys, raw authorization headers or full private prompts in logs or Bluetooth diagnostics.

### 10.3 Background operation

- Use a user-visible foreground service while maintaining an active Bluetooth session.
- Keep a durable outbox/inbox in Room with states such as `RECEIVED`, `SUBMITTING`, `GENERATING`, `FORMATTING`, `DELIVERING`, `ACKED`, `FAILED`.
- Apply explicit network and provider timeouts.
- Retry only transient failures; do not retry authentication, invalid request or unsupported-model failures indefinitely.
- Provide notification actions to disconnect, cancel generation or open diagnostics.
- Expect Android/OEM background restrictions; test with screen off, Doze, battery saver and app process recreation.

### 10.4 Reply formatting profile

Android receives calculator capabilities during handshake:

```text
width_px=96; height_px=64; font=small-v1;
max_line_px=92; glyph_set=ti84-v1;
formula_set=math-lite-v1; max_message_bytes=2048
```

The formatter should:

- remove unsupported Markdown structures;
- convert tables to compact labeled lines;
- translate formulas to the supported math subset;
- wrap using glyph pixel widths, not character counts;
- keep code indentation only when readable;
- prefer short paragraphs and semantic breaks;
- enforce byte and line limits;
- optionally ask the AI provider for concise calculator-friendly output, while still applying deterministic local formatting afterward.

Provider output is untrusted data. It must never become protocol commands; control frames and content frames remain structurally separate.

### Milestone 2 acceptance criteria

- Provider self-test distinguishes credentials, network, quota/rate limit, model access and parse failures.
- A received calculator message survives Android process death and is relayed exactly once.
- A completed response survives Bluetooth loss and resumes at the last acknowledged chunk.
- API secrets are absent from APK resources, database plaintext, exported diagnostics and logs.
- The relay operates for an eight-hour screen-off soak test with documented device settings.
- Formatter golden tests cover prose, code, lists, tables, Unicode, long words and formulas.

## 11. Repository layout

```text
TI84/
├─ README.md
├─ document/
│  └─ blueprints.md
├─ calculator/
│  ├─ src/
│  ├─ include/
│  ├─ assets/
│  ├─ tests/
│  └─ toolchain.lock.md
├─ android/
│  ├─ app/
│  ├─ bluetooth/
│  ├─ protocol/
│  ├─ relay/
│  ├─ providers/
│  └─ formatter/
├─ protocol/
│  ├─ spec.md
│  └─ test-vectors/
├─ hardware/
│  ├─ target.md
│  ├─ schematic/
│  ├─ bom.csv
│  └─ feasibility-report.md
└─ tools/
   └─ protocol-harness/
```

## 12. Development sequence

### Phase 0 — de-risk hardware

- freeze exact calculator, Arduino Uno and ZS-040 variants;
- build and verify the protected 2.5 mm link interface;
- complete Steps 1 and 2: bidirectional bytes and visible calculator text;
- do not attach the Bluetooth module until the wired link passes.

### Phase 1 — protocol and host harness

- write protocol v1 and golden vectors;
- implement the Kotlin reference codec and desktop/debug harness;
- fuzz decoder boundaries and verify duplicate handling.

### Phase 2 — calculator vertical slice

- render one incoming static message;
- add editor and send one frame;
- add ACK/retry, chunking and connection state;
- add bounded history and supported math glyphs.

### Phase 3 — debug Android app

- pair/connect through system Bluetooth;
- add frame console, scripted tests and metrics;
- pass milestone 1 soak and power-cycle tests.

### Phase 4 — one AI provider end to end

- add secure configuration and provider self-test;
- relay one request with streaming/cancellation;
- persist exactly-once state;
- apply deterministic calculator formatting.

### Phase 5 — reliability and additional providers

- extract provider interface only after the first adapter works;
- add a second provider to validate the abstraction;
- test Doze, process death, offline queue, rate limits and reconnect resume;
- prepare signed releases and reproducible build instructions.

## 13. Testing strategy

### Calculator

- emulator tests for UI/state logic where timing is not hardware-dependent;
- real-hardware tests for link timing, storage, key rollover and power cycles;
- canary bytes around buffers in debug builds;
- golden screenshots or framebuffer hashes for layout cases.

### Protocol

- round-trip properties for every frame type;
- randomized fragmentation/concatenation of the byte stream;
- fuzz malformed lengths, escapes, CRCs and sequence transitions;
- duplicate, drop, reorder and delayed-ACK simulation;
- compatibility test before any protocol version bump.

### Android/relay

- fake Bluetooth streams and provider adapters for deterministic tests;
- HTTP mock server for streaming, timeout, rate-limit and malformed-response cases;
- database migration and process-restart tests;
- physical-device matrix covering at least two Android API levels and two vendors;
- long-running screen-off and reconnect soak tests.

## 14. Security, privacy and operational rules

- User must explicitly enable AI relay and understand that calculator text is sent to the selected provider.
- Use TLS for provider traffic and Android Keystore-backed secret storage.
- Minimize transcript retention and expose delete/export controls.
- Redact secrets and optionally message content from diagnostics.
- Bound all lengths before allocation or storage on both peers.
- Treat Bluetooth pairing as local-link access control, not end-to-end confidentiality against a compromised phone.
- If sensitive use is intended, add application-layer authenticated encryption in a later protocol version; do not invent cryptography during milestone 1.
- Do not market the system for exams or environments where wireless devices or AI assistance are prohibited.

## 15. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Direct ZS-040 interface is electrically/timing incompatible | Blocks original hardware goal | Feasibility spike; retain bridge-MCU fallback |
| TI-84 Plus RAM/display constraints | Poor UI or crashes | Bounded buffers, ring history, pixel-aware formatter |
| Android kills background work | Lost connection | Foreground service, durable queue, OEM/device tests |
| Stream framing errors | Corrupt messages | COBS/SLIP, length bounds, CRC, ACK/retry, fuzz tests |
| Duplicate AI calls after reconnect | Cost and confusing replies | Persistent idempotency IDs and exactly-once relay state |
| Provider/model changes | Broken relay | Provider adapters, capability self-test, phone-side configuration |
| HC-05 clone differences | Unstable pairing/electrical behavior | Record exact board revision; qualify purchased batches |
| Arbitrary Markdown/Unicode | Broken calculator rendering | Deterministic normalization and explicit glyph fallback |

## 16. Initial backlog

- [ ] Photograph and identify exact calculator model/revision.
- [ ] Photograph both sides of the ZS-040 and record chip/firmware markings.
- [x] Select Path C with Arduino Uno as the prototype bridge.
- [x] Select the calculator 2.5 mm I/O link port instead of USB.
- [ ] Create and review the two-channel open-drain link-interface schematic.
- [ ] Capture calculator link-port waveforms before attaching the Uno.
- [ ] Transfer all byte values Uno → TI-84 and TI-84 → Uno.
- [ ] Display `HELLO FROM ARDUINO` on the calculator 100 consecutive times.
- [ ] Display a calculator-entered message in the Uno serial monitor.
- [ ] Capture ZS-040 supply and UART waveforms before connecting it.
- [ ] Freeze protocol v1 framing and limits.
- [ ] Build Kotlin reference codec and test vectors.
- [ ] Render calculator status bar, transcript and editor mock.
- [ ] Send the first acknowledged frame both directions.
- [ ] Build Android frame console and fault injector.
- [ ] Pass milestone 1 soak/power-cycle criteria.
- [ ] Add encrypted provider configuration and self-test.
- [ ] Implement one end-to-end AI request and resumable reply.

## 17. Definition of “first useful demo”

The calculator connects to an Android phone, shows a stable link indicator, sends a typed question, receives a simulated or real provider reply, wraps it correctly on the 96×64 screen, scrolls through it, and recovers from one radio power cycle without duplicating the question. This vertical slice should be completed before adding rich formulas, multiple providers or visual polish.

## 18. Reference starting points

These links are starting points; verify current requirements when implementation begins:

- [Android Bluetooth overview](https://developer.android.com/develop/connectivity/bluetooth)
- [Android Bluetooth permissions](https://developer.android.com/develop/connectivity/bluetooth/bt-permissions)
- [Android background-work guidance](https://developer.android.com/develop/background-work)
- [Android Keystore](https://developer.android.com/privacy-and-security/keystore)
- [OpenAI API documentation](https://developers.openai.com/api/docs/)
- [OpenAI production best practices](https://developers.openai.com/api/docs/guides/production-best-practices)
- [TI education technology support](https://education.ti.com/en/customer-support)

Before hardware fabrication, replace community pinout assumptions with measurements and documentation for the exact calculator and module revisions.
