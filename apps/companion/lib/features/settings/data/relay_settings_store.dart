import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class RelaySettings {
  const RelaySettings({required this.baseUrl, required this.adminToken});

  final String baseUrl;
  final String adminToken;

  bool get isConfigured => baseUrl.isNotEmpty && adminToken.isNotEmpty;
}

class RelaySettingsStore {
  const RelaySettingsStore();

  static const _storage = FlutterSecureStorage();
  static const _baseUrlKey = 'relay_base_url';
  static const _adminTokenKey = 'relay_admin_token';

  Future<RelaySettings> read() async {
    return RelaySettings(
      baseUrl: await _storage.read(key: _baseUrlKey) ?? '',
      adminToken: await _storage.read(key: _adminTokenKey) ?? '',
    );
  }

  Future<void> write(RelaySettings settings) async {
    await _storage.write(key: _baseUrlKey, value: settings.baseUrl.trim());
    await _storage.write(
      key: _adminTokenKey,
      value: settings.adminToken.trim(),
    );
  }
}
