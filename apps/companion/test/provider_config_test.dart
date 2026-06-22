import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpti84_companion/features/providers/data/ai_provider_store.dart';
import 'package:gpti84_companion/features/providers/data/direct_ai_client.dart';

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  test('provider configuration round-trips without losing credentials', () {
    const original = AiProviderConfig(
      kind: AiProviderKind.openAi,
      model: 'test-model',
      apiKey: 'secret-key',
      baseUrl: 'https://api.example.com/v1',
    );

    final restored = AiProviderConfig.fromJson(original.toJson());

    expect(restored.kind, AiProviderKind.openAi);
    expect(restored.model, 'test-model');
    expect(restored.apiKey, 'secret-key');
    expect(restored.baseUrl, 'https://api.example.com/v1');
    expect(restored.isConfigured, isTrue);
  });

  test('Ollama does not require an API key', () {
    final config = AiProviderConfig.defaults(AiProviderKind.ollama);
    expect(config.isConfigured, isTrue);
  });

  test('subscription tokens and expiry survive secure serialization', () {
    final expiry = DateTime.utc(2030, 1, 2, 3, 4, 5);
    final original = AiProviderConfig(
      kind: AiProviderKind.chatGptSubscription,
      model: 'gpt-test',
      apiKey: 'access',
      refreshToken: 'refresh',
      accountId: 'account-123',
      tokenExpiresAt: expiry,
      baseUrl: 'https://chatgpt.com/backend-api/codex',
    );

    final restored = AiProviderConfig.fromJson(original.toJson());
    expect(restored.refreshToken, 'refresh');
    expect(restored.tokenExpiresAt, expiry);
    expect(restored.accountId, 'account-123');
    expect(restored.isConfigured, isTrue);
  });

  test('migrates the legacy provider into a favorite named profile', () async {
    const legacy = AiProviderConfig(
      kind: AiProviderKind.openAi,
      model: 'legacy-model',
      apiKey: 'legacy-secret',
      baseUrl: 'https://api.openai.com/v1',
    );
    FlutterSecureStorage.setMockInitialValues({
      'active_ai_provider_v1': jsonEncode(legacy.toJson()),
    });

    final vault = await const AiProviderStore().readVault();

    expect(vault.profiles, hasLength(1));
    expect(vault.favorite?.config.apiKey, 'legacy-secret');
    expect(vault.favorite?.config.model, 'legacy-model');
  });

  test(
    'allows duplicate kinds and promotes a replacement after deletion',
    () async {
      const store = AiProviderStore();
      final config = AiProviderConfig.defaults(AiProviderKind.ollama);
      await store.upsert(
        ProviderProfile(id: 'home', name: 'Home', config: config),
      );
      await store.upsert(
        ProviderProfile(id: 'laptop', name: 'Laptop', config: config),
      );
      await store.setFavorite('laptop');

      final vault = await store.delete('laptop');

      expect(vault.profiles.single.id, 'home');
      expect(vault.favoriteProfileId, 'home');
    },
  );

  test('records a failed non-generation provider test', () async {
    const store = AiProviderStore();
    await store.upsert(
      const ProviderProfile(
        id: 'broken',
        name: 'Broken',
        config: AiProviderConfig(
          kind: AiProviderKind.openAi,
          model: 'model',
          apiKey: 'bad-key',
          baseUrl: 'https://api.example.test/v1',
        ),
      ),
    );
    final dio = Dio()..httpClientAdapter = _RejectingAdapter();

    final result = await DirectAiClient(store, dio: dio).testProfile('broken');
    final recorded = await store.readProfile('broken');

    expect(result.success, isFalse);
    expect(recorded?.testStatus, ProviderTestStatus.failure);
    expect(recorded?.testMessage, contains('HTTP 401'));
  });
}

class _RejectingAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    return ResponseBody.fromString(
      '{"error":"invalid key"}',
      401,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}
