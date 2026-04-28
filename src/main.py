"""Pico W boot entry. Runs the calc<->desktop bridge as an appliance.

To temporarily disable autoboot during dev (e.g. you want a clean REPL):
  mpremote exec 'import os; os.rename("main.py", "main.py.off")'
and put it back with the inverse.
"""

import bridge

# The bridge handles Str1/Str2 pairing internally and relays anything else
# raw; no filter args needed.
bridge.run()
