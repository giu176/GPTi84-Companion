# TI-84 Companion mobile app

Flutter application for Android and iOS.

## Implemented

- Material 3 chat, calculator, and settings navigation;
- Drift/SQLite local conversations and messages;
- an eight-chat local pin limit matching calculator capacity;
- secure relay URL/token storage;
- relay health and idempotent text-message API client;
- Markdown assistant rendering and message delivery states;
- Android/iOS Bluetooth and photo permission declarations.

## Next

- production relay API and sync repository;
- provider configuration screens;
- image selection and multimodal messages;
- BLE Pico 2WH provisioning;
- pinned-chat synchronization and standalone calculator event import.

## Checks

```powershell
C:\Users\giuli\flutter-sdk\bin\flutter.bat pub get
C:\Users\giuli\flutter-sdk\bin\flutter.bat pub run build_runner build
C:\Users\giuli\flutter-sdk\bin\flutter.bat analyze
C:\Users\giuli\flutter-sdk\bin\flutter.bat test
```
