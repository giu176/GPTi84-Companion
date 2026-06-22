import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:uuid/uuid.dart';

enum AiProviderKind {
  openAi('OpenAI'),
  chatGptSubscription('ChatGPT Subscription (experimental)'),
  anthropic('Anthropic'),
  gemini('Google Gemini'),
  openAiCompatible('OpenAI-compatible'),
  ollama('Ollama');

  const AiProviderKind(this.label);
  final String label;
}

enum ProviderTestStatus { notTested, success, failure }

class AiProviderConfig {
  const AiProviderConfig({
    required this.kind,
    required this.model,
    required this.apiKey,
    required this.baseUrl,
    this.refreshToken = '',
    this.tokenExpiresAt,
  });

  final AiProviderKind kind;
  final String model;
  final String apiKey;
  final String baseUrl;
  final String refreshToken;
  final DateTime? tokenExpiresAt;

  bool get isConfigured =>
      model.trim().isNotEmpty &&
      (kind == AiProviderKind.ollama || apiKey.trim().isNotEmpty);

  AiProviderConfig copyWith({
    String? model,
    String? apiKey,
    String? baseUrl,
    String? refreshToken,
    DateTime? tokenExpiresAt,
  }) {
    return AiProviderConfig(
      kind: kind,
      model: model ?? this.model,
      apiKey: apiKey ?? this.apiKey,
      baseUrl: baseUrl ?? this.baseUrl,
      refreshToken: refreshToken ?? this.refreshToken,
      tokenExpiresAt: tokenExpiresAt ?? this.tokenExpiresAt,
    );
  }

  Map<String, Object?> toJson() => {
    'kind': kind.name,
    'model': model,
    'apiKey': apiKey,
    'baseUrl': baseUrl,
    'refreshToken': refreshToken,
    'tokenExpiresAt': tokenExpiresAt?.toIso8601String(),
  };

  factory AiProviderConfig.fromJson(Map<String, dynamic> json) {
    return AiProviderConfig(
      kind: AiProviderKind.values.byName(json['kind'] as String),
      model: json['model'] as String? ?? '',
      apiKey: json['apiKey'] as String? ?? '',
      baseUrl: json['baseUrl'] as String? ?? '',
      refreshToken: json['refreshToken'] as String? ?? '',
      tokenExpiresAt: DateTime.tryParse(
        json['tokenExpiresAt'] as String? ?? '',
      ),
    );
  }

  factory AiProviderConfig.defaults(AiProviderKind kind) {
    return switch (kind) {
      AiProviderKind.openAi => const AiProviderConfig(
        kind: AiProviderKind.openAi,
        model: 'gpt-5.5',
        apiKey: '',
        baseUrl: 'https://api.openai.com/v1',
      ),
      AiProviderKind.chatGptSubscription => const AiProviderConfig(
        kind: AiProviderKind.chatGptSubscription,
        model: 'gpt-5.5',
        apiKey: '',
        baseUrl: 'https://chatgpt.com/backend-api/codex',
      ),
      AiProviderKind.anthropic => const AiProviderConfig(
        kind: AiProviderKind.anthropic,
        model: 'claude-sonnet-4-6',
        apiKey: '',
        baseUrl: 'https://api.anthropic.com/v1',
      ),
      AiProviderKind.gemini => const AiProviderConfig(
        kind: AiProviderKind.gemini,
        model: 'gemini-2.5-flash',
        apiKey: '',
        baseUrl: 'https://generativelanguage.googleapis.com/v1beta',
      ),
      AiProviderKind.openAiCompatible => const AiProviderConfig(
        kind: AiProviderKind.openAiCompatible,
        model: '',
        apiKey: '',
        baseUrl: 'https://example.com/v1',
      ),
      AiProviderKind.ollama => const AiProviderConfig(
        kind: AiProviderKind.ollama,
        model: 'llama3.2',
        apiKey: '',
        baseUrl: 'http://localhost:11434',
      ),
    };
  }
}

class ProviderProfile {
  const ProviderProfile({
    required this.id,
    required this.name,
    required this.config,
    this.testStatus = ProviderTestStatus.notTested,
    this.lastTestedAt,
    this.testMessage = '',
  });

  final String id;
  final String name;
  final AiProviderConfig config;
  final ProviderTestStatus testStatus;
  final DateTime? lastTestedAt;
  final String testMessage;

  ProviderProfile copyWith({
    String? name,
    AiProviderConfig? config,
    ProviderTestStatus? testStatus,
    DateTime? lastTestedAt,
    String? testMessage,
  }) {
    return ProviderProfile(
      id: id,
      name: name ?? this.name,
      config: config ?? this.config,
      testStatus: testStatus ?? this.testStatus,
      lastTestedAt: lastTestedAt ?? this.lastTestedAt,
      testMessage: testMessage ?? this.testMessage,
    );
  }

  Map<String, Object?> toJson() => {
    'id': id,
    'name': name,
    'config': config.toJson(),
    'testStatus': testStatus.name,
    'lastTestedAt': lastTestedAt?.toIso8601String(),
    'testMessage': testMessage,
  };

  factory ProviderProfile.fromJson(Map<String, dynamic> json) {
    return ProviderProfile(
      id: json['id'] as String,
      name: json['name'] as String,
      config: AiProviderConfig.fromJson(json['config'] as Map<String, dynamic>),
      testStatus: ProviderTestStatus.values.byName(
        json['testStatus'] as String? ?? ProviderTestStatus.notTested.name,
      ),
      lastTestedAt: DateTime.tryParse(json['lastTestedAt'] as String? ?? ''),
      testMessage: json['testMessage'] as String? ?? '',
    );
  }
}

class ProviderVault {
  const ProviderVault({
    this.version = 2,
    this.profiles = const [],
    this.favoriteProfileId,
  });

  final int version;
  final List<ProviderProfile> profiles;
  final String? favoriteProfileId;

  ProviderProfile? get favorite {
    for (final profile in profiles) {
      if (profile.id == favoriteProfileId) return profile;
    }
    return profiles.isEmpty ? null : profiles.first;
  }

  ProviderProfile? profile(String id) {
    for (final profile in profiles) {
      if (profile.id == id) return profile;
    }
    return null;
  }

  Map<String, Object?> toJson() => {
    'version': version,
    'favoriteProfileId': favoriteProfileId,
    'profiles': profiles.map((profile) => profile.toJson()).toList(),
  };

  factory ProviderVault.fromJson(Map<String, dynamic> json) {
    return ProviderVault(
      version: json['version'] as int? ?? 2,
      favoriteProfileId: json['favoriteProfileId'] as String?,
      profiles: (json['profiles'] as List<dynamic>? ?? const [])
          .whereType<Map<String, dynamic>>()
          .map(ProviderProfile.fromJson)
          .toList(),
    );
  }
}

class AiProviderStore {
  const AiProviderStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _vaultKey = 'ai_provider_vault_v2';
  static const _legacyKey = 'active_ai_provider_v1';
  final FlutterSecureStorage _storage;

  Future<ProviderVault> readVault() async {
    final encoded = await _storage.read(key: _vaultKey);
    if (encoded != null && encoded.isNotEmpty) {
      return ProviderVault.fromJson(
        jsonDecode(encoded) as Map<String, dynamic>,
      );
    }
    return _migrateLegacy();
  }

  Future<ProviderProfile?> readProfile(String id) async {
    return (await readVault()).profile(id);
  }

  Future<ProviderVault> upsert(ProviderProfile profile) async {
    final vault = await readVault();
    final profiles = [...vault.profiles];
    final index = profiles.indexWhere((item) => item.id == profile.id);
    if (index < 0) {
      profiles.add(profile);
    } else {
      profiles[index] = profile;
    }
    final updated = ProviderVault(
      profiles: profiles,
      favoriteProfileId: vault.favoriteProfileId ?? profile.id,
    );
    await _write(updated);
    return updated;
  }

  Future<ProviderVault> setFavorite(String id) async {
    final vault = await readVault();
    if (vault.profile(id) == null) {
      throw StateError('Provider profile not found');
    }
    final updated = ProviderVault(
      profiles: vault.profiles,
      favoriteProfileId: id,
    );
    await _write(updated);
    return updated;
  }

  Future<ProviderVault> delete(String id) async {
    final vault = await readVault();
    final profiles = vault.profiles.where((item) => item.id != id).toList();
    final favorite = vault.favoriteProfileId == id
        ? (profiles.isEmpty ? null : profiles.first.id)
        : vault.favoriteProfileId;
    final updated = ProviderVault(
      profiles: profiles,
      favoriteProfileId: favorite,
    );
    await _write(updated);
    return updated;
  }

  Future<ProviderVault> updateConfig(String id, AiProviderConfig config) async {
    final profile = await readProfile(id);
    if (profile == null) throw StateError('Provider profile not found');
    return upsert(profile.copyWith(config: config));
  }

  Future<ProviderVault> recordTest(
    String id, {
    required ProviderTestStatus status,
    required String message,
  }) async {
    final profile = await readProfile(id);
    if (profile == null) throw StateError('Provider profile not found');
    return upsert(
      profile.copyWith(
        testStatus: status,
        lastTestedAt: DateTime.now(),
        testMessage: message,
      ),
    );
  }

  Future<ProviderVault> _migrateLegacy() async {
    final legacy = await _storage.read(key: _legacyKey);
    if (legacy == null || legacy.isEmpty) return const ProviderVault();
    final config = AiProviderConfig.fromJson(
      jsonDecode(legacy) as Map<String, dynamic>,
    );
    final profile = ProviderProfile(
      id: const Uuid().v4(),
      name: config.kind.label,
      config: config,
    );
    final vault = ProviderVault(
      profiles: [profile],
      favoriteProfileId: profile.id,
    );
    await _write(vault);
    await _storage.delete(key: _legacyKey);
    return vault;
  }

  Future<void> _write(ProviderVault vault) {
    return _storage.write(key: _vaultKey, value: jsonEncode(vault.toJson()));
  }
}
