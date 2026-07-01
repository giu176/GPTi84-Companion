import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';

import 'calculator_relay.dart';

const phoneRelayDefaultPort = 8784;

class PhoneRelaySnapshot {
  const PhoneRelaySnapshot({
    required this.running,
    required this.port,
    required this.requestCount,
    required this.lastEvent,
    required this.addresses,
  });

  final bool running;
  final int port;
  final int requestCount;
  final String lastEvent;
  final List<String> addresses;

  String get endpoint {
    final host = addresses.isEmpty ? 'phone-ip' : addresses.first;
    return '$host:$port';
  }
}

class PhoneRelayServer extends ChangeNotifier {
  PhoneRelayServer({required this.relay});

  final CalculatorRelay relay;

  ServerSocket? _server;
  var _port = phoneRelayDefaultPort;
  var _requestCount = 0;
  var _lastEvent = 'Stopped';
  var _addresses = <String>[];

  PhoneRelaySnapshot get snapshot => PhoneRelaySnapshot(
    running: _server != null,
    port: _port,
    requestCount: _requestCount,
    lastEvent: _lastEvent,
    addresses: List.unmodifiable(_addresses),
  );

  Future<void> start({int port = phoneRelayDefaultPort}) async {
    if (_server != null) return;
    _port = port;
    _addresses = await localIpv4Addresses();
    _server = await ServerSocket.bind(InternetAddress.anyIPv4, port);
    _lastEvent = 'Listening on ${snapshot.endpoint}';
    notifyListeners();
    _server!.listen(
      _handleClient,
      onError: (Object error) {
        _lastEvent = 'Relay socket error: $error';
        notifyListeners();
      },
      onDone: () {
        _lastEvent = 'Stopped';
        notifyListeners();
      },
      cancelOnError: false,
    );
  }

  Future<void> stop() async {
    final server = _server;
    _server = null;
    await server?.close();
    _lastEvent = 'Stopped';
    notifyListeners();
  }

  Future<void> _handleClient(Socket socket) async {
    _lastEvent = 'Pico connected from ${socket.remoteAddress.address}';
    notifyListeners();
    final buffer = BytesBuilder(copy: false);
    var needed = -1;
    try {
      await for (final chunk in socket) {
        buffer.add(chunk);
        var bytes = buffer.takeBytes();
        while (true) {
          if (needed < 0) {
            if (bytes.length < 4) break;
            needed = ByteData.sublistView(
              Uint8List.fromList(bytes.sublist(0, 4)),
            ).getUint32(0);
            bytes = bytes.sublist(4);
            if (needed > 1 << 20) {
              throw const FormatException('Frame too large');
            }
          }
          if (bytes.length < needed) break;
          final payload = bytes.sublist(0, needed);
          bytes = bytes.sublist(needed);
          needed = -1;
          _requestCount++;
          _lastEvent = 'Request $_requestCount received';
          notifyListeners();
          final reply = await relay.reply(
            payload,
            idempotencyKey:
                'tcp-${socket.remoteAddress.address}-$_requestCount',
          );
          _lastEvent = 'Reply $_requestCount delivered';
          notifyListeners();
          _writeFrame(socket, reply);
        }
        if (bytes.isNotEmpty) buffer.add(bytes);
      }
    } catch (error) {
      _lastEvent = 'Pico connection failed: $error';
      notifyListeners();
    } finally {
      await socket.close();
    }
  }

  void _writeFrame(Socket socket, List<int> payload) {
    final header = ByteData(4)..setUint32(0, payload.length);
    socket.add(header.buffer.asUint8List());
    socket.add(payload);
  }
}

Future<List<String>> localIpv4Addresses() async {
  final interfaces = await NetworkInterface.list(
    includeLinkLocal: false,
    type: InternetAddressType.IPv4,
  );
  final addresses = <String>[];
  for (final interface in interfaces) {
    for (final address in interface.addresses) {
      if (!address.isLoopback) addresses.add(address.address);
    }
  }
  addresses.sort();
  return addresses;
}
