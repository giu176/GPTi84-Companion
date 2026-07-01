"""Pico 2 W boot entry. Runs the calculator<->phone bridge as an appliance.

To temporarily disable autoboot during dev (e.g. you want a clean REPL):
  mpremote exec 'import os; os.rename("main.py", "main.py.off")'
and put it back with the inverse.
"""

import secrets

if getattr(secrets, "BLE_ECHO_MODE", False):
    from ble_transport import echo_mode
    echo_mode(name=getattr(secrets, "BLE_DEVICE_NAME", "GPTi84-Pico"))
elif getattr(secrets, "RAW_AXE_MOCK_MODE", False):
    from raw_axe_mock import run
    run()
else:
    import bridge
    # The bridge relays raw Axe link frames to the phone and back.
    bridge.run()
