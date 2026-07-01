import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';
import '../../providers/data/ai_provider_store.dart';
import '../../providers/presentation/ai_services_screen.dart';
import 'about_screen.dart';
import 'advanced_settings_screen.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  ProviderVault? _vault;

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
    final favorite = _vault?.favorite;
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: _vault == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
              children: [
                Card(
                  child: Column(
                    children: [
                      ListTile(
                        leading: const CircleAvatar(
                          child: Icon(Icons.auto_awesome_outlined),
                        ),
                        title: const Text('Default AI service'),
                        subtitle: Text(
                          favorite == null
                              ? 'No service configured'
                              : '${favorite.name} • ${favorite.config.model}',
                        ),
                      ),
                      const Divider(height: 1),
                      ListTile(
                        leading: const Icon(Icons.manage_accounts_outlined),
                        title: const Text('Manage AI services'),
                        subtitle: Text(
                          '${_vault!.profiles.length} configured • add, test, edit, or remove',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () => _open(const AiServicesScreen()),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.tune_outlined),
                    title: const Text('Advanced'),
                    subtitle: const Text('Phone relay and Pico diagnostics'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => _open(const AdvancedSettingsScreen()),
                  ),
                ),
                const SizedBox(height: 32),
                ListTile(
                  leading: const Icon(Icons.info_outline),
                  title: const Text('About'),
                  subtitle: const Text('Files, security, billing, and privacy'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => _open(const AboutScreen()),
                ),
              ],
            ),
    );
  }

  Future<void> _open(Widget screen) async {
    await Navigator.of(
      context,
    ).push(MaterialPageRoute<void>(builder: (_) => screen));
    await _load();
  }
}
