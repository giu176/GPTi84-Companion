package com.ti84relay.android

import com.ti84relay.android.data.*
import com.ti84relay.android.provider.ProviderRegistry
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.time.LocalTime
import java.time.format.DateTimeFormatter

enum class ConnectionState {
    BLUETOOTH_OFF, PERMISSION_REQUIRED, NOT_PAIRED, PAIRING, PAIRED,
    CONNECTING, HANDSHAKING, READY, BUSY, RECONNECTING, ERROR, DISCONNECTED
}

data class RelayUiState(
    val connection: ConnectionState = ConnectionState.DISCONNECTED,
    val detail: String = "Not connected",
    val deviceName: String? = null,
    val deviceAddress: String? = null,
    val activeProvider: ProviderKind = ProviderKind.OPENAI,
    val lastTransaction: String = "No transactions yet",
    val logs: List<String> = emptyList(),
)

class RelayRuntime(
    val settings: SecureSettings,
    val database: TransactionDatabase,
    val providers: ProviderRegistry,
) {
    private val _state = MutableStateFlow(
        RelayUiState(
            deviceName = settings.deviceName,
            deviceAddress = settings.deviceAddress,
            activeProvider = settings.activeProvider,
        )
    )
    val state: StateFlow<RelayUiState> = _state.asStateFlow()

    fun connection(state: ConnectionState, detail: String) {
        _state.value = _state.value.copy(connection = state, detail = detail)
        log("${state.name}: $detail")
    }

    fun selectedDevice(name: String?, address: String) {
        settings.deviceName = name
        settings.deviceAddress = address
        _state.value = _state.value.copy(deviceName = name, deviceAddress = address)
        connection(ConnectionState.PAIRED, "${name ?: "Bluetooth device"} selected")
    }

    fun activeProvider(kind: ProviderKind) {
        settings.activeProvider = kind
        _state.value = _state.value.copy(activeProvider = kind)
    }

    fun transaction(detail: String) {
        _state.value = _state.value.copy(lastTransaction = detail)
        log(detail)
    }

    fun log(message: String) {
        val time = LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm:ss"))
        _state.value = _state.value.copy(logs = (listOf("$time  $message") + _state.value.logs).take(100))
    }
}

