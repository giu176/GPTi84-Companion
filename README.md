# GPTi84-Companion

GPTi84 Companion connects a plain monochrome TI-84 Plus to AI providers through a Raspberry Pi Pico 2WH, a personal relay, and an Android/iOS companion app.

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
- The companion supports multiple named, securely stored profiles for OpenAI, Anthropic, Gemini, OpenAI-compatible APIs, Ollama, and experimental ChatGPT Subscription access.
- A global favorite supplies the default for new chats, while each conversation can select and retain its own service.
- Phone chats support persistent images and files, Markdown replies, delivery states, and calculator pinning.
- Pico 2WH hardware parity, the production relay, BLE provisioning, and remote pin synchronization remain planned work.

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

## Provider authentication

Provider API keys are stored with Android Keystore or iOS Keychain through Flutter secure storage. The app also offers an experimental ChatGPT Subscription connector modeled independently after Odysseus: it uses OpenAI's Codex device authorization and private Codex Responses backend. This is not a documented third-party ChatGPT API and may stop working without notice. GPTi84 Companion never collects ChatGPT passwords, cookies, or browser sessions.

## Upstream

This project is derived from [xandwr/GPTi84-Plus](https://github.com/xandwr/GPTi84-Plus). The `upstream` Git remote tracks that repository. See [NOTICE](NOTICE) and [LICENSE](LICENSE).
