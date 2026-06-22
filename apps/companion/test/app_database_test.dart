import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gpti84_companion/features/conversations/data/app_database.dart';

void main() {
  late AppDatabase database;

  setUp(() => database = AppDatabase.forTesting(NativeDatabase.memory()));
  tearDown(() => database.close());

  test('persists attachment metadata with a chat message', () async {
    await database.createConversation(id: 'chat', title: 'Files');
    await database.addMessage(
      id: 'message',
      conversationId: 'chat',
      role: 'user',
      content: 'Read this',
      attachmentsJson:
          '[{"path":"/private/example.pdf","name":"example.pdf","mimeType":"application/pdf"}]',
    );

    final message = (await database.getMessages('chat')).single;
    expect(message.attachmentsJson, contains('example.pdf'));
  });

  test('enforces the eight pinned chat limit', () async {
    for (var index = 0; index < 9; index++) {
      await database.createConversation(id: '$index', title: 'Chat $index');
    }
    for (var index = 0; index < 8; index++) {
      await database.setPinned('$index', true);
    }

    await expectLater(
      database.setPinned('8', true),
      throwsA(isA<StateError>()),
    );
  });

  test('stores and reassigns conversation and message providers', () async {
    await database.createConversation(
      id: 'chat',
      title: 'Providers',
      providerProfileId: 'old',
    );
    await database.addMessage(
      id: 'answer',
      conversationId: 'chat',
      role: 'assistant',
      content: 'Hello',
      providerProfileId: 'old',
    );

    await database.reassignProvider('old', 'favorite');
    final conversation = (await database.watchConversations().first).single;
    final message = (await database.getMessages('chat')).single;

    expect(conversation.providerProfileId, 'favorite');
    expect(message.providerProfileId, 'old');
  });
}
