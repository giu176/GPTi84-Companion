import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/providers.dart';

class DeviceScreen extends ConsumerWidget {
  const DeviceScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final relay = ref.read(bleRelayServiceProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Calculator')),
      body: AnimatedBuilder(
        animation: relay,
        builder: (context, _) {
          final snapshot = relay.snapshot;
          return ListView(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Icon(
                        snapshot.connectedDeviceId == null
                            ? Icons.bluetooth_searching
                            : Icons.bluetooth_connected,
                        size: 52,
                        color: Theme.of(context).colorScheme.primary,
                      ),
                      const SizedBox(height: 12),
                      Text(
                        snapshot.connectionState,
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 12),
                      _StatusRow(
                        label: 'Device',
                        value: snapshot.connectedDeviceId ?? 'None',
                      ),
                      _StatusRow(
                        label: 'Firmware',
                        value: snapshot.firmwareStatus,
                      ),
                      _StatusRow(
                        label: 'Session',
                        value: snapshot.activeSession?.toString() ?? 'Idle',
                      ),
                      if (snapshot.lastError != null)
                        Text(
                          snapshot.lastError!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      const SizedBox(height: 14),
                      if (snapshot.connectedDeviceId == null)
                        FilledButton.icon(
                          onPressed: snapshot.scanning ? null : relay.scan,
                          icon: snapshot.scanning
                              ? const SizedBox.square(
                                  dimension: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Icon(Icons.bluetooth_searching),
                          label: Text(
                            snapshot.scanning ? 'Scanning…' : 'Find Pico 2 W',
                          ),
                        )
                      else
                        OutlinedButton.icon(
                          onPressed: relay.disconnect,
                          icon: const Icon(Icons.link_off),
                          label: const Text('Disconnect'),
                        ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 14),
              if (snapshot.devices.isNotEmpty)
                Card(
                  child: Column(
                    children: [
                      for (final device in snapshot.devices)
                        ListTile(
                          leading: const Icon(Icons.memory),
                          title: Text(device.name),
                          subtitle: Text('${device.id} · ${device.rssi} dBm'),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: snapshot.connectedDeviceId == null
                              ? () => relay.connect(device.id)
                              : null,
                        ),
                    ],
                  ),
                )
              else
                const Card(
                  child: Padding(
                    padding: EdgeInsets.all(18),
                    child: Text(
                      'Power the Pico with BLE firmware installed, then scan. '
                      'The app is the BLE central and the Pico is the peripheral.',
                      textAlign: TextAlign.center,
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
            width: 80,
            child: Text(label, style: Theme.of(context).textTheme.labelLarge),
          ),
          Expanded(child: SelectableText(value)),
        ],
      ),
    );
  }
}
