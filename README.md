# ti84-superdeluxe

A TI-84 Plus that talks to a large language model.

You type a question on the calculator, hit `enter`, wait a couple of
seconds, and page through the reply with the left/right arrow keys. No
hardware mods, no firmware patch, no calculator side-loader: a stock
84+ from any Walmart, an unmodified link cable, a Raspberry Pi Pico W
in between, and a small relay process anywhere on the public internet.

This repo is the full stack: the bit-bang DBUS implementation on the
Pico, the WebSocket-over-TLS bridge, the relay server, and the on-calc
TI-BASIC + Z80 programs that drive the UX.

```
[ TI-84 Plus ] -- 2.5mm link cable --> [ Pico W ] --(WSS)--> [ relay ] --> [ Ollama / OpenAI / ... ]
       ^                                                                          |
       +---- arrow-key pager (TI-BASIC) <-- silent-link push <-------- paginated reply
```

## What's in here

- `src/`: MicroPython sources for the Pico W. Bit-bang DBUS, packet
  layer, variable transfers, WebSocket-over-TLS client, and the
  bridge supervisor.
- `tools/`: host-side utilities. Relay server (echo / LLM / passthrough
  modes), TI-BASIC source-to-`.8Xp` tokenizer, `.8Xp` extractor, ad-hoc
  push/listen scripts.
- `programs/`: on-calculator code. `asm_chat/CHAT.z80` (the dumb pipe)
  and `basic_deck/DECK.basic` (the user-facing pager) are the two that
  matter for the chat UX. The other directories are bring-up artifacts
  kept around as worked examples.
- `tests/`: host-side tests for the framing layers (packet, variable
  headers, BASIC tokenizer, .8Xp extractor, bridge pairing logic).
- `references/`: vendored protocol docs (TI Link Guide, WikiTI
  mirrors, ArTICL, spasm-ng include files). Read these before
  changing anything wire-level.
- `deploy/`: example systemd units and a sudoers drop-in for running
  the relay as a service on a Linux host. These are personal-deploy
  reference: read them, don't blindly run them.

## Hardware

- TI-84 Plus (any 84+ family calculator with a 2.5mm link port).
  Tested on plain 84+ (not Silver Edition, not CSE/CE).
- Raspberry Pi Pico W. Wifi is required: the bridge connects out to a
  TCP or WSS endpoint.
- Cable: a 2.5mm TRS link cable wired to two Pico GPIOs and ground.
  Default pin mapping in `src/wire.py`: TIP -> GP6, RING -> GP7. Both
  lines have internal pullups enabled.

## Quick start: LAN-only loop

Goal: prove the wire works, with no public internet, no relay, no LLM.

1. Wire up the Pico to the calculator's link port. Plug the Pico into
   USB.
2. `cp src/secrets.py.example src/secrets.py` and fill in your wifi
   credentials. Leave `SERVER_WSS = False`. Set `SERVER_HOST` to your
   workstation's LAN IP and `SERVER_PORT = 9999`.
3. Install MicroPython on the Pico, then `just sync` to copy `src/*.py`
   onto the Pico's filesystem.
4. On your workstation, run `just relay` to start the echo relay on
   port 9999. Anything the calc sends gets echoed back.
5. Build and push the on-calc programs:
   ```
   just push-asm   programs/asm_chat/CHAT.z80
   just push-basic programs/basic_deck/DECK.basic
   ```
6. On the calc, run `prgmDECK`. Type a prompt at the `PROMPT?` and
   `MATH?` inputs. The deck calls `Asm(prgmCHAT)`, the asm ships
   Str1+Str2 to the Pico, the relay echoes them back, the Pico
   PC-master-pushes the reply into Str3..Str0, and the deck pages
   through with left/right arrow keys.

## Production loop (LLM via WSS)

Same wiring, but the relay lives on a public host behind Cloudflare
Tunnel + Cloudflare Access, and proxies into Ollama (cloud or local).

1. Stand up the relay somewhere reachable. It's a single-file Python
   script with no dependencies beyond the stdlib + `urllib`. Run it
   under systemd (see `deploy/systemd/relay-llm.service` for a working
   unit) with `--port 9999 --llm` and the env vars from `.env.example`
   set.
2. Front it with Cloudflare Tunnel and create a Cloudflare Access
   service token. The token's `CF-Access-Client-Id` and
   `CF-Access-Client-Secret` go into `src/secrets.py` on the Pico.
3. In `src/secrets.py`, set `SERVER_WSS = True`, `SERVER_HOST` to your
   Cloudflare hostname, `SERVER_PORT = 443`, `WS_PATH = "/ws"`, and the
   two Access fields.
4. `just sync` to push the new `secrets.py` to the Pico, then reset.

The bridge auto-connects on boot and exposes its state via the onboard
LED (off / solid / 1Hz / 4Hz blink: see the docstring at the top of
`src/bridge.py`).

## On the wire

The Pico talks DBUS (TI's silent-link protocol over the 2.5mm port) to
the calculator. The wire layer is a software bit-bang: idle is both
lines high, sender pulls one line low to encode a bit, receiver
acknowledges by pulling the other low. Bytes are LSB-first. Packets are
`[machine_id][cmd][len_lo][len_hi][data...][cs_lo][cs_hi]`.

The chat path uses two transfer directions:

- **Calc -> Pico**: Z80 program (`CHAT.z80`) calls `_SendVarCmd` for
  Str1 (text) and Str2 (math). The Pico's listen loop receives them via
  the standard RTS/CTS/DATA flow.
- **Pico -> Calc**: PC-master push of Str3..Str9, Str0 (reply pages),
  followed by real var N (page count). The calc must be at the home
  screen for the OS's idle silent-link receive to accept these. The asm
  exits cleanly so the deck is parked there before the push starts.

There is a settle delay (`SETTLE_MS` in `src/bridge.py`, default 600ms)
between pushes: the OS needs wallclock to rearm the idle silent-link
receive after each redraw.

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

The personal-deploy recipes (`deploy-relay-llm`, `bootstrap-agent-ssh`,
`relay-llm-logs`, `sudoers-relay-deploy`) assume ssh aliases `nimble`
and `nimble-agent`, an `agent` user account on the relay host, and a
sudoers drop-in installed at `/etc/sudoers.d/xander-relay-deploy`.
Read them as worked examples; substitute your own infrastructure.

## Why does this exist

The 84+ has a documented serial protocol (DBUS), a documented binary
format for variables (.8Xp), an OS that politely accepts incoming
variable pushes whenever the home screen is idle, and a built-in
TI-BASIC interpreter that can render text, read string vars, and poll
real vars in a loop. That's enough machinery to embed a network client
behind it without modifying the calculator at all. The Pico fills in
the missing pieces: a wifi stack, TLS, and the patience to bit-bang
DBUS at the speed the OS expects.

The result is a stock calculator that talks to GPT-class models. It is
deeply impractical and that is the entire point.

## License

MIT. See `LICENSE`.

Vendored references in `references/` are third-party material. Each
file or directory carries its source attribution; see the original
projects (TI Link Guide, WikiTI, ArTICL, spasm-ng) for their licenses.
