# Security policy

## Reporting a vulnerability

Do not open a public issue containing credentials, private prompts, Bluetooth addresses, or exploitable vulnerability details. Use GitHub's private vulnerability reporting feature for this repository when available, or contact the repository owner privately through their GitHub profile.

Include affected version/commit, impact, reproduction steps, and a proposed mitigation when possible.

## Credential model

The Android app encrypts provider credentials with an Android Keystore key. Credentials must never be placed in source files, Gradle properties, fixtures, diagnostics, or screenshots.

The prototype calls provider APIs directly from the user's phone. A broadly distributed product should consider user-owned keys or a controlled server-side token broker.

## Bluetooth limitations

HC-05/HC-06 modules use legacy Bluetooth Classic pairing and should not be treated as a high-security transport. Avoid sending sensitive personal, financial, medical, or proprietary information through the prototype.

