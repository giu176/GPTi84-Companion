#include <SoftwareSerial.h>

// ZS-040 TXD -> D10. D11 -> 1k -> ZS-040 RXD, with 2k RXD-to-GND.
SoftwareSerial bluetooth(10, 11);

constexpr uint8_t BT_STATE_PIN = 7;
constexpr bool USE_BT_STATE = false;
constexpr uint8_t VERSION = 1;
constexpr size_t MAX_PAYLOAD = 128;
constexpr size_t HEADER_SIZE = 11;
constexpr size_t MAX_DECODED = HEADER_SIZE + MAX_PAYLOAD + 2;
constexpr size_t MAX_ENCODED = MAX_DECODED + 3;

enum MessageType : uint8_t {
  HELLO = 0x01,
  HELLO_ACK = 0x02,
  PING = 0x03,
  PONG = 0x04,
  STATUS = 0x30,
  ACK = 0x31,
  NACK = 0x32,
  ERROR_MESSAGE = 0x33,
};

struct PacketBuffer {
  uint8_t data[MAX_ENCODED];
  size_t length = 0;
  bool overflow = false;
};

PacketBuffer usbPacket;
PacketBuffer btPacket;

uint16_t crc16Ccitt(const uint8_t *data, size_t length) {
  uint16_t crc = 0xFFFF;
  for (size_t i = 0; i < length; ++i) {
    crc ^= static_cast<uint16_t>(data[i]) << 8;
    for (uint8_t bit = 0; bit < 8; ++bit) {
      crc = (crc & 0x8000) ? static_cast<uint16_t>((crc << 1) ^ 0x1021) : static_cast<uint16_t>(crc << 1);
    }
  }
  return crc;
}

size_t cobsDecode(const uint8_t *input, size_t length, uint8_t *output) {
  size_t readIndex = 0;
  size_t writeIndex = 0;
  while (readIndex < length) {
    uint8_t code = input[readIndex++];
    if (code == 0) return 0;
    for (uint8_t i = 1; i < code; ++i) {
      if (readIndex >= length || writeIndex >= MAX_DECODED) return 0;
      output[writeIndex++] = input[readIndex++];
    }
    if (code != 0xFF && readIndex < length) {
      if (writeIndex >= MAX_DECODED) return 0;
      output[writeIndex++] = 0;
    }
  }
  return writeIndex;
}

size_t cobsEncode(const uint8_t *input, size_t length, uint8_t *output) {
  size_t readIndex = 0;
  size_t writeIndex = 1;
  size_t codeIndex = 0;
  uint8_t code = 1;
  while (readIndex < length) {
    if (input[readIndex] == 0) {
      output[codeIndex] = code;
      code = 1;
      codeIndex = writeIndex++;
      ++readIndex;
    } else {
      output[writeIndex++] = input[readIndex++];
      ++code;
      if (code == 0xFF) {
        output[codeIndex] = code;
        code = 1;
        codeIndex = writeIndex++;
      }
    }
  }
  output[codeIndex] = code;
  return writeIndex;
}

uint16_t readU16(const uint8_t *data) {
  return static_cast<uint16_t>(data[0]) | (static_cast<uint16_t>(data[1]) << 8);
}

void writeU16(uint8_t *data, uint16_t value) {
  data[0] = value & 0xFF;
  data[1] = value >> 8;
}

void writeU32(uint8_t *data, uint32_t value) {
  data[0] = value & 0xFF;
  data[1] = (value >> 8) & 0xFF;
  data[2] = (value >> 16) & 0xFF;
  data[3] = (value >> 24) & 0xFF;
}

bool validDecodedFrame(const uint8_t *frame, size_t length) {
  if (length < HEADER_SIZE + 2 || frame[0] != VERSION) return false;
  uint16_t payloadLength = readU16(frame + 9);
  if (payloadLength > MAX_PAYLOAD || length != HEADER_SIZE + payloadLength + 2) return false;
  uint16_t expected = readU16(frame + length - 2);
  return crc16Ccitt(frame, length - 2) == expected;
}

void sendFrame(Stream &destination, uint8_t type, uint16_t sequence, uint32_t transactionId,
               const uint8_t *payload, uint16_t payloadLength) {
  uint8_t decoded[MAX_DECODED];
  uint8_t encoded[MAX_ENCODED];
  decoded[0] = VERSION;
  decoded[1] = type;
  decoded[2] = 0;
  writeU16(decoded + 3, sequence);
  writeU32(decoded + 5, transactionId);
  writeU16(decoded + 9, payloadLength);
  for (uint16_t i = 0; i < payloadLength; ++i) decoded[HEADER_SIZE + i] = payload[i];
  uint16_t crc = crc16Ccitt(decoded, HEADER_SIZE + payloadLength);
  writeU16(decoded + HEADER_SIZE + payloadLength, crc);
  size_t encodedLength = cobsEncode(decoded, HEADER_SIZE + payloadLength + 2, encoded);
  destination.write(encoded, encodedLength);
  destination.write(static_cast<uint8_t>(0));
}

void sendText(Stream &destination, uint8_t type, uint16_t sequence, uint32_t transactionId, const char *text) {
  size_t length = strlen(text);
  if (length > MAX_PAYLOAD) length = MAX_PAYLOAD;
  sendFrame(destination, type, sequence, transactionId, reinterpret_cast<const uint8_t *>(text), length);
}

void sendError(Stream &destination, uint16_t sequence, uint32_t transactionId, const char *code, const char *message) {
  uint8_t payload[MAX_PAYLOAD];
  size_t position = 0;
  while (*code && position < MAX_PAYLOAD) payload[position++] = static_cast<uint8_t>(*code++);
  if (position < MAX_PAYLOAD) payload[position++] = 0;
  while (*message && position < MAX_PAYLOAD) payload[position++] = static_cast<uint8_t>(*message++);
  sendFrame(destination, ERROR_MESSAGE, sequence, transactionId, payload, position);
}

bool bluetoothConnected() {
  return !USE_BT_STATE || digitalRead(BT_STATE_PIN) == HIGH;
}

void processPacket(PacketBuffer &packet, Stream &source, Stream &destination, bool fromUsb) {
  if (packet.overflow || packet.length == 0) {
    packet.length = 0;
    packet.overflow = false;
    return;
  }

  uint8_t decoded[MAX_DECODED];
  size_t decodedLength = cobsDecode(packet.data, packet.length, decoded);
  packet.length = 0;
  if (decodedLength == 0 || !validDecodedFrame(decoded, decodedLength)) {
    sendText(source, NACK, 0, 0, "BAD_FRAME");
    return;
  }

  const uint8_t type = decoded[1];
  const uint16_t sequence = readU16(decoded + 3);
  const uint32_t transactionId = static_cast<uint32_t>(decoded[5]) |
      (static_cast<uint32_t>(decoded[6]) << 8) |
      (static_cast<uint32_t>(decoded[7]) << 16) |
      (static_cast<uint32_t>(decoded[8]) << 24);

  if (type == HELLO) {
    sendText(source, HELLO_ACK, sequence, transactionId,
             fromUsb ? (bluetoothConnected() ? "ARDUINO;BT=CONNECTED" : "ARDUINO;BT=UNKNOWN") : "ARDUINO;USB=READY");
    return;
  }
  if (type == PING) {
    sendFrame(source, PONG, sequence, transactionId, nullptr, 0);
    return;
  }
  if (fromUsb && !bluetoothConnected()) {
    sendError(source, sequence, transactionId, "BT_DISCONNECTED", "HC-05 STATE is low");
    return;
  }

  uint8_t encoded[MAX_ENCODED];
  size_t encodedLength = cobsEncode(decoded, decodedLength, encoded);
  destination.write(encoded, encodedLength);
  destination.write(static_cast<uint8_t>(0));
}

void consume(Stream &source, Stream &destination, PacketBuffer &packet, bool fromUsb) {
  while (source.available()) {
    int value = source.read();
    if (value < 0) return;
    if (value == 0) {
      processPacket(packet, source, destination, fromUsb);
    } else if (packet.length < MAX_ENCODED) {
      packet.data[packet.length++] = static_cast<uint8_t>(value);
    } else {
      packet.overflow = true;
    }
  }
}

void setup() {
  pinMode(BT_STATE_PIN, INPUT);
  Serial.begin(115200);
  bluetooth.begin(9600);
}

void loop() {
  consume(Serial, bluetooth, usbPacket, true);
  consume(bluetooth, Serial, btPacket, false);
}
