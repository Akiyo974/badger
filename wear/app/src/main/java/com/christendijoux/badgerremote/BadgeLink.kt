package com.christendijoux.badgerremote

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothStatusCodes
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.ParcelUuid
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

sealed interface LinkState {
    data object NoPermission : LinkState
    data object BluetoothOff : LinkState
    data object Searching : LinkState
    data class Connecting(val name: String) : LinkState
    data class Connected(val name: String) : LinkState
    data object Lost : LinkState
}

/**
 * Bluetooth link to the badge: finds it (the one used last time, or the first
 * one seen), connects, and writes the commands one at a time. Reconnects on its
 * own, since the badge reboots every time one of its apps exits.
 *
 * Everything except the Bluetooth callbacks runs on [scope] (main thread).
 */
// Every Bluetooth call happens after hasPermissions() said yes
@SuppressLint("MissingPermission")
class BadgeLink(private val context: Context, private val scope: CoroutineScope) {
    private val adapter = context.getSystemService(BluetoothManager::class.java)?.adapter
    private val prefs = context.getSharedPreferences("badge", Context.MODE_PRIVATE)

    private val _state = MutableStateFlow<LinkState>(LinkState.Searching)
    val state: StateFlow<LinkState> = _state.asStateFlow()

    // Only the latest presses matter if the link falls behind
    private val commands = Channel<ByteArray>(capacity = 16, onBufferOverflow = BufferOverflow.DROP_OLDEST)

    private var gatt: BluetoothGatt? = null
    private var characteristic: BluetoothGattCharacteristic? = null
    @Volatile private var writeDone: CompletableDeferred<Unit>? = null
    private var running = false
    private var scanning = false
    private var retry: Job? = null
    private var scanTimeout: Job? = null
    private var writer: Job? = null

    fun hasPermissions(): Boolean = requiredPermissions().all {
        context.checkSelfPermission(it) == PackageManager.PERMISSION_GRANTED
    }

    fun start() {
        if (running) return
        running = true
        writer = scope.launch { for (bytes in commands) write(bytes) }
        connect()
    }

    fun stop() {
        running = false
        retry?.cancel()
        writer?.cancel()
        stopScan()
        closeGatt()
    }

    /** Forgets the remembered badge and connects to the next one found. */
    fun forget() {
        prefs.edit().remove(KEY_ADDRESS).apply()
        if (!running) return
        stop()
        start()
    }

    fun send(action: Action, button: BadgeButton) {
        if (_state.value is LinkState.Connected) commands.trySend(Protocol.encode(action, button))
    }

    private fun connect() {
        if (!running) return
        when {
            !hasPermissions() -> _state.value = LinkState.NoPermission
            adapter == null || !adapter.isEnabled -> {
                _state.value = LinkState.BluetoothOff
                retryLater(RETRY_OFF_MS)
            }
            else -> startScan()
        }
    }

    private fun retryLater(delayMs: Long) {
        retry?.cancel()
        retry = scope.launch {
            delay(delayMs)
            connect()
        }
    }

    // Scan --------------------------------------------------------------------

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            scope.launch { onBadgeFound(result.device, result.scanRecord?.deviceName) }
        }

        override fun onScanFailed(errorCode: Int) {
            scope.launch {
                scanning = false
                _state.value = LinkState.Lost
                retryLater(RETRY_LOST_MS)
            }
        }
    }

    private fun startScan() {
        val scanner = adapter?.bluetoothLeScanner
        if (scanner == null) {
            retryLater(RETRY_OFF_MS)
            return
        }
        if (scanning) return
        _state.value = LinkState.Searching
        val filter = ScanFilter.Builder().setServiceUuid(ParcelUuid(Protocol.SERVICE)).build()
        val settings = ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build()
        scanner.startScan(listOf(filter), settings, scanCallback)
        scanning = true
        // Android stops long scans on its own: start a fresh one now and then
        scanTimeout?.cancel()
        scanTimeout = scope.launch {
            delay(SCAN_WINDOW_MS)
            if (scanning) {
                stopScan()
                connect()
            }
        }
    }

    private fun stopScan() {
        scanTimeout?.cancel()
        if (!scanning) return
        scanning = false
        if (adapter?.isEnabled == true) adapter.bluetoothLeScanner?.stopScan(scanCallback)
    }

    private fun onBadgeFound(device: BluetoothDevice, name: String?) {
        if (!scanning || !running) return
        // Once a badge has been used, stick to it (several badges at a conference)
        val saved = prefs.getString(KEY_ADDRESS, null)
        if (saved != null && device.address != saved) return
        stopScan()
        _state.value = LinkState.Connecting(name ?: device.address)
        val g = device.connectGatt(context, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
        gatt = g
        // Android only gives up after 30 s: a badge that just rebooted is quicker to find again
        retry?.cancel()
        retry = scope.launch {
            delay(CONNECT_TIMEOUT_MS)
            if (gatt === g && characteristic == null) {
                closeGatt()
                _state.value = LinkState.Lost
                connect()
            }
        }
    }

    // GATT --------------------------------------------------------------------

    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                g.requestConnectionPriority(BluetoothGatt.CONNECTION_PRIORITY_HIGH)
                g.discoverServices()
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                scope.launch { onLost(g) }
            }
        }

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            val found = g.getService(Protocol.SERVICE)?.getCharacteristic(Protocol.COMMAND)
            scope.launch { onReady(g, found) }
        }

        override fun onCharacteristicWrite(g: BluetoothGatt, c: BluetoothGattCharacteristic, status: Int) {
            writeDone?.complete(Unit)
        }
    }

    private fun onReady(g: BluetoothGatt, found: BluetoothGattCharacteristic?) {
        if (gatt !== g) return
        if (found == null) {
            g.disconnect()
            return
        }
        characteristic = found
        prefs.edit().putString(KEY_ADDRESS, g.device.address).apply()
        val name = (_state.value as? LinkState.Connecting)?.name ?: g.device.address
        _state.value = LinkState.Connected(name)
    }

    private fun onLost(g: BluetoothGatt) {
        g.close()
        if (gatt !== g) return
        gatt = null
        characteristic = null
        writeDone?.complete(Unit)
        if (!running) return
        _state.value = LinkState.Lost
        retryLater(RETRY_LOST_MS)
    }

    private fun closeGatt() {
        gatt?.let {
            it.disconnect()
            it.close()
        }
        gatt = null
        characteristic = null
        writeDone?.complete(Unit)
    }

    /** One write at a time: Android rejects a write sent before the previous one finished. */
    private suspend fun write(bytes: ByteArray) {
        val g = gatt ?: return
        val c = characteristic ?: return
        val done = CompletableDeferred<Unit>()
        writeDone = done
        val type = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
        val started = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            g.writeCharacteristic(c, bytes, type) == BluetoothStatusCodes.SUCCESS
        } else {
            @Suppress("DEPRECATION")
            c.writeType = type
            @Suppress("DEPRECATION")
            c.value = bytes
            @Suppress("DEPRECATION")
            g.writeCharacteristic(c)
        }
        if (started) withTimeoutOrNull(WRITE_TIMEOUT_MS) { done.await() }
    }

    companion object {
        private const val KEY_ADDRESS = "address"
        private const val SCAN_WINDOW_MS = 25_000L
        private const val RETRY_OFF_MS = 3_000L
        private const val RETRY_LOST_MS = 1_000L
        private const val WRITE_TIMEOUT_MS = 1_000L
        private const val CONNECT_TIMEOUT_MS = 10_000L

        fun requiredPermissions(): Array<String> =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
            } else {
                arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            }
    }
}
