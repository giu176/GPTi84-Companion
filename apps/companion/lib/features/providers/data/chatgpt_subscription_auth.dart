import 'dart:convert';

import 'package:dio/dio.dart';

import 'ai_provider_store.dart';

class ChatGptDeviceSession {
  const ChatGptDeviceSession({
    required this.deviceAuthId,
    required this.userCode,
    required this.verificationUri,
    required this.interval,
    required this.expiresAt,
  });

  final String deviceAuthId;
  final String userCode;
  final Uri verificationUri;
  final Duration interval;
  final DateTime expiresAt;
}

class ChatGptSubscriptionAuth {
  ChatGptSubscriptionAuth({Dio? dio}) : _dio = dio ?? Dio();

  static const clientId = 'app_EMoamEEZ73f0CkXaXp7hrann';
  static const issuer = 'https://auth.openai.com';
  static const redirectUri = '$issuer/deviceauth/callback';
  static const baseUrl = 'https://chatgpt.com/backend-api/codex';

  final Dio _dio;

  Future<ChatGptDeviceSession> start() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$issuer/api/accounts/deviceauth/usercode',
      data: {'client_id': clientId},
    );
    final data = response.data ?? const <String, dynamic>{};
    final deviceAuthId = data['device_auth_id']?.toString() ?? '';
    final userCode = data['user_code']?.toString() ?? '';
    if (deviceAuthId.isEmpty || userCode.isEmpty) {
      throw const FormatException(
        'OpenAI did not return a complete device code',
      );
    }
    final expiresIn = int.tryParse(data['expires_in']?.toString() ?? '') ?? 900;
    final interval = int.tryParse(data['interval']?.toString() ?? '') ?? 5;
    return ChatGptDeviceSession(
      deviceAuthId: deviceAuthId,
      userCode: userCode,
      verificationUri: Uri.parse(
        data['verification_uri']?.toString() ?? '$issuer/codex/device',
      ),
      interval: Duration(seconds: interval < 2 ? 2 : interval),
      expiresAt: DateTime.now().add(Duration(seconds: expiresIn)),
    );
  }

  Future<AiProviderConfig?> poll(ChatGptDeviceSession session) async {
    Response<Map<String, dynamic>> response;
    try {
      response = await _dio.post<Map<String, dynamic>>(
        '$issuer/api/accounts/deviceauth/token',
        data: {
          'device_auth_id': session.deviceAuthId,
          'user_code': session.userCode,
        },
        options: Options(
          validateStatus: (status) => status != null && status < 500,
        ),
      );
    } on DioException catch (error) {
      if (error.response?.statusCode == 403 ||
          error.response?.statusCode == 404) {
        return null;
      }
      if (_isTransientPollFailure(error)) return null;
      rethrow;
    }
    if (response.statusCode == 403 || response.statusCode == 404) return null;
    final data = response.data ?? const <String, dynamic>{};
    final authorizationCode = data['authorization_code']?.toString() ?? '';
    final codeVerifier = data['code_verifier']?.toString() ?? '';
    if (authorizationCode.isEmpty || codeVerifier.isEmpty) return null;
    return _exchange(authorizationCode, codeVerifier);
  }

  bool _isTransientPollFailure(DioException error) {
    if ((error.response?.statusCode ?? 0) >= 500) return true;
    return switch (error.type) {
      DioExceptionType.connectionError ||
      DioExceptionType.connectionTimeout ||
      DioExceptionType.receiveTimeout ||
      DioExceptionType.sendTimeout => true,
      _ => false,
    };
  }

  Future<AiProviderConfig> refresh(AiProviderConfig config) async {
    if (config.refreshToken.isEmpty) {
      throw StateError('ChatGPT Subscription must be connected again');
    }
    final response = await _dio.post<Map<String, dynamic>>(
      '$issuer/oauth/token',
      data: {
        'grant_type': 'refresh_token',
        'refresh_token': config.refreshToken,
        'client_id': clientId,
      },
      options: Options(contentType: Headers.formUrlEncodedContentType),
    );
    return _configFromTokens(response.data ?? const {}, fallback: config);
  }

  Future<AiProviderConfig> _exchange(String code, String verifier) async {
    final response = await _dio.post<Map<String, dynamic>>(
      '$issuer/oauth/token',
      data: {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirectUri,
        'client_id': clientId,
        'code_verifier': verifier,
      },
      options: Options(contentType: Headers.formUrlEncodedContentType),
    );
    return _configFromTokens(response.data ?? const {});
  }

  AiProviderConfig _configFromTokens(
    Map<String, dynamic> data, {
    AiProviderConfig? fallback,
  }) {
    final accessToken = data['access_token']?.toString() ?? '';
    if (accessToken.isEmpty) {
      throw const FormatException('OpenAI returned no access token');
    }
    final expiresIn =
        int.tryParse(data['expires_in']?.toString() ?? '') ?? 3600;
    return AiProviderConfig(
      kind: AiProviderKind.chatGptSubscription,
      model: fallback?.model ?? 'gpt-5.5',
      apiKey: accessToken,
      refreshToken:
          data['refresh_token']?.toString() ?? fallback?.refreshToken ?? '',
      accountId:
          _accountIdFromToken(data['id_token']?.toString() ?? accessToken) ??
          data['account_id']?.toString() ??
          fallback?.accountId ??
          '',
      tokenExpiresAt: DateTime.now().add(Duration(seconds: expiresIn)),
      baseUrl: baseUrl,
    );
  }

  String? _accountIdFromToken(String token) {
    try {
      final parts = token.split('.');
      if (parts.length != 3) return null;
      final payload = jsonDecode(
        utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))),
      );
      if (payload is! Map<String, dynamic>) return null;
      final auth = payload['https://api.openai.com/auth'];
      if (auth is! Map<String, dynamic>) return null;
      return auth['chatgpt_account_id']?.toString();
    } catch (_) {
      return null;
    }
  }
}
