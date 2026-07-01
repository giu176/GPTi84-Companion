import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:gpti84_companion/features/relay/data/ble_protocol.dart';

void main() {
  test('BLE envelope round trips and validates CRC', () {
    final encoded = BleEnvelope(
      type: BleMessageType.requestChunk,
      sessionId: 7,
      sequence: 2,
      totalLength: 11,
      chunkOffset: 5,
      chunk: Uint8List.fromList('world'.codeUnits),
    ).encode();

    final decoded = BleEnvelope.decode(encoded);
    expect(decoded.type, BleMessageType.requestChunk);
    expect(decoded.sessionId, 7);
    expect(decoded.sequence, 2);
    expect(decoded.chunk, 'world'.codeUnits);

    encoded[encoded.length - 1] ^= 1;
    expect(() => BleEnvelope.decode(encoded), throwsFormatException);
  });

  test('BLE assembler tolerates duplicate chunks', () {
    final payload = Uint8List.fromList('prompt:hello\nmath:\n'.codeUnits);
    final chunks = chunkBleMessage(
      type: BleMessageType.requestChunk,
      sessionId: 9,
      payload: payload,
    );
    final assembler = BleMessageAssembler();
    for (final chunk in chunks) {
      assembler
        ..add(chunk)
        ..add(chunk);
    }

    expect(assembler.finish(9), payload);
  });
}
