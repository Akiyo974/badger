package com.christendijoux.badgerremote

import android.content.SharedPreferences
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.lifecycle.lifecycleScope
import com.christendijoux.badgerremote.steps.StepPermission
import com.christendijoux.badgerremote.steps.StepStore
import com.christendijoux.badgerremote.steps.StepsService
import com.christendijoux.badgerremote.ui.RemoteScreen
import com.christendijoux.badgerremote.ui.StepsStatus
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import java.time.LocalDateTime

class MainActivity : ComponentActivity() {
    private lateinit var link: BadgeLink
    private lateinit var store: StepStore
    private val steps = MutableStateFlow<StepsStatus?>(null)
    private var storeListener: SharedPreferences.OnSharedPreferenceChangeListener? = null
    private var pendingSync: Job? = null

    private val permissions = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        if (StepPermission.NAME in result) StepPermission.markAsked(this)
        if (StepPermission.granted(this)) startSteps()
        if (link.hasPermissions()) restart()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        link = BadgeLink(applicationContext, lifecycleScope)
        store = StepStore(applicationContext)
        if (!link.hasPermissions() || StepPermission.shouldAsk(this)) askPermissions()
        if (StepPermission.granted(this)) startSteps()
        setContent {
            val state by link.state.collectAsState()
            val stepsStatus by steps.collectAsState()
            RemoteScreen(
                state = state,
                steps = stepsStatus,
                onSend = link::send,
                onForget = link::forget,
                onAskPermission = ::askPermissions,
            )
        }
        // A new connection (the badge reboots after each of its apps) gets the steps again
        lifecycleScope.launch {
            link.state.collect { if (it is LinkState.Connected) syncSoon(0) }
        }
    }

    // Connected only while the app is on screen: no Bluetooth in the background
    override fun onStart() {
        super.onStart()
        link.start()
        if (StepPermission.granted(this)) {
            showSteps(sent = false)
            storeListener = store.listen { syncSoon(SYNC_DEBOUNCE_MS) }
            // Ask Health Services for what it has not delivered yet
            lifecycleScope.launch { runCatching { StepsService.flush(applicationContext) } }
        }
    }

    override fun onStop() {
        storeListener?.let(store::stopListening)
        storeListener = null
        link.stop()
        super.onStop()
    }

    private fun askPermissions() {
        val wanted = BadgeLink.requiredPermissions().toMutableList()
        if (StepPermission.shouldAsk(this)) wanted += StepPermission.NAME
        permissions.launch(wanted.toTypedArray())
    }

    private fun startSteps() {
        lifecycleScope.launch { runCatching { StepsService.register(applicationContext) } }
    }

    private fun restart() {
        link.stop()
        link.start()
    }

    private fun showSteps(sent: Boolean) {
        steps.value = StepsStatus(store.today().total, sent)
    }

    /** Sends today's steps to the badge, once things settle for [delayMs]. */
    private fun syncSoon(delayMs: Long) {
        if (!StepPermission.granted(this)) return
        pendingSync?.cancel()
        pendingSync = lifecycleScope.launch {
            delay(delayMs)
            showSteps(sent = false)
            val today = store.today()
            val sent = link.sendSteps { maxBytes -> Protocol.encodeSteps(today, LocalDateTime.now(), maxBytes) }
            showSteps(sent)
        }
    }

    private companion object {
        const val SYNC_DEBOUNCE_MS = 1_500L
    }
}
