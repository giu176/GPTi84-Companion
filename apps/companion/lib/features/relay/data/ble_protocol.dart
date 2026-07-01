import 'dart:typed_data';

const bleProtocolVersion = 1;
const bleEnvelopeHeaderLength = 15;
const bleDefaultChunkLength = 5;

const gpti84ServiceUuid = '7e400001-b5a3-f393-e0a9-e50e24dcca9e';
const gpti84ControlUuid = '7e400002-b5a3-f393-e0a9-e50e24dcca9e';
const gpti84PicoToPhoneUuid = '7e400003-b5a3-f393-e0a9-e50e24dcca9e';
const gpti84PhoneToPicoUuid = '7e400004-b5a3-f393-e0a9-e50e24dcca9e';
const gpti84StatusUuid = '7e400005-b5a3-f393-e0a9-e50e24dcca9e';

enum BleMessageType {
  hello(1),
  requestChunk(2),
  requestEnd(3),
  ack(4),
  responseChunk(5),
  responseEnd(6),
  error(7),
  cancel(8),
  ping(9),
  pong(10),
  status(11);

  const BleMessageType(this.code);
  final int code;

  static BleMessageType fromCode(int code) =>
      values.firstWhere((value) => value.code == code);
}

class BleEnvelope {
  const BleEnvelope({
    required this.type,
    required this.sessionId,
    required this.sequence,
    required this.totalLength,
    required this.chunkOffset,
    required this.chunk,
    this.flags = 0,
  });

  final BleMessageType type;
  final int sessionId;
  final int sequence;
  final int totalLength;
  final int chunkOffset;
  final Uint8List chunk;
  final int flags;

  Uint8List encode() {
    if (chunk.length > 0xffff) {
      throw const FormatException('BLE chunk is too large');
    }
    final bytes = Uint8List(bleEnvelopeHeaderLength + chunk.length);
    final data = ByteData.sublistView(bytes);
    data.setUint8(0, bleProtocolVersion);
    data.setUint8(1, type.code);
    data.setUint16(2, sessionId);
    data.setUint16(4, sequence);
    data.setUint16(6, totalLength);
    data.setUint16(8, chunkOffset);
    data.setUint16(10, chunk.length);
    data.setUint8(12, flags);
    bytes.setRange(bleEnvelopeHeaderLength, bytes.length, chunk);
    data.setUint16(13, _crcFor(bytes));
    return bytes;
  }

  static BleEnvelope decode(List<int> value) {
    final bytes = Uint8List.fromList(value);
    if (bytes.length < bleEnvelopeHeaderLength) {
      throw const FormatException('Truncated BLE envelope');
    }
    final data = ByteData.sublistView(bytes);
    if (data.getUint8(0) != bleProtocolVersion) {
      throw const FormatException('Unsupported BLE protocol version');
    }
    final chunkLength = data.getUint16(10);
    if (bytes.length != bleEnvelopeHeaderLength + chunkLength) {
      throw const FormatException('BLE envelope length mismatch');
    }
    final expectedCrc = data.getUint16(13);
    if (_crcFor(bytes) != expectedCrc) {
      throw const FormatException('BLE envelope CRC mismatch');
    }
    return BleEnvelope(
      type: BleMessageType.fromCode(data.getUint8(1)),
      sessionId: data.getUint16(2),
      sequence: data.getUint16(4),
      totalLength: data.getUint16(6),
      chunkOffset: data.getUint16(8),
      chunk: Uint8List.sublistView(bytes, bleEnvelopeHeaderLength),
      flags: data.getUint8(12),
    );
  }

  static int _crcFor(Uint8List bytes) {
    final copy = Uint8List.fromList(bytes);
    copy[13] = 0;
    copy[14] = 0;
    return crc16Ccitt(copy);
  }
}

int crc16Ccitt(List<int> bytes) {
  var crc = 0xffff;
  for (final value in bytes) {
    crc ^= value << 8;
    for (var bit = 0; bit < 8; bit++) {
      crc = (crc & 0x8000) != 0
          ? ((crc << 1) ^ 0x1021) & 0xffff
          : (crc << 1) & 0xffff;
    }
  }
  return crc;
}

List<BleEnvelope> chunkBleMessage({
  required BleMessageType type,
  required int sessionId,
  required List<int> payload,
  int chunkLength = bleDefaultChunkLength,
}) {
  if (payload.length > 0xffff) {
    throw const FormatException('BLE message is too large');
  }
  final chunks = <BleEnvelope>[];
  var sequence = 0;
  for (var offset = 0; offset < payload.length; offset += chunkLength) {
    final end = (offset + chunkLength).clamp(0, payload.length);
    chunks.add(
      BleEnvelope(
        type: type,
        sessionId: sessionId,
        sequence: sequence++,
        totalLength: payload.length,
        chunkOffset: offset,
        chunk: Uint8List.fromList(payload.sublist(offset, end)),
      ),
    );
  }
  return chunks;
}

class BleMessageAssembler {
  int? _sessionId;
  int? _totalLength;
  final Map<int, Uint8List> _chunks = {};

  void reset() {
    _sessionId = null;
    _totalLength = null;
    _chunks.clear();
  }

  void add(BleEnvelope envelope) {
    if (_sessionId != null && _sessionId != envelope.sessionId) reset();
    _sessionId = envelope.sessionId;
    _totalLength = envelope.totalLength;
    _chunks.putIfAbsent(envelope.chunkOffset, () => envelope.chunk);
  }

  Uint8List? finish(int sessionId) {
    if (_sessionId != sessionId || _totalLength == null) return null;
    final output = BytesBuilder(copy: false);
    var offset = 0;
    while (offset < _totalLength!) {
      final chunk = _chunks[offset];
      if (chunk == null) return null;
      output.add(chunk);
      offset += chunk.length;
    }
    final bytes = output.takeBytes();
    if (bytes.length != _totalLength) return null;
    reset();
    return bytes;
  }
}
