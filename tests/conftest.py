"""Make src/ importable on the host and stub out the MicroPython-only
`machine` module so wire.py's `from machine import Pin` works under CPython.

The wire bit-bang code itself is not exercised by these tests; they cover
the pure-data layers (packet framing, var headers, real/list codecs,
.8Xp parsing). Only the import side-effect of constructing two Pin
objects at module load needs to succeed.
"""

import sys
import time
import types
from pathlib import Path

# MicroPython exposes monotonic-millisecond helpers on `time`. CPython
# doesn't ship these, so anything in src/ that imports `time` and uses
# ticks_ms / ticks_diff / ticks_add / sleep_ms breaks under host pytest.
# Polyfill with the obvious wall-clock equivalents -- close enough for
# host tests that just compare arrival timestamps for staleness.
if not hasattr(time, "ticks_ms"):
    time.ticks_ms = lambda: int(time.monotonic() * 1000)
if not hasattr(time, "ticks_diff"):
    time.ticks_diff = lambda a, b: a - b
if not hasattr(time, "ticks_add"):
    time.ticks_add = lambda a, b: a + b
if not hasattr(time, "sleep_ms"):
    time.sleep_ms = lambda ms: time.sleep(ms / 1000.0)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
TOOLS = ROOT / "tools"
for p in (SRC, TOOLS):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

if "machine" not in sys.modules:
    machine = types.ModuleType("machine")

    class _Pin:
        IN = 0
        OUT = 1
        PULL_UP = 2

        def __init__(self, *args, **kwargs):
            pass

        def init(self, *args, **kwargs):
            pass

        def value(self, *args):
            return 1

        def on(self):
            pass

        def off(self):
            pass

    machine.Pin = _Pin
    sys.modules["machine"] = machine

# `network` is MicroPython-only too. Stub it just enough that `import net`
# (which is `from network import WLAN, STA_IF` indirectly) doesn't blow up.
# We never call into the wifi path under pytest.
if "network" not in sys.modules:
    network = types.ModuleType("network")
    network.STA_IF = 0

    class _WLAN:
        def __init__(self, *args, **kwargs):
            pass

        def active(self, *args):
            return True

        def isconnected(self):
            return True

        def connect(self, *args, **kwargs):
            pass

        def ifconfig(self):
            return ("0.0.0.0", "0.0.0.0", "0.0.0.0", "0.0.0.0")

    network.WLAN = _WLAN
    sys.modules["network"] = network
