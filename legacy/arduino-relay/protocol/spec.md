# TI-84 Relay Wire Protocol v1

## Framing

Every decoded frame is:

| Field | Size | Encoding |
|---|---:|---|
| version | 1 | `0x01` |
| type | 1 | message type |
| flags | 1 | reserved, zero in v1 |
| sequence | 2 | unsigned little-endian |
| transaction ID | 4 | unsigned little-endian |
| payload length | 2 | unsigned little-endian, maximum 128 |
| payload | 0–128 | type-specific |
| CRC | 2 | CRC-16/CCITT-FALSE over every preceding decoded byte |

The decoded frame is COBS encoded and terminated with `0x00`. Integer fields are little-endian.

CRC-16/CCITT-FALSE parameters: polynomial `0x1021`, initial value `0xFFFF`, no reflection, final XOR `0x0000`.

## Message types

| Value | Name | Payload |
|---:|---|---|
| `0x01` | HELLO | UTF-8 peer name |
| `0x02` | HELLO_ACK | UTF-8 peer name/status |
| `0x03` | PING | empty |
| `0x04` | PONG | empty |
| `0x10` | REQUEST_BEGIN | total UTF-8 byte length as `u32` |
| `0x11` | REQUEST_CHUNK | raw UTF-8 bytes |
| `0x12` | REQUEST_END | CRC-32 of complete query as `u32` |
| `0x20` | RESPONSE_BEGIN | total UTF-8 byte length as `u32` |
| `0x21` | RESPONSE_CHUNK | raw UTF-8 bytes |
| `0x22` | RESPONSE_END | CRC-32 of complete response as `u32` |
| `0x30` | STATUS | UTF-8 status text |
| `0x31` | ACK | empty; sequence equals acknowledged frame |
| `0x32` | NACK | UTF-8 reason; sequence equals rejected frame |
| `0x33` | ERROR | `CODE`, NUL, human-readable message |
| `0x34` | CANCEL | empty |

## Reliability

- REQUEST and RESPONSE frames use stop-and-wait acknowledgements.
- ACK timeout is 2 seconds, with at most three retransmissions.
- Receivers deduplicate `(transaction ID, sequence)` and ACK duplicates without applying them twice.
- Queries are limited to 4096 bytes; responses are limited to 16384 bytes.
- `REQUEST_END` or `RESPONSE_END` is accepted only when declared size and CRC-32 match.
- A transaction ID identifies one provider call. Android persists it before submission and never submits a completed transaction twice.
- Peers may send PING every five seconds and consider a connection dead after 15 seconds without valid frames.

