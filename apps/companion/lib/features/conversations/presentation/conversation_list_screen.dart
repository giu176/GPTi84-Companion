import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:uuid/uuid.dart';

import '../../../core/providers.dart';
import '../data/app_database.dart';
import 'conversation_screen.dart';

final conversationsProvider = StreamProvider<List<Conversation>>(
  (ref) => ref.watch(databaseProvider).watchConversations(),
);

class ConversationListScreen extends ConsumerWidget {
  const ConversationListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final conversations = ref.watch(conversationsProvider);
    return Scaffold(
      appBar: AppBar(
        title: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('GPTi84 Companion'),
            Text(
              'Your conversations',
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.normal),
            ),
          ],
        ),
      ),
      body: conversations.when(
        data: (items) => items.isEmpty
            ? const _EmptyConversations()
            : ListView.separated(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 100),
                itemCount: items.length,
                separatorBuilder: (_, _) => const SizedBox(height: 10),
                itemBuilder: (context, index) {
                  final conversation = items[index];
                  return Card(
                    key: ValueKey(conversation.id),
                    child: ListTile(
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 18,
                        vertical: 8,
                      ),
                      leading: CircleAvatar(
                        child: Icon(
                          conversation.isPinned
                              ? Icons.calculate
                              : Icons.chat_bubble_outline,
                        ),
                      ),
                      title: Text(
                        conversation.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      subtitle: Text(
                        conversation.isPinned
                            ? 'Pinned to calculator • ${DateFormat.MMMd().format(conversation.updatedAt)}'
                            : DateFormat.yMMMd().add_jm().format(
                                conversation.updatedAt,
                              ),
                      ),
                      trailing: PopupMenuButton<String>(
                        onSelected: (action) {
                          if (action == 'rename') {
                            _renameConversation(context, ref, conversation);
                          } else if (action == 'delete') {
                            ref
                                .read(databaseProvider)
                                .deleteConversation(conversation.id);
                          }
                        },
                        itemBuilder: (_) => const [
                          PopupMenuItem(value: 'rename', child: Text('Rename')),
                          PopupMenuItem(value: 'delete', child: Text('Delete')),
                        ],
                      ),
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => ConversationScreen(
                            conversationId: conversation.id,
                            title: conversation.title,
                            initiallyPinned: conversation.isPinned,
                            initialProviderProfileId:
                                conversation.providerProfileId,
                          ),
                        ),
                      ),
                    ),
                  );
                },
              ),
        error: (error, _) =>
            Center(child: Text('Could not load chats: $error')),
        loading: () => const Center(child: CircularProgressIndicator()),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _createConversation(context, ref),
        icon: const Icon(Icons.add_comment_outlined),
        label: const Text('New chat'),
      ),
    );
  }

  Future<void> _createConversation(BuildContext context, WidgetRef ref) async {
    final id = const Uuid().v4();
    const title = 'New chat';
    final vault = await ref.read(aiProviderStoreProvider).readVault();
    final profileId = vault.favoriteProfileId;
    await ref
        .read(databaseProvider)
        .createConversation(id: id, title: title, providerProfileId: profileId);
    if (!context.mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ConversationScreen(
          conversationId: id,
          title: title,
          initiallyPinned: false,
          initialProviderProfileId: profileId,
        ),
      ),
    );
  }

  Future<void> _renameConversation(
    BuildContext context,
    WidgetRef ref,
    Conversation conversation,
  ) async {
    final controller = TextEditingController(text: conversation.title);
    final title = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Rename chat'),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLength: 120,
          onSubmitted: (value) => Navigator.pop(context, value),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text),
            child: const Text('Save'),
          ),
        ],
      ),
    );
    controller.dispose();
    if (title != null && title.trim().isNotEmpty) {
      await ref
          .read(databaseProvider)
          .renameConversation(conversation.id, title);
    }
  }
}

class _EmptyConversations extends StatelessWidget {
  const _EmptyConversations();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.forum_outlined,
              size: 68,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 20),
            Text(
              'A quiet little terminal',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 8),
            const Text(
              'Start a chat here. Later, pin it to make its text projection available on your TI-84.',
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
