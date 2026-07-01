# Raw Axe link protocol

The Axe app talks to the Pico over calculator link bytes. The Pico forwards the
ASCII V2 payload to the phone relay and returns the phone page frame unchanged.

## Frame format

```text
0      start       0x7E
1      type        0x01 request, 0x02 response, 0x03 status, 0x7F error
2..3   length      payload length, little-endian
4..n   payload     ASCII V2 command or phone `pages:N` body
last   checksum    XOR(type, len_lo, len_hi, payload bytes)
```

Maximum payload is 1024 bytes. The first Axe MVP uses much less than this, but
1024 leaves room for eight fixed 16x8 pages plus the `pages:N` header.

## Payloads

Calculator requests:

```text
LIST
OPEN:<slot>
NEW
ACTIVE
POLL:ACTIVE
SEND:ACTIVE:<prompt>
SEND:<chatId>:<prompt>
```

Pico responses:

```text
pages:N\n<page1>\0<page2>...
```

Errors are ASCII text in an `0x7F` frame. The calculator displays them in its
native UI and stays running.

## Responsibilities

- Calculator owns screen, key loop, page parsing, selection, and status bar.
- Pico owns raw framing, timeout handling, phone relay forwarding, catalog
  cache writes, and error conversion.
- Phone remains authoritative for chat IDs, pinned state, full messages,
  provider calls, revisions, and conflict resolution.

## Timeout behavior

- Pico ignores noise until it sees `0x7E`.
- Partial frames timeout and return an error frame when possible.
- Phone response timeout returns an error frame instead of resetting the Pico.
- The calculator never exits merely because the phone is slow or disconnected.

## Mock mode implemented today

`src/raw_axe_mock.py` is the phone-free calculator test authority. It stores
complete chats persistently in `chats.v1.json`, renders them into calculator
pages on demand, and supports:

- `LIST`
- `NEW`
- `OPEN:<slot>`
- `ACTIVE`
- `POLL:ACTIVE`
- `SEND:ACTIVE:<prompt>`
- `SEND:<chatId>:<prompt>`

The mock appends the user prompt immediately, schedules a fake assistant reply
with a bounded delay, and later appends:

```text
this is totally an AI generated answer
```

The current Axe calculator app transmits the raw frames but still uses a local
mirror for display. Pico `pages:N` receive parsing is the next calculator-side
milestone.
