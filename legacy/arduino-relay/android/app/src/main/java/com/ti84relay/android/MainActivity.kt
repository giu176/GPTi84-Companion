package com.ti84relay.android

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.companion.AssociationInfo
import android.companion.AssociationRequest
import android.companion.BluetoothDeviceFilter
import android.companion.CompanionDeviceManager
import android.content.Intent
import android.content.IntentSender
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.IntentSenderRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import com.ti84relay.android.bluetooth.BluetoothRelayService
import com.ti84relay.android.data.*
import kotlinx.coroutines.launch
import java.util.regex.Pattern

@OptIn(ExperimentalMaterial3Api::class)
class MainActivity : ComponentActivity() {
    private val runtime get() = (application as RelayApplication).runtime

    private val pairingResult = registerForActivityResult(ActivityResultContracts.StartIntentSenderForResult()) { result ->
        if (result.resultCode != Activity.RESULT_OK) {
            runtime.connection(ConnectionState.NOT_PAIRED, "Pairing cancelled")
            return@registerForActivityResult
        }
        val data = result.data
        val device = if (Build.VERSION.SDK_INT >= 33) {
            data?.getParcelableExtra(CompanionDeviceManager.EXTRA_DEVICE, BluetoothDevice::class.java)
        } else {
            @Suppress("DEPRECATION") data?.getParcelableExtra(CompanionDeviceManager.EXTRA_DEVICE)
        }
        if (device == null) {
            runtime.connection(ConnectionState.ERROR, "Android did not return a Bluetooth device")
        } else if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED) acceptDevice(device)
    }

    private val permissionResult = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { results ->
        if (results[Manifest.permission.BLUETOOTH_SCAN] == true && results[Manifest.permission.BLUETOOTH_CONNECT] == true) {
            beginCompanionPairing()
        } else {
            runtime.connection(ConnectionState.PERMISSION_REQUIRED, "Nearby-device permission denied")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { RelayTheme { RelayScreen() } }
    }

    private fun requestPairing() {
        val permissions = buildList {
            add(Manifest.permission.BLUETOOTH_SCAN)
            add(Manifest.permission.BLUETOOTH_CONNECT)
            if (Build.VERSION.SDK_INT >= 33) add(Manifest.permission.POST_NOTIFICATIONS)
        }.toTypedArray()
        if (permissions.take(2).all { checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED }) beginCompanionPairing()
        else permissionResult.launch(permissions)
    }

    private fun beginCompanionPairing() {
        runtime.connection(ConnectionState.PAIRING, "Choose TI84-RELAY in the Android dialog")
        val filter = BluetoothDeviceFilter.Builder()
            .setNamePattern(Pattern.compile("(TI84-RELAY.*|HC-0[56])", Pattern.CASE_INSENSITIVE))
            .build()
        val request = AssociationRequest.Builder().addDeviceFilter(filter).setSingleDevice(false).build()
        val manager = getSystemService(CompanionDeviceManager::class.java)
        val callback = object : CompanionDeviceManager.Callback() {
            override fun onAssociationPending(intentSender: IntentSender) {
                pairingResult.launch(IntentSenderRequest.Builder(intentSender).build())
            }

            @Suppress("DEPRECATION")
            override fun onDeviceFound(chooserLauncher: IntentSender) {
                pairingResult.launch(IntentSenderRequest.Builder(chooserLauncher).build())
            }

            override fun onAssociationCreated(associationInfo: AssociationInfo) { runtime.log("Companion association created") }

            override fun onFailure(error: CharSequence?) {
                runtime.connection(ConnectionState.ERROR, error?.toString() ?: "Companion pairing failed")
            }
        }
        if (Build.VERSION.SDK_INT >= 33) {
            manager.associate(request, mainExecutor, callback)
        } else {
            @Suppress("DEPRECATION")
            manager.associate(request, callback, Handler(Looper.getMainLooper()))
        }
    }

    @SuppressLint("MissingPermission")
    private fun acceptDevice(device: BluetoothDevice) {
        runtime.selectedDevice(device.name, device.address)
        if (device.bondState != BluetoothDevice.BOND_BONDED) device.createBond()
    }

    @SuppressLint("MissingPermission")
    private fun selectBondedModule() {
        if (checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
            permissionResult.launch(arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT))
            return
        }
        val adapter = getSystemService(BluetoothManager::class.java).adapter
        val candidate = adapter.bondedDevices.firstOrNull { device ->
            val name = device.name.orEmpty().uppercase()
            name.startsWith("TI84-RELAY") || name == "HC-05" || name == "HC-06"
        }
        if (candidate == null) runtime.connection(ConnectionState.NOT_PAIRED, "No bonded TI84-RELAY, HC-05, or HC-06 found")
        else acceptDevice(candidate)
    }

    private fun connect() {
        ContextCompat.startForegroundService(this, Intent(this, BluetoothRelayService::class.java).setAction(BluetoothRelayService.ACTION_CONNECT))
    }

    private fun disconnect() {
        startService(Intent(this, BluetoothRelayService::class.java).setAction(BluetoothRelayService.ACTION_DISCONNECT))
    }

    @Composable
    private fun RelayScreen() {
        val state by runtime.state.collectAsStateWithLifecycle()
        var tab by remember { mutableIntStateOf(0) }
        Scaffold(topBar = { TopAppBar(title = { Text("TI-84 Relay") }, actions = { ConnectionBadge(state.connection) }) }) { padding ->
            Column(Modifier.padding(padding).fillMaxSize()) {
                TabRow(selectedTabIndex = tab) {
                    listOf("Device", "Provider", "Relay", "Logs").forEachIndexed { index, title ->
                        Tab(selected = tab == index, onClick = { tab = index }, text = { Text(title) })
                    }
                }
                when (tab) {
                    0 -> DeviceTab(state)
                    1 -> ProviderTab(state.activeProvider)
                    2 -> RelayTab(state)
                    else -> DiagnosticsTab(state)
                }
            }
        }
    }

    @Composable
    private fun DeviceTab(state: RelayUiState) {
        Column(Modifier.padding(20.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Text("Bluetooth Classic SPP", style = MaterialTheme.typography.headlineSmall)
            Text("Android uses the system pairing dialog and remembers one associated HC-05/HC-06 device. Pairing cannot be silent.")
            InfoRow("State", state.connection.name)
            InfoRow("Detail", state.detail)
            InfoRow("Device", state.deviceName ?: "Not selected")
            InfoRow("Address", state.deviceAddress ?: "—")
            Button(onClick = ::requestPairing, modifier = Modifier.fillMaxWidth()) { Text("Pair TI84-RELAY") }
            OutlinedButton(onClick = ::selectBondedModule, modifier = Modifier.fillMaxWidth()) { Text("Use bonded HC-05 / HC-06") }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(onClick = ::connect, enabled = state.deviceAddress != null, modifier = Modifier.weight(1f)) { Text("Connect") }
                OutlinedButton(onClick = ::disconnect, modifier = Modifier.weight(1f)) { Text("Disconnect") }
            }
            OutlinedButton(
                onClick = { startActivity(Intent(Settings.ACTION_BLUETOOTH_SETTINGS)) },
                modifier = Modifier.fillMaxWidth()
            ) { Text("Open Android Bluetooth settings") }
        }
    }

    @Composable
    private fun ProviderTab(active: ProviderKind) {
        var selected by remember(active) { mutableStateOf(active) }
        var config by remember(selected) { mutableStateOf(runtime.settings.load(selected)) }
        var key by remember(selected) { mutableStateOf(config.apiKey) }
        var model by remember(selected) { mutableStateOf(config.model) }
        var baseUrl by remember(selected) { mutableStateOf(config.baseUrl) }
        var path by remember(selected) { mutableStateOf(config.path) }
        var health by remember { mutableStateOf("") }
        var testing by remember { mutableStateOf(false) }

        Column(Modifier.padding(20.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("AI provider", style = MaterialTheme.typography.headlineSmall)
            ProviderKind.entries.forEach { kind ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected == kind, onClick = {
                        selected = kind; config = runtime.settings.load(kind); key = config.apiKey
                        model = config.model; baseUrl = config.baseUrl; path = config.path
                    })
                    Text(kind.displayName)
                }
            }
            OutlinedTextField(model, { model = it }, label = { Text("Model") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(baseUrl, { baseUrl = it }, label = { Text("HTTPS base URL") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(path, { path = it }, label = { Text("API path") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(
                key, { key = it }, label = { Text("API key") }, modifier = Modifier.fillMaxWidth(),
                visualTransformation = PasswordVisualTransformation(), singleLine = true
            )
            Text("Credentials are encrypted with an Android Keystore key and are never included in diagnostics.", style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(onClick = {
                    config = ProviderConfig(selected, model, baseUrl, path, key)
                    runtime.settings.save(config); runtime.activeProvider(selected); health = "Saved"
                }, modifier = Modifier.weight(1f)) { Text("Save") }
                OutlinedButton(onClick = {
                    config = ProviderConfig(selected, model, baseUrl, path, key)
                    runtime.settings.save(config); testing = true; health = "Testing…"
                    lifecycleScope.launch {
                        val result = runtime.providers.provider(selected).selfTest(config)
                        testing = false; health = result.message
                    }
                }, enabled = !testing, modifier = Modifier.weight(1f)) { Text("Self-test") }
            }
            if (health.isNotBlank()) Text(health)
        }
    }

    @Composable
    private fun RelayTab(state: RelayUiState) {
        Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Text("Relay status", style = MaterialTheme.typography.headlineSmall)
            InfoRow("Connection", state.connection.name)
            InfoRow("Provider", state.activeProvider.displayName)
            InfoRow("Last transaction", state.lastTransaction)
            Text("Queries arrive from the Arduino. Complete replies are persisted before Bluetooth delivery.")
        }
    }

    @Composable
    private fun DiagnosticsTab(state: RelayUiState) {
        Column(Modifier.padding(20.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Diagnostics", style = MaterialTheme.typography.headlineSmall)
            Text("The latest 100 connection events are kept in memory. API keys and authorization headers are never logged.")
            HorizontalDivider()
            state.logs.forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
        }
    }

    @Composable
    private fun InfoRow(label: String, value: String) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(label, style = MaterialTheme.typography.labelLarge)
            Text(value, modifier = Modifier.padding(start = 16.dp))
        }
    }

    @Composable
    private fun ConnectionBadge(state: ConnectionState) {
        val color = when (state) {
            ConnectionState.READY -> MaterialTheme.colorScheme.primary
            ConnectionState.BUSY, ConnectionState.CONNECTING, ConnectionState.RECONNECTING, ConnectionState.HANDSHAKING -> MaterialTheme.colorScheme.tertiary
            else -> MaterialTheme.colorScheme.error
        }
        Text(state.name, color = color, style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(end = 12.dp))
    }
}

@Composable
private fun RelayTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = androidx.compose.ui.graphics.Color(0xFF166534),
            secondary = androidx.compose.ui.graphics.Color(0xFF3F6212),
            surface = androidx.compose.ui.graphics.Color(0xFFF7FAF7),
        ),
        content = content,
    )
}
