import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gpti84_companion/app.dart';
import 'package:gpti84_companion/features/conversations/data/app_database.dart';
import 'package:gpti84_companion/features/conversations/presentation/conversation_list_screen.dart';
import 'package:gpti84_companion/features/settings/presentation/settings_screen.dart';

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));

  testWidgets('shows the companion navigation', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          conversationsProvider.overrideWith((ref) => Stream.value(const [])),
        ],
        child: const Gpti84CompanionApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Chats'), findsOneWidget);
    expect(find.text('Calculator'), findsOneWidget);
    expect(find.text('Settings'), findsOneWidget);
    expect(find.text('New chat'), findsOneWidget);
  });

  testWidgets('settings separates services, advanced, and about', (
    tester,
  ) async {
    await tester.pumpWidget(
      const ProviderScope(child: MaterialApp(home: SettingsScreen())),
    );
    await tester.pumpAndSettle();

    expect(find.text('Manage AI services'), findsOneWidget);
    expect(find.text('Advanced'), findsOneWidget);
    expect(find.text('About'), findsOneWidget);
    expect(find.text('Credential security'), findsNothing);

    await tester.tap(find.text('About'));
    await tester.pumpAndSettle();

    expect(find.text('Files and pictures'), findsOneWidget);
    expect(find.text('Credential security'), findsOneWidget);
    expect(find.text('API billing'), findsOneWidget);
    expect(find.text('Local-first privacy'), findsOneWidget);
  });

  testWidgets('switches tabs without tearing down inherited dependencies', (
    tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          conversationsProvider.overrideWith((ref) => Stream.value(const [])),
        ],
        child: const Gpti84CompanionApp(),
      ),
    );
    await tester.pumpAndSettle();

    for (var index = 0; index < 3; index++) {
      await tester.tap(find.text('Settings'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Chats'));
      await tester.pumpAndSettle();
    }

    expect(tester.takeException(), isNull);
    expect(find.text('New chat'), findsOneWidget);
  });

  testWidgets('opens and closes a conversation repeatedly', (tester) async {
    final now = DateTime(2026, 6, 22);
    final conversation = Conversation(
      id: 'chat-1',
      title: 'Lifecycle test',
      isPinned: false,
      pinOrder: null,
      providerProfileId: null,
      createdAt: now,
      updatedAt: now,
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          conversationsProvider.overrideWith(
            (ref) => Stream.value([conversation]),
          ),
        ],
        child: const Gpti84CompanionApp(),
      ),
    );
    await tester.pumpAndSettle();

    for (var index = 0; index < 3; index++) {
      await tester.tap(find.text('Lifecycle test'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));
      await tester.pageBack();
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));
    }

    expect(tester.takeException(), isNull);
    expect(find.text('Lifecycle test'), findsOneWidget);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(milliseconds: 1));
  });
}
