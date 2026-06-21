package com.ti84relay.android.protocol

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class WireProtocolTest {
    @Test fun crcKnownVector() {
        assertEquals(0x29b1, WireProtocol.crc16("123456789".toByteArray()))
    }

    @Test fun frameRoundTrip() {
        val frame = Frame(MessageType.REQUEST_CHUNK, 42, 0x12345678, "hello\u0000world".toByteArray())
        assertEquals(frame, WireProtocol.decode(WireProtocol.encode(frame)))
    }

    @Test fun cobsRoundTrip() {
        val bytes = byteArrayOf(0, 1, 2, 0, 3, 0, 0, 4)
        assertArrayEquals(bytes, WireProtocol.cobsDecode(WireProtocol.cobsEncode(bytes)))
    }

    @Test fun corruptionRejected() {
        val encoded = WireProtocol.encode(Frame(MessageType.PING, 1))
        encoded[3] = (encoded[3].toInt() xor 0x55).toByte()
        assertThrows(ProtocolException::class.java) { WireProtocol.decode(encoded) }
    }
}
