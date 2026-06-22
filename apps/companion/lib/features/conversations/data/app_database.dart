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
    return (update(chatMessages)..where((row) => row.id.equals(id))).write(
      ChatMessagesCompanion(status: Value(status)),
    );
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
    if (pinned) {
      final count =
          await (selectOnly(conversations)
                ..addColumns([conversations.id.count()])
                ..where(conversations.isPinned.equals(true)))
              .map((row) => row.read(conversations.id.count()) ?? 0)
              .getSingle();
      if (count >= 8) throw StateError('Only eight chats can be pinned');
    }
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

LazyDatabase _openConnection() {
  return LazyDatabase(() async {
    final directory = await getApplicationDocumentsDirectory();
    return NativeDatabase.createInBackground(
      File(p.join(directory.path, 'gpti84_companion.sqlite')),
    );
  });
}
