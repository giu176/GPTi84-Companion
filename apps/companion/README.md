# GPTi84 Companion mobile app

Flutter application for Android and iOS.

## Implemented

- Material 3 chat, calculator, and settings navigation;
- Drift/SQLite local conversations and messages;
- an eight-chat local pin limit matching calculator capacity;
- a BLE GATT central for Pico-originated calculator chat;
- calculator-safe 16x8 text pagination for Pico replies;
- Markdown assistant rendering and message delivery states;
- Android/iOS Bluetooth and photo permission declarations;
- direct OpenAI, Anthropic, Gemini, OpenAI-compatible, and Ollama adapters;
- an encrypted multi-profile provider vault with named duplicates, a global favorite, health testing, and per-chat selection;
- camera, gallery, and document attachments copied to app-private storage.

Settings keeps provider management on its own AI services page, phone relay diagnostics under Advanced, and explanatory file/security/billing/privacy material under About.

## Authentication boundary

Use provider-issued API credentials for the stable path. An opt-in experimental ChatGPT Subscription connector uses OpenAI's Codex device-code authorization and private Codex backend. It does not scrape sessions or request account passwords, but the endpoint is undocumented and compatibility is not guaranteed.

## Next

- physical Android/iPhone BLE parity and reconnect testing;
- device-bound pairing-secret onboarding;
- pinned-chat browsing and standalone calculator event import.

## Checks

```powershell
C:\Users\giuli\flutter-sdk\bin\flutter.bat pub get
C:\Users\giuli\flutter-sdk\bin\flutter.bat pub run build_runner build
C:\Users\giuli\flutter-sdk\bin\flutter.bat analyze
C:\Users\giuli\flutter-sdk\bin\flutter.bat test
```
