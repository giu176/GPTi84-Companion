"""Stream calculator-originated DBUS variables from Pico to the host console.

This is a bring-up diagnostic for the calculator -> Pico -> PC path only.
It does not import or use BLE, Android, provider, or phone relay code.

Example:
  .venv\\Scripts\\python.exe tools\\calc_stream_monitor.py --port COM4 --duration 90

While it is running, send a variable from the calculator, or run prgmDECK /
prgmCHAT. The host terminal will show each received variable and decoded text.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


PICO_MONITOR = r'''
import time

import tokens
from transfer import listen_loop


SIZE_PREFIXED = (0x04, 0x05, 0x06, 0x15)


def _hex(data, limit=64):
    b = bytes(data)
    shown = b[:limit]
    text = " ".join("{:02X}".format(x) for x in shown)
    if len(b) > limit:
        text += " ..."
    return text


def _strip_size(type_id, data):
    if type_id in SIZE_PREFIXED and len(data) >= 2:
        declared = data[0] | (data[1] << 8)
        if declared == len(data) - 2:
            return data[2:]
    return data


def _name_text(type_id, name8):
    name = bytes(name8)
    if type_id == 0x04 and len(name) >= 2 and name[0] == 0xAA:
        slot = name[1]
        if slot == 9:
            return "Str0"
        return "Str{}".format(slot + 1)
    stripped = name.rstrip(b"\x00")
    try:
        return stripped.decode("ascii")
    except Exception:
        return repr(name)


def _ascii_preview(type_id, name8, payload):
    if type_id == 0x04 and len(name8) >= 2 and name8[0] == 0xAA:
        mode = "math" if name8[1] == 1 else "text"
        return tokens.tokens_to_ascii(payload, mode=mode)
    try:
        return bytes(payload).decode("ascii")
    except Exception:
        return repr(bytes(payload))


def on_var(type_id, name8, hdr, data):
    payload = _strip_size(type_id, data)
    print("")
    print("=== CALC VAR ===")
    print("type: 0x{:02X}".format(type_id))
    print("name:", _name_text(type_id, name8))
    print("header_len:", len(hdr), "raw_len:", len(data), "payload_len:", len(payload))
    print("payload_hex:", _hex(payload))
    print("decoded:", repr(_ascii_preview(type_id, name8, payload)))
    print("===============")


duration_ms = __DURATION_MS__
end = time.ticks_add(time.ticks_ms(), duration_ms) if duration_ms else None
print("calc-stream: listening; run/send something on the calculator now")
while True:
    if end is not None and time.ticks_diff(end, time.ticks_ms()) <= 0:
        print("calc-stream: done")
        break
    listen_loop(on_var=on_var, timeout_ms=500)
'''


def default_mpremote() -> str:
    local = ROOT / ".venv" / "Scripts" / "mpremote.exe"
    if local.exists():
        return str(local)
    found = shutil.which("mpremote")
    if found:
        return found
    return "mpremote"


def build_script(duration: int) -> str:
    duration_ms = max(duration, 0) * 1000
    return PICO_MONITOR.replace("__DURATION_MS__", str(duration_ms))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Print calculator-originated TI link transfers via the Pico.",
    )
    parser.add_argument("--port", default="COM4", help="Pico serial port")
    parser.add_argument(
        "--duration",
        type=int,
        default=90,
        help="Seconds to listen; use 0 for forever",
    )
    parser.add_argument(
        "--mpremote",
        default=default_mpremote(),
        help="Path to mpremote.exe",
    )
    args = parser.parse_args(argv)

    script = build_script(args.duration)
    with tempfile.NamedTemporaryFile(
        "w",
        suffix="_calc_stream_monitor.py",
        delete=False,
        encoding="ascii",
        newline="\n",
    ) as handle:
        handle.write(script)
        temp_path = Path(handle.name)

    print("calc-stream: using", args.mpremote)
    print("calc-stream: connect", args.port)
    print("calc-stream: Ctrl-C stops the monitor")
    try:
        completed = subprocess.run(
            [args.mpremote, "connect", args.port, "run", str(temp_path)],
            cwd=ROOT,
            check=False,
        )
        return completed.returncode
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
