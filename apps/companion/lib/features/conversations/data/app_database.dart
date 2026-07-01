import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

part 'app_database.g.dart';

class Conversations extends Table {
  TextColumn get id => text()();
  TextColumn get title => text().withLength(min: 1, max: 120)();
  BoolColumn get isPinned => boolean().withDefault(const Constant(false))();
  IntColumn get pinOrder => integer().nullable()();
  TextColumn get providerProfileId => text().nullable()();
  DateTimeColumn get createdAt => dateTime()();
  DateTimeColumn get updatedAt => dateTime()();

  @override
  Set<Column<Object>> get primaryKey => {id};
}

class ChatMessages extends Table {
  TextColumn get id => text()();
  TextColumn get conversationId => text()();
  TextColumn get role => text()();
  TextColumn get content => text()();
  TextColumn get origin => text().withDefault(const Constant('phone'))();
  TextColumn get status => text().withDefault(const Constant('complete'))();
  TextColumn get attachmentsJson => text().nullable()();
  TextColumn get providerProfileId => text().nullable()();
  DateTimeColumn get createdAt => dateTime()();

  @override
  Set<Column<Object>> get primaryKey => {id};
}

@DriftDatabase(tables: [Conversations, ChatMessages])
class AppDatabase extends _$AppDatabase {
  AppDatabase() : super(_openConnection());

  AppDatabase.forTesting(super.executor);

  @override
  int get schemaVersion => 3;

  @override
  MigrationStrategy get migration => MigrationStrategy(
    onCreate: (migrator) => migrator.createAll(),
    onUpgrade: (migrator, from, to) async {
      if (from < 2) {
        await migrator.addColumn(chatMessages, chatMessages.attachmentsJson);
      }
      if (from < 3) {
        await migrator.addColumn(
          conversations,
          conversations.providerProfileId,
        );
        await migrator.addColumn(chatMessages, chatMessages.providerProfileId);
      }
    },
  );

  Stream<List<Conversation>> watchConversations() {
    return (select(conversations)..orderBy([
          (row) => OrderingTerm.desc(row.isPinned),
          (row) => OrderingTerm.desc(row.updatedAt),
        ]))
        .watch();
  }

  Stream<List<ChatMessage>> watchMessages(String conversationId) {
    return (select(chatMessages)
          ..where((row) => row.conversationId.equals(conversationId))
          ..orderBy([(row) => OrderingTerm.asc(row.createdAt)]))
        .watch();
  }

  Future<List<ChatMessage>> getMessages(String conversationId) {
    return (select(chatMessages)
          ..where((row) => row.conversationId.equals(conversationId))
          ..orderBy([(row) => OrderingTerm.asc(row.createdAt)]))
        .get();
  }

  Future<ChatMessage?> getMessage(String id) {
    return (select(
      chatMessages,
    )..where((row) => row.id.equals(id))).getSingleOrNull();
  }

  Future<List<PinnedConversationProjection>> getPinnedProjections() async {
    final pinned =
        await (select(conversations)
              ..where((row) => row.isPinned.equals(true))
              ..orderBy([
                (row) => OrderingTerm.asc(row.pinOrder),
                (row) => OrderingTerm.asc(row.updatedAt),
              ]))
            .get();
    final result = <PinnedConversationProjection>[];
    for (final conversation in pinned) {
      final messages =
          await (select(chatMessages)
                ..where((row) => row.conversationId.equals(conversation.id))
                ..orderBy([(row) => OrderingTerm.desc(row.createdAt)])
                ..limit(12))
              .get();
      final text = messages.reversed
          .map((message) => '${message.role}: ${message.content}')
          .join('\n');
      result.add(
        PinnedConversationProjection(
          conversationId: conversation.id,
          title: conversation.title,
          text: text,
          pinOrder: conversation.pinOrder ?? 0,
          revision: conversation.updatedAt.millisecondsSinceEpoch,
        ),
      );
    }
    return result;
  }

  Future<PinnedConversationProjection?> getPinnedProjectionBySlot(
    int slot,
  ) async {
    if (slot < 1) return null;
    final projections = await getPinnedProjections();
    if (slot > projections.length) return null;
    return projections[slot - 1];
  }

  Future<Conversation?> getConversation(String id) {
    return (select(
      conversations,
    )..where((row) => row.id.equals(id))).getSingleOrNull();
  }

  Future<int> getConversationRevision(String id) async {
    final conversation = await getConversation(id);
    return conversation?.updatedAt.millisecondsSinceEpoch ?? 0;
  }

  Future<void> createConversation({
    required String id,
    required String title,
    String? providerProfileId,
  }) {
    final now = DateTime.now();
    return into(conversations).insert(
      ConversationsCompanion.insert(
        id: id,
        title: title,
        providerProfileId: Value(providerProfileId),
        createdAt: now,
        updatedAt: now,
      ),
    );
  }

  Future<void> ensureConversation({
    required String id,
    required String title,
    String? providerProfileId,
  }) async {
    final existing = await (select(
      conversations,
    )..where((row) => row.id.equals(id))).getSingleOrNull();
    if (existing != null) return;
    await createConversation(
      id: id,
      title: title,
      providerProfileId: providerProfileId,
    );
  }

  Future<void> addMessage({
    required String id,
    required String conversationId,
    required String role,
    required String content,
    String origin = 'phone',
    String status = 'complete',
    String? attachmentsJson,
    String? providerProfileId,
  }) async {
    await transaction(() async {
      await into(chatMessages).insert(
        ChatMessagesCompanion.insert(
          id: id,
          conversationId: conversationId,
          role: role,
          content: content,
          origin: Value(origin),
          status: Value(status),
          attachmentsJson: Value(attachmentsJson),
          providerProfileId: Value(providerProfileId),
          createdAt: DateTime.now(),
        ),
      );
      await (update(conversations)
            ..where((row) => row.id.equals(conversationId)))
          .write(ConversationsCompanion(updatedAt: Value(DateTime.now())));
    });
  }

  Future<void> setMessageStatus(String id, String status) {
    return transaction(() async {
      final message = await getMessage(id);
      await (update(chatMessages)..where((row) => row.id.equals(id))).write(
        ChatMessagesCompanion(status: Value(status)),
      );
      if (message != null) {
        await (update(conversations)
              ..where((row) => row.id.equals(message.conversationId)))
            .write(ConversationsCompanion(updatedAt: Value(DateTime.now())));
      }
    });
  }

  Future<void> setConversationProvider(String id, String? profileId) {
    return (update(conversations)..where((row) => row.id.equals(id))).write(
      ConversationsCompanion(
        providerProfileId: Value(profileId),
        updatedAt: Value(DateTime.now()),
      ),
    );
  }

  Future<void> renameConversation(String id, String title) {
    final cleaned = title.trim();
    if (cleaned.isEmpty) throw ArgumentError.value(title, 'title');
    return (update(conversations)..where((row) => row.id.equals(id))).write(
      ConversationsCompanion(
        title: Value(cleaned),
        updatedAt: Value(DateTime.now()),
      ),
    );
  }

  Future<bool> replaceConversationTitle({
    required String id,
    required String expectedTitle,
    required String title,
  }) async {
    final cleaned = title.trim();
    if (cleaned.isEmpty) throw ArgumentError.value(title, 'title');
    final updated =
        await (update(conversations)..where(
              (row) => row.id.equals(id) & row.title.equals(expectedTitle),
            ))
            .write(
              ConversationsCompanion(
                title: Value(cleaned),
                updatedAt: Value(DateTime.now()),
              ),
            );
    return updated == 1;
  }

  Future<void> reassignProvider(String removedId, String? replacementId) async {
    await transaction(() async {
      await (update(
        conversations,
      )..where((row) => row.providerProfileId.equals(removedId))).write(
        ConversationsCompanion(
          providerProfileId: Value(replacementId),
          updatedAt: Value(DateTime.now()),
        ),
      );
    });
  }

  Future<void> setPinned(String id, bool pinned) async {
    await (update(conversations)..where((row) => row.id.equals(id))).write(
      ConversationsCompanion(
        isPinned: Value(pinned),
        pinOrder: Value(pinned ? DateTime.now().millisecondsSinceEpoch : null),
        updatedAt: Value(DateTime.now()),
      ),
    );
  }

  Future<void> deleteConversation(String id) async {
    await transaction(() async {
      await (delete(
        chatMessages,
      )..where((row) => row.conversationId.equals(id))).go();
      await (delete(conversations)..where((row) => row.id.equals(id))).go();
    });
  }
}

class PinnedConversationProjection {
  const PinnedConversationProjection({
    required this.conversationId,
    required this.title,
    required this.text,
    required this.pinOrder,
    required this.revision,
  });

  final String conversationId;
  final String title;
  final String text;
  final int pinOrder;
  final int revision;
}

LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final directory = await getApplicationDocumentsDirectory();
    return NativeDatabase.createInBackground(
      File(p.join(directory.path, 'gpti84_companion.sqlite')),
    );
  });
}
