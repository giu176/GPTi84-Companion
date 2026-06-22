import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:uuid/uuid.dart';

import '../../../core/providers.dart';
import '../data/ai_provider_store.dart';
import '../data/chatgpt_subscription_auth.dart';

class AiServicesScreen extends ConsumerStatefulWidget {
  const AiServicesScreen({super.key});

  @override
  ConsumerState<AiServicesScreen> createState() => _AiServicesScreenState();
}

class _AiServicesScreenState extends ConsumerState<AiServicesScreen> {
  ProviderVault? _vault;
  final _testing = <String>{};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final vault = await ref.read(aiProviderStoreProvider).readVault();
    if (mounted) setState(() => _vault = vault);
  }

  @override
  Widget build(BuildContext context) {
    final vault = _vault;
    return Scaffold(
      appBar: AppBar(title: const Text('AI services')),
      body: vault == null
          ? const Center(child: CircularProgressIndicator())
          : vault.profiles.isEmpty
          ? const _EmptyServices()
          : ListView.separated(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 100),
              itemCount: vault.profiles.length,
              separatorBuilder: (_, _) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final profile = vault.profiles[index];
                return _ProviderCard(
                  profile: profile,
                  favorite: profile.id == vault.favoriteProfileId,
                  testing: _testing.contains(profile.id),
                  onFavorite: () => _favorite(profile.id),
                  onEdit: () => _edit(profile),
                  onReconnect:
                      profile.config.kind == AiProviderKind.chatGptSubscription
                      ? () => _connectSubscription(existing: profile)
                      : null,
                  onTest: () => _test(profile),
                  onDelete: () => _delete(profile),
                );
              },
            ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _add,
        icon: const Icon(Icons.add),
        label: const Text('Add service'),
      ),
    );
  }

  Future<void> _add() async {
    final kind = await showModalBottomSheet<AiProviderKind>(
      context: context,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const ListTile(
              title: Text('Choose an AI service'),
              subtitle: Text('You can add more than one of each type.'),
            ),
            for (final kind in AiProviderKind.values)
              ListTile(
                leading: Icon(_providerIcon(kind)),
                title: Text(kind.label),
                subtitle: kind == AiProviderKind.chatGptSubscription
                    ? const Text('Browser device-code authorization')
                    : null,
                onTap: () => Navigator.pop(context, kind),
              ),
          ],
        ),
      ),
    );
    if (kind == null) return;
    if (!mounted) return;
    if (kind == AiProviderKind.chatGptSubscription) {
      await _connectSubscription();
      return;
    }
    final profile = await showDialog<ProviderProfile>(
      context: context,
      builder: (context) => _ProfileDialog(
        initial: ProviderProfile(
          id: const Uuid().v4(),
          name: kind.label,
          config: AiProviderConfig.defaults(kind),
        ),
      ),
    );
    if (profile == null) return;
    final vault = await ref.read(aiProviderStoreProvider).upsert(profile);
    if (mounted) setState(() => _vault = vault);
  }

  Future<void> _edit(ProviderProfile profile) async {
    final updated = await showDialog<ProviderProfile>(
      context: context,
      builder: (context) => _ProfileDialog(initial: profile),
    );
    if (updated == null) return;
    final vault = await ref.read(aiProviderStoreProvider).upsert(updated);
    if (mounted) setState(() => _vault = vault);
  }

  Future<void> _connectSubscription({ProviderProfile? existing}) async {
    final config = await showDialog<AiProviderConfig>(
      context: context,
      barrierDismissible: false,
      builder: (context) => const _ChatGptDeviceDialog(),
    );
    if (config == null) return;
    final profile = ProviderProfile(
      id: existing?.id ?? const Uuid().v4(),
      name: existing?.name ?? 'ChatGPT Subscription',
      config: config.copyWith(model: existing?.config.model),
    );
    final vault = await ref.read(aiProviderStoreProvider).upsert(profile);
    if (mounted) setState(() => _vault = vault);
  }

  Future<void> _favorite(String id) async {
    final vault = await ref.read(aiProviderStoreProvider).setFavorite(id);
    if (mounted) setState(() => _vault = vault);
  }

  Future<void> _test(ProviderProfile profile) async {
    setState(() => _testing.add(profile.id));
    final result = await ref
        .read(directAiClientProvider)
        .testProfile(profile.id);
    final vault = await ref.read(aiProviderStoreProvider).readVault();
    if (!mounted) return;
    setState(() {
      _testing.remove(profile.id);
      _vault = vault;
    });
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(result.message)));
  }

  Future<void> _delete(ProviderProfile profile) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Delete ${profile.name}?'),
        content: const Text(
          'Its encrypted credentials will be removed. Chats using it will be reassigned to the favorite remaining service.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    final vault = await ref.read(aiProviderStoreProvider).delete(profile.id);
    await ref
        .read(databaseProvider)
        .reassignProvider(profile.id, vault.favoriteProfileId);
    if (mounted) setState(() => _vault = vault);
  }
}

class _ProviderCard extends StatelessWidget {
  const _ProviderCard({
    required this.profile,
    required this.favorite,
    required this.testing,
    required this.onFavorite,
    required this.onEdit,
    required this.onTest,
    required this.onDelete,
    this.onReconnect,
  });

  final ProviderProfile profile;
  final bool favorite;
  final bool testing;
  final VoidCallback onFavorite;
  final VoidCallback onEdit;
  final VoidCallback onTest;
  final VoidCallback onDelete;
  final VoidCallback? onReconnect;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 8, 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            CircleAvatar(child: Icon(_providerIcon(profile.config.kind))),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          profile.name,
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                      ),
                      if (favorite)
                        const Chip(
                          avatar: Icon(Icons.star, size: 16),
                          label: Text('Default'),
                        ),
                    ],
                  ),
                  Text(
                    '${profile.config.kind.label} • ${profile.config.model}',
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Icon(
                        switch (profile.testStatus) {
                          ProviderTestStatus.notTested => Icons.help_outline,
                          ProviderTestStatus.success => Icons.check_circle,
                          ProviderTestStatus.failure => Icons.error,
                        },
                        size: 17,
                        color: switch (profile.testStatus) {
                          ProviderTestStatus.notTested => colors.outline,
                          ProviderTestStatus.success => Colors.green,
                          ProviderTestStatus.failure => colors.error,
                        },
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          profile.lastTestedAt == null
                              ? 'Not tested'
                              : '${profile.testMessage} • ${DateFormat.MMMd().add_jm().format(profile.lastTestedAt!)}',
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            if (testing)
              const Padding(
                padding: EdgeInsets.all(12),
                child: SizedBox.square(
                  dimension: 22,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              )
            else
              PopupMenuButton<String>(
                onSelected: (action) {
                  switch (action) {
                    case 'favorite':
                      onFavorite();
                    case 'edit':
                      onEdit();
                    case 'reconnect':
                      onReconnect?.call();
                    case 'test':
                      onTest();
                    case 'delete':
                      onDelete();
                  }
                },
                itemBuilder: (context) => [
                  if (!favorite)
                    const PopupMenuItem(
                      value: 'favorite',
                      child: Text('Make default'),
                    ),
                  const PopupMenuItem(value: 'edit', child: Text('Edit')),
                  if (onReconnect != null)
                    const PopupMenuItem(
                      value: 'reconnect',
                      child: Text('Reconnect account'),
                    ),
                  const PopupMenuItem(value: 'test', child: Text('Test')),
                  const PopupMenuDivider(),
                  const PopupMenuItem(value: 'delete', child: Text('Delete')),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

class _ProfileDialog extends StatefulWidget {
  const _ProfileDialog({required this.initial});
  final ProviderProfile initial;

  @override
  State<_ProfileDialog> createState() => _ProfileDialogState();
}

class _ProfileDialogState extends State<_ProfileDialog> {
  late final _name = TextEditingController(text: widget.initial.name);
  late final _model = TextEditingController(text: widget.initial.config.model);
  late final _key = TextEditingController(text: widget.initial.config.apiKey);
  late final _url = TextEditingController(text: widget.initial.config.baseUrl);
  var _obscure = true;

  @override
  void dispose() {
    _name.dispose();
    _model.dispose();
    _key.dispose();
    _url.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final config = widget.initial.config;
    final subscription = config.kind == AiProviderKind.chatGptSubscription;
    final needsKey = config.kind != AiProviderKind.ollama && !subscription;
    return AlertDialog(
      title: Text('Edit ${config.kind.label}'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _name,
              decoration: const InputDecoration(labelText: 'Profile name'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _model,
              decoration: const InputDecoration(labelText: 'Model'),
            ),
            if (!subscription) ...[
              const SizedBox(height: 12),
              TextField(
                controller: _url,
                keyboardType: TextInputType.url,
                autocorrect: false,
                decoration: const InputDecoration(labelText: 'Base URL'),
              ),
            ],
            if (needsKey) ...[
              const SizedBox(height: 12),
              TextField(
                controller: _key,
                obscureText: _obscure,
                autocorrect: false,
                decoration: InputDecoration(
                  labelText: 'API key',
                  suffixIcon: IconButton(
                    onPressed: () => setState(() => _obscure = !_obscure),
                    icon: Icon(
                      _obscure
                          ? Icons.visibility_outlined
                          : Icons.visibility_off_outlined,
                    ),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(onPressed: _save, child: const Text('Save')),
      ],
    );
  }

  void _save() {
    final previous = widget.initial.config;
    final updated = AiProviderConfig(
      kind: previous.kind,
      model: _model.text.trim(),
      apiKey: _key.text.trim(),
      baseUrl: _url.text.trim(),
      refreshToken: previous.refreshToken,
      tokenExpiresAt: previous.tokenExpiresAt,
    );
    final uri = Uri.tryParse(updated.baseUrl);
    if (_name.text.trim().isEmpty ||
        !updated.isConfigured ||
        uri == null ||
        !uri.hasScheme) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Enter a name, model, URL, and API key')),
      );
      return;
    }
    Navigator.pop(
      context,
      widget.initial.copyWith(
        name: _name.text.trim(),
        config: updated,
        testStatus: ProviderTestStatus.notTested,
        testMessage: '',
      ),
    );
  }
}

class _ChatGptDeviceDialog extends StatefulWidget {
  const _ChatGptDeviceDialog();

  @override
  State<_ChatGptDeviceDialog> createState() => _ChatGptDeviceDialogState();
}

class _ChatGptDeviceDialogState extends State<_ChatGptDeviceDialog> {
  final _auth = ChatGptSubscriptionAuth();
  ChatGptDeviceSession? _session;
  String? _error;

  @override
  void initState() {
    super.initState();
    _start();
  }

  Future<void> _start() async {
    try {
      final session = await _auth.start();
      if (!mounted) return;
      setState(() {
        _session = session;
        _error = null;
      });
      await launchUrl(
        session.verificationUri,
        mode: LaunchMode.externalApplication,
      );
      while (mounted && DateTime.now().isBefore(session.expiresAt)) {
        await Future<void>.delayed(session.interval);
        final config = await _auth.poll(session);
        if (config != null && mounted) {
          Navigator.pop(context, config);
          return;
        }
      }
      if (mounted) setState(() => _error = 'The device code expired.');
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = _session;
    return AlertDialog(
      title: const Text('Connect ChatGPT Subscription'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text(
            'Experimental Codex device authorization. This private backend may change without notice.',
          ),
          const SizedBox(height: 18),
          if (_error != null)
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            )
          else if (session == null)
            const CircularProgressIndicator()
          else ...[
            const Text('Enter this code in the browser:'),
            const SizedBox(height: 10),
            SelectableText(
              session.userCode,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: () =>
                  Clipboard.setData(ClipboardData(text: session.userCode)),
              icon: const Icon(Icons.copy),
              label: const Text('Copy code'),
            ),
            const SizedBox(height: 12),
            const LinearProgressIndicator(),
            const SizedBox(height: 8),
            const Text('Waiting for browser authorization…'),
          ],
        ],
      ),
      actions: [
        if (_error != null)
          TextButton(onPressed: _start, child: const Text('Try again')),
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
      ],
    );
  }
}

class _EmptyServices extends StatelessWidget {
  const _EmptyServices();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(32),
        child: Text(
          'Add an AI service to start chatting. You can keep separate personal, work, and local profiles.',
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}

IconData _providerIcon(AiProviderKind kind) => switch (kind) {
  AiProviderKind.openAi => Icons.bolt,
  AiProviderKind.chatGptSubscription => Icons.login,
  AiProviderKind.anthropic => Icons.psychology_outlined,
  AiProviderKind.gemini => Icons.auto_awesome,
  AiProviderKind.openAiCompatible => Icons.hub_outlined,
  AiProviderKind.ollama => Icons.computer,
};
