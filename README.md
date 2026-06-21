# TI-84 Companion

TI-84 Companion connects a plain monochrome TI-84 Plus to AI providers through a Raspberry Pi Pico 2WH, a personal relay, and an Android/iOS companion app.

```text
TI-84 Plus <--2.5 mm DBUS--> Pico 2WH <--WSS/Wi-Fi--> relay <--HTTPS--> AI providers
                                                          ^
                                                          |
                                              Flutter Android/iOS app
```

## Current state

- GPTi84-Plus DBUS, TI transfer, token, pager, and WSS implementation retained at the repository root.
- Existing Arduino/HC-06/Android prototype imported with history under `legacy/arduino-relay/`.
- Flutter Android/iOS application scaffolded under `apps/companion/`.
- Initial app slice includes persistent local chats, secure relay settings, a relay API boundary, pinned-chat limits, Markdown replies, and calculator/settings surfaces.
- Pico 2WH hardware parity, production relay, BLE provisioning, images, and remote pin synchronization remain planned work.

The upstream firmware was validated on the original Pico W. Do not assume RP2350 parity until the staged Pico 2WH gate in [the architecture document](docs/architecture.md) passes.

## Repository map

| Path | Purpose |
|---|---|
| `src/`, `programs/`, `tools/`, `tests/` | Retained GPTi84-Plus firmware, calculator code, and tests |
| `apps/companion/` | Flutter Android/iOS companion |
| `backend/` | Planned authenticated provider relay |
| `legacy/arduino-relay/` | Complete previous Arduino prototype |
| `docs/architecture.md` | Product decisions, ownership boundaries, and roadmap |

## Companion development

```powershell
cd apps\companion
C:\Users\giuli\flutter-sdk\bin\flutter.bat pub get
C:\Users\giuli\flutter-sdk\bin\flutter.bat pub run build_runner build
C:\Users\giuli\flutter-sdk\bin\flutter.bat analyze
C:\Users\giuli\flutter-sdk\bin\flutter.bat test
```

Android APK builds additionally require an Android SDK. iOS builds require macOS and Xcode.

## Upstream

This project is derived from [xandwr/GPTi84-Plus](https://github.com/xandwr/GPTi84-Plus). The `upstream` Git remote tracks that repository. See [NOTICE](NOTICE) and [LICENSE](LICENSE).
