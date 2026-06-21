import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';

import '../../../core/providers.dart';
import '../data/app_database.dart';

final _messagesProvider = StreamProvider.family<List<ChatMessage>, String>(
  (ref, conversationId) =>
      ref.watch(databaseProvider).watchMessages(conversationId),
);

class ConversationScreen extends ConsumerStatefulWidget {
  const ConversationScreen({
    required this.conversationId,
    required this.title,
    required this.initiallyPinned,
    super.key,
  });

  final String conversationId;
  final String title;
  final bool initiallyPinned;

  @override
  ConsumerState<ConversationScreen> createState() => _ConversationScreenState();
}

class _ConversationScreenState extends ConsumerState<ConversationScreen> {
  final _composer = TextEditingController();
  final _scrollController = ScrollController();
  var _sending = false;
  late var _pinned = widget.initiallyPinned;

  @override
  void dispose() {
    _composer.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final messages = ref.watch(_messagesProvider(widget.conversationId));
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title, overflow: TextOverflow.ellipsis),
        actions: [
          IconButton(
            tooltip: _pinned ? 'Remove from calculator' : 'Pin to calculator',
            onPressed: _togglePinned,
            icon: Icon(_pinned ? Icons.push_pin : Icons.push_pin_outlined),
          ),
        ],
      ),
      body: Column(
        children: [
          if (_pinned)
            MaterialBanner(
              content: const Text(
                'This chat will be available in the TI-84 pinned list.',
              ),
              leading: const Icon(Icons.calculate_outlined),
              actions: [
                TextButton(
                  onPressed: _togglePinned,
                  child: const Text('Unpin'),
                ),
              ],
            ),
          Expanded(
            child: messages.when(
              data: (items) {
                if (items.isEmpty) return const _EmptyChat();
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  if (_scrollController.hasClients) {
                    _scrollController.animateTo(
                      _scrollController.position.maxScrollExtent,
                      duration: const Duration(milliseconds: 220),
                      curve: Curves.easeOut,
                    );
                  }
                });
                return ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.fromLTRB(12, 16, 12, 12),
                  itemCount: items.length,
                  itemBuilder: (_, index) =>
                      _MessageBubble(message: items[index]),
                );
              },
              error: (error, _) =>
                  Center(child: Text('Could not load messages: $error')),
              loading: () => const Center(child: CircularProgressIndicator()),
            ),
          ),
          _Composer(controller: _composer, sending: _sending, onSend: _send),
        ],
      ),
    );
  }

  Future<void> _togglePinned() async {
    try {
      await ref
          .read(databaseProvider)
          .setPinned(widget.conversationId, !_pinned);
      if (mounted) setState(() => _pinned = !_pinned);
    } on StateError catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.message)));
      }
    }
  }

  Future<void> _send() async {
    final text = _composer.text.trim();
    if (text.isEmpty || _sending) return;
    _composer.clear();
    setState(() => _sending = true);
    final messageId = const Uuid().v4();
    final database = ref.read(databaseProvider);
    await database.addMessage(
      id: messageId,
      conversationId: widget.conversationId,
      role: 'user',
      content: text,
      status: 'sending',
    );
    try {
      final reply = await ref
          .read(relayClientProvider)
          .sendText(
            messageId: messageId,
            conversationId: widget.conversationId,
            text: text,
          );
      await database.setMessageStatus(messageId, 'complete');
      await database.addMessage(
        id: reply.id,
        conversationId: widget.conversationId,
        role: 'assistant',
        content: reply.text,
      );
    } catch (error) {
      await database.setMessageStatus(messageId, 'failed');
      if (mounted) {
        final detail = error is DioException
            ? error.response?.data?.toString() ?? error.message
            : error.toString();
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(detail ?? 'Relay request failed')),
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});

  final ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == 'user';
    final colors = Theme.of(context).colorScheme;
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 620),
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: isUser
              ? colors.primaryContainer
              : colors.surfaceContainerHighest,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(20),
            topRight: const Radius.circular(20),
            bottomLeft: Radius.circular(isUser ? 20 : 4),
            bottomRight: Radius.circular(isUser ? 4 : 20),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (isUser)
              Text(message.content)
            else
              MarkdownBody(data: message.content, selectable: true),
            if (message.status != 'complete') ...[
              const SizedBox(height: 6),
              Text(
                message.status == 'failed' ? 'Not sent' : 'Sending…',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: message.status == 'failed'
                      ? colors.error
                      : colors.outline,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({
    required this.controller,
    required this.sending,
    required this.onSend,
  });

  final TextEditingController controller;
  final bool sending;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            IconButton.filledTonal(
              tooltip: 'Attach image (next milestone)',
              onPressed: null,
              icon: const Icon(Icons.add_photo_alternate_outlined),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextField(
                controller: controller,
                minLines: 1,
                maxLines: 6,
                textCapitalization: TextCapitalization.sentences,
                decoration: const InputDecoration(
                  hintText: 'Message the assistant',
                  filled: true,
                ),
                onSubmitted: (_) => onSend(),
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filled(
              tooltip: 'Send',
              onPressed: sending ? null : onSend,
              icon: sending
                  ? const SizedBox.square(
                      dimension: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.arrow_upward),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyChat extends StatelessWidget {
  const _EmptyChat();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(32),
        child: Text(
          'This conversation is ready. Configure your relay, then send the first message.',
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}
