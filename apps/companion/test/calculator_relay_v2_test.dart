import 'dart:async';
import 'dart:convert';

import 'package:drift/native.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpti84_companion/features/conversations/data/app_database.dart';
import 'package:gpti84_companion/features/providers/data/ai_provider_store.dart';
import 'package:gpti84_companion/features/providers/data/direct_ai_client.dart';
import 'package:gpti84_companion/features/relay/data/calculator_relay.dart';
import 'package:gpti84_companion/features/relay/data/pinned_catalog.dart';

void main() {
  late AppDatabase database;
  late AiProviderStore store;
  late _FakeAiClient aiClient;
  late CalculatorRelay relay;

  setUp(() async {
    FlutterSecureStorage.setMockInitialValues({});
    database = AppDatabase.forTesting(NativeDatabase.memory());
    store = const AiProviderStore();
    await store.upsert(
      const ProviderProfile(
        id: 'test',
        name: 'Test',
        config: AiProviderConfig(
          kind: AiProviderKind.ollama,
          model: 'test-model',
          apiKey: '',
          baseUrl: 'http://localhost:11434',
        ),
      ),
    );
    await store.setFavorite('test');
    aiClient = _FakeAiClient(store);
    relay = CalculatorRelay(
      database: database,
      providerStore: store,
      directAiClient: aiClient,
    );
  });

  tearDown(() async {
    await database.close();
  });

  test('SEND appends to the addressed chat and emits reply update', () async {
    await database.createConversation(
      id: 'CTARGET',
      title: 'Target',
      providerProfileId: 'test',
    );
    await database.setPinned('CTARGET', true);

    final updateFuture = relay.updates.firstWhere(
      (frame) => ascii.decode(frame, allowInvalid: true).contains('AI: reply'),
    );
    final pending = await relay.reply(
      ascii.encode('SEND CTARGET MSG1\nhello from calc'),
      idempotencyKey: 'ble-device-1',
    );

    expect(ascii.decode(pending), contains('YOU (sending):'));
    final messages = await database.getMessages('CTARGET');
    expect(messages.single.content, 'hello from calc');
    expect(aiClient.sendCount, 1);

    final update = await updateFuture.timeout(const Duration(seconds: 2));
    final updatedText = ascii.decode(update, allowInvalid: true);
    expect(updatedText, contains('AI: reply'));
    expect(await database.getMessages('CTARGET'), hasLength(2));
  });

  test(
    'LIST renders calculator slots without exposing full chat ids',
    () async {
      await database.createConversation(
        id: 'C1234567890ABCDEF',
        title: 'AI App Test',
        providerProfileId: 'test',
      );
      await database.setPinned('C1234567890ABCDEF', true);

      final frame = await relay.reply(
        ascii.encode('LIST'),
        idempotencyKey: 'l1',
      );
      final text = ascii.decode(frame, allowInvalid: true);
      final rows = _pageRows(text);

      expect(rows, contains('0 NEW CHAT'));
      expect(rows, contains('1 AI APP TEST'));
      expect(text, isNot(contains('C1234567890ABCDEF')));
    },
  );

  test(
    'duplicate client message id does not duplicate provider calls',
    () async {
      await database.createConversation(
        id: 'CTARGET',
        title: 'Target',
        providerProfileId: 'test',
      );

      await relay.reply(
        ascii.encode('SEND CTARGET MSG1\nhello'),
        idempotencyKey: 'first',
      );
      await _waitForMessages(database, 'CTARGET', 2);
      await relay.reply(
        ascii.encode('SEND CTARGET MSG1\nhello'),
        idempotencyKey: 'retry',
      );

      expect(aiClient.sendCount, 1);
      expect(await database.getMessages('CTARGET'), hasLength(2));
    },
  );

  test('pinned catalog escapes fields and hashes deterministically', () async {
    await database.createConversation(id: 'c|1', title: 'A|B');
    await database.addMessage(
      id: 'm',
      conversationId: 'c|1',
      role: 'user',
      content: 'line\npercent %',
    );
    await database.setPinned('c|1', true);

    final catalog = PinnedCatalog.fromProjections(
      deviceId: 'phone|one',
      projections: await database.getPinnedProjections(),
    ).encode();

    expect(catalog, startsWith('GPTI84PINS 1\n'));
    expect(catalog, contains('device=phone%7Cone'));
    expect(catalog, contains('C|c%7C1|'));
    expect(catalog, contains('A%7CB'));
    expect(fnv1a32('hello'.codeUnits), 0x4f9f2cab);
  });
}

List<String> _pageRows(String frameText) {
  final pageBody = frameText.substring(frameText.indexOf('\n') + 1);
  return pageBody
      .split('\x00')
      .expand(
        (page) => [
          for (var index = 0; index + 16 <= page.length; index += 16)
            page.substring(index, index + 16).trimRight(),
        ],
      )
      .toList();
}

Future<void> _waitForMessages(
  AppDatabase database,
  String conversationId,
  int count,
) async {
  final deadline = DateTime.now().add(const Duration(seconds: 2));
  while (DateTime.now().isBefore(deadline)) {
    if ((await database.getMessages(conversationId)).length >= count) return;
    await Future<void>.delayed(const Duration(milliseconds: 20));
  }
  throw TimeoutException('Timed out waiting for $count messages');
}

class _FakeAiClient extends DirectAiClient {
  _FakeAiClient(super.store);

  int sendCount = 0;

  @override
  Future<AiReply> send({
    required String profileId,
    required List<ChatTurn> history,
    required String text,
    required List<ChatAttachment> attachments,
  }) async {
    sendCount += 1;
    await Future<void>.delayed(const Duration(milliseconds: 10));
    return const AiReply('reply from fake AI');
  }
}
