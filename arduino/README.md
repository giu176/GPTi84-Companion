# Arduino and ZS-040 wiring

## Data-mode wiring

The circuit deliberately omits external capacitors; add local decoupling only if testing shows resets or corruption.

| ZS-040 | Arduino Uno | Notes |
|---|---|---|
| VCC | 5 V | Only for a ZS-040 carrier with onboard regulator |
| GND | GND | Common ground |
| TXD | D10 | 3.3 V output is accepted by the Uno |
| RXD | D11 through 1 kΩ | Add 2 kΩ from module RXD to GND |
| STATE | D7 through 1 kΩ | Optional; set `USE_BT_STATE` accordingly |
| KEY/EN | disconnected | Data mode |

Keep wiring short. Never drive the module RX pin directly with an Uno 5 V output.

## Upload

1. Identify the module name. Use `hc05_config/hc05_config.ino` only for HC-05 firmware and `hc06_config/hc06_config.ino` for HC-06 firmware.
2. Upload `pc_bt_bridge/pc_bt_bridge.ino`.
3. Open Serial Monitor at 115200 baud. Human-readable boot diagnostics are printed before binary protocol use; close Serial Monitor before running the Python file relay.

ZS-040 clones use different AT-command modes. HC-06 is slave-only, which is suitable for this project. The configuration sketches are intentionally interactive and print the module's real responses instead of assuming every command succeeded. Do not send HC-05 commands to an HC-06.
