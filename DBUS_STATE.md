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

## PC-initiated send (native real upload working)

The native TI-83+/TI-84+ upload path now succeeds for at least a simple
real variable send:

```
>>> dbus.put_real_83p('A', 1.5, quiet=True)
sending DATA
pkt: cmd= 0x56
done
True
```

The critical discovery was that the calc *was* sending CTS after RTS, but
our packet parser was discarding it. After `RTS`, a traced reply showed:

```
[115, 9, 13, 0]   # 73 09 0D 00
```

That is a valid `CTS` packet on this link: command `0x09` with a nonzero
16-bit length/status field but no trailing body or checksum. Our original
`recv_packet()` trusted the length field unconditionally, waited for 13
data bytes that never existed, and then reported a misleading "no CTS"
timeout. The fix was to parse no-data commands (`CTS`, `ACK`, `ERR`, `RDY`,
`SCR`, `EOT`, `VER`) by command semantics rather than by the raw length
word alone.

Related diagnostics that helped pin this down:

- `ready_check()` succeeds on the native 83+/84+ path with machine ID `0x23`.
- `del_real_83p('A')` succeeds with the same 13-byte native header shape as
  `RTS`, proving the calc accepts our machine ID and header encoding.
- `probe_rts_real_83p('A', 1.5)` showed the calc really was transmitting CTS;
  the bug was entirely in our packet receive logic.

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
- **Upload handshake ordering**: `send_var()` already followed the correct
  `RTS -> ACK -> CTS -> ACK -> DATA -> ACK -> EOT` sequence; the failure was
  not "sending DATA too early".
- **RTS size field**: for real uploads we already sent `09 00`, i.e. the
  future DATA payload length, not the 13-byte header size.
- **Whether the calc was actually sending CTS**: yes. `probe_rts_real_83p()`
  captured `73 09 0D 00` immediately after the initial ACK.

## What we have NOT yet ruled out / not yet re-verified

- **Larger outbound payloads**: native real upload is proven; list/matrix/
  longer DATA payloads should still be re-run explicitly.
- **Cold-calc behavior**: earlier testing showed a cold home-screen calc can
  ACK RTS without following through. The currently proven success case is the
  native upload path exercised during this debugging session, not every calc
  UI state.
- **Electrical margins under sustained send load**: the parser bug was the
  blocking issue for real upload, but scope-level confirmation of rise times
  and line margins could still matter for larger/faster transfers.

## Source map

- `src/dbus.py` -- single MicroPython module containing the bit layer,
  packet layer, calc-initiated handshake (`recv_var`, `req_var`), native
  PC-initiated send (`send_var`, `put_real`, `put_l1`, plus their `_83p`
  variants on machine 0x73), and several upload diagnostics (`ready_check`,
  `delete_var`, `probe_rts_reply`, `recv_n_traced`).
- `references/linkguide/` -- vendored copy of the TI Link Guide. Key
  pages: `ti83+/silent.html`, `ti83+/packet.html`, `ti83+/vars.html`,
  `ti82/silent.html`, `ti82/packet.html`.

## Convenience entry points

| Function                         | Direction      | Status   |
|----------------------------------|----------------|----------|
| `recv_var()`                     | calc -> Pico   | working  |
| `req_var(type, name)` / `get_l1()` | Pico -> calc REQ, then calc -> Pico | working |
| `ready_check()` (RDY 0x68)       | Pico -> calc   | useful probe; only ACKs in silent-receive mode |
| `send_var(...)` / `put_real(...)` | Pico -> calc | working for native real upload |
| `put_real_83p(...)` | Pico -> calc, machine 0x73 | working |
| `put_l1(...)` / `put_l1_83p(...)` | Pico -> calc | unverified after parser fix |
| `delete_var(...)` / `del_real_83p()` | Pico -> calc | working diagnostic |
| `probe_rts_reply(...)` / `probe_rts_real_83p()` | Pico -> calc | working diagnostic |
| `snoop()`                        | passive line monitor | working diagnostic |
| `first_bits(n)`                  | one-shot edge logger | working diagnostic |
