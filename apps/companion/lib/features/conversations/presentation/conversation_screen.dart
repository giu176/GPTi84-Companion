import 'dart:convert';
import 'dart:io';

import 'package:dio/dio.dart';
import 'package:file_selector/file_selector.dart';
import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:mime/mime.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

import '../../../core/providers.dart';
import '../../providers/data/ai_provider_store.dart';
import '../../providers/data/direct_ai_client.dart';
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
    required this.initialProviderProfileId,
    super.key,
  });

  final String conversationId;
  final String title;
  final bool initiallyPinned;
  final String? initialProviderProfileId;

  @override
  ConsumerState<ConversationScreen> createState() => _ConversationScreenState();
}

class _ConversationScreenState extends ConsumerState<ConversationScreen> {
  final _composer = TextEditingController();
  final _scrollController = ScrollController();
  var _sending = false;
  final _attachments = <ChatAttachment>[];
  late var _pinned = widget.initiallyPinned;
  String? _providerProfileId;
  List<ProviderProfile> _providerProfiles = const [];

  @override
  void initState() {
    super.initState();
    _providerProfileId = widget.initialProviderProfileId;
    _loadProviders();
  }

  Future<void> _loadProviders() async {
    final vault = await ref.read(aiProviderStoreProvider).readVault();
    var selected = _providerProfileId;
    if (selected == null || vault.profile(selected) == null) {
      selected = vault.favoriteProfileId;
      if (selected != null) {
        await ref
            .read(databaseProvider)
            .setConversationProvider(widget.conversationId, selected);
      }
    }
    if (mounted) {
      setState(() {
        _providerProfiles = vault.profiles;
        _providerProfileId = selected;
      });
    }
  }

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
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.title, overflow: TextOverflow.ellipsis),
            Text(
              _selectedProfile?.name ?? 'No AI service selected',
              style: Theme.of(context).textTheme.labelSmall,
            ),
          ],
        ),
        actions: [
          PopupMenuButton<String>(
            tooltip: 'Choose AI service',
            icon: const Icon(Icons.auto_awesome_outlined),
            enabled: _providerProfiles.isNotEmpty,
            onSelected: _selectProvider,
            itemBuilder: (context) => _providerProfiles
                .map(
                  (profile) => PopupMenuItem(
                    value: profile.id,
                    child: Row(
                      children: [
                        Icon(
                          profile.id == _providerProfileId
                              ? Icons.radio_button_checked
                              : Icons.radio_button_unchecked,
                        ),
                        const SizedBox(width: 10),
                        Expanded(child: Text(profile.name)),
                      ],
                    ),
                  ),
                )
                .toList(),
          ),
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
                  itemBuilder: (_, index) => _MessageBubble(
                    message: items[index],
                    providerName: _profileName(items[index].providerProfileId),
                  ),
                );
              },
              error: (error, _) =>
                  Center(child: Text('Could not load messages: $error')),
              loading: () => const Center(child: CircularProgressIndicator()),
            ),
          ),
          if (_attachments.isNotEmpty)
            SizedBox(
              height: 62,
              child: ListView.separated(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 6,
                ),
                scrollDirection: Axis.horizontal,
                itemCount: _attachments.length,
                separatorBuilder: (_, _) => const SizedBox(width: 8),
                itemBuilder: (context, index) {
                  final attachment = _attachments[index];
                  return InputChip(
                    avatar: attachment.isImage
                        ? ClipOval(
                            child: Image.file(
                              File(attachment.path),
                              width: 28,
                              height: 28,
                              fit: BoxFit.cover,
                            ),
                          )
                        : const Icon(Icons.description_outlined, size: 18),
                    label: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 180),
                      child: Text(
                        attachment.name,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    onDeleted: _sending
                        ? null
                        : () => setState(() => _attachments.removeAt(index)),
                  );
                },
              ),
            ),
          _Composer(
            controller: _composer,
            sending: _sending,
            onSend: _send,
            onAttach: _showAttachmentPicker,
          ),
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

  ProviderProfile? get _selectedProfile {
    for (final profile in _providerProfiles) {
      if (profile.id == _providerProfileId) return profile;
    }
    return null;
  }

  String? _profileName(String? id) {
    if (id == null) return null;
    for (final profile in _providerProfiles) {
      if (profile.id == id) return profile.name;
    }
    return 'Removed service';
  }

  Future<void> _selectProvider(String id) async {
    await ref
        .read(databaseProvider)
        .setConversationProvider(widget.conversationId, id);
    if (mounted) setState(() => _providerProfileId = id);
  }

  Future<void> _send() async {
    final text = _composer.text.trim();
    if ((text.isEmpty && _attachments.isEmpty) || _sending) return;
    final profileId = _providerProfileId;
    if (profileId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Configure an AI service in Settings before sending'),
        ),
      );
      return;
    }
    _composer.clear();
    setState(() => _sending = true);
    final pendingAttachments = List<ChatAttachment>.of(_attachments);
    _attachments.clear();
    final messageId = const Uuid().v4();
    final database = ref.read(databaseProvider);
    await database.addMessage(
      id: messageId,
      conversationId: widget.conversationId,
      role: 'user',
      content: text,
      status: 'sending',
      attachmentsJson: jsonEncode(
        pendingAttachments
            .map(
              (item) => {
                'path': item.path,
                'name': item.name,
                'mimeType': item.mimeType,
              },
            )
            .toList(),
      ),
      providerProfileId: profileId,
    );
    try {
      final messages = await database.getMessages(widget.conversationId);
      final history = messages
          .where((message) => message.id != messageId)
          .map((message) => ChatTurn(role: message.role, text: message.content))
          .toList();
      final reply = await ref
          .read(directAiClientProvider)
          .send(
            profileId: profileId,
            history: history,
            text: text,
            attachments: pendingAttachments,
          );
      await database.setMessageStatus(messageId, 'complete');
      await database.addMessage(
        id: '${messageId}_assistant',
        conversationId: widget.conversationId,
        role: 'assistant',
        content: reply.text,
        providerProfileId: profileId,
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

  Future<void> _showAttachmentPicker() async {
    final source = await showModalBottomSheet<String>(
      context: context,
      builder: (context) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Picture from gallery'),
              onTap: () => Navigator.pop(context, 'gallery'),
            ),
            ListTile(
              leading: const Icon(Icons.camera_alt_outlined),
              title: const Text('Take a picture'),
              onTap: () => Navigator.pop(context, 'camera'),
            ),
            ListTile(
              leading: const Icon(Icons.attach_file),
              title: const Text('Choose a file'),
              onTap: () => Navigator.pop(context, 'file'),
            ),
          ],
        ),
      ),
    );
    if (source == null) return;
    if (source == 'file') {
      final files = await openFiles();
      for (final file in files) {
        await _addAttachment(file.path, file.name);
      }
    } else {
      final image = await ImagePicker().pickImage(
        source: source == 'camera' ? ImageSource.camera : ImageSource.gallery,
        imageQuality: 90,
      );
      if (image != null) await _addAttachment(image.path, image.name);
    }
  }

  Future<void> _addAttachment(String path, String name) async {
    final size = File(path).lengthSync();
    if (size > 50 * 1024 * 1024) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Each attachment must be smaller than 50 MB'),
        ),
      );
      return;
    }
    final directory = Directory(
      p.join((await getApplicationDocumentsDirectory()).path, 'attachments'),
    );
    await directory.create(recursive: true);
    final storedPath = p.join(
      directory.path,
      '${const Uuid().v4()}_${p.basename(name)}',
    );
    await File(path).copy(storedPath);
    final attachment = ChatAttachment(
      path: storedPath,
      name: name,
      mimeType: lookupMimeType(path) ?? 'application/octet-stream',
    );
    if (mounted) setState(() => _attachments.add(attachment));
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message, this.providerName});

  final ChatMessage message;
  final String? providerName;

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
            ..._attachmentWidgets(context),
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
            ] else if (!isUser && providerName != null) ...[
              const SizedBox(height: 6),
              Text(
                providerName!,
                style: Theme.of(
                  context,
                ).textTheme.labelSmall?.copyWith(color: colors.outline),
              ),
            ],
          ],
        ),
      ),
    );
  }

  List<Widget> _attachmentWidgets(BuildContext context) {
    final raw = message.attachmentsJson;
    if (raw == null || raw.isEmpty) return const [];
    final items = (jsonDecode(raw) as List<dynamic>)
        .whereType<Map<String, dynamic>>();
    return [
      for (final item in items) ...[
        if ((item['mimeType']?.toString() ?? '').startsWith('image/') &&
            File(item['path']?.toString() ?? '').existsSync())
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: Image.file(
                File(item['path'].toString()),
                width: 260,
                height: 180,
                fit: BoxFit.cover,
              ),
            ),
          )
        else
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.description_outlined, size: 18),
                const SizedBox(width: 6),
                Flexible(child: Text(item['name']?.toString() ?? 'Attachment')),
              ],
            ),
          ),
      ],
    ];
  }
}

class _Composer extends StatelessWidget {
  const _Composer({
    required this.controller,
    required this.sending,
    required this.onSend,
    required this.onAttach,
  });

  final TextEditingController controller;
  final bool sending;
  final VoidCallback onSend;
  final VoidCallback onAttach;

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
              onPressed: sending ? null : onAttach,
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
