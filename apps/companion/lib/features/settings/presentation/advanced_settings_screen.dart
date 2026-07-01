import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';

class AdvancedSettingsScreen extends ConsumerWidget {
  const AdvancedSettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final relay = ref.read(phoneRelayServerProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Advanced')),
      body: AnimatedBuilder(
        animation: relay,
        builder: (context, _) {
          final snapshot = relay.snapshot;
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Developer TCP relay',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 4),
                      const Text(
                        'Temporary Android/LAN diagnostics only. Production calculator relay uses BLE from the Calculator screen.',
                      ),
                      const SizedBox(height: 18),
                      _StatusRow(
                        label: 'State',
                        value: snapshot.running ? 'Listening' : 'Stopped',
                      ),
                      _StatusRow(label: 'Endpoint', value: snapshot.endpoint),
                      _StatusRow(
                        label: 'Requests',
                        value: snapshot.requestCount.toString(),
                      ),
                      _StatusRow(
                        label: 'Last event',
                        value: snapshot.lastEvent,
                      ),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(
                            child: FilledButton.icon(
                              onPressed: snapshot.running
                                  ? null
                                  : () => relay.start(),
                              icon: const Icon(Icons.play_arrow),
                              label: const Text('Start'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: OutlinedButton.icon(
                              onPressed: snapshot.running
                                  ? () => relay.stop()
                                  : null,
                              icon: const Icon(Icons.stop),
                              label: const Text('Stop'),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _StatusRow extends StatelessWidget {
  const _StatusRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 92,
            child: Text(label, style: Theme.of(context).textTheme.labelLarge),
          ),
          Expanded(child: SelectableText(value)),
        ],
      ),
    );
  }
}
