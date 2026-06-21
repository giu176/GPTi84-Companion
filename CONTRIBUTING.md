# Contributing

Thanks for helping build TI-84 Relay.

## Before opening a pull request

1. Discuss large protocol, hardware, or architecture changes in an issue first.
2. Keep secrets, personal transcripts, build artifacts, and device-specific configuration out of commits.
3. Preserve protocol compatibility or update `protocol/spec.md` and every implementation together.
4. Add tests for bug fixes and new protocol/provider behavior.
5. Run Python, Arduino, and Android checks documented in `README.md`.

## Hardware changes

Hardware pull requests should include a schematic, voltage assumptions, component values, failure behavior, and real-device test results. Do not recommend direct Uno GPIO connections to the TI-84 link port.

## Code style

- Kotlin follows the official Kotlin style.
- Python should remain dependency-light and compatible with Python 3.10+.
- Arduino code must avoid dynamic `String` allocation and remain within Uno SRAM limits.
- Logs and fixtures must redact Bluetooth addresses, API keys, and private prompt content.

By contributing, you agree that your contribution is licensed under the repository's MIT License.

