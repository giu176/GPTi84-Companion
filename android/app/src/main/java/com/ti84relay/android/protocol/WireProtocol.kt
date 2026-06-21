package com.ti84relay.android.protocol

import java.io.ByteArrayOutputStream

const val PROTOCOL_VERSION: Int = 1
const val MAX_PAYLOAD: Int = 128

enum class MessageType(val wire: Int) {
    HELLO(0x01), HELLO_ACK(0x02), PING(0x03), PONG(0x04),
    REQUEST_BEGIN(0x10), REQUEST_CHUNK(0x11), REQUEST_END(0x12),
    RESPONSE_BEGIN(0x20), RESPONSE_CHUNK(0x21), RESPONSE_END(0x22),
    STATUS(0x30), ACK(0x31), NACK(0x32), ERROR(0x33), CANCEL(0x34);

    companion object {
        fun fromWire(value: Int): MessageType = entries.firstOrNull { it.wire == value }
            ?: throw ProtocolException("Unknown message type: $value")
    }
}

data class Frame(
    val type: MessageType,
    val sequence: Int,
    val transactionId: Long = 0,
    val payload: ByteArray = byteArrayOf(),
    val flags: Int = 0,
) {
    override fun equals(other: Any?): Boolean = other is Frame && type == other.type &&
        sequence == other.sequence && transactionId == other.transactionId && flags == other.flags &&
        payload.contentEquals(other.payload)
    override fun hashCode(): Int = 31 * type.hashCode() + payload.contentHashCode()
}

class ProtocolException(message: String) : IllegalArgumentException(message)

object WireProtocol {
    private const val HEADER_SIZE = 11

    fun encode(frame: Frame): ByteArray {
        require(frame.payload.size <= MAX_PAYLOAD)
        val body = ByteArray(HEADER_SIZE + frame.payload.size)
        body[0] = PROTOCOL_VERSION.toByte()
        body[1] = frame.type.wire.toByte()
        body[2] = frame.flags.toByte()
        putU16(body, 3, frame.sequence)
        putU32(body, 5, frame.transactionId)
        putU16(body, 9, frame.payload.size)
        frame.payload.copyInto(body, HEADER_SIZE)
        val crc = crc16(body)
        val decoded = body + byteArrayOf((crc and 0xff).toByte(), (crc ushr 8).toByte())
        return cobsEncode(decoded) + 0.toByte()
    }

    fun decode(encoded: ByteArray): Frame {
        val packet = if (encoded.lastOrNull() == 0.toByte()) encoded.dropLast(1).toByteArray() else encoded
        val decoded = cobsDecode(packet)
        if (decoded.size < HEADER_SIZE + 2) throw ProtocolException("Frame too short")
        val body = decoded.copyOf(decoded.size - 2)
        val received = u16(decoded, decoded.size - 2)
        if (crc16(body) != received) throw ProtocolException("CRC mismatch")
        if (body[0].toInt() and 0xff != PROTOCOL_VERSION) throw ProtocolException("Unsupported version")
        val payloadLength = u16(body, 9)
        if (payloadLength > MAX_PAYLOAD || body.size != HEADER_SIZE + payloadLength) {
            throw ProtocolException("Invalid payload length")
        }
        return Frame(
            type = MessageType.fromWire(body[1].toInt() and 0xff),
            sequence = u16(body, 3),
            transactionId = u32(body, 5),
            payload = body.copyOfRange(HEADER_SIZE, body.size),
            flags = body[2].toInt() and 0xff,
        )
    }

    fun crc16(bytes: ByteArray): Int {
        var crc = 0xffff
        bytes.forEach { byte ->
            crc = crc xor ((byte.toInt() and 0xff) shl 8)
            repeat(8) { crc = if (crc and 0x8000 != 0) ((crc shl 1) xor 0x1021) and 0xffff else (crc shl 1) and 0xffff }
        }
        return crc
    }

    fun cobsEncode(input: ByteArray): ByteArray {
        val output = ArrayList<Byte>(input.size + 2)
        output.add(0)
        var codeIndex = 0
        var code = 1
        input.forEach { value ->
            if (value == 0.toByte()) {
                output[codeIndex] = code.toByte()
                codeIndex = output.size
                output.add(0)
                code = 1
            } else {
                output.add(value)
                code++
                if (code == 0xff) {
                    output[codeIndex] = code.toByte()
                    codeIndex = output.size
                    output.add(0)
                    code = 1
                }
            }
        }
        output[codeIndex] = code.toByte()
        return output.toByteArray()
    }

    fun cobsDecode(input: ByteArray): ByteArray {
        val output = ByteArrayOutputStream()
        var index = 0
        while (index < input.size) {
            val code = input[index].toInt() and 0xff
            if (code == 0) throw ProtocolException("Zero inside COBS packet")
            index++
            val end = index + code - 1
            if (end > input.size) throw ProtocolException("Truncated COBS packet")
            output.write(input, index, end - index)
            index = end
            if (code != 0xff && index < input.size) output.write(0)
        }
        return output.toByteArray()
    }

    fun u16(bytes: ByteArray, offset: Int): Int =
        (bytes[offset].toInt() and 0xff) or ((bytes[offset + 1].toInt() and 0xff) shl 8)

    fun u32(bytes: ByteArray, offset: Int): Long =
        (bytes[offset].toLong() and 0xff) or ((bytes[offset + 1].toLong() and 0xff) shl 8) or
            ((bytes[offset + 2].toLong() and 0xff) shl 16) or ((bytes[offset + 3].toLong() and 0xff) shl 24)

    fun u32Bytes(value: Long): ByteArray = ByteArray(4).also { putU32(it, 0, value) }

    private fun putU16(bytes: ByteArray, offset: Int, value: Int) {
        bytes[offset] = value.toByte(); bytes[offset + 1] = (value ushr 8).toByte()
    }

    private fun putU32(bytes: ByteArray, offset: Int, value: Long) {
        bytes[offset] = value.toByte(); bytes[offset + 1] = (value ushr 8).toByte()
        bytes[offset + 2] = (value ushr 16).toByte(); bytes[offset + 3] = (value ushr 24).toByte()
    }
}

class StreamDecoder(private val maximum: Int = 160) {
    private val buffer = ByteArrayOutputStream()

    fun feed(bytes: ByteArray): List<Frame> {
        val result = mutableListOf<Frame>()
        bytes.forEach { value ->
            if (value == 0.toByte()) {
                if (buffer.size() > 0) {
                    result += WireProtocol.decode(buffer.toByteArray())
                    buffer.reset()
                }
            } else {
                if (buffer.size() >= maximum) {
                    buffer.reset()
                    throw ProtocolException("Encoded frame overflow")
                }
                buffer.write(value.toInt())
            }
        }
        return result
    }
}
