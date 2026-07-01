import 'dart:async';
import 'dart:convert';

import 'package:uuid/uuid.dart';

import '../../conversations/data/app_database.dart';
import '../../providers/data/ai_provider_store.dart';
import '../../providers/data/direct_ai_client.dart';
import 'pinned_catalog.dart';

const phoneRelayConversationId = 'calculator-relay';
const calculatorNewChatId = 'NEW';

class CalculatorRelay {
  CalculatorRelay({
    required this.database,
    required this.providerStore,
    required this.directAiClient,
  });

  final AppDatabase database;
  final AiProviderStore providerStore;
  final DirectAiClient directAiClient;
  final Map<String, Future<List<int>>> _inFlight = {};
  final Map<String, int> _scrollOffsets = {};
  final _updates = StreamController<List<int>>.broadcast();

  Stream<List<int>> get updates => _updates.stream;

  void dispose() {
    _updates.close();
  }

  Future<List<int>> reply(List<int> payload, {required String idempotencyKey}) {
    final existing = _inFlight[idempotencyKey];
    if (existing != null) return existing;
    final future = _reply(payload, idempotencyKey: idempotencyKey);
    _inFlight[idempotencyKey] = future;
    future.whenComplete(() {
      if (identical(_inFlight[idempotencyKey], future)) {
        _inFlight.remove(idempotencyKey);
      }
    });
    return future;
  }

  Future<List<int>> _reply(
    List<int> payload, {
    required String idempotencyKey,
  }) async {
    final text = ascii.decode(payload, allowInvalid: true);
    final command = parseCalculatorCommandV2(_normalizePayload(text));
    if (command == null) {
      return pagesFrame('UNKNOWN COMMAND\n${_normalizePayload(text)}');
    }
    try {
      switch (command) {
        case ListChatsCommand():
          return pagesFrame(await _listChatsText());
        case CatalogCommand():
          return await _catalogFrame();
        case OpenChatCommand(:final chatId):
          return pagesFrame(await _openChatText(chatId));
        case NewChatCommand():
          return pagesFrame(await _newChatText());
        case PollChatCommand(:final chatId, :final knownRevision):
          return pagesFrame(await _pollChatText(chatId, knownRevision));
        case ScrollChatCommand(:final chatId, :final delta):
          return pagesFrame(await _scrollChatText(chatId, delta));
        case SendPromptCommand(
          :final chatId,
          :final clientMessageId,
          :final prompt,
        ):
          return await _sendPromptToChat(
            chatId: chatId,
            clientMessageId: clientMessageId,
            prompt: prompt,
          );
      }
    } catch (error) {
      return pagesFrame('Phone relay error: $error');
    }
  }

  Future<String> _catalogText() async {
    final projections = await database.getPinnedProjections();
    return PinnedCatalog.fromProjections(
      deviceId: 'phone-master',
      projections: projections,
    ).encode();
  }

  Future<List<int>> _catalogFrame() async {
    final catalog = await _catalogText();
    return ascii.encode('catalog:${catalog.length}\n$catalog');
  }

  Future<String> _listChatsText() async {
    final projections = await database.getPinnedProjections();
    final lines = <String>['0 NEW CHAT', 'SELECT CHAT'];
    for (var index = 0; index < projections.length; index += 1) {
      final slot = index + 1;
      final projection = projections[index];
      lines.add('$slot ${_calculatorListTitle(projection.title)}');
    }
    if (projections.isEmpty) {
      lines.add('NO PINNED CHATS');
      lines.add('SELECT 0');
    }
    return lines.join('\n');
  }

  Future<String> _openChatText(String chatId) async {
    if (chatId == calculatorNewChatId) return _newChatText();
    final resolvedSlot = await _resolveSlotAlias(chatId);
    if (resolvedSlot != null) return _openChatText(resolvedSlot);
    final conversation = await database.getConversation(chatId);
    if (conversation == null) {
      return 'UNKNOWN CHAT\nPHONE WILL RESYNC\n\n${await _listChatsText()}';
    }
    _scrollOffsets.putIfAbsent(chatId, () => 0);
    return _renderChat(chatId);
  }

  Future<String> _newChatText() async {
    final vault = await providerStore.readVault();
    final profileId = vault.favoriteProfileId;
    final id = _newChatId();
    await database.createConversation(
      id: id,
      title: 'Calculator chat',
      providerProfileId: profileId,
    );
    await database.setPinned(id, true);
    _scrollOffsets[id] = 0;
    _updates.add(await _catalogFrame());
    return 'NEW CHAT\nID $id\nENTER PROMPT';
  }

  Future<String> _pollChatText(String chatId, int knownRevision) async {
    final revision = await database.getConversationRevision(chatId);
    if (revision == 0) return 'UNKNOWN CHAT\nPHONE WILL RESYNC';
    if (revision <= knownRevision) {
      return 'NO UPDATE\nID $chatId\nREV $revision';
    }
    return _renderChat(chatId);
  }

  Future<String> _scrollChatText(String chatId, int delta) async {
    final current = _scrollOffsets[chatId] ?? 0;
    _scrollOffsets[chatId] = (current + delta).clamp(0, 999999).toInt();
    return _renderChat(chatId);
  }

  Future<List<int>> _sendPromptToChat({
    required String chatId,
    required String clientMessageId,
    required String prompt,
  }) async {
    final cleaned = prompt.trim();
    if (cleaned.isEmpty) return pagesFrame('EMPTY PROMPT');

    final vault = await providerStore.readVault();
    final fallbackProfileId = vault.favoriteProfileId;
    if (fallbackProfileId == null) {
      return pagesFrame(
        'Configure an AI service on the phone before using calculator chat.',
      );
    }

    final conversationId = await _resolveConversationId(
      chatId,
      prompt: cleaned,
      profileId: fallbackProfileId,
    );
    final conversation = await database.getConversation(conversationId);
    final profileId = conversation?.providerProfileId ?? fallbackProfileId;
    final messageId = _messageId(conversationId, clientMessageId);
    final assistantId = '${messageId}_assistant';
    final assistant = await database.getMessage(assistantId);
    if (assistant != null) return pagesFrame(await _renderChat(conversationId));

    if (await database.getMessage(messageId) == null) {
      final wasEmpty = (await database.getMessages(conversationId)).isEmpty;
      if (wasEmpty) {
        await database.renameConversation(
          conversationId,
          _initialTitle(cleaned),
        );
      }
      await database.addMessage(
        id: messageId,
        conversationId: conversationId,
        role: 'user',
        content: cleaned,
        origin: 'calculator',
        status: 'sending',
        providerProfileId: profileId,
      );
      _updates.add(await _catalogFrame());
    }

    unawaited(
      _completeAssistantReply(
        conversationId: conversationId,
        messageId: messageId,
        assistantId: assistantId,
        profileId: profileId,
        prompt: cleaned,
      ),
    );
    return pagesFrame(await _renderChat(conversationId));
  }

  Future<void> _completeAssistantReply({
    required String conversationId,
    required String messageId,
    required String assistantId,
    required String profileId,
    required String prompt,
  }) async {
    try {
      if (await database.getMessage(assistantId) != null) return;
      final messages = await database.getMessages(conversationId);
      final history = messages
          .where((message) => message.id != messageId)
          .map((message) => ChatTurn(role: message.role, text: message.content))
          .toList();
      final reply = await directAiClient.send(
        profileId: profileId,
        history: history,
        text: prompt,
        attachments: const [],
      );
      await database.setMessageStatus(messageId, 'complete');
      await database.addMessage(
        id: assistantId,
        conversationId: conversationId,
        role: 'assistant',
        content: reply.text,
        origin: 'calculator',
        providerProfileId: profileId,
      );
      _updates.add(await _catalogFrame());
      _updates.add(pagesFrame(await _renderChat(conversationId)));
    } catch (error) {
      await database.setMessageStatus(messageId, 'failed');
      _updates.add(pagesFrame('Phone relay error: $error'));
    }
  }

  Future<String> _resolveConversationId(
    String chatId, {
    required String prompt,
    required String profileId,
  }) async {
    if (chatId != calculatorNewChatId) {
      final resolvedSlot = await _resolveSlotAlias(chatId);
      final resolvedId = resolvedSlot ?? chatId;
      final conversation = await database.getConversation(resolvedId);
      if (conversation != null) return resolvedId;
    }
    final id = _newChatId();
    await database.createConversation(
      id: id,
      title: _initialTitle(prompt),
      providerProfileId: profileId,
    );
    await database.setPinned(id, true);
    _scrollOffsets[id] = 0;
    return id;
  }

  Future<String> _renderChat(String chatId) async {
    final conversation = await database.getConversation(chatId);
    if (conversation == null) return 'UNKNOWN CHAT\n$chatId';
    final revision = await database.getConversationRevision(chatId);
    final messages = await database.getMessages(chatId);
    final lines = <String>[
      conversation.title,
      'ID ${_shortId(chatId)} REV $revision',
      '',
    ];
    for (final message in messages) {
      final prefix = switch (message.role) {
        'assistant' => 'AI',
        'user' => 'YOU',
        _ => message.role.toUpperCase(),
      };
      final status = message.status == 'complete' ? '' : ' (${message.status})';
      lines.add('$prefix$status: ${message.content}');
    }
    if (messages.isEmpty) lines.add('NO MESSAGES');
    return lines.join('\n');
  }

  String _newChatId() =>
      'C${const Uuid().v4().replaceAll('-', '').toUpperCase()}';

  Future<String?> _resolveSlotAlias(String chatId) async {
    if (!chatId.startsWith('#SLOT:')) return null;
    final slot = int.tryParse(chatId.substring(6));
    if (slot == null) return null;
    if (slot == 0) return calculatorNewChatId;
    return (await database.getPinnedProjectionBySlot(slot))?.conversationId;
  }

  String _shortId(String chatId) =>
      chatId.length <= 10 ? chatId : '${chatId.substring(0, 10)}...';

  String _calculatorListTitle(String title) {
    final cleaned = calculatorSafeText(title).trim().toUpperCase();
    if (cleaned.isEmpty) return 'UNTITLED';
    return cleaned.length <= 14 ? cleaned : cleaned.substring(0, 14);
  }

  String _initialTitle(String message) {
    final words = message.trim().split(RegExp(r'\s+')).take(6).join(' ');
    return words.length <= 120 ? words : '${words.substring(0, 117)}...';
  }

  String _messageId(String chatId, String key) {
    final safeChat = chatId.replaceAll(RegExp('[^A-Za-z0-9_.-]'), '_');
    final safeKey = key.replaceAll(RegExp('[^A-Za-z0-9_.-]'), '_');
    return 'calc-$safeChat-$safeKey';
  }
}

sealed class CalculatorCommand {
  const CalculatorCommand();
}

class ListChatsCommand extends CalculatorCommand {
  const ListChatsCommand();
}

class CatalogCommand extends CalculatorCommand {
  const CatalogCommand();
}

class OpenChatCommand extends CalculatorCommand {
  const OpenChatCommand(this.chatId);

  final String chatId;
}

class NewChatCommand extends CalculatorCommand {
  const NewChatCommand();
}

class PollChatCommand extends CalculatorCommand {
  const PollChatCommand({required this.chatId, required this.knownRevision});

  final String chatId;
  final int knownRevision;
}

class ScrollChatCommand extends CalculatorCommand {
  const ScrollChatCommand({required this.chatId, required this.delta});

  final String chatId;
  final int delta;
}

class SendPromptCommand extends CalculatorCommand {
  const SendPromptCommand({
    required this.chatId,
    required this.clientMessageId,
    required this.prompt,
  });

  final String chatId;
  final String clientMessageId;
  final String prompt;
}

CalculatorCommand? parseCalculatorCommandV2(String text) {
  final normalized = text.replaceAll('\r\n', '\n').trimRight();
  final firstNewline = normalized.indexOf('\n');
  final firstLine = firstNewline == -1
      ? normalized.trim()
      : normalized.substring(0, firstNewline).trim();
  final body = firstNewline == -1 ? '' : normalized.substring(firstNewline + 1);
  final parts = firstLine
      .split(RegExp(r'\s+'))
      .where((p) => p.isNotEmpty)
      .toList();
  if (parts.isEmpty) return null;
  final verb = parts.first.toUpperCase();
  if (verb == 'LIST') return const ListChatsCommand();
  if (verb == 'CATALOG') return const CatalogCommand();
  if (verb == 'NEW') return const NewChatCommand();
  if (normalized.startsWith('OPEN:')) {
    final slot = int.tryParse(normalized.substring('OPEN:'.length).trim());
    if (slot != null) return OpenChatCommand('#SLOT:$slot');
  }
  if (normalized.startsWith('SEND:')) {
    final rest = normalized.substring('SEND:'.length);
    final separator = rest.indexOf(':');
    if (separator > 0) {
      final slot = int.tryParse(rest.substring(0, separator).trim());
      if (slot != null) {
        return SendPromptCommand(
          chatId: '#SLOT:$slot',
          clientMessageId: 'LEGACY${DateTime.now().microsecondsSinceEpoch}',
          prompt: rest.substring(separator + 1),
        );
      }
    }
  }
  if (verb == 'OPEN' && parts.length >= 2) return OpenChatCommand(parts[1]);
  if (verb == 'POLL' && parts.length >= 3) {
    final revision = int.tryParse(parts[2]);
    if (revision != null) {
      return PollChatCommand(chatId: parts[1], knownRevision: revision);
    }
  }
  if (verb == 'SCROLL' && parts.length >= 3) {
    final delta = int.tryParse(parts[2]);
    if (delta != null) return ScrollChatCommand(chatId: parts[1], delta: delta);
  }
  if (verb == 'SEND' && parts.length >= 3) {
    final inline = parts.length > 3 ? parts.skip(3).join(' ') : '';
    final prompt = body.trim().isNotEmpty ? body : inline;
    return SendPromptCommand(
      chatId: parts[1],
      clientMessageId: parts[2],
      prompt: prompt,
    );
  }
  return null;
}

String _normalizePayload(String text) {
  final (legacyPrompt, legacyMath) = parseCalculatorPair(text);
  if (legacyPrompt.isNotEmpty || legacyMath.isNotEmpty) {
    return legacyPrompt.isEmpty ? legacyMath : legacyPrompt;
  }
  return text;
}

(String prompt, String math) parseCalculatorPair(String text) {
  var prompt = '';
  var math = '';
  for (final line in text.split('\n')) {
    if (line.startsWith('prompt:')) {
      prompt = line.substring('prompt:'.length);
    } else if (line.startsWith('math:')) {
      math = line.substring('math:'.length);
    }
  }
  return (prompt, math);
}

List<int> pagesFrame(String text) {
  final pages = layoutCalculatorPages(text);
  return ascii.encode('pages:${pages.length}\n${pages.join('\x00')}');
}

List<String> layoutCalculatorPages(String text) {
  final rows = <String>[];
  final normalized = calculatorSafeText(text);
  for (final logical in normalized.split('\n')) {
    rows.addAll(_wrapLine(logical));
  }
  if (rows.isEmpty) rows.add('');
  final pages = <String>[];
  var index = 0;
  while (index < rows.length && pages.length < 8) {
    final pageRows = rows.skip(index).take(7).toList();
    index += 7;
    while (pageRows.length < 7) {
      pageRows.add('');
    }
    pages.add(pageRows.map((row) => row.padRight(16).substring(0, 16)).join());
  }
  return pages.isEmpty ? [' '.padRight(112)] : pages;
}

String calculatorSafeText(String text) {
  return text.runes
      .map(
        (codePoint) =>
            codePoint == 0x0a || codePoint >= 0x20 && codePoint < 0x7f
            ? codePoint
            : 0x20,
      )
      .map(String.fromCharCode)
      .join();
}

List<String> _wrapLine(String line) {
  final trimmed = line.trimRight();
  if (trimmed.isEmpty) return [''];
  final rows = <String>[];
  var current = '';
  for (final word in trimmed.split(' ')) {
    if (word.length > 16) {
      if (current.isNotEmpty) {
        rows.add(current);
        current = '';
      }
      for (var index = 0; index < word.length; index += 16) {
        final end = (index + 16).clamp(0, word.length);
        final chunk = word.substring(index, end);
        if (chunk.length == 16) {
          rows.add(chunk);
        } else {
          current = chunk;
        }
      }
    } else if (current.isEmpty) {
      current = word;
    } else if (current.length + 1 + word.length <= 16) {
      current = '$current $word';
    } else {
      rows.add(current);
      current = word;
    }
  }
  if (current.isNotEmpty) rows.add(current);
  return rows;
}
