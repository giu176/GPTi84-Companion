import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';
import '../data/relay_settings_store.dart';

class AdvancedSettingsScreen extends ConsumerStatefulWidget {
  const AdvancedSettingsScreen({super.key});

  @override
  ConsumerState<AdvancedSettingsScreen> createState() =>
      _AdvancedSettingsScreenState();
}

class _AdvancedSettingsScreenState
    extends ConsumerState<AdvancedSettingsScreen> {
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
      appBar: AppBar(title: const Text('Advanced')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
              children: [
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(18),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Personal relay',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        const SizedBox(height: 4),
                        const Text(
                          'Used for standalone calculator chat and future synchronization.',
                        ),
                        const SizedBox(height: 18),
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
                              onPressed: () => setState(
                                () => _obscureToken = !_obscureToken,
                              ),
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
                          Text(_health!),
                        ],
                      ],
                    ),
                  ),
                ),
              ],
            ),
    );
  }

  Future<bool> _save() async {
    final uri = Uri.tryParse(_url.text.trim());
    if (uri == null ||
        !uri.hasScheme ||
        (!uri.isScheme('https') && !uri.isScheme('http'))) {
      _show('Enter a valid HTTP or HTTPS relay URL');
      return false;
    }
    await ref
        .read(relaySettingsStoreProvider)
        .write(RelaySettings(baseUrl: _url.text, adminToken: _token.text));
    _show('Relay settings saved');
    return true;
  }

  Future<void> _test() async {
    if (!await _save()) return;
    try {
      final status = await ref.read(relayClientProvider).health();
      if (mounted) setState(() => _health = 'Relay answered: $status');
    } catch (error) {
      if (mounted) setState(() => _health = 'Relay unavailable: $error');
    }
  }

  void _show(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }
}
