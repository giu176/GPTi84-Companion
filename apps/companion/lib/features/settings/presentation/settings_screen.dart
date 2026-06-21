import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';
import '../data/relay_settings_store.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _url = TextEditingController();
  final _token = TextEditingController();
  var _loading = true;
  var _obscureToken = true;
  String? _health;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final settings = await ref.read(relaySettingsStoreProvider).read();
    if (!mounted) return;
    _url.text = settings.baseUrl;
    _token.text = settings.adminToken;
    setState(() => _loading = false);
  }

  @override
  void dispose() {
    _url.dispose();
    _token.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
              children: [
                _SectionCard(
                  icon: Icons.cloud_outlined,
                  title: 'Personal relay',
                  subtitle:
                      'The relay owns provider calls and standalone calculator chat.',
                  child: Column(
                    children: [
                      TextField(
                        controller: _url,
                        keyboardType: TextInputType.url,
                        autocorrect: false,
                        decoration: const InputDecoration(
                          labelText: 'Relay URL',
                          hintText: 'https://relay.example.com',
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _token,
                        obscureText: _obscureToken,
                        autocorrect: false,
                        decoration: InputDecoration(
                          labelText: 'Administrator token',
                          suffixIcon: IconButton(
                            onPressed: () =>
                                setState(() => _obscureToken = !_obscureToken),
                            icon: Icon(
                              _obscureToken
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(
                            child: FilledButton.icon(
                              onPressed: _save,
                              icon: const Icon(Icons.lock_outline),
                              label: const Text('Save securely'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          IconButton.filledTonal(
                            tooltip: 'Test relay',
                            onPressed: _test,
                            icon: const Icon(Icons.monitor_heart_outlined),
                          ),
                        ],
                      ),
                      if (_health != null) ...[
                        const SizedBox(height: 12),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: Text(
                            _health!,
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 14),
                const _SectionCard(
                  icon: Icons.auto_awesome_outlined,
                  title: 'AI providers',
                  subtitle:
                      'OpenAI, Anthropic, Gemini, OpenAI-compatible, and Ollama.',
                  child: ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text('Provider management'),
                    subtitle: Text(
                      'Arrives with the production relay API milestone.',
                    ),
                    trailing: Icon(Icons.schedule),
                  ),
                ),
                const SizedBox(height: 14),
                const _SectionCard(
                  icon: Icons.privacy_tip_outlined,
                  title: 'Local-first privacy',
                  subtitle:
                      'Complete chats and images stay in app-private storage.',
                  child: Text(
                    'Only pinned text projections and pending calculator events are retained by the relay.',
                  ),
                ),
              ],
            ),
    );
  }

  Future<void> _save() async {
    final uri = Uri.tryParse(_url.text.trim());
    if (uri == null ||
        !uri.hasScheme ||
        (!uri.isScheme('https') && !uri.isScheme('http'))) {
      _show('Enter a valid HTTP or HTTPS relay URL');
      return;
    }
    await ref
        .read(relaySettingsStoreProvider)
        .write(RelaySettings(baseUrl: _url.text, adminToken: _token.text));
    _show('Relay settings saved in secure storage');
  }

  Future<void> _test() async {
    await _save();
    try {
      final status = await ref.read(relayClientProvider).health();
      if (mounted) setState(() => _health = 'Relay answered: $status');
    } catch (error) {
      if (mounted) setState(() => _health = 'Relay unavailable: $error');
    }
  }

  void _show(String message) {
    if (mounted) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
    }
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.child,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(child: Icon(icon)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 2),
                      Text(
                        subtitle,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            child,
          ],
        ),
      ),
    );
  }
}
