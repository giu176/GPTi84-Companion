import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/conversations/data/app_database.dart';
import '../features/providers/data/ai_provider_store.dart';
import '../features/providers/data/direct_ai_client.dart';
import '../features/relay/data/ble_relay_service.dart';
import '../features/relay/data/calculator_relay.dart';
import '../features/relay/data/phone_relay_server.dart';

final databaseProvider = Provider<AppDatabase>((ref) {
  final database = AppDatabase();
  ref.onDispose(database.close);
  return database;
});

final aiProviderStoreProvider = Provider<AiProviderStore>(
  (ref) => const AiProviderStore(),
);

final directAiClientProvider = Provider<DirectAiClient>(
  (ref) => DirectAiClient(ref.read(aiProviderStoreProvider)),
);

final calculatorRelayProvider = Provider<CalculatorRelay>((ref) {
  final relay = CalculatorRelay(
    database: ref.read(databaseProvider),
    providerStore: ref.read(aiProviderStoreProvider),
    directAiClient: ref.read(directAiClientProvider),
  );
  ref.onDispose(relay.dispose);
  return relay;
});

final bleRelayServiceProvider = Provider<BleRelayService>((ref) {
  final service = BleRelayService(relay: ref.read(calculatorRelayProvider));
  ref.onDispose(service.dispose);
  return service;
});

final phoneRelayServerProvider = Provider<PhoneRelayServer>((ref) {
  final server = PhoneRelayServer(relay: ref.read(calculatorRelayProvider));
  ref.onDispose(() {
    server.stop();
  });
  return server;
});
