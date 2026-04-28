# DBUS bring-up state

Snapshot of what is proven on the Pico/MicroPython side of the 2.5mm link
to a TI-84 Plus, as of 2026-04-28.

## Hardware setup

- **MCU**: Raspberry Pi Pico 1 W running MicroPython.
- **Power**: Pico powered over USB; 3.3V logic on the GPIO side.
- **Pin map**:
  - `GPIO6` = TIP (red wire, "0-line" in TI nomenclature)
  - `GPIO7` = RING (white wire, "1-line")
  - GND of the cable shared with Pico GND.
- **Link cable**: standard TI 2.5mm "graylink" plugged directly into the
  Pico GPIO pins. No level shifting, no buffer ICs, no external pull-ups.
- **Pico-side line discipline**: each line is held in `Pin.IN, Pin.PULL_UP`
  while idle, so the internal pull-up wins when neither side is driving.
  To assert a line we re-init it as `OUT, value=0`. Without `PULL_UP` the
  rise after release is too slow and the calc misreads bits; this was
  confirmed empirically and is documented in `src/dbus.py`.
- **Calc**: TI-84 Plus (silver-edition era, the one with the 2.5mm port).
  No special firmware on the calc; stock OS.

## Bit layer (proven working)

The 2.5mm DBUS bit-level protocol is fully working in both directions:

- `recv_bit` / `recv_byte` correctly reads bytes from the calc, LSB-first.
- `send_bit` / `send_byte` correctly transmits bytes to the calc, LSB-first.
- The polarity convention used (`bit=0` -> pull TIP, ack on RING; `bit=1` ->
  pull RING, ack on TIP) is consistent between send and receive and matches
  what the calc expects.
- Our bit-bang is structurally identical to the canonical Arduino DBUS
  reference (KermM's ArTICL, plus an older Tim-Singer-era `put92`/`get92`
  snippet), confirmed line-by-line.

The strongest evidence the bit layer is correct is that **calc-initiated
flows round-trip data byte-perfectly** (see "Packet layer" below).

## Packet layer (proven working)

`send_packet` / `recv_packet` correctly frame and deframe DBUS packets:

```
[machine_id : 1] [cmd : 1] [length : 2 le] [data : N] [checksum : 2 le]
```

- 16-bit checksum is the lower 16 bits of the byte-wise sum of `data`.
- The checksum field is omitted when `length == 0`.
- Proven against the TI Link Guide examples in `references/linkguide/`.

## Calc-initiated flows (proven working)

These work end-to-end against a real TI-84+:

- **Pico receiving a variable that the calc sends.** When the user pushes
  a variable from the calc (`2nd LINK SEND`), `recv_var` performs the
  full handshake (RTS -> ACK -> CTS -> ACK -> DATA -> ACK [-> EOT -> ACK])
  and returns the variable header and payload bytes intact.
- **Pico requesting a variable from the calc.** `req_var` (and the
  `get_l1` convenience wrapper) successfully send REQ, receive VAR, ACK,
  CTS, receive DATA, ACK. The returned bytes parse cleanly through
  `parse_real_list` / `parse_real_list_str` and round-trip the same
  numerical values that were on the calc.

These flows exercise both directions of the bit layer and exercise our
checksum and framing code in both encoding and decoding directions.

## PC-initiated send (NOT working)

Sending a variable from the Pico to the calc (`send_var` / `put_real` /
`put_l1`) does not yet succeed. Two distinct failure modes have been
observed depending on the calc's state:

### Calc cold (home screen, not in receive mode)

```
sending RTS for type=0x0 name=b'A\x00...' len=9
pkt: cmd=0x56                 # ACK from calc, our RTS was accepted
no CTS within 10000 ms
idle now: lines=(1, 1)
```

The calc ACKs the RTS but never proceeds to send CTS or SKIP. The lines
return to idle. The calc displays no error.

Interpretation: on the 83+/84+, "silent" commands (RTS/REQ/RDY) are only
fully honored when the calc has been put into receive mode. A cold calc
parses our RTS, ACKs it as a well-formed packet, but does not act on it.

### Calc in receive mode (`2nd LINK RECEIVE`)

```
sending RTS for type=0x0 name=b'A\x00...' len=9
no ACK after RTS
False
```

The calc never sends ACK and **displays "Error in Xmit"** on screen.

Interpretation: the calc is reading our RTS bytes bit-by-bit and at some
point bails out -- either a checksum mismatch on its side, a bit-level
timing miss, or a header field it does not like. We never see what made
it bail because the failure displaces the ACK we were waiting for.

The transition between the two failure modes (cold -> ACK with no
follow-up; receive-mode -> hard reject mid-packet) is itself useful
information: in receive mode the calc is stricter and gates more
validation behind its accept path.

## What we have ruled out

- **Bit layer / polarity / LSB ordering**: would break receive too, but
  receive works.
- **Packet framing / checksum**: the same code is used in both directions
  and decodes calc-sent packets correctly, including against linkguide
  example bytes.
- **Machine ID byte**: the `pc_id_for(0x73) -> 0x23` mapping matches the
  linkguide table for "Computer sending TI-83+/TI-84+ data." The same
  mapping is used by `recv_var` when it replies and that flow works.
- **Variable header layout for proto=83**: our 13-byte body for
  `RTS Real "A"` is `09 00 00 41 00 00 00 00 00 00 00 00 00`, byte-for-byte
  identical to the linkguide example body.
- **Checksum value for the example RTS**: `0x4A`, matches.
- **List-name encoding (`5D 00` -> L1)**: matches both the linkguide note
  and our verified token reference.

## What we have NOT yet ruled out

- **Inter-bit timing under MicroPython interpreter overhead**: our
  `send_bit` busy-waits using `pin.value()` calls in a Python loop, which
  is much slower than the C/asm reference implementations. The calc may
  tolerate this on receive (where it controls the pace) but be strict
  about it on send.
- **Inter-byte timing**: we have no deliberate gap between bytes. Some
  receivers want a small idle window between bytes for their own
  bookkeeping.
- **Slow rise on line release**: we rely on `PULL_UP`-only rise, no
  active drive-high. The receive-side comment at the top of `dbus.py`
  notes this caused glitches before; the same effect could be hurting
  send under heavier wire loading.
- **Power supply / voltage compatibility**: the 84+ runs at 5V on its
  link port hardware historically, but the open-collector wire-OR design
  is supposed to be tolerant of 3.3V drivers. Worth confirming with a
  scope before pursuing software theories further.
- **Whether the failing byte is in the header, the checksum, or an
  earlier framing byte**: we currently abort `send_var` on the first
  missing ACK without telemetry on which byte the calc was reading when
  it bailed. Adding `recv_byte_traced`-equivalent logging on the reply
  side, plus a per-byte hex dump on the send side, is the next concrete
  diagnostic step.

## Source map

- `src/dbus.py` -- single MicroPython module containing the bit layer,
  packet layer, calc-initiated handshake (`recv_var`, `req_var`), and
  the not-yet-working PC-initiated send (`send_var`, `put_real`,
  `put_l1`, plus their `_83p` variants on machine 0x73).
- `references/linkguide/` -- vendored copy of the TI Link Guide. Key
  pages: `ti83+/silent.html`, `ti83+/packet.html`, `ti83+/vars.html`,
  `ti82/silent.html`, `ti82/packet.html`.

## Convenience entry points

| Function                         | Direction      | Status   |
|----------------------------------|----------------|----------|
| `recv_var()`                     | calc -> Pico   | working  |
| `req_var(type, name)` / `get_l1()` | Pico -> calc REQ, then calc -> Pico | working |
| `ready_check()` (RDY 0x68)       | Pico -> calc   | useful probe; only ACKs in silent-receive mode |
| `send_var(...)` / `put_real(...)` / `put_l1(...)` | Pico -> calc | NOT working |
| `put_real_83p(...)` / `put_l1_83p(...)` | Pico -> calc, machine 0x73 | NOT working |
| `snoop()`                        | passive line monitor | working diagnostic |
| `first_bits(n)`                  | one-shot edge logger | working diagnostic |
