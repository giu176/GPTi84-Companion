package com.ti84relay.android.bluetooth

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.Intent
import android.content.pm.PackageManager
import android.os.IBinder
import androidx.core.app.ActivityCompat
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import android.content.pm.ServiceInfo
import com.ti84relay.android.*
import com.ti84relay.android.data.*
import com.ti84relay.android.protocol.*
import kotlinx.coroutines.*
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger
import java.util.zip.CRC32

class BluetoothRelayService : Service() {
    companion object {
        const val ACTION_CONNECT = "com.ti84relay.CONNECT"
        const val ACTION_DISCONNECT = "com.ti84relay.DISCONNECT"
        private const val CHANNEL = "relay_connection"
        private const val NOTIFICATION_ID = 84
        private const val QUERY_LIMIT = 4096
        private const val RESPONSE_LIMIT = 16384
        private val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    }

    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private lateinit var runtime: RelayRuntime
    private lateinit var adapter: BluetoothAdapter
    private var socket: BluetoothSocket? = null
    private var explicitDisconnect = false
    private val decoder = StreamDecoder()
    private val writeMutex = kotlinx.coroutines.sync.Mutex()
    private val pendingAcks = ConcurrentHashMap<Int, CompletableDeferred<Unit>>()
    private val sequence = AtomicInteger(100)
    private val seenFrames = LinkedHashSet<String>()
    private var assembly: RequestAssembly? = null

    private data class RequestAssembly(val transactionId: Long, val expectedLength: Int, val bytes: ByteArrayOutputStream)

    override fun onCreate() {
        super.onCreate()
        runtime = (application as RelayApplication).runtime
        adapter = getSystemService(BluetoothManager::class.java).adapter
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_DISCONNECT -> disconnect(true)
            ACTION_CONNECT -> {
                explicitDisconnect = false
                startForegroundNotification("Connecting…")
                serviceScope.launch { connectionLoop() }
            }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        disconnect(true)
        serviceScope.cancel()
        super.onDestroy()
    }

    private suspend fun connectionLoop() {
        val delays = longArrayOf(1, 2, 4, 8, 15, 30)
        var attempt = 0
        while (!explicitDisconnect) {
            try {
                connectOnce()
                attempt = 0
                readLoop()
            } catch (failure: Exception) {
                closeSocket()
                if (explicitDisconnect) break
                val seconds = delays[attempt.coerceAtMost(delays.lastIndex)]
                attempt++
                runtime.connection(ConnectionState.RECONNECTING, "${failure.message ?: "Connection lost"}; retry in ${seconds}s")
                updateNotification("Reconnecting in ${seconds}s")
                delay(seconds * 1000)
            }
        }
    }

    private suspend fun connectOnce() {
        if (!adapter.isEnabled) throw IOException("Bluetooth is off")
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            runtime.connection(ConnectionState.PERMISSION_REQUIRED, "Bluetooth permission required")
            throw SecurityException("BLUETOOTH_CONNECT not granted")
        }
        val address = runtime.settings.deviceAddress ?: run {
            runtime.connection(ConnectionState.NOT_PAIRED, "Select TI84-RELAY first")
            throw IOException("No selected device")
        }
        runtime.connection(ConnectionState.CONNECTING, "Opening RFCOMM socket")
        adapter.cancelDiscovery()
        val device = adapter.getRemoteDevice(address)
        socket = device.createRfcommSocketToServiceRecord(SPP_UUID).also { it.connect() }
        runtime.connection(ConnectionState.HANDSHAKING, "Connected; checking bridge protocol")
        updateNotification("Connected to ${device.name ?: address}")
        sendRaw(Frame(MessageType.HELLO, nextSequence(), payload = "ANDROID-RELAY".toByteArray()))
        val connectedSocket = socket
        serviceScope.launch {
            delay(5000)
            if (socket === connectedSocket && runtime.state.value.connection == ConnectionState.HANDSHAKING) {
                runtime.connection(ConnectionState.ERROR, "Bluetooth connected, but Arduino bridge did not answer within 5 seconds")
                runCatching { connectedSocket?.close() }
            }
        }
    }

    private suspend fun readLoop() {
        val input = socket?.inputStream ?: throw IOException("Socket has no input stream")
        val buffer = ByteArray(256)
        while (currentCoroutineContext().isActive) {
            val count = input.read(buffer)
            if (count < 0) throw IOException("Bluetooth stream closed")
            val frames = try { decoder.feed(buffer.copyOf(count)) } catch (failure: ProtocolException) {
                runtime.log("Rejected Bluetooth frame: ${failure.message}")
                continue
            }
            frames.forEach { frame -> serviceScope.launch { process(frame) } }
        }
    }

    private suspend fun process(frame: Frame) {
        when (frame.type) {
            MessageType.HELLO_ACK -> {
                runtime.connection(ConnectionState.READY, String(frame.payload))
                serviceScope.launch { redeliverPending() }
            }
            MessageType.PING -> sendRaw(Frame(MessageType.PONG, frame.sequence, frame.transactionId))
            MessageType.PONG -> Unit
            MessageType.ACK -> pendingAcks.remove(frame.sequence)?.complete(Unit)
            MessageType.NACK -> pendingAcks.remove(frame.sequence)?.completeExceptionally(IOException(String(frame.payload)))
            MessageType.REQUEST_BEGIN, MessageType.REQUEST_CHUNK, MessageType.REQUEST_END -> processRequestFrame(frame)
            MessageType.CANCEL -> {
                assembly = null
                runtime.connection(ConnectionState.READY, "Transaction cancelled")
            }
            else -> runtime.log("Ignored ${frame.type}")
        }
    }

    private suspend fun processRequestFrame(frame: Frame) {
        val key = "${frame.transactionId}:${frame.sequence}:${frame.type}"
        synchronized(seenFrames) {
            if (key in seenFrames) {
                serviceScope.launch { acknowledge(frame) }
                return
            }
            seenFrames += key
            while (seenFrames.size > 256) seenFrames.remove(seenFrames.first())
        }

        when (frame.type) {
            MessageType.REQUEST_BEGIN -> {
                if (frame.payload.size != 4) return reject(frame, "BAD_REQUEST_BEGIN")
                val expected = WireProtocol.u32(frame.payload, 0).toInt()
                if (expected !in 1..QUERY_LIMIT) return reject(frame, "QUERY_INVALID")
                assembly = RequestAssembly(frame.transactionId, expected, ByteArrayOutputStream(expected))
                acknowledge(frame)
                sendStatus(frame.transactionId, "ACCEPTED")
            }
            MessageType.REQUEST_CHUNK -> {
                val current = assembly
                if (current == null || current.transactionId != frame.transactionId) return reject(frame, "NO_REQUEST")
                if (current.bytes.size() + frame.payload.size > current.expectedLength) return reject(frame, "QUERY_TOO_LARGE")
                current.bytes.write(frame.payload)
                acknowledge(frame)
            }
            MessageType.REQUEST_END -> {
                val current = assembly
                if (current == null || current.transactionId != frame.transactionId || frame.payload.size != 4) {
                    return reject(frame, "BAD_REQUEST_END")
                }
                val bytes = current.bytes.toByteArray()
                val crc = CRC32().apply { update(bytes) }.value
                if (bytes.size != current.expectedLength || crc != WireProtocol.u32(frame.payload, 0)) return reject(frame, "QUERY_CHECK_FAILED")
                assembly = null
                acknowledge(frame)
                val query = runCatching { bytes.toString(Charsets.UTF_8) }.getOrElse { return sendError(frame.transactionId, "QUERY_INVALID", "Query is not UTF-8") }
                serviceScope.launch { relay(frame.transactionId, query) }
            }
            else -> Unit
        }
    }

    private suspend fun relay(transactionId: Long, query: String) {
        val dao = runtime.database.transactions()
        val existing = dao.get(transactionId)
        if (existing?.state in setOf("COMPLETED", "DELIVERED") && existing?.response != null) {
            runtime.log("Reusing stored transaction $transactionId")
            deliverResponse(transactionId, existing.response)
            dao.upsert(existing.copy(state = "DELIVERED", updatedAt = System.currentTimeMillis()))
            return
        }
        if (existing?.state == "SUBMITTING") {
            sendError(transactionId, "TRANSACTION_INDETERMINATE", "The app restarted during provider submission; refusing a duplicate API call")
            return
        }
        if (existing?.state == "FAILED") {
            sendError(transactionId, existing.errorCode ?: "PROVIDER_ERROR", existing.errorMessage ?: "Stored provider failure")
            return
        }

        runtime.connection(ConnectionState.BUSY, "Calling ${runtime.settings.activeProvider.displayName}")
        runtime.transaction("Transaction $transactionId: API_PENDING")
        dao.upsert(RelayTransaction(transactionId, "SUBMITTING", query))
        sendStatus(transactionId, "API_PENDING")
        try {
            val config = runtime.settings.load(runtime.settings.activeProvider)
            val result = runtime.providers.provider(config.kind).complete(config, query)
            val responseBytes = result.text.toByteArray(Charsets.UTF_8)
            if (responseBytes.size > RESPONSE_LIMIT) throw ProviderFailure("RESPONSE_TOO_LARGE", "Response is over 16 KiB")
            dao.upsert(RelayTransaction(transactionId, "COMPLETED", query, result.text))
            runtime.transaction("Transaction $transactionId: response ready (${responseBytes.size} bytes)")
            deliverResponse(transactionId, result.text)
            dao.upsert(RelayTransaction(transactionId, "DELIVERED", query, result.text))
            runtime.connection(ConnectionState.READY, "Reply delivered")
        } catch (failure: ProviderFailure) {
            dao.upsert(RelayTransaction(transactionId, "FAILED", query, errorCode = failure.code, errorMessage = failure.message))
            sendError(transactionId, failure.code, failure.message ?: "Provider failed")
            runtime.connection(ConnectionState.ERROR, "${failure.code}: ${failure.message}")
        } catch (failure: Exception) {
            dao.upsert(RelayTransaction(transactionId, "FAILED", query, errorCode = "INTERNAL", errorMessage = failure.message))
            sendError(transactionId, "INTERNAL", failure.message ?: "Unexpected relay error")
            runtime.connection(ConnectionState.ERROR, failure.message ?: "Unexpected relay error")
        }
    }

    private suspend fun deliverResponse(transactionId: Long, response: String) {
        val bytes = response.toByteArray(Charsets.UTF_8)
        sendReliable(MessageType.RESPONSE_BEGIN, transactionId, WireProtocol.u32Bytes(bytes.size.toLong()))
        bytes.asList().chunked(MAX_PAYLOAD).forEach { chunk ->
            sendReliable(MessageType.RESPONSE_CHUNK, transactionId, chunk.toByteArray())
        }
        val crc = CRC32().apply { update(bytes) }.value
        sendReliable(MessageType.RESPONSE_END, transactionId, WireProtocol.u32Bytes(crc))
    }

    private suspend fun redeliverPending() {
        runtime.database.transactions().recent().filter { it.state == "COMPLETED" && it.response != null }.forEach { transaction ->
            runCatching {
                runtime.log("Resuming response ${transaction.transactionId}")
                deliverResponse(transaction.transactionId, transaction.response!!)
                runtime.database.transactions().upsert(transaction.copy(state = "DELIVERED", updatedAt = System.currentTimeMillis()))
            }.onFailure { runtime.log("Resume delayed: ${it.message}") }
        }
    }

    private suspend fun acknowledge(frame: Frame) = sendRaw(Frame(MessageType.ACK, frame.sequence, frame.transactionId))

    private suspend fun reject(frame: Frame, reason: String) {
        sendRaw(Frame(MessageType.NACK, frame.sequence, frame.transactionId, reason.toByteArray()))
    }

    private suspend fun sendStatus(transactionId: Long, status: String) {
        sendRaw(Frame(MessageType.STATUS, nextSequence(), transactionId, status.toByteArray()))
    }

    private suspend fun sendError(transactionId: Long, code: String, message: String) {
        val payload = "$code\u0000${message.take(96)}".toByteArray()
        sendRaw(Frame(MessageType.ERROR, nextSequence(), transactionId, payload))
    }

    private suspend fun sendReliable(type: MessageType, transactionId: Long, payload: ByteArray) {
        val sequence = nextSequence()
        repeat(3) { attempt ->
            val deferred = CompletableDeferred<Unit>()
            pendingAcks[sequence] = deferred
            sendRaw(Frame(type, sequence, transactionId, payload))
            try {
                withTimeout(2000) { deferred.await() }
                return
            } catch (failure: Exception) {
                pendingAcks.remove(sequence)
                if (attempt == 2) throw IOException("No ACK for $type sequence $sequence", failure)
            }
        }
    }

    private suspend fun sendRaw(frame: Frame) {
        val output = socket?.outputStream ?: throw IOException("Bluetooth is not connected")
        writeMutex.lock()
        try {
            output.write(WireProtocol.encode(frame))
            output.flush()
        } finally {
            writeMutex.unlock()
        }
    }

    private fun nextSequence(): Int = sequence.updateAndGet { if (it >= 0xffff) 1 else it + 1 }

    private fun disconnect(explicit: Boolean) {
        explicitDisconnect = explicit
        closeSocket()
        runtime.connection(ConnectionState.DISCONNECTED, if (explicit) "Disconnected by user" else "Disconnected")
        stopForeground(STOP_FOREGROUND_REMOVE)
        if (explicit) stopSelf()
    }

    private fun closeSocket() {
        runCatching { socket?.close() }
        socket = null
        pendingAcks.values.forEach { it.cancel() }
        pendingAcks.clear()
    }

    private fun createNotificationChannel() {
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL, "Calculator relay connection", NotificationManager.IMPORTANCE_LOW)
        )
    }

    private fun notification(text: String) = NotificationCompat.Builder(this, CHANNEL)
        .setSmallIcon(android.R.drawable.stat_sys_data_bluetooth)
        .setContentTitle("TI-84 Relay")
        .setContentText(text)
        .setOngoing(true)
        .build()

    private fun startForegroundNotification(text: String) {
        ServiceCompat.startForeground(this, NOTIFICATION_ID, notification(text), ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
    }

    private fun updateNotification(text: String) {
        getSystemService(NotificationManager::class.java).notify(NOTIFICATION_ID, notification(text))
    }
}
