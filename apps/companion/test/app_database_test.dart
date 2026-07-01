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

  test('allows more than eight pinned chats', () async {
    for (var index = 0; index < 9; index++) {
      await database.createConversation(id: '$index', title: 'Chat $index');
    }
    for (var index = 0; index < 9; index++) {
      await database.setPinned('$index', true);
    }

    expect(await database.getPinnedProjections(), hasLength(9));
  });

  test('builds text-only pinned projections', () async {
    await database.createConversation(id: 'chat', title: 'Pinned');
    await database.addMessage(
      id: 'user',
      conversationId: 'chat',
      role: 'user',
      content: 'Hello',
    );
    await database.addMessage(
      id: 'assistant',
      conversationId: 'chat',
      role: 'assistant',
      content: 'Hi back',
    );
    await database.setPinned('chat', true);

    final projection = (await database.getPinnedProjections()).single;

    expect(projection.conversationId, 'chat');
    expect(projection.title, 'Pinned');
    expect(projection.text, contains('user: Hello'));
    expect(projection.text, contains('assistant: Hi back'));
    expect(projection.revision, greaterThan(0));
  });

  test('resolves pinned projections by calculator slot', () async {
    await database.createConversation(id: 'first', title: 'First');
    await database.createConversation(id: 'second', title: 'Second');
    await database.setPinned('first', true);
    await database.setPinned('second', true);

    expect(
      (await database.getPinnedProjectionBySlot(1))?.conversationId,
      'first',
    );
    expect(
      (await database.getPinnedProjectionBySlot(2))?.conversationId,
      'second',
    );
    expect(await database.getPinnedProjectionBySlot(3), isNull);
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

  test('generated title only replaces the automatic preview', () async {
    await database.createConversation(id: 'generated', title: 'New chat');
    await database.renameConversation('generated', 'Initial prompt preview');

    expect(
      await database.replaceConversationTitle(
        id: 'generated',
        expectedTitle: 'Initial prompt preview',
        title: 'Generated short title',
      ),
      isTrue,
    );
    expect(
      await database.replaceConversationTitle(
        id: 'generated',
        expectedTitle: 'Initial prompt preview',
        title: 'Late generated title',
      ),
      isFalse,
    );

    final conversation = (await database.watchConversations().first).single;
    expect(conversation.title, 'Generated short title');
  });
}
