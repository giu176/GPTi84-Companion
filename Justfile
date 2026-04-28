set shell := ["bash", "-cu"]

PY      := ".venv/bin/python"
PYTEST  := ".venv/bin/pytest"
MPR     := "mpremote"
SRC     := "src"
SPASM   := "spasm"
SPASM_INC := "references/other_projects/spasm"

# default: list recipes
default:
    @just --list

# --- host-only ---

# Run host tests (packet framing, var headers, real codec, .8Xp parser).
test:
    {{PYTEST}} tests/ -q

# Extract the variable payload from a .8Xp to stdout (binary).
extract FILE:
    {{PY}} tools/extract_8xp.py {{FILE}}

# --- pico / mpremote ---

# Drop into the Pico REPL.
repl:
    {{MPR}} repl

# Soft-reset the Pico.
reset:
    {{MPR}} reset

# List files on the Pico filesystem.
ls:
    {{MPR}} ls

# Copy src/*.py to the Pico filesystem (one-shot deploy).
sync:
    @for f in {{SRC}}/*.py; do echo "cp $f :"; {{MPR}} cp "$f" :; done

# Run a local .py file on the Pico without installing it (one-shot).
run FILE:
    {{MPR}} run {{FILE}}

# One-shot Python eval on the Pico. Quote the expression.
# Example: just exec 'import dbus; dbus.idle()'
exec EXPR:
    {{MPR}} exec "{{EXPR}}"

# --- e2e (calc must be plugged in and idle at the home screen) ---

# Assemble a Z80 source with spasm-ng to a sibling .8xp.
# Example: just asm programs/asm_hello/HELLO.z80
asm FILE:
    @echo "==> assembling {{FILE}}"
    {{SPASM}} -I {{SPASM_INC}} {{FILE}} {{ without_extension(FILE) }}.8xp

# Assemble a Z80 source then push the resulting .8Xp to the calc.
# Example: just push-asm programs/asm_hello/HELLO.z80
push-asm FILE:
    just asm {{FILE}}
    just push {{ without_extension(FILE) }}.8xp

# Push a .8Xp program to the calc. Default is FLAPPY.
push FILE="programs/flappy_bird/FLAPPY.8xp":
    @echo "==> generating push script for {{FILE}}"
    {{PY}} tools/build_e2e.py push {{FILE}} > /tmp/ti84_e2e_push.py
    @echo "==> running on Pico"
    {{MPR}} run /tmp/ti84_e2e_push.py

# Listen on the Pico for a calc-initiated variable transfer. NAME filters
# by 8-byte var name (e.g. CHATMSG); TYPE filters by hex type byte (e.g. 15
# for AppVar). Both optional. Ctrl-C to stop.
# Example: just listen CHATMSG 15
listen NAME="" TYPE="":
    @echo "==> generating listen script (name={{NAME}} type={{TYPE}})"
    {{PY}} tools/build_e2e.py listen {{NAME}} {{TYPE}} > /tmp/ti84_e2e_listen.py
    @echo "==> running on Pico (Ctrl-C to stop)"
    {{MPR}} run /tmp/ti84_e2e_listen.py

# Push a .8Xp, then request it back and byte-compare on the Pico.
roundtrip FILE="programs/flappy_bird/FLAPPY.8xp":
    @echo "==> generating roundtrip script for {{FILE}}"
    {{PY}} tools/build_e2e.py roundtrip {{FILE}} > /tmp/ti84_e2e_rt.py
    @echo "==> running on Pico"
    {{MPR}} run /tmp/ti84_e2e_rt.py

# Run the desktop-side TCP relay. Reads length-prefixed frames from
# any connected client and prints them. Default port 9999.
relay PORT="9999":
    {{PY}} tools/relay_server.py --port {{PORT}}

# Run the relay in echo mode: every frame from the calc is auto-replied
# with "echo: <text>". v0 stub for the ChatGPT-on-calc loop.
relay-echo PORT="9999":
    {{PY}} tools/relay_server.py --port {{PORT}} --echo

# Disable Pico autoboot of the bridge (renames main.py -> main.py.off).
# Use during dev when autoboot fights mpremote run / repl.
autoboot-off:
    {{MPR}} exec 'import os; os.rename("main.py", "main.py.off")'

# Re-enable Pico autoboot of the bridge.
autoboot-on:
    {{MPR}} exec 'import os; os.rename("main.py.off", "main.py")'

# Bring up the calc<->desktop chat bridge on the Pico. Connects to
# wifi (creds in src/secrets.py), opens a TCP socket to the desktop
# (host/port in secrets.py), and forwards calc-initiated AppVar/Program
# transfers as length-prefixed frames. Ctrl-C to stop.
# Example: just chat-bridge CHATMSG 15
chat-bridge NAME="" TYPE="":
    @echo "==> generating bridge script (name={{NAME}} type={{TYPE}})"
    {{PY}} tools/build_e2e.py bridge {{NAME}} {{TYPE}} > /tmp/ti84_e2e_bridge.py
    @echo "==> running on Pico (Ctrl-C to stop)"
    {{MPR}} run /tmp/ti84_e2e_bridge.py

# Wire-only test for calc-master REQ. Runs listen_loop on the Pico with
# a hardcoded on_req that always serves PAYLOAD as AppVar CHATIN. Pair
# with `Asm(prgmREQTEST)` on the calc; expect the PAYLOAD text to appear
# on the calc screen on row 6 plus "12345" status markers in column 15.
# Example: just reqtest "hello there"
reqtest PAYLOAD="hello calc":
    @echo "==> generating reqtest script (payload={{PAYLOAD}})"
    {{PY}} tools/build_e2e.py reqtest "{{PAYLOAD}}" > /tmp/ti84_e2e_reqtest.py
    @echo "==> running on Pico (Ctrl-C to stop)"
    {{MPR}} run /tmp/ti84_e2e_reqtest.py

# Full e2e gate: host tests + push FLAPPY + roundtrip FLAPPY + roundtrip SEX.
test-e2e: test
    just push  programs/flappy_bird/FLAPPY.8xp
    just roundtrip programs/flappy_bird/FLAPPY.8xp
    just roundtrip programs/debug/SEX.8xp
