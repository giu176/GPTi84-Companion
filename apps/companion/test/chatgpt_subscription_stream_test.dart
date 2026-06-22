import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpti84_companion/features/providers/data/ai_provider_store.dart';
import 'package:gpti84_companion/features/providers/data/direct_ai_client.dart';

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  test(
    'subscription requests and combines streaming response events',
    () async {
      const store = AiProviderStore();
      await store.upsert(
        ProviderProfile(
          id: 'subscription',
          name: 'ChatGPT Subscription',
          config: AiProviderConfig(
            kind: AiProviderKind.chatGptSubscription,
            model: 'gpt-test',
            apiKey: 'access-token',
            refreshToken: 'refresh-token',
            tokenExpiresAt: DateTime.now().add(const Duration(hours: 1)),
            baseUrl: 'https://chatgpt.com/backend-api/codex',
          ),
        ),
      );
      final adapter = _StreamingAdapter();
      final client = DirectAiClient(
        store,
        dio: Dio()..httpClientAdapter = adapter,
      );

      final reply = await client.send(
        profileId: 'subscription',
        history: const [],
        text: 'Hello',
        attachments: const [],
      );

      expect(reply.text, 'Hello world');
      expect(adapter.requestData?['stream'], isTrue);
      expect(adapter.responseType, ResponseType.stream);
    },
  );
}

class _StreamingAdapter implements HttpClientAdapter {
  Map<String, dynamic>? requestData;
  ResponseType? responseType;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    requestData = options.data as Map<String, dynamic>;
    responseType = options.responseType;
    const events =
        'data: {"type":"response.output_text.delta","delta":"Hello "}\n\n'
        'data: {"type":"response.output_text.delta","delta":"world"}\n\n'
        'data: [DONE]\n\n';
    return ResponseBody.fromBytes(
      utf8.encode(events),
      200,
      headers: {
        Headers.contentTypeHeader: ['text/event-stream'],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}
