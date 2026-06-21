# TI-84 Relay Android app

Android 12+ application for pairing with `TI84-RELAY`, receiving framed queries over Bluetooth Classic SPP, calling an AI provider, and returning a checked response.

## Build

Open this directory in Android Studio with JDK 17 and Android SDK 35 installed, or run:

```powershell
.\gradlew.bat testDebugUnitTest lintDebug assembleDebug
```

The debug APK is generated at `app/build/outputs/apk/debug/app-debug.apk`.

## Setup

1. Power the configured HC-05 or HC-06 bridge and grant Nearby Devices permission.
2. On Device, choose **Pair TI84-RELAY** and complete Android's PIN dialog.
3. Select the paired device and tap **Connect**.
4. On Provider, select OpenAI, Anthropic, Gemini, or OpenAI-compatible.
5. Enter a provider API key and model, save, then run **Self-test**.

The app uses system companion-device onboarding, the standard SPP UUID, a connected-device foreground service, bounded reconnect backoff, an encrypted Keystore credential store, and a Room transaction journal. An already bonded device named `HC-05` or `HC-06` can be selected directly.

## Provider defaults

Defaults reflect official documentation at implementation time and remain editable:

- OpenAI Responses API: `gpt-5.5`
- Anthropic Messages API: `claude-sonnet-4-6`
- Gemini generateContent: `gemini-3.5-flash`
- Generic OpenAI-compatible Chat Completions: user-supplied endpoint/model

Provider self-tests make a small real API call and may incur provider charges.
