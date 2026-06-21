import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ti84_companion/app.dart';
import 'package:ti84_companion/features/conversations/presentation/conversation_list_screen.dart';

void main() {
  testWidgets('shows the companion navigation', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          conversationsProvider.overrideWith((ref) => Stream.value(const [])),
        ],
        child: const Ti84CompanionApp(),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('Chats'), findsOneWidget);
    expect(find.text('Calculator'), findsOneWidget);
    expect(find.text('Settings'), findsOneWidget);
    expect(find.text('New chat'), findsOneWidget);
  });
}
