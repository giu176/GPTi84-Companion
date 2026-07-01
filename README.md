# GPTi84-Companion

GPTi84 Companion connects a plain monochrome TI-84 Plus to AI providers through a Raspberry Pi Pico 2 W and an Android/iOS companion app. The phone is the relay.

```text
TI-84 Plus Axe app <--raw link bytes--> Pico 2 W <--BLE GATT--> Flutter Android/iOS app <--HTTPS--> AI providers
```

## Current state

- GPTi84-Plus DBUS, TI transfer, token, and pager implementation retained as bring-up reference code.
- Existing Arduino/HC-06/Android prototype imported with history under `legacy/arduino-relay/`.
- Flutter Android/iOS application scaffolded under `apps/companion/`.
- The companion supports multiple named, securely stored profiles for OpenAI, Anthropic, Gemini, OpenAI-compatible APIs, Ollama, and experimental ChatGPT Subscription access.
- A global favorite supplies the default for new chats, while each conversation can select and retain its own service.
- Phone chats support persistent images and files, Markdown replies, delivery states, and calculator pinning.
- The app and Pico firmware now implement the versioned BLE GATT relay protocol, and the calculator path is moving to an Axe-native raw-link app.

The upstream firmware was validated on the original Pico W. Do not assume RP2350 parity until the staged Pico 2 W gate in [the architecture document](docs/architecture.md) passes.

## Repository map

| Path | Purpose |
|---|---|
| `src/`, `programs/`, `tools/`, `tests/` | Retained GPTi84-Plus firmware, calculator code, and tests |
| `apps/companion/` | Flutter Android/iOS companion |
| `backend/` | Temporary external-relay prototype; not the intended production path |
| `legacy/arduino-relay/` | Complete previous Arduino prototype |
| `docs/architecture.md` | Product decisions, ownership boundaries, and roadmap |
| `docs/axe_native_app.md` | Axe-native calculator app workflow |
| `docs/raw_axe_link_protocol.md` | Raw calculator-to-Pico frame protocol |

## Calculator UI direction

The TI-BASIC `programs/basic_gpti84/GPTI84.basic` program is now only a
bring-up reference. The active calculator direction is the Axe source under
`programs/axe_gpti84/`, compiled on calculator/emulator with Axe Parser into a
no-stub executable that owns the screen, keys, timing, status bar, and raw link
transactions directly.

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
