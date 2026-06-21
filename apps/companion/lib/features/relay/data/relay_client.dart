import 'package:dio/dio.dart';

import '../../settings/data/relay_settings_store.dart';

class RelayAssistantMessage {
  const RelayAssistantMessage({required this.id, required this.text});

  final String id;
  final String text;
}

class RelayClient {
  RelayClient(this._settingsStore);

  final RelaySettingsStore _settingsStore;

  Future<String> health() async {
    final client = await _client();
    final response = await client.get<Map<String, dynamic>>('/v1/health');
    return response.data?['status']?.toString() ?? 'ok';
  }

  Future<RelayAssistantMessage> sendText({
    required String messageId,
    required String conversationId,
    required String text,
  }) async {
    final client = await _client();
    final response = await client.post<Map<String, dynamic>>(
      '/v1/messages',
      data: {
        'id': messageId,
        'conversationId': conversationId,
        'parts': [
          {'type': 'text', 'text': text},
        ],
      },
      options: Options(headers: {'Idempotency-Key': messageId}),
    );
    final body = response.data ?? const <String, dynamic>{};
    final message = body['message'] is Map<String, dynamic>
        ? body['message'] as Map<String, dynamic>
        : body;
    final reply = message['text']?.toString() ?? '';
    if (reply.isEmpty) throw const FormatException('Relay returned no text');
    return RelayAssistantMessage(
      id: message['id']?.toString() ?? '${messageId}_assistant',
      text: reply,
    );
  }

  Future<Dio> _client() async {
    final settings = await _settingsStore.read();
    if (!settings.isConfigured) {
      throw StateError('Configure the relay URL and administrator token first');
    }
    final baseUrl = settings.baseUrl.endsWith('/')
        ? settings.baseUrl.substring(0, settings.baseUrl.length - 1)
        : settings.baseUrl;
    return Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(minutes: 2),
        headers: {'Authorization': 'Bearer ${settings.adminToken}'},
      ),
    );
  }
}
