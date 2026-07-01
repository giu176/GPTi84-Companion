import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_blue_plus/flutter_blue_plus.dart';

import 'ble_protocol.dart';
import 'calculator_relay.dart';

class BleRelayDevice {
  const BleRelayDevice({
    required this.id,
    required this.name,
    required this.rssi,
  });

  final String id;
  final String name;
  final int rssi;
}

class BleRelaySnapshot {
  const BleRelaySnapshot({
    required this.scanning,
    required this.connectionState,
    required this.devices,
    required this.connectedDeviceId,
    required this.firmwareStatus,
    required this.activeSession,
    required this.lastError,
  });

  final bool scanning;
  final String connectionState;
  final List<BleRelayDevice> devices;
  final String? connectedDeviceId;
  final String firmwareStatus;
  final int? activeSession;
  final String? lastError;
}

class BleRelayService extends ChangeNotifier {
  BleRelayService({required this.relay});

  final CalculatorRelay relay;

  StreamSubscription<List<ScanResult>>? _scanSubscription;
  StreamSubscription<List<int>>? _requestSubscription;
  StreamSubscription<List<int>>? _statusSubscription;
  StreamSubscription<List<int>>? _relayUpdateSubscription;
  StreamSubscription<BluetoothConnectionState>? _connectionSubscription;
  final Map<String, ScanResult> _results = {};
  final Map<String, Completer<void>> _acks = {};
  final BleMessageAssembler _requestAssembler = BleMessageAssembler();

  BluetoothDevice? _device;
  BluetoothCharacteristic? _control;
  BluetoothCharacteristic? _picoToPhone;
  BluetoothCharacteristic? _phoneToPico;
  BluetoothCharacteristic? _status;
  bool _scanning = false;
  String _connectionState = 'Disconnected';
  String _firmwareStatus = 'Not available';
  int? _activeSession;
  int _nextPhoneSession = 0x8000;
  Future<void> _sendChain = Future<void>.value();
  String? _lastError;
  bool _disposed = false;

  BleRelaySnapshot get snapshot => BleRelaySnapshot(
    scanning: _scanning,
    connectionState: _connectionState,
    devices:
        _results.values
            .map(
              (result) => BleRelayDevice(
                id: result.device.remoteId.str,
                name: result.advertisementData.advName.isEmpty
                    ? 'GPTi84 Pico'
                    : result.advertisementData.advName,
                rssi: result.rssi,
              ),
            )
            .toList()
          ..sort((a, b) => b.rssi.compareTo(a.rssi)),
    connectedDeviceId: _device?.remoteId.str,
    firmwareStatus: _firmwareStatus,
    activeSession: _activeSession,
    lastError: _lastError,
  );

  Future<void> scan() async {
    _lastError = null;
    _results.clear();
    _scanning = true;
    notifyListeners();
    await _scanSubscription?.cancel();
    _scanSubscription = FlutterBluePlus.scanResults.listen((results) {
      for (final result in results) {
        final advertisedName = result.advertisementData.advName;
        final hasService = result.advertisementData.serviceUuids.contains(
          Guid(gpti84ServiceUuid),
        );
        if (hasService || advertisedName.startsWith('GPTi84')) {
          _results[result.device.remoteId.str] = result;
        }
      }
      notifyListeners();
    }, onError: (Object error) => _fail('BLE scan failed: $error'));
    try {
      await FlutterBluePlus.startScan(
        timeout: const Duration(seconds: 8),
        androidUsesFineLocation: false,
      );
      await FlutterBluePlus.isScanning.where((value) => !value).first;
    } catch (error) {
      _fail('BLE scan failed: $error');
    } finally {
      _scanning = false;
      notifyListeners();
    }
  }

  Future<void> connect(String deviceId) async {
    final result = _results[deviceId];
    if (result == null) return;
    _lastError = null;
    _connectionState = 'Connecting';
    notifyListeners();
    try {
      await disconnect();
      final device = result.device;
      _device = device;
      _connectionSubscription = device.connectionState.listen((state) {
        final sameDevice = _device?.remoteId == device.remoteId;
        final established = _connectionState == 'Connected';
        if (sameDevice &&
            established &&
            state == BluetoothConnectionState.disconnected) {
          unawaited(disconnect());
        }
      });
      await device.connect(
        license: License.nonprofit,
        timeout: const Duration(seconds: 20),
        mtu: 128,
      );
      final services = await device.discoverServices();
      final service = services.firstWhere(
        (value) => value.uuid == Guid(gpti84ServiceUuid),
      );
      for (final characteristic in service.characteristics) {
        if (characteristic.uuid == Guid(gpti84ControlUuid)) {
          _control = characteristic;
        } else if (characteristic.uuid == Guid(gpti84PicoToPhoneUuid)) {
          _picoToPhone = characteristic;
        } else if (characteristic.uuid == Guid(gpti84PhoneToPicoUuid)) {
          _phoneToPico = characteristic;
        } else if (characteristic.uuid == Guid(gpti84StatusUuid)) {
          _status = characteristic;
        }
      }
      if (_control == null ||
          _picoToPhone == null ||
          _phoneToPico == null ||
          _status == null) {
        throw const FormatException('GPTi84 GATT service is incomplete');
      }
      _requestSubscription = _picoToPhone!.onValueReceived.listen(
        _onPicoEnvelope,
        onError: (Object error) => _fail('BLE notification failed: $error'),
      );
      _statusSubscription = _status!.onValueReceived.listen(_onStatusValue);
      await _picoToPhone!.setNotifyValue(true);
      await _status!.setNotifyValue(true);
      final initialStatus = await _status!.read();
      _onStatusValue(initialStatus);
      await _writeControl(BleMessageType.hello);
      _relayUpdateSubscription = relay.updates.listen(
        (frame) => unawaited(_sendAsyncUpdate(frame)),
        onError: (Object error) => _fail('Relay update failed: $error'),
      );
      if (_device?.remoteId != device.remoteId) {
        throw StateError('BLE connection was superseded');
      }
      _connectionState = 'Connected';
      notifyListeners();
    } catch (error) {
      _fail('BLE connection failed: $error');
      await disconnect();
    }
  }

  Future<void> disconnect({bool notify = true}) async {
    await _requestSubscription?.cancel();
    await _statusSubscription?.cancel();
    await _relayUpdateSubscription?.cancel();
    await _connectionSubscription?.cancel();
    _requestSubscription = null;
    _statusSubscription = null;
    _relayUpdateSubscription = null;
    _connectionSubscription = null;
    final device = _device;
    _device = null;
    _control = null;
    _picoToPhone = null;
    _phoneToPico = null;
    _status = null;
    _connectionState = 'Disconnected';
    _firmwareStatus = 'Not available';
    _activeSession = null;
    _sendChain = Future<void>.value();
    _requestAssembler.reset();
    for (final completer in _acks.values) {
      if (!completer.isCompleted) {
        completer.completeError(StateError('BLE disconnected'));
      }
    }
    _acks.clear();
    if (device != null && device.isConnected) await device.disconnect();
    if (notify && !_disposed) notifyListeners();
  }

  Future<void> _onPicoEnvelope(List<int> value) async {
    try {
      final envelope = BleEnvelope.decode(value);
      if (envelope.type == BleMessageType.ack) {
        _acks.remove(_ackKey(envelope))?.complete();
        return;
      }
      if (envelope.type == BleMessageType.ping) {
        await _writeControl(
          BleMessageType.pong,
          sessionId: envelope.sessionId,
          sequence: envelope.sequence,
        );
        return;
      }
      if (envelope.type == BleMessageType.requestChunk) {
        _activeSession = envelope.sessionId;
        _requestAssembler.add(envelope);
        notifyListeners();
        await _writeAck(envelope);
        return;
      }
      if (envelope.type == BleMessageType.requestEnd) {
        final request = _requestAssembler.finish(envelope.sessionId);
        if (request == null) {
          throw const FormatException('Incomplete BLE calculator request');
        }
        await _writeAck(envelope);
        final response = await relay.reply(
          request,
          idempotencyKey:
              'ble-${_device?.remoteId.str ?? "unknown"}-${envelope.sessionId}',
        );
        await _queueResponse(envelope.sessionId, response);
        _activeSession = null;
        notifyListeners();
      }
    } catch (error) {
      _fail('BLE session failed: $error');
    }
  }

  Future<void> _sendResponse(int sessionId, List<int> response) async {
    final chunks = chunkBleMessage(
      type: BleMessageType.responseChunk,
      sessionId: sessionId,
      payload: response,
    );
    for (final chunk in chunks) {
      await _writeWithAck(chunk);
    }
    await _writeWithAck(
      BleEnvelope(
        type: BleMessageType.responseEnd,
        sessionId: sessionId,
        sequence: chunks.length,
        totalLength: response.length,
        chunkOffset: response.length,
        chunk: Uint8List(0),
      ),
    );
  }

  Future<void> _sendAsyncUpdate(List<int> response) async {
    if (_phoneToPico == null || _device?.isConnected != true) return;
    _nextPhoneSession = (_nextPhoneSession + 1) & 0xffff;
    if (_nextPhoneSession == 0) _nextPhoneSession = 0x8000;
    try {
      await _queueResponse(_nextPhoneSession, response);
    } catch (error) {
      _fail('BLE async update failed: $error');
    }
  }

  Future<void> _queueResponse(int sessionId, List<int> response) {
    final send = _sendChain.then((_) => _sendResponse(sessionId, response));
    _sendChain = send.catchError((_) {});
    return send;
  }

  Future<void> _writeWithAck(BleEnvelope envelope) async {
    final characteristic = _phoneToPico;
    if (characteristic == null) throw StateError('Pico is not connected');
    final key = _ackKey(envelope);
    for (var attempt = 0; attempt < 3; attempt++) {
      final completer = Completer<void>();
      _acks[key] = completer;
      await characteristic.write(envelope.encode());
      try {
        await completer.future.timeout(const Duration(seconds: 2));
        _acks.remove(key);
        return;
      } on TimeoutException {
        _acks.remove(key);
      }
    }
    throw TimeoutException('Pico did not acknowledge BLE message');
  }

  Future<void> _writeAck(BleEnvelope received) {
    final characteristic = _phoneToPico;
    if (characteristic == null) throw StateError('Pico is not connected');
    return characteristic.write(
      BleEnvelope(
        type: BleMessageType.ack,
        sessionId: received.sessionId,
        sequence: received.sequence,
        totalLength: received.totalLength,
        chunkOffset: received.chunkOffset,
        chunk: Uint8List(0),
      ).encode(),
    );
  }

  Future<void> _writeControl(
    BleMessageType type, {
    int sessionId = 0,
    int sequence = 0,
  }) {
    final characteristic = _control;
    if (characteristic == null) throw StateError('Pico is not connected');
    return characteristic.write(
      BleEnvelope(
        type: type,
        sessionId: sessionId,
        sequence: sequence,
        totalLength: 0,
        chunkOffset: 0,
        chunk: Uint8List(0),
      ).encode(),
    );
  }

  void _onStatusValue(List<int> value) {
    if (value.isEmpty) return;
    try {
      final envelope = BleEnvelope.decode(value);
      _firmwareStatus = utf8.decode(envelope.chunk, allowMalformed: true);
    } catch (_) {
      _firmwareStatus = utf8.decode(value, allowMalformed: true);
    }
    notifyListeners();
  }

  String _ackKey(BleEnvelope envelope) =>
      '${envelope.sessionId}:${envelope.sequence}';

  void _fail(String message) {
    if (_disposed) return;
    _lastError = message;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    unawaited(disconnect(notify: false));
    unawaited(_scanSubscription?.cancel());
    super.dispose();
  }
}
