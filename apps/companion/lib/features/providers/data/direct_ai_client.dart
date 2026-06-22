import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';

import 'ai_provider_store.dart';
import 'chatgpt_subscription_auth.dart';

class ChatAttachment {
  const ChatAttachment({
    required this.path,
    required this.name,
    required this.mimeType,
  });

  final String path;
  final String name;
  final String mimeType;
  bool get isImage => mimeType.startsWith('image/');

  Future<String> base64Data() async =>
      base64Encode(await File(path).readAsBytes());
}

class ChatTurn {
  const ChatTurn({required this.role, required this.text});
  final String role;
  final String text;
}

class AiReply {
  const AiReply(this.text);
  final String text;
}

class ProviderTestResult {
  const ProviderTestResult({required this.success, required this.message});
  final bool success;
  final String message;
}

class DirectAiClient {
  DirectAiClient(this._store, {Dio? dio}) : _dio = dio ?? Dio();

  final AiProviderStore _store;
  final Dio _dio;

  Future<AiReply> send({
    required String profileId,
    required List<ChatTurn> history,
    required String text,
    required List<ChatAttachment> attachments,
  }) async {
    final profile = await _store.readProfile(profileId);
    final config = profile?.config;
    if (config == null || !config.isConfigured) {
      throw StateError(
        'Choose an AI provider and save its credentials in Settings',
      );
    }
    return switch (config.kind) {
      AiProviderKind.openAi => _openAi(config, history, text, attachments),
      AiProviderKind.chatGptSubscription => _chatGptSubscription(
        profileId,
        config,
        history,
        text,
        attachments,
      ),
      AiProviderKind.openAiCompatible => _openAiCompatible(
        config,
        history,
        text,
        attachments,
      ),
      AiProviderKind.anthropic => _anthropic(
        config,
        history,
        text,
        attachments,
      ),
      AiProviderKind.gemini => _gemini(config, history, text, attachments),
      AiProviderKind.ollama => _ollama(config, history, text, attachments),
    };
  }

  Future<ProviderTestResult> testProfile(String profileId) async {
    final profile = await _store.readProfile(profileId);
    if (profile == null) throw StateError('Provider profile not found');
    var config = profile.config;
    try {
      switch (config.kind) {
        case AiProviderKind.openAi:
        case AiProviderKind.openAiCompatible:
          await _dio.get<void>(
            '${_trim(config.baseUrl)}/models',
            options: Options(
              headers: config.apiKey.isEmpty
                  ? null
                  : {'Authorization': 'Bearer ${config.apiKey}'},
            ),
          );
        case AiProviderKind.anthropic:
          await _dio.get<void>(
            '${_trim(config.baseUrl)}/models',
            options: Options(
              headers: {
                'x-api-key': config.apiKey,
                'anthropic-version': '2023-06-01',
              },
            ),
          );
        case AiProviderKind.gemini:
          await _dio.get<void>(
            '${_trim(config.baseUrl)}/models',
            queryParameters: {'key': config.apiKey},
          );
        case AiProviderKind.ollama:
          await _dio.get<void>('${_trim(config.baseUrl)}/api/tags');
        case AiProviderKind.chatGptSubscription:
          final expiry = config.tokenExpiresAt;
          if (expiry == null ||
              expiry.isBefore(DateTime.now().add(const Duration(minutes: 2)))) {
            config = await ChatGptSubscriptionAuth().refresh(config);
            await _store.updateConfig(profileId, config);
          }
          await _dio.get<void>(
            '${_trim(config.baseUrl)}/models',
            queryParameters: {'client_version': '1.0.0'},
            options: Options(headers: _chatGptHeaders(config.apiKey)),
          );
      }
      final message = 'Connected to ${config.kind.label}';
      await _store.recordTest(
        profileId,
        status: ProviderTestStatus.success,
        message: message,
      );
      return ProviderTestResult(success: true, message: message);
    } catch (error) {
      final message = _errorMessage(error);
      await _store.recordTest(
        profileId,
        status: ProviderTestStatus.failure,
        message: message,
      );
      return ProviderTestResult(success: false, message: message);
    }
  }

  Future<AiReply> _chatGptSubscription(
    String profileId,
    AiProviderConfig config,
    List<ChatTurn> history,
    String text,
    List<ChatAttachment> attachments, {
    bool retried = false,
  }) async {
    if (attachments.isNotEmpty) {
      throw UnsupportedError(
        'The experimental ChatGPT Subscription connector currently supports text only. Use the OpenAI API provider for files and pictures.',
      );
    }
    final expiry = config.tokenExpiresAt;
    if (expiry == null ||
        expiry.isBefore(DateTime.now().add(const Duration(minutes: 2)))) {
      config = await ChatGptSubscriptionAuth().refresh(config);
      await _store.updateConfig(profileId, config);
    }
    final input = <Map<String, dynamic>>[
      ...history.map(
        (turn) => {
          'role': turn.role,
          'content': [
            {
              'type': turn.role == 'assistant' ? 'output_text' : 'input_text',
              'text': turn.text,
            },
          ],
        },
      ),
      {
        'role': 'user',
        'content': [
          {'type': 'input_text', 'text': text},
        ],
      },
    ];
    try {
      final response = await _dio.post<ResponseBody>(
        '${_trim(config.baseUrl)}/responses',
        data: {
          'model': config.model,
          'instructions': 'You are a helpful AI assistant.',
          'input': input,
          'stream': true,
          'store': false,
        },
        options: Options(
          headers: {..._chatGptHeaders(config.apiKey)},
          responseType: ResponseType.stream,
        ),
      );
      final body = response.data;
      if (body == null)
        throw const FormatException('Provider returned no data');
      return AiReply(await _chatGptStreamText(body.stream));
    } on DioException catch (error) {
      if (!retried &&
          (error.response?.statusCode == 401 ||
              error.response?.statusCode == 403)) {
        final refreshed = await ChatGptSubscriptionAuth().refresh(config);
        await _store.updateConfig(profileId, refreshed);
        return _chatGptSubscription(
          profileId,
          refreshed,
          history,
          text,
          attachments,
          retried: true,
        );
      }
      rethrow;
    }
  }

  Future<String> _chatGptStreamText(Stream<List<int>> stream) async {
    final deltas = StringBuffer();
    String fallback = '';
    await for (final line
        in stream
            .cast<List<int>>()
            .transform(utf8.decoder)
            .transform(const LineSplitter())) {
      if (!line.startsWith('data:')) continue;
      final payload = line.substring(5).trimLeft();
      if (payload.isEmpty || payload == '[DONE]') continue;
      final decoded = jsonDecode(payload);
      if (decoded is! Map<String, dynamic>) continue;
      switch (decoded['type']) {
        case 'response.output_text.delta':
          deltas.write(decoded['delta']?.toString() ?? '');
        case 'response.output_text.done':
          fallback = decoded['text']?.toString() ?? fallback;
        case 'response.completed':
          final response = decoded['response'];
          if (deltas.isEmpty && response is Map<String, dynamic>) {
            fallback = _responsesText(response);
          }
        case 'response.failed':
        case 'error':
          final error = decoded['error'];
          final detail = error is Map<String, dynamic>
              ? error['message']?.toString()
              : error?.toString();
          throw StateError(detail ?? 'ChatGPT streaming request failed');
      }
    }
    return _requireText(deltas.isNotEmpty ? deltas.toString() : fallback);
  }

  Future<AiReply> _openAi(
    AiProviderConfig config,
    List<ChatTurn> history,
    String text,
    List<ChatAttachment> attachments,
  ) async {
    final content = <Map<String, dynamic>>[
      {'type': 'input_text', 'text': text},
    ];
    for (final attachment in attachments) {
      final encoded = await attachment.base64Data();
      content.add(
        attachment.isImage
            ? {
                'type': 'input_image',
                'image_url': 'data:${attachment.mimeType};base64,$encoded',
              }
            : {
                'type': 'input_file',
                'filename': attachment.name,
                'file_data': 'data:${attachment.mimeType};base64,$encoded',
              },
      );
    }
    final input = <Map<String, dynamic>>[
      ...history.map(
        (turn) => {
          'role': turn.role,
          'content': [
            {
              'type': turn.role == 'assistant' ? 'output_text' : 'input_text',
              'text': turn.text,
            },
          ],
        },
      ),
      {'role': 'user', 'content': content},
    ];
    final response = await _dio.post<Map<String, dynamic>>(
      '${_trim(config.baseUrl)}/responses',
      data: {'model': config.model, 'input': input},
      options: Options(headers: {'Authorization': 'Bearer ${config.apiKey}'}),
    );
    return AiReply(_responsesText(response.data ?? const {}));
  }

  String _responsesText(Map<String, dynamic> body) {
    final direct = body['output_text']?.toString();
    if (direct != null && direct.isNotEmpty) return direct;
    final output = body['output'] as List<dynamic>? ?? const [];
    final parts = output
        .whereType<Map<String, dynamic>>()
        .expand((item) => item['content'] as List<dynamic>? ?? const [])
        .whereType<Map<String, dynamic>>()
        .map((part) => part['text']?.toString() ?? '')
        .where((part) => part.isNotEmpty)
        .join('\n');
    return _requireText(parts);
  }

  Future<AiReply> _openAiCompatible(
    AiProviderConfig config,
    List<ChatTurn> history,
    String text,
    List<ChatAttachment> attachments,
  ) async {
    if (attachments.any((item) => !item.isImage)) {
      throw UnsupportedError(
        'This OpenAI-compatible adapter supports images but not general files',
      );
    }
    final userContent = <Map<String, dynamic>>[
      {'type': 'text', 'text': text},
    ];
    for (final attachment in attachments) {
      userContent.add({
        'type': 'image_url',
        'image_url': {
          'url':
              'data:${attachment.mimeType};base64,${await attachment.base64Data()}',
        },
      });
    }
    final response = await _dio.post<Map<String, dynamic>>(
      '${_trim(config.baseUrl)}/chat/completions',
      data: {
        'model': config.model,
        'messages': [
          ...history.map((turn) => {'role': turn.role, 'content': turn.text}),
          {'role': 'user', 'content': userContent},
        ],
      },
      options: Options(
        headers: config.apiKey.isEmpty
            ? null
            : {'Authorization': 'Bearer ${config.apiKey}'},
      ),
    );
    final choices = response.data?['choices'] as List<dynamic>? ?? const [];
    final first = choices.isEmpty
        ? null
        : choices.first as Map<String, dynamic>?;
    final message = first?['message'] as Map<String, dynamic>?;
    return AiReply(_requireText(message?['content']?.toString() ?? ''));
  }

  Future<AiReply> _anthropic(
    AiProviderConfig config,
    List<ChatTurn> history,
    String text,
    List<ChatAttachment> attachments,
  ) async {
    final content = <Map<String, dynamic>>[
      {'type': 'text', 'text': text},
    ];
    for (final attachment in attachments) {
      final source = {
        'type': 'base64',
        'media_type': attachment.mimeType,
        'data': await attachment.base64Data(),
      };
      if (attachment.isImage) {
        content.add({'type': 'image', 'source': source});
      } else if (attachment.mimeType == 'application/pdf') {
        content.add({'type': 'document', 'source': source});
      } else {
        throw UnsupportedError(
          'Anthropic attachments currently support images and PDF files',
        );
      }
    }
    final response = await _dio.post<Map<String, dynamic>>(
      '${_trim(config.baseUrl)}/messages',
      data: {
        'model': config.model,
        'max_tokens': 4096,
        'messages': [
          ...history.map((turn) => {'role': turn.role, 'content': turn.text}),
          {'role': 'user', 'content': content},
        ],
      },
      options: Options(
        headers: {
          'x-api-key': config.apiKey,
          'anthropic-version': '2023-06-01',
        },
      ),
    );
    final parts = response.data?['content'] as List<dynamic>? ?? const [];
    return AiReply(
      _requireText(
        parts
            .whereType<Map<String, dynamic>>()
            .map((e) => e['text'] ?? '')
            .join('\n'),
      ),
    );
  }

  Future<AiReply> _gemini(
    AiProviderConfig config,
    List<ChatTurn> history,
    String text,
    List<ChatAttachment> attachments,
  ) async {
    final parts = <Map<String, dynamic>>[
      {'text': text},
    ];
    for (final attachment in attachments) {
      parts.add({
        'inlineData': {
          'mimeType': attachment.mimeType,
          'data': await attachment.base64Data(),
        },
      });
    }
    final response = await _dio.post<Map<String, dynamic>>(
      '${_trim(config.baseUrl)}/models/${Uri.encodeComponent(config.model)}:generateContent',
      queryParameters: {'key': config.apiKey},
      data: {
        'contents': [
          ...history.map(
            (turn) => {
              'role': turn.role == 'assistant' ? 'model' : 'user',
              'parts': [
                {'text': turn.text},
              ],
            },
          ),
          {'role': 'user', 'parts': parts},
        ],
      },
    );
    final candidates =
        response.data?['candidates'] as List<dynamic>? ?? const [];
    final candidate = candidates.isEmpty
        ? null
        : candidates.first as Map<String, dynamic>?;
    final content = candidate?['content'] as Map<String, dynamic>?;
    final answerParts = content?['parts'] as List<dynamic>? ?? const [];
    return AiReply(
      _requireText(
        answerParts
            .whereType<Map<String, dynamic>>()
            .map((e) => e['text'] ?? '')
            .join('\n'),
      ),
    );
  }

  Future<AiReply> _ollama(
    AiProviderConfig config,
    List<ChatTurn> history,
    String text,
    List<ChatAttachment> attachments,
  ) async {
    if (attachments.any((item) => !item.isImage)) {
      throw UnsupportedError('Ollama chat supports image attachments only');
    }
    final response = await _dio.post<Map<String, dynamic>>(
      '${_trim(config.baseUrl)}/api/chat',
      data: {
        'model': config.model,
        'stream': false,
        'messages': [
          ...history.map((turn) => {'role': turn.role, 'content': turn.text}),
          {
            'role': 'user',
            'content': text,
            if (attachments.isNotEmpty)
              'images': await Future.wait(
                attachments.map((item) => item.base64Data()),
              ),
          },
        ],
      },
    );
    final message = response.data?['message'] as Map<String, dynamic>?;
    return AiReply(_requireText(message?['content']?.toString() ?? ''));
  }

  String _trim(String value) =>
      value.endsWith('/') ? value.substring(0, value.length - 1) : value;

  String _requireText(String value) {
    if (value.trim().isEmpty) {
      throw const FormatException('Provider returned no text');
    }
    return value.trim();
  }

  Map<String, String> _chatGptHeaders(String token) => {
    'Authorization': 'Bearer $token',
    'Accept': 'application/json, text/event-stream',
    'Origin': 'https://chatgpt.com',
    'Referer': 'https://chatgpt.com/codex',
    'User-Agent': 'GPTi84 Companion ChatGPT Subscription',
  };

  String _errorMessage(Object error) {
    if (error is DioException) {
      final status = error.response?.statusCode;
      final body = error.response?.data;
      return status == null
          ? (error.message ?? 'Connection failed')
          : 'HTTP $status${body == null ? '' : ': $body'}';
    }
    return error.toString();
  }
}
