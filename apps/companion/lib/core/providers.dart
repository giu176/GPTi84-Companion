import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/conversations/data/app_database.dart';
import '../features/relay/data/relay_client.dart';
import '../features/settings/data/relay_settings_store.dart';

final databaseProvider = Provider<AppDatabase>((ref) {
  final database = AppDatabase();
  ref.onDispose(database.close);
  return database;
});

final relaySettingsStoreProvider = Provider<RelaySettingsStore>(
  (ref) => const RelaySettingsStore(),
);

final relayClientProvider = Provider<RelayClient>(
  (ref) => RelayClient(ref.read(relaySettingsStoreProvider)),
);
