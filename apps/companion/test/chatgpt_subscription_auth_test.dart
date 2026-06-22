import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpti84_companion/features/providers/data/chatgpt_subscription_auth.dart';

void main() {
  test(
    'device authorization polling tolerates transient DNS failures',
    () async {
      final dio = Dio()..httpClientAdapter = _ConnectionFailureAdapter();
      final auth = ChatGptSubscriptionAuth(dio: dio);
      final session = ChatGptDeviceSession(
        deviceAuthId: 'device-id',
        userCode: 'ABCD-EFGH',
        verificationUri: Uri.parse('https://auth.openai.com/codex/device'),
        interval: const Duration(seconds: 5),
        expiresAt: DateTime.now().add(const Duration(minutes: 5)),
      );

      expect(await auth.poll(session), isNull);
    },
  );
}

class _ConnectionFailureAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) {
    throw DioException.connectionError(
      requestOptions: options,
      reason: 'Failed host lookup: auth.openai.com',
    );
  }

  @override
  void close({bool force = false}) {}
}
