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
  DateTimeColumn get createdAt => dateTime()();

  @override
  Set<Column<Object>> get primaryKey => {id};
}

@DriftDatabase(tables: [Conversations, ChatMessages])
class AppDatabase extends _$AppDatabase {
  AppDatabase() : super(_openConnection());

  AppDatabase.forTesting(super.executor);

  @override
  int get schemaVersion => 1;

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

  Future<void> createConversation({required String id, required String title}) {
    final now = DateTime.now();
    return into(conversations).insert(
      ConversationsCompanion.insert(
        id: id,
        title: title,
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
      File(p.join(directory.path, 'ti84_companion.sqlite')),
    );
  });
}
