# GPTi84-Plus

> a TI-84 Plus that talks to a large language model

```
[ TI-84 Plus ] -- 2.5mm link cable --> [ Pico W ] --(WSS)--> [ relay ] --> [ Ollama / OpenAI / ... ]
       ^                                                                          |
       +---- arrow-key pager (TI-BASIC) <-- silent-link push <-------- paginated reply
```

## What's in here

- `src/`: MicroPython sources for the Pico W. Bit-bang DBUS, packet
  layer, variable transfers, WebSocket-over-TLS client, and the
  bridge supervisor
- `tools/`: host-side utilities. Relay server (echo / LLM / passthrough
  modes), TI-BASIC source-to-`.8Xp` tokenizer, `.8Xp` extractor, ad-hoc
  push/listen scripts
- `programs/`: on-calculator code. `asm_chat/CHAT.z80` (the dumb pipe)
  and `basic_deck/DECK.basic` (the user-facing pager) are the two that
  matter for the chat UX. The other directories are bring-up artifacts
  kept around as worked examples
- `tests/`: host-side tests for the framing layers (packet, variable
  headers, BASIC tokenizer, .8Xp extractor, bridge pairing logic).
- `references/`: vendored protocol docs (TI Link Guide, WikiTI
  mirrors, ArTICL, spasm-ng include files). Read these before
  changing anything wire-level
- `deploy/`: example systemd units for running
  the relay as a service on a Linux host

## Hardware

- TI-84 Plus (any 84+ family calculator with a 2.5mm link port)
  Tested on plain 84+ (not Silver Edition, not CSE/CE)
- Raspberry Pi Pico W. Wifi is required: the bridge connects out to a
  TCP or WSS endpoint
- Cable: a 2.5mm TRS link cable wired to two Pico GPIOs and ground.
  Default pin mapping in `src/wire.py`: TIP -> GP6, RING -> GP7. Both
  lines have internal pullups enabled

## On the wire

the pico talks DBUS (TI's silent-link protocol over the 2.5mm port) to
the calculator. The wire layer is a software bit-bang: idle is both
lines high, sender pulls one line low to encode a bit, receiver
acknowledges by pulling the other low. bytes are LSB-first. packets are
`[machine_id][cmd][len_lo][len_hi][data...][cs_lo][cs_hi]`.

The chat path uses two transfer directions:

- **Calc -> Pico**: Z80 program (`CHAT.z80`) calls `_SendVarCmd` for
  Str1 (text) and Str2 (math). The Pico's listen loop receives them via
  the standard RTS/CTS/DATA flow
- **Pico -> Calc**: PC-master push of Str3..Str9, Str0 (reply pages),
  followed by real var N (page count). The calc must be at the home
  screen for the OS's idle silent-link receive to accept these. The asm
  exits cleanly so the deck is parked there before the push starts

there is a settle delay (`SETTLE_MS` in `src/bridge.py`, default 600ms)
between pushes: the OS needs wallclock to rearm the idle silent-link
receive after each redraw.

web console below tails every WebSocket frame the relay handles,
which made debugging the calc-to-LLM round trip vastly easier than
guessing from one side of the wire at a time.

## Development

```
just              # list recipes
just test         # host-side unit tests (pytest)
just sync         # push src/*.py to the Pico
just repl         # mpremote REPL on the Pico
just relay        # local TCP relay on :9999 (passthrough)
just relay-echo   # local TCP relay, auto-reply with "echo: <text>"
just relay-llm    # local LLM relay, reads .env for OLLAMA_API_KEY
```

## License

MIT. See `LICENSE`.
